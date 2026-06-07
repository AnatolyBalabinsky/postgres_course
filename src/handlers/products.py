from dataclasses import dataclass
from decimal import Decimal
from rich.panel import Panel
from rich.table import Table
from psycopg.rows import class_row
from prompt_toolkit import prompt

from db import get_conn
from console import console, render_error
from commands import command, CATEGORY_PRODUCTS
from validators import (
    ChoiceValidator,
    NonEmptyValidator,
    YesNoValidator,
    PriceValidator,
)


@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    category_id: int


def _category_exists(category_id: int) -> bool:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM catalog.product_categories WHERE id = %s", (category_id,)
        )
        return cur.fetchone() is not None


def _get_category_name(category_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM catalog.product_categories WHERE id = %s", (category_id,)
        )
        row = cur.fetchone()
        return row[0] if row else "—"


def _render_product(product: Product):
    """
    Отображает информацию о продукте в виде таблицы внутри панели.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))

    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(product.id))
    table.add_row("SKU", product.sku)
    table.add_row("Имя", product.name)
    table.add_row("Цена", str(product.price))
    table.add_row("Категория", _get_category_name(product.category_id))

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Продукт #{product.id}[/bold green]",
        border_style="green",
    )

    console.print(panel)


@command("list products", "список всех товаров", CATEGORY_PRODUCTS)
def list_products() -> None:
    """
    Выводит список всех продуктов из таблицы catalog.products.
    """
    conn = get_conn()
    table = Table(title="Продукты", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("SKU", style="green", min_width=20)
    table.add_column("Имя", style="yellow", min_width=30)
    table.add_column("Цена", style="magenta", min_width=15)
    table.add_column("Категория", style="blue", min_width=15)

    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products")
        products: list[Product] = cur.fetchall()

    for product in products:
        table.add_row(
            str(product.id),
            product.sku,
            product.name,
            str(product.price),
            _get_category_name(product.category_id),
        )
    console.print(table)


@command("show product", "информация о товаре", CATEGORY_PRODUCTS)
def show_product(_id: str) -> None:
    """
    Показывает детальную информацию о продукте по его ID.
    Если продукт не найден, выводит ошибку через _render_error.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Продукт с ID {_id} не найден")
        return

    _render_product(product)


@command("add product", "добавить товар (интерактивно)", CATEGORY_PRODUCTS)
def add_product() -> None:
    """
    Добавляет новый продукт в базу данных.
    Запрашивает у пользователя: SKU, название, цену и категорию.
    """
    conn = get_conn()
    sku = prompt("SKU: ", validator=NonEmptyValidator()).strip()
    name = prompt("Имя: ", validator=NonEmptyValidator()).strip()
    price = prompt("Цена: ", validator=PriceValidator()).strip()
    category_id = prompt("ID категории: ", validator=NonEmptyValidator()).strip()

    if not _category_exists(int(category_id)):
        render_error(f"Категория с ID {category_id} не найдена")
        return

    conn.execute(
        "INSERT INTO catalog.products (sku, name, price, category_id) VALUES (%s, %s, %s, %s)",
        (sku, name, price, category_id),
    )

    category_name = _get_category_name(int(category_id))
    console.print(
        f"[green]Продукт {name} (SKU: {sku}, категория: {category_name}) добавлен[/green]"
    )


@command("edit product", "редактировать товар", CATEGORY_PRODUCTS)
def edit_product(_id: str) -> None:
    """
    Редактирует существующий продукт.
    Сначала проверяет существование продукта по ID.
    Предлагает текущие значения как default при вводе новых данных.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Продукт с ID {_id} не найден")
        return

    sku = prompt(
        "SKU: ",
        default=product.sku,
        validator=NonEmptyValidator(),
    ).strip()
    name = prompt("Имя: ", default=product.name, validator=NonEmptyValidator()).strip()
    price = prompt(
        "Цена: ", default=str(product.price), validator=PriceValidator()
    ).strip()
    category_id = prompt(
        "ID категории: ",
        default=str(product.category_id),
        validator=NonEmptyValidator(),
    ).strip()

    if not _category_exists(int(category_id)):
        render_error(f"Категория с ID {category_id} не найдена")
        return

    conn.execute(
        """UPDATE catalog.products SET sku = %s, name = %s, price = %s, category_id = %s
        WHERE id = %s""",
        (sku, name, price, category_id, _id),
    )
    category_name = _get_category_name(int(category_id))
    console.print(
        f"[green]Продукт {name} (SKU: {sku}, категория: {category_name}) обновлен[/green]"
    )


@command("delete product", "удалить товар", CATEGORY_PRODUCTS)
def delete_product(_id: str) -> None:
    """
    Удаляет продукт из базы данных.
    Сначала показывает информацию о продукте.
    Запрашивает подтверждение перед удалением.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Продукт с ID {_id} не найден")
        return

    _render_product(product)

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn.execute("DELETE FROM catalog.products WHERE id = %s", (_id,))
        console.print(
            f"[green]Продукт {product.name} (SKU: {product.sku}) удален[/green]"
        )
