from prompt_toolkit.shortcuts import choice
from rich.table import Table

from console import console, render_error
from db import get_conn
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_WORKER


@command(
    "ship delivery",
    "отгрузить накладную доставки",
    CATEGORY_INVENTORY,
    [ROLE_WORKER],
)
def ship_delivery() -> None:
    """Worker отгружает товары по накладной доставки"""
    conn = get_conn()

    # Показываем planned накладные
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.id, d.order_id, o.warehouse_id, d.created_at
            FROM inventory.deliveries d
            JOIN sales.orders o ON d.order_id = o.id
            WHERE d.status = 'planned'
            ORDER BY d.created_at
        """)
        deliveries = cur.fetchall()

    if not deliveries:
        render_error("Нет накладных на доставку для отгрузки")
        return

    delivery_options = [
        (str(d[0]), f"Накладная #{d[0]} (заказ #{d[1]}, склад #{d[2]})")
        for d in deliveries
    ]
    delivery_id = choice(
        message="Выберите накладную для отгрузки:",
        options=delivery_options,
    )

    # Меняем статус накладной на shipping
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.deliveries SET status = 'shipping' WHERE id = %s",
            (delivery_id,),
        )

    # Отгружаем все позиции
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.delivery_items SET status = 'shipped' WHERE delivery_id = %s",
            (delivery_id,),
        )

    # Завершаем накладную
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.deliveries SET status = 'shipped', shipped_at = NOW() WHERE id = %s",
            (delivery_id,),
        )

    # Обновляем заказ
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.orders SET status = 'shipped' WHERE id = (SELECT order_id FROM inventory.deliveries WHERE id = %s)",
            (delivery_id,),
        )

    console.print(f"[green]Накладная #{delivery_id} отгружена, заказ выполнен![/green]")


@command(
    "ship transfer",
    "отгрузить накладную перемещения",
    CATEGORY_INVENTORY,
    [ROLE_WORKER],
)
def ship_transfer() -> None:
    """Worker отгружает товары по накладной перемещения"""
    conn = get_conn()

    # Показываем planned накладные
    with conn.cursor() as cur:
        cur.execute("""
            SELECT t.id, 
                   COALESCE(fw.label, fc.name) as from_name,
                   COALESCE(tw.label, tc.name) as to_name,
                   t.total_amount
            FROM inventory.transfers t
            JOIN catalog.warehouses fw ON t.from_warehouse_id = fw.id
            JOIN catalog.warehouses tw ON t.to_warehouse_id = tw.id
            JOIN catalog.cities fc ON fw.city_id = fc.id
            JOIN catalog.cities tc ON tw.city_id = tc.id
            WHERE t.status = 'planned'
            ORDER BY t.created_at
        """)
        transfers = cur.fetchall()

    if not transfers:
        render_error("Нет накладных на перемещение для отгрузки")
        return

    transfer_options = [
        (str(t[0]), f"Накладная #{t[0]} ({t[1]} → {t[2]}, {t[3]} руб.)")
        for t in transfers
    ]
    transfer_id = choice(
        message="Выберите накладную для отгрузки:",
        options=transfer_options,
    )

    # Меняем статус на shipping
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.transfers SET status = 'shipping', started_at = NOW() WHERE id = %s",
            (transfer_id,),
        )

    # Отгружаем все позиции
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.transfer_items SET status = 'shipped' WHERE transfer_id = %s",
            (transfer_id,),
        )

    # Вычисляем время прибытия
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.duration
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
        arriving_time = f"NOW() + INTERVAL '{route_row[0]}'"
    else:
        arriving_time = "NOW() + INTERVAL '1 hour'"

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE inventory.transfers SET status = 'in_transit', arriving_at = {arriving_time} WHERE id = %s",
            (transfer_id,),
        )

    console.print(f"[green]Накладная #{transfer_id} отгружена, товары в пути![/green]")


@command(
    "receive transfer",
    "принять накладную перемещения",
    CATEGORY_INVENTORY,
    [ROLE_WORKER],
)
def receive_transfer() -> None:
    """Worker принимает товары по накладной перемещения"""
    conn = get_conn()

    # Показываем накладные в пути или прибывшие
    with conn.cursor() as cur:
        cur.execute("""
            SELECT t.id, 
                   COALESCE(fw.label, fc.name) as from_name,
                   COALESCE(tw.label, tc.name) as to_name,
                   t.status,
                   t.total_amount
            FROM inventory.transfers t
            JOIN catalog.warehouses fw ON t.from_warehouse_id = fw.id
            JOIN catalog.warehouses tw ON t.to_warehouse_id = tw.id
            JOIN catalog.cities fc ON fw.city_id = fc.id
            JOIN catalog.cities tc ON tw.city_id = tc.id
            WHERE t.status IN ('in_transit', 'arrived')
            ORDER BY t.created_at
        """)
        transfers = cur.fetchall()

    if not transfers:
        render_error("Нет накладных для приёмки")
        return

    transfer_options = [
        (str(t[0]), f"Накладная #{t[0]} ({t[1]} → {t[2]}, {t[3]})") for t in transfers
    ]
    transfer_id = choice(
        message="Выберите накладную для приёмки:",
        options=transfer_options,
    )

    # Принимаем все позиции
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.transfer_items SET status = 'received' WHERE transfer_id = %s",
            (transfer_id,),
        )

    # Пополняем резервы или stock
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ti.product_id, ti.quantity, ti.reserve_id,
                   t.to_warehouse_id
            FROM inventory.transfer_items ti
            JOIN inventory.transfers t ON ti.transfer_id = t.id
            WHERE ti.transfer_id = %s
        """,
            (transfer_id,),
        )
        items = cur.fetchall()

    for product_id, quantity, reserve_id, to_warehouse_id in items:
        if reserve_id:
            # Пополняем резерв
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE inventory.reserves SET quantity = quantity + %s WHERE id = %s",
                    (quantity, reserve_id),
                )

            # Проверяем, все ли товары зарезервированы для заказа
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT order_id FROM inventory.reserves WHERE id = %s",
                    (reserve_id,),
                )
                order_row = cur.fetchone()
                if order_row:
                    _check_order_complete(order_row[0])
        else:
            # Пополняем stock
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inventory.stock (warehouse_id, product_id, quantity)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (warehouse_id, product_id) 
                       DO UPDATE SET quantity = inventory.stock.quantity + EXCLUDED.quantity""",
                    (to_warehouse_id, product_id, quantity),
                )

    # Завершаем накладную
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory.transfers SET status = 'received', received_at = NOW() WHERE id = %s",
            (transfer_id,),
        )

    console.print(
        f"[green]Накладная #{transfer_id} принята, товары распределены![/green]"
    )


def _check_order_complete(order_id: int) -> None:
    """Проверяет, все ли товары зарезервированы для заказа"""
    conn = get_conn()

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

    if not incomplete:
        # Все товары зарезервированы — создаём накладную на доставку
        from order_processing import _create_delivery

        _create_delivery(str(order_id))
