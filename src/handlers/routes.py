from dataclasses import dataclass
from datetime import timedelta

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from psycopg.rows import class_row
from rich.panel import Panel
from rich.table import Table

from console import console, render_error
from db import get_conn
from validators import (
    ChoiceValidator,
    NonEmptyValidator,
    YesNoValidator,
    PriceValidator,
    QuantityValidator,
)
from commands import command, CATEGORY_INVENTORY

from auth import ROLE_INVENTORY_MANAGER


@dataclass
class Route:
    from_city_id: int
    from_city_name: str
    to_city_id: int
    to_city_name: str
    duration: timedelta
    total_threshold: float


def _get_cities() -> list[tuple[int, str]]:
    """Возвращает список всех городов: [(id, name), ...]"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM catalog.cities ORDER BY name")
        return [(row[0], row[1]) for row in cur.fetchall()]


def _render_route(route: Route) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=20)
    table.add_column("Значение", style="white")

    table.add_row("Откуда", route.from_city_name)
    table.add_row("Куда", route.to_city_name)
    table.add_row("Длительность", str(route.duration))
    table.add_row("Мин. сумма", str(route.total_threshold))

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Маршрут {route.from_city_name} → {route.to_city_name}[/bold green]",
        border_style="green",
    )
    console.print(panel)


@command(
    "list routes",
    "список всех маршрутов",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def list_routes() -> None:
    conn = get_conn()
    table = Table(title="Маршруты", show_header=True, header_style="bold cyan")

    table.add_column("Откуда", style="green", min_width=20)
    table.add_column("Куда", style="yellow", min_width=20)
    table.add_column("Длительность", style="magenta", min_width=15)
    table.add_column("Мин. сумма", style="cyan", min_width=12)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                r.from_city_id, fc.name as from_city,
                r.to_city_id, tc.name as to_city,
                r.duration, r.total_threshold
            FROM inventory.routes r
            JOIN catalog.cities fc ON r.from_city_id = fc.id
            JOIN catalog.cities tc ON r.to_city_id = tc.id
            ORDER BY fc.name, tc.name
        """)
        rows = cur.fetchall()

    for row in rows:
        table.add_row(row[1], row[3], str(row[4]), str(row[5]))

    console.print(table)


@command(
    "show route",
    "информация о маршруте",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def show_route() -> None:
    conn = get_conn()

    # Получаем существующие маршруты для выбора
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                r.from_city_id, fc.name as from_city,
                r.to_city_id, tc.name as to_city,
                r.duration, r.total_threshold
            FROM inventory.routes r
            JOIN catalog.cities fc ON r.from_city_id = fc.id
            JOIN catalog.cities tc ON r.to_city_id = tc.id
            ORDER BY fc.name, tc.name
        """)
        routes = cur.fetchall()

    if not routes:
        render_error("Нет доступных маршрутов")
        return

    route_options = [(f"{r[0]}-{r[2]}", f"{r[1]} → {r[3]}") for r in routes]

    selected = choice(
        message="Выберите маршрут:",
        options=route_options,
    )
    from_id, to_id = selected.split("-")

    selected_route = next(
        (r for r in routes if str(r[0]) == from_id and str(r[2]) == to_id), None
    )

    if selected_route is None:
        render_error("Маршрут не найден")
        return

    route = Route(
        from_city_id=selected_route[0],
        from_city_name=selected_route[1],
        to_city_id=selected_route[2],
        to_city_name=selected_route[3],
        duration=selected_route[4],
        total_threshold=float(selected_route[5]),
    )
    _render_route(route)


@command(
    "add route",
    "добавить маршрут",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def add_route() -> None:
    conn = get_conn()

    # Получаем все доступные пары городов одним запросом
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fc.id, fc.name, tc.id, tc.name
            FROM catalog.cities fc
            CROSS JOIN catalog.cities tc
            LEFT JOIN inventory.routes r 
                ON r.from_city_id = fc.id AND r.to_city_id = tc.id
            WHERE fc.id != tc.id AND r.from_city_id IS NULL
            ORDER BY fc.name, tc.name
        """)
        available_pairs = [(row[0], row[1], row[2], row[3]) for row in cur.fetchall()]

    if not available_pairs:
        render_error("Все возможные маршруты уже созданы")
        return

    # Уникальные города отправления
    from_cities = list(dict.fromkeys((p[0], p[1]) for p in available_pairs))
    available_from = [(str(c[0]), c[1]) for c in from_cities]

    from_id_str = choice(
        message="Выберите город отправления:",
        options=available_from,
    )
    from_id = int(from_id_str)

    # Фильтруем города назначения для выбранного города отправления
    available_to = [(str(p[2]), p[3]) for p in available_pairs if p[0] == from_id]

    if not available_to:
        render_error("Нет доступных городов назначения для выбранного города")
        return

    to_id_str = choice(
        message="Выберите город назначения:",
        options=available_to,
    )
    to_id = int(to_id_str)

    # Ввод длительности
    hours = prompt("Длительность (часы): ", validator=QuantityValidator()).strip()
    minutes = prompt("Длительность (минуты, 0-59): ", default="0").strip()
    duration = f"{hours}:{minutes}:00"

    threshold = prompt("Минимальная сумма: ", validator=PriceValidator()).strip()

    from_name = next(p[1] for p in available_pairs if p[0] == from_id)
    to_name = next(p[3] for p in available_pairs if p[0] == from_id and p[2] == to_id)

    conn.execute(
        """INSERT INTO inventory.routes (from_city_id, to_city_id, duration, total_threshold)
           VALUES (%s, %s, %s::interval, %s)""",
        (from_id, to_id, duration, threshold),
    )

    console.print(f"[green]Маршрут {from_name} → {to_name} добавлен[/green]")


