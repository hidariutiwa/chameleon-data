import sys
from argparse import ArgumentParser
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import questionary
from faker import Faker
from rich.console import Console
from pydantic import BaseModel


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


def mask_column(series: pd.Series, fake_type: str, fake: Faker) -> pd.Series:
    # same original value -> same replacement, so relations between rows are kept
    replaced: dict[str, str] = {}

    def replace(value: str) -> str:
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
    console.print(message, style="red bold")
    sys.exit(1)


def main() -> None:
    parser = ArgumentParser(
        prog="chameleon",
        description="mask columns of csv/tsv/xlsx file with fake data.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=version("chameleon-cli")
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

    df = read_table(input_path)

    headers = list(df.columns)
    mask_columns = questionary.checkbox("select masking columns", headers).ask()
    if mask_columns is None:
        sys.exit(1)
    if not mask_columns:
        exit_with_error("no columns selected.")

    fake_types = {}
    for column in mask_columns:
        fake_type = questionary.select(f"type of {column}", FAKE_TYPES).ask()
        if fake_type is None:
            sys.exit(1)
        fake_types[column] = fake_type

    fake = Faker(args.language)
    if args.seed is not None:
        Faker.seed(args.seed)

    for column, fake_type in fake_types.items():
        df[column] = mask_column(df[column], fake_type, fake)

    write_table(df, output_path)
    console.print(f"save masked file: {output_path}", style="cyan bold")


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
    print(df)

    example_dir = Path(Path.cwd(), "example")
    Path.mkdir(example_dir, exist_ok=True)
    example_path = Path(example_dir, "example.csv")

    df.to_csv(example_path)
    console.print(f"save example csv: {example_path}", style="cyan bold")
    console.print(f"try it! -> chameleon -f {example_path}", style="cyan bold")
