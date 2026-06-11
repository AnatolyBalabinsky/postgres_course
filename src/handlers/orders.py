from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from psycopg.rows import class_row
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import (
    ChoiceValidator,
    NonEmptyValidator,
    YesNoValidator,
    QuantityValidator,
)
from commands import command, CATEGORY_ORDERS


@dataclass
class OrderItem:
    id: int
    order_id: int
    product_id: int
    quantity: int
    price: Decimal


@dataclass
class Order:
    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    warehouse_id: int


def _get_order(order_id: str) -> Order | None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Order)) as cur:
        cur.execute(
            "SELECT * FROM sales.orders WHERE id = %s",
            (order_id,),
        )
        return cur.fetchone()


def _get_order_items(order_id: str) -> list[OrderItem]:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(OrderItem)) as cur:
        cur.execute(
            "SELECT * FROM sales.order_items WHERE order_id = %s",
            (order_id,),
        )
        return cur.fetchall()


def _get_product_name(product_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM catalog.products WHERE id = %s", (product_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(f"Продукт с ID {product_id} не найден в базе")
        return result[0]


def _get_products_completer():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM catalog.products")
        return WordCompleter(
            [row[0] for row in cur.fetchall()], ignore_case=True, sentence=True
        )


def _recalc_total(order_id: str) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT SUM(price * quantity) FROM sales.order_items WHERE order_id = %s",
            (order_id,),
        )
        result = cur.fetchone()
        total = result[0] if result[0] is not None else 0

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.orders SET total_amount = %s WHERE id = %s",
            (total, order_id),
        )


def _render_order(order: Order, items: list[OrderItem]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(order.id))
    table.add_row("Статус", order.status)
    table.add_row("Создан", order.created_at.strftime("%Y-%m-%d %H:%M"))
    table.add_row("Склад", str(order.warehouse_id))
    table.add_row("Сумма", str(order.total_amount))

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Заказ #{order.id}[/bold green]",
        border_style="green",
    )
    console.print(panel)

    if items:
        items_table = Table(
            title="Товары в заказе", show_header=True, header_style="bold cyan"
        )
        items_table.add_column("ID", style="dim", width=6, justify="right")
        items_table.add_column("Название", style="yellow", min_width=30)
        items_table.add_column("Цена", style="magenta", min_width=12)
        items_table.add_column("Кол-во", style="cyan", min_width=8)
        items_table.add_column("Сумма", style="bold white", min_width=12)

        for item in items:
            try:
                product_name = _get_product_name(item.product_id)
            except ValueError as e:
                render_error(str(e))
                return
            items_table.add_row(
                str(item.id),
                product_name,
                str(item.price),
                str(item.quantity),
                str(item.price * item.quantity),
            )
        console.print(items_table)


