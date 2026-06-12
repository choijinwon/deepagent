from datetime import datetime


def file_date_string(value: datetime | None = None) -> str:
    """Return a filesystem-safe timestamp string."""
    current = value or datetime.now()
    return current.strftime("%Y%m%d-%H%M%S")


def display_date_string(value: datetime | None = None) -> str:
    current = value or datetime.now()
    return current.strftime("%Y-%m-%d %H:%M:%S")
