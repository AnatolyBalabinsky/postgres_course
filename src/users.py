from dataclasses import dataclass

from db import get_conn


@dataclass
class User:
    id: int
    username: str
    role: str


def find_user_by_login_and_pass(username: str, password: str) -> User | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, role FROM auth.users "
            "WHERE username = %s AND password = crypt(%s, password)",
            (username, password),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return User(id=row[0], username=row[1], role=row[2])


def get_user(id_: int) -> User:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, role FROM auth.users WHERE id = %s",
            (id_,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Пользователь с ID {id_} не найден")
        return User(id=row[0], username=row[1], role=row[2])