@command(
    "edit route",
    "редактировать маршрут",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def edit_route() -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                r.from_city_id, fc.name as from_city,
                r.to_city_id, tc.name as to_city,
                r.duration, r.total_threshold
            FROM inventory.routes r
            JOIN catalog.cities fc ON r.from_city_id = fc.id
            JOIN catalog.cities tc ON r.to_city_id = tc.id
            ORDER BY fc.name, tc.name
        """)
        routes = cur.fetchall()

    if not routes:
        render_error("Нет доступных маршрутов")
        return

    route_options = [(f"{r[0]}-{r[2]}", f"{r[1]} → {r[3]}") for r in routes]

    selected = choice(
        message="Выберите маршрут для редактирования:",
        options=route_options,
    )
    from_id, to_id = selected.split("-")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT duration, total_threshold
            FROM inventory.routes
            WHERE from_city_id = %s AND to_city_id = %s
        """,
            (from_id, to_id),
        )
        row = cur.fetchone()

    current_duration = row[0]
    current_threshold = float(row[1])

    # Разбираем текущую длительность
    total_seconds = int(current_duration.total_seconds())
    current_hours = total_seconds // 3600
    current_minutes = (total_seconds % 3600) // 60

    hours = prompt(
        "Длительность (часы): ",
        default=str(current_hours),
        validator=QuantityValidator(),
    ).strip()
    minutes = prompt(
        "Длительность (минуты, 0-59): ",
        default=str(current_minutes),
    ).strip()
    duration = f"{hours}:{minutes}:00"

    threshold = prompt(
        "Минимальная сумма: ",
        default=str(current_threshold),
        validator=PriceValidator(),
    ).strip()

    conn.execute(
        """UPDATE inventory.routes 
           SET duration = %s::interval, total_threshold = %s
           WHERE from_city_id = %s AND to_city_id = %s""",
        (duration, threshold, from_id, to_id),
    )
    console.print("[green]Маршрут обновлен[/green]")


@command(
    "delete route",
    "удалить маршрут",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER],
)
def delete_route() -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                r.from_city_id, fc.name as from_city,
                r.to_city_id, tc.name as to_city,
                r.duration, r.total_threshold
            FROM inventory.routes r
            JOIN catalog.cities fc ON r.from_city_id = fc.id
            JOIN catalog.cities tc ON r.to_city_id = tc.id
            ORDER BY fc.name, tc.name
        """)
        routes = cur.fetchall()

    if not routes:
        render_error("Нет доступных маршрутов")
        return

    route_options = [(f"{r[0]}-{r[2]}", f"{r[1]} → {r[3]}") for r in routes]

    selected = choice(
        message="Выберите маршрут для удаления:",
        options=route_options,
    )
    from_id, to_id = selected.split("-")

    route_name = next(r for r in routes if str(r[0]) == from_id and str(r[2]) == to_id)

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator())

    if YesNoValidator.is_yes(answer):
        conn.execute(
            "DELETE FROM inventory.routes WHERE from_city_id = %s AND to_city_id = %s",
            (from_id, to_id),
        )
        console.print(
            f"[green]Маршрут {route_name[1]} → {route_name[3]} удален[/green]"
        )
