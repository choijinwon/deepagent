import os


ENABLE_RICH_CONSOLE = os.getenv("ENABLE_RICH_CONSOLE", "true").lower() in ("1", "true", "yes", "y")

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    Console = None
    Live = None
    Markdown = None
    Panel = None
    Table = None


RICH_AVAILABLE = Console is not None
console = Console() if RICH_AVAILABLE else None


def rich_enabled() -> bool:
    return ENABLE_RICH_CONSOLE and RICH_AVAILABLE


def print_status_line(message: str, style: str = "cyan") -> None:
    if rich_enabled():
        console.print(f"[{style}]{message}[/{style}]")
    else:
        print(message)


def print_rule(title: str = "") -> None:
    if rich_enabled():
        console.rule(title)
    else:
        print("-" * 78)
        if title:
            print(title)


def print_markdown_result(title: str, text: str, border_style: str = "green") -> None:
    if rich_enabled():
        console.print(Panel(Markdown(str(text)), title=title, border_style=border_style, expand=False))
    else:
        print("")
        print(f"{title}>")
        print("-" * 78)
        print(str(text))
        print("-" * 78)


def print_key_value_table(title: str, rows: list[tuple[str, str]]) -> None:
    if rich_enabled():
        table = Table(title=title, show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="bold cyan", no_wrap=True)
        table.add_column("Value")
        for key, value in rows:
            table.add_row(key, value)
        console.print(table)
        return

    print("-" * 78)
    print(title)
    for key, value in rows:
        print(f"{key:<16}: {value}")
    print("-" * 78)


class MarkdownStream:
    def __init__(self, title: str = "assistant", border_style: str = "green") -> None:
        self.title = title
        self.border_style = border_style
        self.text = ""
        self.live = None
        self.started_plain = False

    def __enter__(self):
        if rich_enabled():
            self.live = Live(
                self._render(),
                console=console,
                refresh_per_second=6,
                transient=False,
            )
            self.live.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.live:
            self.live.update(self._render(), refresh=True)
            self.live.stop()
        elif self.started_plain:
            print("")
            print("-" * 78)

    def append(self, value: str) -> None:
        self.text += str(value)
        if self.live:
            self.live.update(self._render(), refresh=True)
        else:
            if not self.started_plain:
                print("")
                print(f"{self.title}>")
                print("-" * 78)
                self.started_plain = True
            print(str(value), end="", flush=True)

    def _render(self):
        body = self.text or "_응답 수신 중..._"
        return Panel(Markdown(body), title=self.title, border_style=self.border_style, expand=False)
