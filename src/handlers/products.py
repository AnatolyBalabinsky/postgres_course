from dataclasses import dataclass
from decimal import Decimal
from rich.panel import Panel
from rich.table import Table
from psycopg.rows import class_row
from prompt_toolkit import prompt

from db import get_conn
from console import console, render_error
from commands import command, CATEGORY_PRODUCTS
from validators import ChoiceValidator, NonEmptyValidator, YesNoValidator, PriceValidator

# TODO: связь с category ??? (ссылка)
# TODO: валидаторы для категорий

@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    category: str


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
    table.add_row("Категория", str(product.category))

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
            product.category
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
    category = prompt("Категория: ", validator=NonEmptyValidator()).strip()

    conn.execute(
        "INSERT INTO catalog.products (sku, name, price, category) VALUES (%s, %s, %s, %s)",
        (sku, name, price, category),
    )

    console.print(f"[green]Продукт {name} (SKU: {sku}, категория: {category}) добавлен[/green]")



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
    name = prompt(
        "Имя: ", default=product.name, validator=NonEmptyValidator()
    ).strip()
    price = prompt(
        "Цена: ", default=str(product.price), validator=PriceValidator()
    ).strip()
    category = (
        prompt("Категория: ", default=product.category, validator=NonEmptyValidator()).strip()
    )
    conn.execute(
        """UPDATE catalog.products SET sku = %s, name = %s, price = %s, category = %s
        WHERE id = %s""",
        (sku, name, price, category, _id),
    )
    console.print(f"[green]Продукт {name} (SKU: {sku}, категория: {category}) обновлен[/green]")


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
        console.print(f"[green]Продукт {product.name} (SKU: {product.sku}) удален[/green]")