@command("list orders", "список всех заказов", CATEGORY_ORDERS)
def list_orders() -> None:
    conn = get_conn()
    table = Table(title="Заказы", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Статус", style="yellow", min_width=12)
    table.add_column("Сумма", style="magenta", min_width=12)
    table.add_column("Создан", style="dim", min_width=20)
    table.add_column("Склад", style="green", min_width=12)

    with conn.cursor(row_factory=class_row(Order)) as cur:
        cur.execute("SELECT * FROM sales.orders")
        orders: list[Order] = cur.fetchall()

    for order in orders:
        table.add_row(
            str(order.id),
            order.status,
            str(order.total_amount),
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            str(order.warehouse_id),
        )
    console.print(table)


@command("show order", "информация о заказе", CATEGORY_ORDERS)
def show_order(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    items = _get_order_items(_id)
    _render_order(order, items)


@command("add order", "добавить заказ (интерактивно)", CATEGORY_ORDERS)
def add_order() -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("SELECT id, city FROM catalog.warehouses")
        warehouses = cur.fetchall()

    if not warehouses:
        render_error("Нет доступных складов")
        return

    warehouse_choices = {f"{w[0]} - {w[1]}": w[0] for w in warehouses}
    warehouse_validator = ChoiceValidator(
        list(warehouse_choices.keys()),
        message="Выберите склад из списка. Используйте Tab для автодополнения.",
    )
    warehouse_completer = WordCompleter(
        list(warehouse_choices.keys()), ignore_case=True, sentence=True
    )

    warehouse_str = prompt(
        "Склад: ",
        validator=warehouse_validator,
        completer=warehouse_completer,
    ).strip()
    warehouse_id = warehouse_choices[warehouse_str]

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sales.orders (warehouse_id) VALUES (%s)",
            (warehouse_id,),
        )
        cur.execute("SELECT MAX(id) FROM sales.orders")
        order_id = cur.fetchone()[0]

    console.print(f"[green]Заказ #{order_id} создан[/green]")

    _add_order_items_loop(order_id)
    _recalc_total(str(order_id))

    order = _get_order(str(order_id))
    if order is None:
        render_error(f"Созданный заказ #{order_id} не найден")
        return

    items = _get_order_items(str(order_id))
    _render_order(order, items)


def _add_order_items_loop(order_id: int) -> None:
    conn = get_conn()
    products_completer = _get_products_completer()

    while True:
        answer = prompt("Добавить товар в заказ? (y/n): ", validator=YesNoValidator())
        if not YesNoValidator.is_yes(answer):
            break

        product_name = prompt(
            "Продукт: ",
            completer=products_completer,
            validator=NonEmptyValidator(),
        ).strip()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, price FROM catalog.products WHERE name = %s",
                (product_name,),
            )
            product = cur.fetchone()

        if product is None:
            render_error(f"Продукт '{product_name}' не найден")
            continue

        product_id, price = product

        quantity = prompt("Количество: ", validator=QuantityValidator()).strip()

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sales.order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, price),
            )
        console.print("[green]Товар добавлен[/green]")


@command("edit order", "редактировать заказ", CATEGORY_ORDERS)
def edit_order(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Нельзя редактировать заказ в статусе '{order.status}'")
        return

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, city FROM catalog.warehouses")
        warehouses = cur.fetchall()

    warehouse_choices = {f"{w[0]} - {w[1]}": w[0] for w in warehouses}
    current_warehouse_str = next(
        (key for key, val in warehouse_choices.items() if val == order.warehouse_id),
        None,
    )
    if current_warehouse_str is None:
        render_error(f"Склад с ID {order.warehouse_id} не найден")
        return

    warehouse_validator = ChoiceValidator(
        list(warehouse_choices.keys()),
        message="Выберите склад из списка. Используйте Tab для автодополнения.",
    )
    warehouse_completer = WordCompleter(
        list(warehouse_choices.keys()), ignore_case=True, sentence=True
    )

    warehouse_str = prompt(
        "Склад: ",
        default=current_warehouse_str,
        validator=warehouse_validator,
        completer=warehouse_completer,
    ).strip()
    warehouse_id = warehouse_choices[warehouse_str]

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.orders SET warehouse_id = %s WHERE id = %s",
            (warehouse_id, _id),
        )
    console.print(f"[green]Заказ #{_id} обновлен[/green]")


@command("delete order", "удалить заказ", CATEGORY_ORDERS)
def delete_order(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Нельзя удалить заказ в статусе '{order.status}'")
        return

    items = _get_order_items(_id)
    _render_order(order, items)

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales.orders WHERE id = %s", (_id,))
        console.print(f"[green]Заказ #{_id} удален[/green]")


@command("publish order", "опубликовать заказ", CATEGORY_ORDERS)
def publish_order(_id: str) -> None:
    order = _get_order(_id)
    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Заказ уже опубликован (статус: {order.status})")
        return

    items = _get_order_items(_id)
    if not items:
        render_error("Нельзя опубликовать пустой заказ")
        return

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.orders SET status = 'new' WHERE id = %s",
            (_id,),
        )
    console.print(f"[green]Заказ #{_id} опубликован (статус: new)[/green]")


