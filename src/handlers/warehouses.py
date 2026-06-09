from dataclasses import dataclass

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from psycopg.rows import class_row
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import ChoiceValidator, NonEmptyValidator, YesNoValidator
from commands import command, CATEGORY_WAREHOUSES

cities = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
]

city_completer = WordCompleter(cities, ignore_case=True, sentence=True)
city_validator = ChoiceValidator(
    cities, message="Город должен быть из списка. Используйте Tab для автодополнения."
)


@dataclass
class Warehouse:
    id: int
    city: str
    address: str
    label: str | None
    is_central: bool


def _render_warehouse(warehouse: Warehouse) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))

    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(warehouse.id))
    table.add_row("Город", warehouse.city)
    table.add_row("Адрес", warehouse.address)
    table.add_row("Метка", warehouse.label or "")
    table.add_row("Центральный", "Да" if warehouse.is_central else "Нет")

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Склад #{warehouse.id}[/bold green]",
        border_style="green",
    )

    console.print(panel)


def _count_warehouses() -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM catalog.warehouses")
        return cur.fetchone()[0]


def _get_central_id() -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM catalog.warehouses WHERE is_central = TRUE")
        row = cur.fetchone()
        if row:
            return row[0]
        raise ValueError("Не удалось получить ID центрального склада")


@command("list warehouses", "список всех складов", CATEGORY_WAREHOUSES)
def list_warehouses() -> None:
    conn = get_conn()
    table = Table(title="Склады", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Город", style="green", min_width=20)
    table.add_column("Адрес", style="yellow", min_width=30)
    table.add_column("Метка", style="magenta", min_width=15)
    table.add_column("Центральный", style="cyan", min_width=12)

    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses")
        warehouses: list[Warehouse] = cur.fetchall()

    for warehouse in warehouses:
        table.add_row(
            str(warehouse.id),
            warehouse.city,
            warehouse.address,
            warehouse.label or "",
            "*" if warehouse.is_central else "",
        )
    console.print(table)


@command("show warehouse", "информация о складе", CATEGORY_WAREHOUSES)
def show_warehouse(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses WHERE id = %s", (_id,))
        warehouse: Warehouse | None = cur.fetchone()

    if warehouse is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    _render_warehouse(warehouse)


@command("add warehouse", "добавить склад (интерактивно)", CATEGORY_WAREHOUSES)
def add_warehouse() -> None:
    conn = get_conn()
    city = prompt("Город: ", validator=city_validator, completer=city_completer).strip()
    address = prompt("Адрес: ", validator=NonEmptyValidator()).strip()
    label = prompt("Метка (необязательно): ").strip() or None

    if _count_warehouses() == 0:
        is_central = True
        console.print("[dim]Это первый склад, он будет назначен центральным[/dim]")
    else:
        answer = prompt("Сделать центральным? (y/n): ", validator=YesNoValidator())
        is_central = YesNoValidator.is_yes(answer)
        if is_central:
            try:
                old_id = _get_central_id()
            except ValueError as e:
                render_error(str(e))
                return
            conn.execute(
                "UPDATE catalog.warehouses SET is_central = FALSE WHERE id = %s",
                (old_id,),
            )

    conn.execute(
        "INSERT INTO catalog.warehouses (city, address, label, is_central) VALUES (%s, %s, %s, %s)",
        (city, address, label, is_central),
    )
    if label:
        console.print(f"[green]Склад в городе {city} ({label}) добавлен [/green]")
    else:
        console.print(f"[green]Склад в городе {city} добавлен [/green]")


@command("edit warehouse", "редактировать склад", CATEGORY_WAREHOUSES)
def edit_warehouse(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses WHERE id = %s", (_id,))
        warehouse: Warehouse | None = cur.fetchone()

    if warehouse is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    city = prompt(
        "Город: ",
        default=warehouse.city,
        validator=city_validator,
        completer=city_completer,
    ).strip()
    address = prompt(
        "Адрес: ", default=warehouse.address, validator=NonEmptyValidator()
    ).strip()
    label = (
        prompt("Метка (необязательно): ", default=warehouse.label or "").strip() or None
    )

    if warehouse.is_central:
        is_central = True
    else:
        answer = prompt(
            "Сделать центральным? (y/n): ", default="n", validator=YesNoValidator()
        )
        is_central = YesNoValidator.is_yes(answer)

    if is_central and not warehouse.is_central:
        try:
            old_id = _get_central_id()
        except ValueError as e:
            render_error(str(e))
            return
        conn.execute(
            "UPDATE catalog.warehouses SET is_central = FALSE WHERE id = %s", (old_id,)
        )

    conn.execute(
        """UPDATE catalog.warehouses SET city = %s, address = %s, label = %s, is_central = %s
        WHERE id = %s""",
        (city, address, label, is_central, _id),
    )
    if label:
        console.print(f"[green]Склад в городе {city} ({label}) обновлен [/green]")
    else:
        console.print(f"[green]Склад в городе {city} обновлен [/green]")


@command("delete warehouse", "удалить склад", CATEGORY_WAREHOUSES)
def delete_warehouse(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses WHERE id = %s", (_id,))
        warehouse: Warehouse | None = cur.fetchone()

    if warehouse is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    _render_warehouse(warehouse)

    if warehouse.is_central and _count_warehouses() > 1:
        render_error(
            "Нельзя удалить центральный склад. Сначала назначьте другой склад центральным."
        )
        return

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn.execute("DELETE FROM catalog.warehouses WHERE id = %s", (_id,))
        if warehouse.label:
            console.print(
                f"[green]Склад в городе {warehouse.city} ({warehouse.label}) удален [/green]"
            )
        else:
            console.print(f"[green]Склад в городе {warehouse.city} удален [/green]")
