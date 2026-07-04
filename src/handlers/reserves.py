from dataclasses import dataclass
from datetime import datetime

from prompt_toolkit.shortcuts import choice
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER


@dataclass
class Reserve:
    id: int
    order_id: int
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_label: str
    quantity: int
    created_at: datetime


@command(
    "list reserves",
    "список всех резервов",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_reserves() -> None:
    conn = get_conn()
    table = Table(title="Резервы", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Заказ", style="green", width=8)
    table.add_column("Товар", style="yellow", min_width=30)
    table.add_column("Склад", style="blue", min_width=15)
    table.add_column("Кол-во", style="cyan", width=8)
    table.add_column("Создан", style="dim", min_width=20)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                r.id, r.order_id,
                p.name,
                COALESCE(w.label, c.name),
                r.quantity, r.created_at
            FROM inventory.reserves r
            JOIN catalog.products p ON r.product_id = p.id
            JOIN catalog.warehouses w ON r.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            ORDER BY r.created_at DESC
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            str(row[1]),
            row[2],
            row[3],
            str(row[4]),
            row[5].strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@command(
    "show reserves by order",
    "показать резервы по заказу",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def show_reserves_by_order(order_id: str) -> None:
    conn = get_conn()

    # Проверяем существование заказа
    with conn.cursor() as cur:
        cur.execute("SELECT id, status FROM sales.orders WHERE id = %s", (order_id,))
        order = cur.fetchone()

    if order is None:
        render_error(f"Заказ #{order_id} не найден")
        return

    table = Table(
        title=f"Резервы заказа #{order_id} (статус: {order[1]})",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("ID", style="dim", width=6)
    table.add_column("Товар", style="yellow", min_width=30)
    table.add_column("Склад", style="blue", min_width=15)
    table.add_column("Кол-во", style="cyan", width=8)
    table.add_column("Создан", style="dim", min_width=20)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                r.id,
                p.name,
                COALESCE(w.label, c.name),
                r.quantity, r.created_at
            FROM inventory.reserves r
            JOIN catalog.products p ON r.product_id = p.id
            JOIN catalog.warehouses w ON r.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE r.order_id = %s
            ORDER BY r.created_at DESC
        """,
            (order_id,),
        )
        rows = cur.fetchall()

    if not rows:
        render_error(f"Нет резервов для заказа #{order_id}")
        return

    for row in rows:
        table.add_row(
            str(row[0]),
            row[1],
            row[2],
            str(row[3]),
            row[4].strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@command(
    "show reserve",
    "показать детали резерва",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def show_reserve(reserve_id: str) -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                r.id, r.order_id,
                p.name as product_name,
                COALESCE(w.label, c.name) as warehouse_name,
                r.quantity, r.created_at
            FROM inventory.reserves r
            JOIN catalog.products p ON r.product_id = p.id
            JOIN catalog.warehouses w ON r.warehouse_id = w.id
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE r.id = %s
        """,
            (reserve_id,),
        )
        row = cur.fetchone()

    if row is None:
        render_error(f"Резерв #{reserve_id} не найден")
        return

    reserve_table = Table(show_header=False, box=None, padding=(0, 2))
    reserve_table.add_column("Поле", style="bold cyan", width=15)
    reserve_table.add_column("Значение", style="white")

    reserve_table.add_row("ID", str(row[0]))
    reserve_table.add_row("Заказ", str(row[1]))
    reserve_table.add_row("Товар", row[2])
    reserve_table.add_row("Склад", row[3])
    reserve_table.add_row("Количество", str(row[4]))
    reserve_table.add_row("Создан", row[5].strftime("%Y-%m-%d %H:%M"))

    panel = Panel(
        reserve_table,
        expand=False,
        title=f"[bold green]Резерв #{reserve_id}[/bold green]",
        border_style="green",
    )
    console.print(panel)
