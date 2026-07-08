from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from prompt_toolkit import prompt
from psycopg.rows import class_row
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import YesNoValidator
from commands import command, CATEGORY_INVENTORY, CATEGORY_ORDERS

from auth import ROLE_INVENTORY_MANAGER, auth_user


@dataclass
class OrderShort:
    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    warehouse_id: int
    created_by: int
    processed_by: int | None


@dataclass
class OrderItemShort:
    order_id: int
    product_id: int
    quantity: int
    price: Decimal


@dataclass
class WarehouseStock:
    product_id: int
    product_name: str
    sku: str
    total_quantity: int
    reserved_quantity: int
    available_quantity: int


def _get_product_name(product_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM catalog.products WHERE id = %s", (product_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(f"Продукт с ID {product_id} не найден в базе")
        return result[0]


def _get_username(user_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT username FROM auth.users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        return result[0] if result else "unknown"


def _get_warehouse_city(warehouse_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.name
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE w.id = %s
        """,
            (warehouse_id,),
        )
        result = cur.fetchone()
        return result[0] if result else f"Склад #{warehouse_id}"


def _get_order(order_id: str) -> OrderShort | None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(OrderShort)) as cur:
        cur.execute("SELECT * FROM sales.orders WHERE id = %s", (order_id,))
        return cur.fetchone()


def _get_order_items(order_id: str) -> list[OrderItemShort]:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(OrderItemShort)) as cur:
        cur.execute(
            "SELECT order_id, product_id, quantity, price FROM sales.order_items WHERE order_id = %s",
            (order_id,),
        )
        return cur.fetchall()


@command(
    "list orders new",
    "список новых заказов",
    CATEGORY_ORDERS,
    [ROLE_INVENTORY_MANAGER],
)
def list_orders_new() -> None:
    conn = get_conn()
    table = Table(title="Новые заказы", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Склад", style="green", min_width=15)
    table.add_column("Сумма", style="magenta", min_width=12)
    table.add_column("Создан", style="dim", min_width=20)
    table.add_column("Создал", style="blue", min_width=15)

    with conn.cursor(row_factory=class_row(OrderShort)) as cur:
        cur.execute(
            "SELECT * FROM sales.orders WHERE status = 'new' ORDER BY created_at"
        )
        orders: list[OrderShort] = cur.fetchall()

    for order in orders:
        table.add_row(
            str(order.id),
            _get_warehouse_city(order.warehouse_id),
            str(order.total_amount),
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            _get_username(order.created_by),
        )
    console.print(table)


@command(
    "list orders processing",
    "список заказов в обработке",
    CATEGORY_ORDERS,
    [ROLE_INVENTORY_MANAGER],
)
def list_orders_processing() -> None:
    conn = get_conn()
    table = Table(
        title="Заказы в обработке", show_header=True, header_style="bold cyan"
    )

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Склад", style="green", min_width=15)
    table.add_column("Сумма", style="magenta", min_width=12)
    table.add_column("Обработчик", style="yellow", min_width=15)
    table.add_column("Создан", style="dim", min_width=20)
    table.add_column("Создал", style="blue", min_width=15)

    with conn.cursor(row_factory=class_row(OrderShort)) as cur:
        cur.execute(
            "SELECT * FROM sales.orders WHERE status = 'processing' ORDER BY created_at"
        )
        orders: list[OrderShort] = cur.fetchall()

    for order in orders:
        table.add_row(
            str(order.id),
            _get_warehouse_city(order.warehouse_id),
            str(order.total_amount),
            _get_username(order.processed_by) if order.processed_by else "—",
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            _get_username(order.created_by),
        )
    console.print(table)


@command(
    "list orders my",
    "список моих заказов",
    CATEGORY_ORDERS,
    [ROLE_INVENTORY_MANAGER],
)
def list_orders_my() -> None:
    user = auth_user()
    conn = get_conn()
    table = Table(title="Мои заказы", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Статус", style="yellow", min_width=12)
    table.add_column("Склад", style="green", min_width=15)
    table.add_column("Сумма", style="magenta", min_width=12)
    table.add_column("Создан", style="dim", min_width=20)
    table.add_column("Создал", style="blue", min_width=15)

    with conn.cursor(row_factory=class_row(OrderShort)) as cur:
        cur.execute(
            "SELECT * FROM sales.orders WHERE processed_by = %s ORDER BY created_at",
            (user.id,),
        )
        orders: list[OrderShort] = cur.fetchall()

    for order in orders:
        table.add_row(
            str(order.id),
            order.status,
            _get_warehouse_city(order.warehouse_id),
            str(order.total_amount),
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            _get_username(order.created_by),
        )
    console.print(table)


@command(
    "mark order processing",
    "взять заказ в обработку",
    CATEGORY_ORDERS,
    [ROLE_INVENTORY_MANAGER],
)
def mark_order_processing(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    if order.status != "new":
        render_error(f"Нельзя взять заказ в обработку: текущий статус '{order.status}'")
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(order.id))
    table.add_row("Статус", order.status)
    table.add_row("Склад", _get_warehouse_city(order.warehouse_id))
    table.add_row("Сумма", str(order.total_amount))
    table.add_row("Создан", order.created_at.strftime("%Y-%m-%d %H:%M"))
    table.add_row("Создал", _get_username(order.created_by))

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Заказ #{order.id}[/bold green]",
        border_style="green",
    )
    console.print(panel)

    answer = prompt("Взять заказ в обработку? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        user = auth_user()
        conn = get_conn()
        conn.execute(
            "UPDATE sales.orders SET status = 'processing', processed_by = %s WHERE id = %s",
            (user.id, _id),
        )
        console.print(f"[green]Заказ #{_id} взят в обработку[/green]")


def _get_item_status(
    order_id: str, order_status: str, product_id: int, quantity: int
) -> str:
    conn = get_conn()

    if order_status == "new":
        return "ожидает обработки"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT di.status
            FROM inventory.delivery_items di
            WHERE di.order_id = %s AND di.product_id = %s
        """,
            (order_id, product_id),
        )
        delivery = cur.fetchone()
        if delivery and delivery[0] == "shipped":
            return "отгружено"
        if delivery and delivery[0] == "planned":
            return "запланирована отгрузка"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(r.quantity), 0)
            FROM inventory.reserves r
            WHERE r.order_id = %s AND r.product_id = %s
        """,
            (order_id, product_id),
        )
        reserved = cur.fetchone()[0]

    if reserved >= quantity:
        return "в резерве"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ti.status, wf.id, cf.name, ti.quantity,
                   tr.arriving_at
            FROM inventory.transfer_items ti
            JOIN inventory.transfers tr ON ti.transfer_id = tr.id
            JOIN catalog.warehouses wf ON tr.from_warehouse_id = wf.id
            JOIN catalog.cities cf ON wf.city_id = cf.id
            WHERE ti.reserve_id IN (
                SELECT r.id FROM inventory.reserves r
                WHERE r.order_id = %s AND r.product_id = %s
            )
            AND ti.status IN ('planned', 'shipped')
            ORDER BY tr.created_at DESC
            LIMIT 1
        """,
            (order_id, product_id),
        )
        transfer = cur.fetchone()

    if transfer:
        status, wh_id, city, qty, arriving = transfer
        arriving_str = ""
        if arriving:
            arriving_str = f", ожидается {arriving.strftime('%Y-%m-%d %H:%M')}"
        return f"в пути ({qty} шт. из {city}{arriving_str})"

    if reserved > 0:
        return f"в резерве ({reserved} из {quantity})"

    return "ожидает обработки"


