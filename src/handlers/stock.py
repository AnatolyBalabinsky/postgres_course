from dataclasses import dataclass

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import QuantityValidator
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER


@dataclass
class StockItem:
    warehouse_id: int
    warehouse_label: str
    product_id: int
    product_name: str
    quantity: int


def _render_stock_item(item: StockItem) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=20)
    table.add_column("Значение", style="white")

    table.add_row("Склад", f"{item.warehouse_label} (ID: {item.warehouse_id})")
    table.add_row("Товар", f"{item.product_name} (ID: {item.product_id})")
    table.add_row("Количество", str(item.quantity))

    panel = Panel(
        table,
        expand=False,
        title="[bold green]Остаток на складе[/bold green]",
        border_style="green",
    )
    console.print(panel)


@command(
    "list stock",
    "список остатков на складах",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_stock() -> None:
    conn = get_conn()
    table = Table(
        title="Остатки на складах", show_header=True, header_style="bold cyan"
    )

    table.add_column("Склад", style="green", min_width=15)
    table.add_column("Товар", style="yellow", min_width=30)
    table.add_column("Количество", style="cyan", min_width=10, justify="right")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                w.id, COALESCE(w.label, w.address),
                p.id, p.name,
                s.quantity
            FROM inventory.stock s
            JOIN catalog.warehouses w ON s.warehouse_id = w.id
            JOIN catalog.products p ON s.product_id = p.id
            ORDER BY w.label, p.name
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            f"{row[1]} (ID: {row[0]})",
            row[3],
            str(row[4]),
        )
    console.print(table)


@command(
    "show stock",
    "остаток товара на складе",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def show_stock() -> None:
    conn = get_conn()

    # Выбор склада
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(label, address) FROM catalog.warehouses ORDER BY label"
        )
        warehouses = cur.fetchall()

    if not warehouses:
        render_error("Нет доступных складов")
        return

    warehouse_options = [(str(w[0]), w[1]) for w in warehouses]
    warehouse_id = choice(
        message="Выберите склад:",
        options=warehouse_options,
    )

    # Выбор товара
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.name
            FROM catalog.products p
            JOIN inventory.stock s ON p.id = s.product_id
            WHERE s.warehouse_id = %s AND s.quantity > 0
            ORDER BY p.name
        """,
            (warehouse_id,),
        )
        products = cur.fetchall()

    if not products:
        render_error("Нет товаров в наличии на этом складе")
        return

    product_options = [(str(p[0]), p[1]) for p in products]
    product_id = choice(
        message="Выберите товар:",
        options=product_options,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                w.id, COALESCE(w.label, w.address),
                p.id, p.name,
                s.quantity
            FROM inventory.stock s
            JOIN catalog.warehouses w ON s.warehouse_id = w.id
            JOIN catalog.products p ON s.product_id = p.id
            WHERE s.warehouse_id = %s AND s.product_id = %s
        """,
            (warehouse_id, product_id),
        )
        row = cur.fetchone()

    if row is None:
        render_error("Остаток не найден")
        return

    item = StockItem(
        warehouse_id=row[0],
        warehouse_label=row[1],
        product_id=row[2],
        product_name=row[3],
        quantity=row[4],
    )
    _render_stock_item(item)


@command(
    "add stock",
    "добавить товар на склад",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def add_stock() -> None:
    conn = get_conn()

    # Выбор склада
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(label, address) FROM catalog.warehouses ORDER BY label"
        )
        warehouses = cur.fetchall()

    warehouse_options = [(str(w[0]), w[1]) for w in warehouses]
    warehouse_id = choice(message="Выберите склад:", options=warehouse_options)

    # Выбор товара
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM catalog.products ORDER BY name")
        products = cur.fetchall()

    product_options = [(str(p[0]), p[1]) for p in products]
    product_id = choice(message="Выберите товар:", options=product_options)

    quantity = prompt("Количество: ", validator=QuantityValidator()).strip()

    conn.execute(
        """INSERT INTO inventory.stock (warehouse_id, product_id, quantity)
           VALUES (%s, %s, %s)
           ON CONFLICT (warehouse_id, product_id) 
           DO UPDATE SET quantity = inventory.stock.quantity + EXCLUDED.quantity""",
        (warehouse_id, product_id, quantity),
    )
    console.print("[green]Остаток обновлен[/green]")


@command(
    "edit stock",
    "изменить остаток товара",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def edit_stock() -> None:
    conn = get_conn()

    # Выбор склада
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(label, address) FROM catalog.warehouses ORDER BY label"
        )
        warehouses = cur.fetchall()

    warehouse_options = [(str(w[0]), w[1]) for w in warehouses]
    warehouse_id = choice(message="Выберите склад:", options=warehouse_options)

    # Выбор товара среди тех, что есть на складе
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.name, s.quantity
            FROM catalog.products p
            JOIN inventory.stock s ON p.id = s.product_id
            WHERE s.warehouse_id = %s
            ORDER BY p.name
        """,
            (warehouse_id,),
        )
        products = cur.fetchall()

    if not products:
        render_error("Нет товаров на этом складе")
        return

    product_options = [
        (str(p[0]), f"{p[1]} (текущий остаток: {p[2]})") for p in products
    ]
    product_id = choice(message="Выберите товар:", options=product_options)

    current_qty = next(p[2] for p in products if str(p[0]) == product_id)
    quantity = prompt(
        "Новое количество: ",
        default=str(current_qty),
        validator=QuantityValidator(),
    ).strip()

    conn.execute(
        "UPDATE inventory.stock SET quantity = %s WHERE warehouse_id = %s AND product_id = %s",
        (quantity, warehouse_id, product_id),
    )
    console.print("[green]Остаток обновлен[/green]")