@command("add order_item", "добавить товар в заказ", CATEGORY_ORDERS)
def add_order_item(order_id: str) -> None:
    order = _get_order(order_id)
    if order is None:
        render_error(f"Заказ с ID {order_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Нельзя редактировать заказ в статусе '{order.status}'")
        return

    _add_order_items_loop(int(order_id))
    _recalc_total(order_id)

    order = _get_order(order_id)
    if order is None:
        render_error(f"Заказ с ID {order_id} не найден после обновления")
        return

    items = _get_order_items(order_id)
    _render_order(order, items)


@command("edit order_item", "редактировать товар в заказе", CATEGORY_ORDERS)
def edit_order_item(order_id: str) -> None:
    order = _get_order(order_id)
    if order is None:
        render_error(f"Заказ с ID {order_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Нельзя редактировать заказ в статусе '{order.status}'")
        return

    items = _get_order_items(order_id)
    if not items:
        render_error("В заказе нет товаров")
        return

    item_choices = {}
    for item in items:
        try:
            product_name = _get_product_name(item.product_id)
        except ValueError as e:
            render_error(str(e))
            return
        item_choices[f"{item.id}: {product_name} x{item.quantity}"] = item.id

    item_validator = ChoiceValidator(
        list(item_choices.keys()),
        message="Выберите товар из списка. Используйте Tab для автодополнения.",
    )
    item_completer = WordCompleter(
        list(item_choices.keys()), ignore_case=True, sentence=True
    )

    choice = prompt(
        "Выберите товар для редактирования: ",
        validator=item_validator,
        completer=item_completer,
    ).strip()
    item_id = item_choices[choice]

    selected_item = next(i for i in items if i.id == item_id)

    quantity = prompt(
        "Количество: ",
        default=str(selected_item.quantity),
        validator=QuantityValidator(),
    ).strip()

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sales.order_items SET quantity = %s WHERE id = %s",
            (quantity, item_id),
        )
    _recalc_total(order_id)

    order = _get_order(order_id)
    if order is None:
        render_error(f"Заказ с ID {order_id} не найден после обновления")
        return

    items = _get_order_items(order_id)
    console.print("[green]Товар обновлен[/green]")
    _render_order(order, items)


@command("delete order_item", "удалить товар из заказа", CATEGORY_ORDERS)
def delete_order_item(order_id: str) -> None:
    order = _get_order(order_id)
    if order is None:
        render_error(f"Заказ с ID {order_id} не найден")
        return

    if order.status != "unpublished":
        render_error(f"Нельзя редактировать заказ в статусе '{order.status}'")
        return

    items = _get_order_items(order_id)
    if not items:
        render_error("В заказе нет товаров")
        return

    item_choices = {}
    for item in items:
        try:
            product_name = _get_product_name(item.product_id)
        except ValueError as e:
            render_error(str(e))
            return
        item_choices[f"{item.id}: {product_name} x{item.quantity}"] = item.id

    item_validator = ChoiceValidator(
        list(item_choices.keys()),
        message="Выберите товар из списка. Используйте Tab для автодополнения.",
    )
    item_completer = WordCompleter(
        list(item_choices.keys()), ignore_case=True, sentence=True
    )

    choice = prompt(
        "Выберите товар для удаления: ",
        validator=item_validator,
        completer=item_completer,
    ).strip()
    item_id = item_choices[choice]

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales.order_items WHERE id = %s", (item_id,))
        _recalc_total(order_id)

        order = _get_order(order_id)
        if order is None:
            render_error(f"Заказ с ID {order_id} не найден после удаления товара")
            return

        items = _get_order_items(order_id)
        console.print("[green]Товар удален[/green]")
        _render_order(order, items)
