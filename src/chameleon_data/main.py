import sys
import time
from argparse import ArgumentParser
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import questionary
from faker import Faker
from pydantic import BaseModel
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


class ExampleData(BaseModel):
    no: int
    first_name: str
    last_name: str
    zipcode: str
    address: str
    phone_number: str


ALLOWED_SUFFIXES = (".csv", ".tsv", ".xlsx")

console = Console()


def fake_address(fake: Faker) -> str:
    # prefecture, chome, etc. exist only in the ja_JP provider
    if not hasattr(fake, "prefecture"):
        return fake.address().replace("\n", " ")
    return f"{fake.prefecture()}{fake.city()}{fake.chome()}{fake.gou()}{fake.ban()}{fake.building_name()}{fake.building_number()}"


FAKE_GENERATORS: dict[str, Callable[[Faker], str]] = {
    "full_name": lambda fake: f"{fake.last_name()} {fake.first_name()}",
    "first_name": lambda fake: fake.first_name(),
    "last_name": lambda fake: fake.last_name(),
    "full_address": fake_address,
    "zipcode": lambda fake: fake.zipcode(),
    "phone_number": lambda fake: fake.phone_number(),
}

FAKE_TYPES = ["masking", *FAKE_GENERATORS]

# questionary prompt texts, keyed by the language part of the Faker locale
PROMPTS: dict[str, dict[str, str]] = {
    "ja": {
        "select_columns": "マスクする列を選択してください",
        "select_columns_hint": "(↑↓で移動、スペースで選択、aで全選択、iで反転、Enterで決定)",
        "select_type": "{column} の置き換え方法を選択してください",
        "select_type_hint": "(↑↓で移動、Enterで決定)",
    },
    "en": {
        "select_columns": "select masking columns",
        "select_columns_hint": "(↑↓ to move, <space> to select, <a> to toggle, <i> to invert)",
        "select_type": "type of {column}",
        "select_type_hint": "(↑↓ to move, <enter> to choose)",
    },
    "zh": {
        "select_columns": "请选择要脱敏的列",
        "select_columns_hint": "(↑↓ 移动，空格 选择，a 全选，i 反选，回车 确认)",
        "select_type": "请选择 {column} 的替换方式",
        "select_type_hint": "(↑↓ 移动，回车 确认)",
    },
}


def get_prompts(language: str) -> dict[str, str]:
    # ja_JP -> ja, zh_TW -> zh; unsupported languages fall back to English
    return PROMPTS.get(language.split("_")[0].lower(), PROMPTS["en"])


def read_table(path: Path) -> pd.DataFrame:
    match path.suffix:
        case ".csv":
            return pd.read_csv(path, dtype=str)
        case ".tsv":
            return pd.read_csv(path, sep="\t", dtype=str)
        case ".xlsx":
            return pd.read_excel(path, dtype=str)
    raise ValueError(f"{path.suffix} is not allowed.")


def write_table(df: pd.DataFrame, path: Path) -> None:
    match path.suffix:
        case ".csv":
            df.to_csv(path, index=False)
        case ".tsv":
            df.to_csv(path, sep="\t", index=False)
        case ".xlsx":
            df.to_excel(path, index=False)
        case _:
            raise ValueError(f"{path.suffix} is not allowed.")


def mask_column(
    series: pd.Series,
    fake_type: str,
    fake: Faker,
    on_row: Callable[[], None] | None = None,
) -> pd.Series:
    # same original value -> same replacement, so relations between rows are kept
    replaced: dict[str, str] = {}

    def replace(value: str) -> str:
        if on_row is not None:
            on_row()
        if pd.isna(value):
            return value
        if value not in replaced:
            if fake_type == "masking":
                replaced[value] = "*" * len(value)
            else:
                replaced[value] = FAKE_GENERATORS[fake_type](fake)
        return replaced[value]

    return series.map(replace)


def exit_with_error(message: str) -> None:
    console.print(
        Panel.fit(message, title="✗ error", title_align="left", border_style="red")
    )
    sys.exit(1)


