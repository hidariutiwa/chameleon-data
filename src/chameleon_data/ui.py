import sys
from pathlib import Path
from typing import NoReturn

import pandas as pd
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()


def exit_with_error(message: str) -> NoReturn:
    console.print(
        Panel.fit(message, title="✗ error", title_align="left", border_style="red")
    )
    sys.exit(1)


def exit_cancelled() -> NoReturn:
    console.print("cancelled.", style="dim")
    sys.exit(1)


def print_header(language: str, seed: int | None, app_version: str) -> None:
    info = f"[dim]mask columns with fake data[/]  ·  locale [cyan]{language}[/]"
    if seed is not None:
        info += f"  ·  seed [cyan]{seed}[/]"
    console.print(
        Panel.fit(
            info,
            title=f"[bold green]🦎 chameleon[/] [dim]v{app_version}[/]",
            border_style="green",
        )
    )


def print_input_info(path: Path, df: pd.DataFrame) -> None:
    console.print(
        f"[bold]Input[/]  {path.name}  [dim]·[/]  {path.suffix[1:].upper()}"
        f"  [dim]·[/]  {len(df)} rows × {len(df.columns)} columns"
    )


def print_mask_plan(fake_types: dict[str, str]) -> None:
    table = Table(box=box.ROUNDED, header_style="bold cyan", border_style="dim")
    table.add_column("column")
    table.add_column("fake type", style="green")
    for column, fake_type in fake_types.items():
        table.add_row(column, fake_type)
    console.print(table)


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(finished_text="[green]✔[/]"),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def print_result(
    output_path: Path, rows: int, columns: list[str], elapsed: float
) -> None:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column(overflow="fold")
    grid.add_row("output", f"[cyan]{output_path}[/]")
    grid.add_row("rows", str(rows))
    grid.add_row("masked", ", ".join(columns))
    grid.add_row("elapsed", f"{elapsed:.2f}s")
    console.print(
        Panel.fit(grid, title="✔ done", title_align="left", border_style="green")
    )
