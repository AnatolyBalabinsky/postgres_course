from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import QuantityValidator
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER, auth_user


@command(
    "list transfers",
    "список накладных на перемещение",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_transfers() -> None:
    conn = get_conn()
    table = Table(
        title="Накладные на перемещение", show_header=True, header_style="bold cyan"
    )

    table.add_column("ID", style="dim", width=6)
    table.add_column("Откуда", style="green", min_width=15)
    table.add_column("Куда", style="yellow", min_width=15)
    table.add_column("Статус", style="magenta", width=12)
    table.add_column("Сумма", style="cyan", width=12)
    table.add_column("Создана", style="dim", min_width=20)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                t.id,
                COALESCE(fw.label, fc.name),
                COALESCE(tw.label, tc.name),
                t.status,
                t.total_amount,
                t.created_at
            FROM inventory.transfers t
            JOIN catalog.warehouses fw ON t.from_warehouse_id = fw.id
            JOIN catalog.warehouses tw ON t.to_warehouse_id = tw.id
            JOIN catalog.cities fc ON fw.city_id = fc.id
            JOIN catalog.cities tc ON tw.city_id = tc.id
            ORDER BY t.created_at DESC
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            row[1],
            row[2],
            row[3],
            str(row[4]),
            row[5].strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@command(
    "request transfer",
    "запросить перемещение товаров",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def request_transfer() -> None:
    """Запросить перемещение недостающих товаров с другого склада"""
    conn = get_conn()
    user = auth_user()

    # Показываем заказы в статусе pending для текущего менеджера
    with conn.cursor() as cur:
        cur.execute("""
            SELECT o.id, o.total_amount, c.name as city_name
            FROM sales.orders o
            JOIN catalog.warehouses w ON o.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE o.status = 'pending'
            ORDER BY o.created_at
        """)
        orders = cur.fetchall()

    if not orders:
        render_error("Нет заказов, ожидающих перемещения")
        return

    order_options = [
        (str(o[0]), f"Заказ #{o[0]} ({o[2]}, {o[1]} руб.)") for o in orders
    ]
    order_id = choice(
        message="Выберите заказ:",
        options=order_options,
    )

    # Получаем склад назначения
    with conn.cursor() as cur:
        cur.execute("SELECT warehouse_id FROM sales.orders WHERE id = %s", (order_id,))
        to_warehouse_id = cur.fetchone()[0]

    # Показываем недостающие товары
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                oi.product_id,
                p.name,
                oi.quantity - COALESCE(SUM(r.quantity), 0) as missing_qty
            FROM sales.order_items oi
            JOIN catalog.products p ON oi.product_id = p.id
            LEFT JOIN inventory.reserves r ON oi.order_id = r.order_id 
                AND oi.product_id = r.product_id
            WHERE oi.order_id = %s
            GROUP BY oi.product_id, p.name, oi.quantity
            HAVING oi.quantity - COALESCE(SUM(r.quantity), 0) > 0
        """,
            (order_id,),
        )
        missing = cur.fetchall()

    if not missing:
        render_error("Нет недостающих товаров")
        return

    # Показываем недостающие товары
    console.print("\n[bold]Недостающие товары:[/bold]")
    for item in missing:
        console.print(f"  • {item[1]}: не хватает {item[2]} шт.")

    # Выбираем товар для перемещения
    item_options = [(str(m[0]), f"{m[1]} (не хватает {m[2]} шт.)") for m in missing]
    product_id = choice(
        message="Выберите товар для перемещения:",
        options=item_options,
    )

    needed_qty = next(m[2] for m in missing if str(m[0]) == product_id)

    # Ищем на других складах
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                w.id,
                COALESCE(w.label, c.name) as warehouse_name,
                s.quantity
            FROM inventory.stock s
            JOIN catalog.warehouses w ON s.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE s.product_id = %s 
              AND s.warehouse_id != %s 
              AND s.quantity > 0
            ORDER BY s.quantity DESC
        """,
            (product_id, to_warehouse_id),
        )
        sources = cur.fetchall()

    if not sources:
        render_error(
            "Товар не найден на других складах. Запросите с центрального склада."
        )
        return

    # Показываем доступные склады
    source_table = Table(title="Доступные склады")
    source_table.add_column("ID", style="dim")
    source_table.add_column("Склад", style="green")
    source_table.add_column("В наличии", style="cyan")

    for src in sources:
        source_table.add_row(str(src[0]), src[1], str(src[2]))
    console.print(source_table)

    source_options = [(str(s[0]), f"{s[1]} (в наличии: {s[2]})") for s in sources]
    from_warehouse_id = choice(
        message="Выберите склад отправки:",
        options=source_options,
    )

    qty = prompt(
        f"Количество (макс. {needed_qty}): ",
        default=str(needed_qty),
        validator=QuantityValidator(),
    ).strip()

    # Ищем или создаём накладную на перемещение
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, total_amount 
            FROM inventory.transfers 
            WHERE from_warehouse_id = %s 
              AND to_warehouse_id = %s 
              AND status = 'planned'
        """,
            (from_warehouse_id, to_warehouse_id),
        )
        transfer = cur.fetchone()

    if transfer:
        transfer_id, current_amount = transfer
        console.print(f"[dim]Найдена существующая накладная #{transfer_id}[/dim]")
    else:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO inventory.transfers (from_warehouse_id, to_warehouse_id, status)
                   VALUES (%s, %s, 'planned') RETURNING id""",
                (from_warehouse_id, to_warehouse_id),
            )
            transfer_id = cur.fetchone()[0]
        current_amount = 0
        console.print(f"[green]Создана новая накладная #{transfer_id}[/green]")

    # Получаем резерв для этого товара (может быть частичный)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM inventory.reserves WHERE order_id = %s AND product_id = %s LIMIT 1",
            (order_id, product_id),
        )
        reserve_row = cur.fetchone()
        reserve_id = reserve_row[0] if reserve_row else None

    # Получаем цену товара
    with conn.cursor() as cur:
        cur.execute("SELECT price FROM catalog.products WHERE id = %s", (product_id,))
        price = cur.fetchone()[0]

    item_cost = price * int(qty)

    # Добавляем товар в накладную
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO inventory.transfer_items 
               (transfer_id, product_id, quantity, reserve_id, requested_by, status)
               VALUES (%s, %s, %s, %s, %s, 'planned')""",
            (transfer_id, product_id, qty, reserve_id, user.id),
        )

    # Обновляем сумму накладной
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.transfers SET total_amount = total_amount + %s WHERE id = %s",
            (item_cost, transfer_id),
        )

    console.print(f"[green]Товар добавлен в накладную #{transfer_id}[/green]")

    # Проверяем порог для маршрута
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.total_threshold
            FROM inventory.transfers t
            JOIN catalog.warehouses fw ON t.from_warehouse_id = fw.id
            JOIN catalog.warehouses tw ON t.to_warehouse_id = tw.id
            JOIN inventory.routes r ON fw.city_id = r.from_city_id 
                AND tw.city_id = r.to_city_id
            WHERE t.id = %s
        """,
            (transfer_id,),
        )
        route_row = cur.fetchone()

    if route_row:
        threshold = route_row[0]
        new_amount = current_amount + item_cost
        if new_amount >= threshold:
            console.print(
                f"[bold green]✓ Порог достигнут ({new_amount} >= {threshold})! Можно отправлять![/bold green]"
            )
        else:
            console.print(
                f"[dim]Сумма: {new_amount}/{threshold} (не достигнут порог)[/dim]"
            )
    else:
        console.print("[yellow]⚠ Маршрут не настроен для этих складов[/yellow]")
