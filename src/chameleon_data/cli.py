import sys
import time
from argparse import ArgumentParser, Namespace
from importlib.metadata import version
from pathlib import Path

from faker import Faker

from chameleon_data.example import create_example
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
    print_deprecation,
    print_header,
    print_input_info,
    print_mask_plan,
    print_result,
)

COMMANDS = ("mask", "example")
# top-level options that must not be rewritten into "mask ..."
TOP_LEVEL_OPTIONS = ("-h", "--help", "-v", "--version")


def build_parser(app_version: str) -> ArgumentParser:
    parser = ArgumentParser(
        prog="chameleon",
        description="mask or generate csv/tsv/xlsx data with fake values.",
    )
    parser.add_argument("-v", "--version", action="version", version=app_version)
    subparsers = parser.add_subparsers(dest="command", required=True)

    mask = subparsers.add_parser(
        "mask", help="mask columns of csv/tsv/xlsx file with fake data."
    )
    mask.add_argument(
        "-f",
        "--filepath",
        required=True,
        help="filepath read file. allowed format: csv, tsv, xlsx",
    )
    mask.add_argument(
        "-o",
        "--output",
        help="filepath to save masked file. default: <filename>_masked.<suffix>",
    )
    mask.add_argument(
        "-l",
        "--language",
        default="ja_JP",
        help="language of fake data. default: ja_JP",
    )
    mask.add_argument(
        "-s",
        "--seed",
        type=int,
        help="you need same data everytimes, set seed any number.",
    )

    subparsers.add_parser(
        "example", help="write a sample file to ./example/example.csv."
    )
    return parser


def normalize_argv(argv: list[str]) -> tuple[list[str], bool]:
    # v0.4 form "chameleon -f data.csv" is read as "chameleon mask -f data.csv"
    # returns (argv, legacy) so the caller can warn; remove in v0.6.0
    if argv and argv[0] not in COMMANDS and argv[0] not in TOP_LEVEL_OPTIONS:
        return ["mask", *argv], True
    return argv, False


def parse_args(app_version: str, argv: list[str] | None = None) -> Namespace:
    raw = sys.argv[1:] if argv is None else argv
    normalized, legacy = normalize_argv(raw)
    if legacy:
        print_deprecation("chameleon -f ...", "chameleon mask -f ...")
    return build_parser(app_version).parse_args(normalized)


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


def run_mask(args: Namespace, app_version: str) -> None:
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


def main(argv: list[str] | None = None) -> None:
    app_version = version("chameleon-data")
    args = parse_args(app_version, argv)
    if args.command == "mask":
        run_mask(args, app_version)
    elif args.command == "example":
        create_example()


def legacy_example() -> None:
    # entry point of the v0.4 "chameleon-example" command; remove in v0.6.0
    print_deprecation("chameleon-example", "chameleon example")
    create_example()