def exit_cancelled() -> None:
    console.print("cancelled.", style="dim")
    sys.exit(1)


def print_header(language: str, seed: int | None) -> None:
    info = f"[dim]mask columns with fake data[/]  ·  locale [cyan]{language}[/]"
    if seed is not None:
        info += f"  ·  seed [cyan]{seed}[/]"
    console.print(
        Panel.fit(
            info,
            title=f"[bold green]🦎 chameleon[/] [dim]v{version('chameleon-data')}[/]",
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


def main() -> None:
    parser = ArgumentParser(
        prog="chameleon",
        description="mask columns of csv/tsv/xlsx file with fake data.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=version("chameleon-data")
    )
    parser.add_argument(
        "-f",
        "--filepath",
        required=True,
        help="filepath read file. allowed format: csv, tsv, xlsx",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="filepath to save masked file. default: <filename>_masked.<suffix>",
    )
    parser.add_argument(
        "-l",
        "--language",
        default="ja_JP",
        help="language of fake data. default: ja_JP",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        help="you need same data everytimes, set seed any number.",
    )
    args = parser.parse_args()

    print_header(args.language, args.seed)

    input_path = Path(args.filepath).resolve()
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_stem(f"{input_path.stem}_masked")

    for path in (input_path, output_path):
        if path.suffix not in ALLOWED_SUFFIXES:
            exit_with_error(f"{path.suffix} is not allowed.")
    if not input_path.exists():
        exit_with_error(f"{input_path} is not found.")

    with console.status(f"reading {input_path.name} ..."):
        df = read_table(input_path)
    print_input_info(input_path, df)

    prompts = get_prompts(args.language)
    headers = list(df.columns)
    mask_columns = questionary.checkbox(
        prompts["select_columns"],
        headers,
        instruction=prompts["select_columns_hint"],
    ).ask()
    if mask_columns is None:
        exit_cancelled()
    if not mask_columns:
        exit_with_error("no columns selected.")

    fake_types = {}
    for column in mask_columns:
        fake_type = questionary.select(
            prompts["select_type"].format(column=column),
            FAKE_TYPES,
            instruction=prompts["select_type_hint"],
        ).ask()
        if fake_type is None:
            exit_cancelled()
        fake_types[column] = fake_type
    print_mask_plan(fake_types)

    fake = Faker(args.language)
    if args.seed is not None:
        Faker.seed(args.seed)

    started = time.perf_counter()
    with Progress(
        SpinnerColumn(finished_text="[green]✔[/]"),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        tasks = {
            column: progress.add_task(column, total=len(df)) for column in fake_types
        }
        for column, fake_type in fake_types.items():
            task = tasks[column]
            df[column] = mask_column(
                df[column], fake_type, fake, on_row=lambda: progress.advance(task)
            )

    with console.status(f"writing {output_path.name} ..."):
        write_table(df, output_path)
    print_result(output_path, len(df), list(fake_types), time.perf_counter() - started)


def create_example() -> None:
    Faker.seed(223)
    fake = Faker("ja_JP")

    persons = [
        ExampleData(
            no=i + 1,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            zipcode=fake.zipcode(),
            address=fake_address(fake),
            phone_number=fake.phone_number(),
        )
        for i in range(10)
    ]

    df = pd.DataFrame([p.model_dump() for p in persons])
    df = df.set_index("no")

    table = Table(box=box.ROUNDED, header_style="bold cyan", border_style="dim")
    table.add_column("no", justify="right", style="dim")
    for column in df.columns:
        table.add_column(column)
    for no, row in df.iterrows():
        table.add_row(str(no), *row)
    console.print(table)

    example_dir = Path(Path.cwd(), "example")
    Path.mkdir(example_dir, exist_ok=True)
    example_path = Path(example_dir, "example.csv")

    df.to_csv(example_path)
    console.print(
        Panel.fit(
            f"[bold]saved[/]    [cyan]{example_path}[/]\n"
            f"[bold]try it![/]  chameleon -f {example_path}",
            title="✔ example",
            title_align="left",
            border_style="green",
        )
    )
