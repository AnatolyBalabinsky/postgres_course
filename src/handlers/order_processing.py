from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import YesNoValidator
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER, auth_user


@command(
    "take order",
    "взять заказ в обработку",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def take_order() -> None:
    """Взять новый заказ в обработку"""
    conn = get_conn()
    user = auth_user()

    # Показываем новые заказы
    with conn.cursor() as cur:
        cur.execute("""
            SELECT o.id, o.total_amount, o.created_at, 
                   c.name as city_name
            FROM sales.orders o
            JOIN catalog.warehouses w ON o.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE o.status = 'new'
            ORDER BY o.created_at
        """)
        orders = cur.fetchall()

    if not orders:
        render_error("Нет новых заказов для обработки")
        return

    table = Table(title="Новые заказы", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Сумма", style="magenta", width=12)
    table.add_column("Склад (город)", style="green", min_width=20)
    table.add_column("Создан", style="dim", min_width=20)

    for order in orders:
        table.add_row(
            str(order[0]),
            str(order[1]),
            order[3],
            order[2].strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)

    order_options = [
        (str(o[0]), f"Заказ #{o[0]} ({o[3]}, {o[1]} руб.)") for o in orders
    ]
    order_id = choice(
        message="Выберите заказ для обработки:",
        options=order_options,
    )

    # Берём заказ в обработку
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE sales.orders 
               SET status = 'processing' 
               WHERE id = %s AND status = 'new'""",
            (order_id,),
        )
        if cur.rowcount == 0:
            render_error("Заказ уже взят в обработку другим менеджером")
            return

    console.print(f"[green]Заказ #{order_id} взят в обработку[/green]")

    # Автоматически проверяем наличие
    _check_and_reserve(order_id)


def _check_and_reserve(order_id: str) -> None:
    """Проверяет наличие товаров и резервирует"""
    conn = get_conn()

    # Получаем склад заказа
    with conn.cursor() as cur:
        cur.execute("SELECT warehouse_id FROM sales.orders WHERE id = %s", (order_id,))
        row = cur.fetchone()
        if not row:
            render_error(f"Заказ #{order_id} не найден")
            return
        warehouse_id = row[0]

    # Получаем товары из заказа
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT oi.product_id, oi.quantity, p.name
            FROM sales.order_items oi
            JOIN catalog.products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """,
            (order_id,),
        )
        items = cur.fetchall()

    if not items:
        render_error(f"Заказ #{order_id} пуст")
        return

    all_reserved = True
    missing_items = []

    for product_id, needed_qty, product_name in items:
        # Проверяем наличие на складе
        with conn.cursor() as cur:
            cur.execute(
                "SELECT quantity FROM inventory.stock WHERE warehouse_id = %s AND product_id = %s",
                (warehouse_id, product_id),
            )
            stock_row = cur.fetchone()
            available = stock_row[0] if stock_row else 0

        # Резервируем что есть
        reserve_qty = min(available, needed_qty)

        if reserve_qty > 0:
            # Создаём резерв
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inventory.reserves (order_id, product_id, warehouse_id, quantity)
                       VALUES (%s, %s, %s, %s)""",
                    (order_id, product_id, warehouse_id, reserve_qty),
                )

            # Списываем со stock
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE inventory.stock 
                       SET quantity = quantity - %s 
                       WHERE warehouse_id = %s AND product_id = %s""",
                    (reserve_qty, warehouse_id, product_id),
                )

        if reserve_qty < needed_qty:
            all_reserved = False
            missing_qty = needed_qty - reserve_qty
            missing_items.append((product_id, product_name, missing_qty, reserve_qty))

    # Выводим результаты
    console.print(f"\n[bold]Результаты резервирования для заказа #{order_id}:[/bold]")

    for product_id, needed_qty, product_name in items:
        reserved = next((m[3] for m in missing_items if m[0] == product_id), needed_qty)
        if reserved == needed_qty:
            console.print(f"  [green]✓ {product_name}: {reserved}/{needed_qty}[/green]")
        else:
            console.print(
                f"  [yellow]⚠ {product_name}: {reserved}/{needed_qty} (не хватает {needed_qty - reserved})[/yellow]"
            )

    if all_reserved:
        console.print(
            "\n[bold green]Все товары зарезервированы! Можно создавать накладную на доставку.[/bold green]"
        )
        _create_delivery(order_id)
    else:
        console.print(
            "\n[bold yellow]Не хватает товаров. Используйте 'request transfer' для запроса перемещения.[/bold yellow]"
        )
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sales.orders SET status = 'pending' WHERE id = %s", (order_id,)
            )


@command(
    "create delivery",
    "создать накладную на доставку",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def create_delivery_cmd(order_id: str) -> None:
    """Создать накладную на доставку для заказа"""
    _create_delivery(order_id)


def _create_delivery(order_id: str) -> None:
    """Создаёт накладную на доставку из резервов"""
    conn = get_conn()

    # Проверяем, что все товары зарезервированы
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                oi.product_id,
                oi.quantity as needed,
                COALESCE(SUM(r.quantity), 0) as reserved
            FROM sales.order_items oi
            LEFT JOIN inventory.reserves r ON oi.order_id = r.order_id 
                AND oi.product_id = r.product_id
            WHERE oi.order_id = %s
            GROUP BY oi.product_id, oi.quantity
            HAVING COALESCE(SUM(r.quantity), 0) < oi.quantity
        """,
            (order_id,),
        )
        incomplete = cur.fetchall()

    if incomplete:
        render_error(
            f"Не все товары зарезервированы. Не хватает: "
            + ", ".join(f"product #{r[0]} ({r[2]}/{r[1]})" for r in incomplete)
        )
        return

    # Создаём накладную
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO inventory.deliveries (order_id, status) VALUES (%s, 'planned')",
            (order_id,),
        )
        cur.execute(
            "SELECT id FROM inventory.deliveries WHERE order_id = %s", (order_id,)
        )
        delivery_id = cur.fetchone()[0]

    # Переносим резервы в delivery_items
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO inventory.delivery_items (delivery_id, product_id, quantity, reserve_id, status)
            SELECT %s, product_id, quantity, id, 'planned'
            FROM inventory.reserves
            WHERE order_id = %s
        """,
            (delivery_id, order_id),
        )

    # Обновляем статус заказа
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.orders SET status = 'packing' WHERE id = %s", (order_id,)
        )

    console.print(
        f"[green]Накладная на доставку #{delivery_id} создана для заказа #{order_id}[/green]"
    )
