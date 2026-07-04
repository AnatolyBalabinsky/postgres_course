from prompt_toolkit.shortcuts import choice
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER


@command(
    "list deliveries",
    "список накладных на доставку",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_deliveries() -> None:
    conn = get_conn()
    table = Table(
        title="Накладные на доставку", show_header=True, header_style="bold cyan"
    )

    table.add_column("ID", style="dim", width=6)
    table.add_column("Заказ", style="green", width=8)
    table.add_column("Статус", style="magenta", width=12)
    table.add_column("Создана", style="dim", min_width=20)
    table.add_column("Отгружена", style="dim", min_width=20)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, order_id, status, created_at, shipped_at
            FROM inventory.deliveries
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            str(row[1]),
            row[2],
            row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "",
            row[4].strftime("%Y-%m-%d %H:%M") if row[4] else "",
        )
    console.print(table)


@command(
    "show delivery",
    "показать накладную доставки",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def show_delivery(delivery_id: str) -> None:
    conn = get_conn()

    # Информация о накладной
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.order_id, d.status, d.created_at, d.shipped_at,
                   o.warehouse_id, o.total_amount
            FROM inventory.deliveries d
            JOIN sales.orders o ON d.order_id = o.id
            WHERE d.id = %s
        """,
            (delivery_id,),
        )
        delivery = cur.fetchone()

    if delivery is None:
        render_error(f"Накладная #{delivery_id} не найдена")
        return

    # Основная информация
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(delivery[0]))
    table.add_row("Заказ", str(delivery[1]))
    table.add_row("Склад", str(delivery[5]))
    table.add_row("Статус", delivery[2])
    table.add_row(
        "Создана", delivery[3].strftime("%Y-%m-%d %H:%M") if delivery[3] else ""
    )
    table.add_row(
        "Отгружена", delivery[4].strftime("%Y-%m-%d %H:%M") if delivery[4] else ""
    )

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Накладная доставки #{delivery_id}[/bold green]",
        border_style="green",
    )
    console.print(panel)

    # Позиции накладной
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT di.product_id, p.name, di.quantity, di.status
            FROM inventory.delivery_items di
            JOIN catalog.products p ON di.product_id = p.id
            WHERE di.delivery_id = %s
        """,
            (delivery_id,),
        )
        items = cur.fetchall()

    if items:
        items_table = Table(
            title="Позиции накладной", show_header=True, header_style="bold cyan"
        )
        items_table.add_column("Товар", style="yellow", min_width=30)
        items_table.add_column("Кол-во", style="cyan", width=8)
        items_table.add_column("Статус", style="green", width=12)

        for item in items:
            items_table.add_row(item[1], str(item[2]), item[3])
        console.print(items_table)
