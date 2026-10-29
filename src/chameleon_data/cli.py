import time
from argparse import ArgumentParser, Namespace
from importlib.metadata import version
from pathlib import Path

from faker import Faker

from chameleon_data.fakers import sample_fake_values
from chameleon_data.masking import apply_masks
from chameleon_data.prompts import (
    ask_columns,
    ask_fake_types,
    get_prompts,
    get_type_labels,
)
from chameleon_data.table_io import ALLOWED_SUFFIXES, read_table, write_table
from chameleon_data.ui import (
    console,
    exit_with_error,
    make_progress,
    print_header,
    print_input_info,
    print_mask_plan,
    print_result,
)


def parse_args(app_version: str) -> Namespace:
    parser = ArgumentParser(
        prog="chameleon",
        description="mask columns of csv/tsv/xlsx file with fake data.",
    )
    parser.add_argument("-v", "--version", action="version", version=app_version)
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
    return parser.parse_args()


def resolve_paths(args: Namespace) -> tuple[Path, Path]:
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
    return input_path, output_path


def main() -> None:
    app_version = version("chameleon-data")
    args = parse_args(app_version)
    print_header(args.language, args.seed, app_version)
    input_path, output_path = resolve_paths(args)

    with console.status(f"reading {input_path.name} ..."):
        df = read_table(input_path)
    print_input_info(input_path, df)

    prompts = get_prompts(args.language)
    mask_columns = ask_columns(df, prompts)
    # samples consume random state, but seeding below resets it
    fake = Faker(args.language)
    fake_types = ask_fake_types(
        mask_columns,
        df,
        sample_fake_values(fake),
        prompts,
        get_type_labels(args.language),
    )
    print_mask_plan(fake_types)

    if args.seed is not None:
        Faker.seed(args.seed)

    started = time.perf_counter()
    with make_progress() as progress:
        tasks = {
            column: progress.add_task(column, total=len(df)) for column in fake_types
        }
        df = apply_masks(
            df,
            fake_types,
            fake,
            on_advance=lambda column: progress.advance(tasks[column]),
        )

    with console.status(f"writing {output_path.name} ..."):
        write_table(df, output_path)
    print_result(output_path, len(df), list(fake_types), time.perf_counter() - started)
