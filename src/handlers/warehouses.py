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

from auth import ROLE_CATALOG_MANAGER, ROLE_SALES_MANAGER


@dataclass
class Warehouse:
    id: int
    city_id: int
    city_name: str
    address: str
    label: str | None
    is_central: bool


def _get_cities() -> list[tuple[int, str]]:
    """Возвращает список городов из БД"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM catalog.cities ORDER BY name")
        return [(row[0], row[1]) for row in cur.fetchall()]


def _get_city_completer():
    """Создаёт completer на основе городов из БД"""
    cities = _get_cities()
    return WordCompleter([name for _, name in cities], ignore_case=True, sentence=True)


def _get_city_validator():
    """Создаёт валидатор на основе городов из БД"""
    cities = _get_cities()
    city_names = [name for _, name in cities]
    return ChoiceValidator(
        city_names,
        message="Город должен быть из списка. Используйте Tab для автодополнения.",
    )


def _get_city_id_by_name(name: str) -> int | None:
    """Получает ID города по имени"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM catalog.cities WHERE name = %s", (name,))
        row = cur.fetchone()
        return row[0] if row else None


def _get_city_name_by_id(city_id: int) -> str:
    """Получает имя города по ID"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM catalog.cities WHERE id = %s", (city_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Город с ID {city_id} не найден")
        return row[0]


def _render_warehouse(warehouse: Warehouse) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))

    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(warehouse.id))
    table.add_row("Город", warehouse.city_name)
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


@command(
    "list warehouses",
    "список всех складов",
    CATEGORY_WAREHOUSES,
    [ROLE_CATALOG_MANAGER, ROLE_SALES_MANAGER],
)
def list_warehouses() -> None:
    conn = get_conn()
    table = Table(title="Склады", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Город", style="green", min_width=20)
    table.add_column("Адрес", style="yellow", min_width=30)
    table.add_column("Метка", style="magenta", min_width=15)
    table.add_column("Центральный", style="cyan", min_width=12)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT w.id, w.city_id, c.name as city_name, 
                   w.address, w.label, w.is_central
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(
            str(row[0]),
            row[2],
            row[3],
            row[4] or "",
            "*" if row[5] else "",
        )
    console.print(table)


@command(
    "show warehouse",
    "информация о складе",
    CATEGORY_WAREHOUSES,
    [ROLE_CATALOG_MANAGER, ROLE_SALES_MANAGER],
)
def show_warehouse(_id: str) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id, w.city_id, c.name as city_name, 
                   w.address, w.label, w.is_central
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE w.id = %s
        """,
            (_id,),
        )
        row = cur.fetchone()

    if row is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    warehouse = Warehouse(
        id=row[0],
        city_id=row[1],
        city_name=row[2],
        address=row[3],
        label=row[4],
        is_central=row[5],
    )
    _render_warehouse(warehouse)


@command(
    "add warehouse",
    "добавить склад (интерактивно)",
    CATEGORY_WAREHOUSES,
    [ROLE_CATALOG_MANAGER],
)
def add_warehouse() -> None:
    conn = get_conn()
    city_completer = _get_city_completer()
    city_validator = _get_city_validator()

    city_name = prompt(
        "Город: ", validator=city_validator, completer=city_completer
    ).strip()
    address = prompt("Адрес: ", validator=NonEmptyValidator()).strip()
    label = prompt("Метка (необязательно): ").strip() or None

    city_id = _get_city_id_by_name(city_name)

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
        "INSERT INTO catalog.warehouses (city_id, address, label, is_central) VALUES (%s, %s, %s, %s)",
        (city_id, address, label, is_central),
    )
    if label:
        console.print(f"[green]Склад в городе {city_name} ({label}) добавлен [/green]")
    else:
        console.print(f"[green]Склад в городе {city_name} добавлен [/green]")


@command(
    "edit warehouse", "редактировать склад", CATEGORY_WAREHOUSES, [ROLE_CATALOG_MANAGER]
)
def edit_warehouse(_id: str) -> None:
    conn = get_conn()
    city_completer = _get_city_completer()
    city_validator = _get_city_validator()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id, w.city_id, c.name as city_name, 
                   w.address, w.label, w.is_central
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE w.id = %s
        """,
            (_id,),
        )
        row = cur.fetchone()

    if row is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    warehouse = Warehouse(
        id=row[0],
        city_id=row[1],
        city_name=row[2],
        address=row[3],
        label=row[4],
        is_central=row[5],
    )

    city_name = prompt(
        "Город: ",
        default=warehouse.city_name,
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

    new_city_id = _get_city_id_by_name(city_name)

    conn.execute(
        """UPDATE catalog.warehouses 
           SET city_id = %s, address = %s, label = %s, is_central = %s
           WHERE id = %s""",
        (new_city_id, address, label, is_central, _id),
    )
    if label:
        console.print(f"[green]Склад в городе {city_name} ({label}) обновлен [/green]")
    else:
        console.print(f"[green]Склад в городе {city_name} обновлен [/green]")


@command(
    "delete warehouse", "удалить склад", CATEGORY_WAREHOUSES, [ROLE_CATALOG_MANAGER]
)
def delete_warehouse(_id: str) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id, w.city_id, c.name as city_name, 
                   w.address, w.label, w.is_central
            FROM catalog.warehouses w
            JOIN catalog.cities c ON w.city_id = c.id
            WHERE w.id = %s
        """,
            (_id,),
        )
        row = cur.fetchone()

    if row is None:
        render_error(f"Склад с ID {_id} не найден")
        return

    warehouse = Warehouse(
        id=row[0],
        city_id=row[1],
        city_name=row[2],
        address=row[3],
        label=row[4],
        is_central=row[5],
    )

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
                f"[green]Склад в городе {warehouse.city_name} ({warehouse.label}) удален [/green]"
            )
        else:
            console.print(
                f"[green]Склад в городе {warehouse.city_name} удален [/green]"
            )
