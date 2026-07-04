from dataclasses import dataclass
from datetime import datetime

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
                p.id, p.name,
                w.id, COALESCE(w.label, w.address),
                r.quantity, r.created_at
            FROM inventory.reserves r
            JOIN catalog.products p ON r.product_id = p.id
            JOIN catalog.warehouses w ON r.warehouse_id = w.id
            ORDER BY r.created_at DESC
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            str(row[1]),
            row[3],
            f"{row[5]} (ID: {row[4]})",
            str(row[6]),
            row[7].strftime("%Y-%m-%d %H:%M"),
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
    table = Table(
        title=f"Резервы заказа #{order_id}",
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
                p.id, p.name,
                w.id, COALESCE(w.label, w.address),
                r.quantity, r.created_at
            FROM inventory.reserves r
            JOIN catalog.products p ON r.product_id = p.id
            JOIN catalog.warehouses w ON r.warehouse_id = w.id
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
            row[2],
            f"{row[4]} (ID: {row[3]})",
            str(row[5]),
            row[6].strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)
