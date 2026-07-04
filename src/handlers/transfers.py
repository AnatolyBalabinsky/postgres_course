from commands import command, CATEGORY_INVENTORY
from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER


@command(
    "list transfers",
    "список накладных на перемещение",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_transfers() -> None:
    pass  # TODO: реализовать в этапе 8
