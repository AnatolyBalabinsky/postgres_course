from commands import command, CATEGORY_INVENTORY
from auth import ROLE_INVENTORY_MANAGER, ROLE_WORKER


@command(
    "list deliveries",
    "список накладных на доставку",
    CATEGORY_INVENTORY,
    [ROLE_INVENTORY_MANAGER, ROLE_WORKER],
)
def list_deliveries() -> None:
    pass  # TODO: реализовать в этапе 8