@command(
    "show order",
    "карточка заказа (inventory_manager)",
    CATEGORY_ORDERS,
    [ROLE_INVENTORY_MANAGER],
)
def show_order(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(order.id))
    table.add_row("Склад отгрузки", _get_warehouse_city(order.warehouse_id))
    table.add_row("Статус", order.status)
    table.add_row("Создан", order.created_at.strftime("%Y-%m-%d %H:%M"))
    table.add_row("Создал", _get_username(order.created_by))
    if order.processed_by:
        table.add_row("Обработчик", _get_username(order.processed_by))

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Заказ #{order.id}[/bold green]",
        border_style="green",
    )
    console.print(panel)

    items = _get_order_items(_id)
    if not items:
        console.print("[dim]В заказе нет позиций[/dim]")
        return

    items_table = Table(
        title="Позиции заказа", show_header=True, header_style="bold cyan"
    )
    items_table.add_column("ID", style="dim", width=6, justify="right")
    items_table.add_column("Продукт", style="yellow", min_width=25)
    items_table.add_column("Цена", style="magenta", min_width=12)
    items_table.add_column("Кол-во", style="cyan", min_width=8)
    items_table.add_column("Статус", style="bold white", min_width=35)

    for item in items:
        try:
            product_name = _get_product_name(item.product_id)
        except ValueError as e:
            render_error(str(e))
            return

        status = _get_item_status(_id, order.status, item.product_id, item.quantity)
        items_table.add_row(
            str(item.product_id),
            product_name,
            str(item.price),
            str(item.quantity),
            status,
        )
    console.print(items_table)


