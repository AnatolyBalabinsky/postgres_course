from dataclasses import dataclass
from rich.panel import Panel
from rich.table import Table
from psycopg.rows import class_row
from prompt_toolkit import prompt

from db import get_conn
from console import console, render_error
from commands import command, CATEGORY_PRODUCTS
from validators import NonEmptyValidator, YesNoValidator


@dataclass
class ProductCategory:
    id: int
    name: str


def _render_product_category(category: ProductCategory):
    """
    Отображает информацию о категории в виде таблицы внутри панели.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))

    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(category.id))
    table.add_row("Имя", category.name)

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Категория #{category.id}[/bold green]",
        border_style="green",
    )

    console.print(panel)


@command("list product_categories", "список всех категорий", CATEGORY_PRODUCTS)
def list_product_categories() -> None:
    """
    Выводит список всех категорий из таблицы catalog.product_categories.
    """
    conn = get_conn()
    table = Table(title="Категории продуктов", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Имя", style="green", min_width=30)

    with conn.cursor(row_factory=class_row(ProductCategory)) as cur:
        cur.execute("SELECT * FROM catalog.product_categories")
        categories: list[ProductCategory] = cur.fetchall()

    for category in categories:
        table.add_row(
            str(category.id),
            category.name,
        )
    console.print(table)


@command("show product_category", "информация о категории", CATEGORY_PRODUCTS)
def show_product_category(_id: str) -> None:
    """
    Показывает детальную информацию о категории по её ID.
    Если категория не найдена, выводит ошибку.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(ProductCategory)) as cur:
        cur.execute("SELECT * FROM catalog.product_categories WHERE id = %s", (_id,))
        category: ProductCategory | None = cur.fetchone()

    if category is None:
        render_error(f"Категория с ID {_id} не найдена")
        return

    _render_product_category(category)


@command("add product_category", "добавить категорию (интерактивно)", CATEGORY_PRODUCTS)
def add_product_category() -> None:
    """
    Добавляет новую категорию в базу данных.
    Запрашивает у пользователя имя категории.
    """
    conn = get_conn()
    name = prompt("Имя: ", validator=NonEmptyValidator()).strip()

    conn.execute(
        "INSERT INTO catalog.product_categories (name) VALUES (%s)",
        (name,),
    )

    console.print(f"[green]Категория {name} добавлена[/green]")


@command("edit product_category", "редактировать категорию", CATEGORY_PRODUCTS)
def edit_product_category(_id: str) -> None:
    """
    Редактирует существующую категорию.
    Сначала проверяет существование категории по ID.
    Предлагает текущее имя как default при вводе нового.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(ProductCategory)) as cur:
        cur.execute("SELECT * FROM catalog.product_categories WHERE id = %s", (_id,))
        category: ProductCategory | None = cur.fetchone()

    if category is None:
        render_error(f"Категория с ID {_id} не найдена")
        return

    name = prompt(
        "Имя: ", default=category.name, validator=NonEmptyValidator()
    ).strip()

    conn.execute(
        """UPDATE catalog.product_categories SET name = %s
        WHERE id = %s""",
        (name, _id),
    )
    console.print(f"[green]Категория {name} обновлена[/green]")


@command("delete product_category", "удалить категорию", CATEGORY_PRODUCTS)
def delete_product_category(_id: str) -> None:
    """
    Удаляет категорию из базы данных.
    Сначала показывает информацию о категории.
    Запрашивает подтверждение перед удалением.
    """
    conn = get_conn()
    with conn.cursor(row_factory=class_row(ProductCategory)) as cur:
        cur.execute("SELECT * FROM catalog.product_categories WHERE id = %s", (_id,))
        category: ProductCategory | None = cur.fetchone()

    if category is None:
        render_error(f"Категория с ID {_id} не найдена")
        return

    _render_product_category(category)

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn.execute("DELETE FROM catalog.product_categories WHERE id = %s", (_id,))
        console.print(f"[green]Категория {category.name} удалена[/green]")