@command(
    "view warehouse stock",
    "остатки по складу",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def view_warehouse_stock(warehouse_id: str) -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM catalog.warehouses WHERE id = %s", (warehouse_id,))
        if cur.fetchone() is None:
            render_error(f"Склад с ID {warehouse_id} не найден")
            return

    warehouse_city = _get_warehouse_city(int(warehouse_id))

    table = Table(
        title=f"Остатки по складу: {warehouse_city}",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("SKU", style="green", min_width=15)
    table.add_column("Продукт", style="yellow", min_width=25)
    table.add_column("Всего", style="bold white", min_width=10)
    table.add_column("В резерве", style="magenta", min_width=12)
    table.add_column("Доступно", style="cyan", min_width=10)

    with conn.cursor(row_factory=class_row(WarehouseStock)) as cur:
        cur.execute(
            """
            SELECT
                p.id as product_id,
                p.name as product_name,
                p.sku as sku,
                COALESCE(s.quantity, 0) + COALESCE(
                    (SELECT SUM(r.quantity)
                     FROM inventory.reserves r
                     JOIN sales.orders o ON r.order_id = o.id
                     WHERE r.product_id = p.id AND o.warehouse_id = %s
                    ), 0
                ) as total_quantity,
                COALESCE(
                    (SELECT SUM(r.quantity)
                     FROM inventory.reserves r
                     JOIN sales.orders o ON r.order_id = o.id
                     WHERE r.product_id = p.id AND o.warehouse_id = %s
                    ), 0
                ) as reserved_quantity,
                COALESCE(s.quantity, 0) as available_quantity
            FROM catalog.products p
            LEFT JOIN inventory.stock s ON p.id = s.product_id AND s.warehouse_id = %s
            ORDER BY p.name
        """,
            (warehouse_id, warehouse_id, warehouse_id),
        )
        stocks: list[WarehouseStock] = cur.fetchall()

    for stock in stocks:
        table.add_row(
            str(stock.product_id),
            stock.sku,
            stock.product_name,
            str(stock.total_quantity),
            str(stock.reserved_quantity),
            str(stock.available_quantity),
        )
    console.print(table)


@command(
    "view product stock",
    "остатки по продукту на разных складах",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def view_product_stock(product_id: str) -> None:
    conn = get_conn()

    try:
        product_name = _get_product_name(int(product_id))
    except ValueError as e:
        render_error(str(e))
        return

    table = Table(
        title=f"Остатки по продукту: {product_name}",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Склад", style="green", min_width=15)
    table.add_column("Город", style="yellow", min_width=15)
    table.add_column("Всего", style="bold white", min_width=10)
    table.add_column("В резерве", style="magenta", min_width=12)
    table.add_column("Доступно", style="cyan", min_width=10)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                w.id,
                c.name,
                COALESCE(s.quantity, 0) + COALESCE(
                    (SELECT SUM(r.quantity)
                     FROM inventory.reserves r
                     JOIN sales.orders o ON r.order_id = o.id
                     WHERE r.product_id = %s AND o.warehouse_id = w.id
                    ), 0
                ) as total_quantity,
                COALESCE(
                    (SELECT SUM(r.quantity)
                     FROM inventory.reserves r
                     JOIN sales.orders o ON r.order_id = o.id
                     WHERE r.product_id = %s AND o.warehouse_id = w.id
                    ), 0
                ) as reserved_quantity,
                COALESCE(s.quantity, 0) as available_quantity
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
            LEFT JOIN inventory.stock s ON w.id = s.warehouse_id AND s.product_id = %s
            ORDER BY available_quantity DESC
        """,
            (product_id, product_id, product_id),
        )
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            row[1],
            str(row[2]),
            str(row[3]),
            str(row[4]),
        )
    console.print(table)
