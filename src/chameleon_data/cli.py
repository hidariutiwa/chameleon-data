import sys
import time
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from importlib.metadata import version
from pathlib import Path

from faker import Faker

from chameleon_data.example import create_example
from chameleon_data.fakers import sample_fake_values
from chameleon_data.generate import generate_table
from chameleon_data.masking import apply_masks
from chameleon_data.prompts import (
    ask_columns,
    ask_fake_types,
    ask_new_columns,
    get_prompts,
    get_type_labels,
)
from chameleon_data.table_io import (
    ALLOWED_SUFFIXES,
    OUTPUT_SUFFIXES,
    read_header,
    read_table,
    write_table,
)
from chameleon_data.ui import (
    console,
    exit_with_error,
    make_progress,
    print_deprecation,
    print_header,
    print_input_info,
    print_mask_plan,
    print_result,
    print_template_info,
)

COMMANDS = ("mask", "generate", "example")
# top-level options that must not be rewritten into "mask ..."
TOP_LEVEL_OPTIONS = ("-h", "--help", "-v", "--version")

GENERATE_FORMATS = tuple(suffix[1:] for suffix in OUTPUT_SUFFIXES)
DEFAULT_GENERATE_FORMAT = "csv"
DEFAULT_GENERATE_ROWS = 100
# output stem of generate when no template file is given
DEFAULT_GENERATE_STEM = "fake_data"


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise ArgumentTypeError(f"{value} is not an integer.") from None
    if number < 1:
        raise ArgumentTypeError(f"{value} must be 1 or more.")
    return number


def build_parser(app_version: str) -> ArgumentParser:
    parser = ArgumentParser(
        prog="chameleon",
        description="mask or generate csv/tsv/xlsx data with fake values.",
    )
    parser.add_argument("-v", "--version", action="version", version=app_version)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # options shared by commands that generate fake values
    faker_options = ArgumentParser(add_help=False)
    faker_options.add_argument(
        "-l",
        "--language",
        default="ja_JP",
        help="language of fake data. default: ja_JP",
    )
    faker_options.add_argument(
        "-s",
        "--seed",
        type=int,
        help="you need same data everytimes, set seed any number.",
    )

    mask = subparsers.add_parser(
        "mask",
        parents=[faker_options],
        help="mask columns of csv/tsv/xlsx file with fake data.",
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

    generate = subparsers.add_parser(
        "generate",
        parents=[faker_options],
        help="generate test data. columns come from a header row or are entered.",
    )
    generate.add_argument(
        "-f",
        "--filepath",
        help="file whose header row gives the columns. allowed format: csv, tsv, xlsx."
        " without it, enter column names interactively.",
    )
    generate.add_argument(
        "-o",
        "--output",
        help="filepath to save generated file; its suffix decides the format."
        f" default: <filename>_fake.<format>, or {DEFAULT_GENERATE_STEM}.<format>"
        " without -f",
    )
    generate.add_argument(
        "-n",
        "--rows",
        type=positive_int,
        default=DEFAULT_GENERATE_ROWS,
        help=f"number of rows to generate. default: {DEFAULT_GENERATE_ROWS}",
    )
    generate.add_argument(
        "--format",
        choices=GENERATE_FORMATS,
        help=f"output format. default: {DEFAULT_GENERATE_FORMAT}"
        " (or the suffix of -o)",
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


def resolve_generate_paths(args: Namespace) -> tuple[Path | None, Path]:
    template_path = None
    if args.filepath:
        template_path = Path(args.filepath).resolve()
        if template_path.suffix not in ALLOWED_SUFFIXES:
            exit_with_error(f"{template_path.suffix} is not allowed.")
        if not template_path.exists():
            exit_with_error(f"{template_path} is not found.")

    if args.output:
        output_path = Path(args.output).resolve()
        if output_path.suffix not in OUTPUT_SUFFIXES:
            exit_with_error(f"{output_path.suffix} is not allowed.")
        if args.format and output_path.suffix != f".{args.format}":
            exit_with_error(
                f"--format {args.format} does not match the output {output_path.name}."
            )
    else:
        suffix = f".{args.format or DEFAULT_GENERATE_FORMAT}"
        if template_path is None:
            output_path = Path.cwd() / f"{DEFAULT_GENERATE_STEM}{suffix}"
        else:
            output_path = template_path.with_name(f"{template_path.stem}_fake{suffix}")
    return template_path, output_path


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


def run_generate(args: Namespace, app_version: str) -> None:
    print_header(args.language, args.seed, app_version, subtitle="generate test data")
    template_path, output_path = resolve_generate_paths(args)

    prompts = get_prompts(args.language)
    labels = get_type_labels(args.language)
    # samples consume random state, but seeding below resets it
    fake = Faker(args.language)
    samples = sample_fake_values(fake)
    if template_path is None:
        fake_types = ask_new_columns(samples, prompts, labels)
    else:
        columns = read_header(template_path)
        if not columns:
            exit_with_error(f"{template_path.name} has no header row.")
        print_template_info(template_path, columns)
        fake_types = ask_fake_types(columns, None, samples, prompts, labels)
    print_mask_plan(fake_types)

    if args.seed is not None:
        Faker.seed(args.seed)

    started = time.perf_counter()
    with make_progress() as progress:
        tasks = {
            column: progress.add_task(column, total=args.rows) for column in fake_types
        }
        df = generate_table(
            fake_types,
            args.rows,
            fake,
            on_advance=lambda column: progress.advance(tasks[column]),
        )

    with console.status(f"writing {output_path.name} ..."):
        write_table(df, output_path)
    print_result(
        output_path,
        len(df),
        list(fake_types),
        time.perf_counter() - started,
        columns_label="generated",
    )


def main(argv: list[str] | None = None) -> None:
    app_version = version("chameleon-data")
    args = parse_args(app_version, argv)
    # argparse rejects unknown commands, so one of these always matches
    if args.command == "mask":
        run_mask(args, app_version)
    elif args.command == "generate":
        run_generate(args, app_version)
    elif args.command == "example":
        create_example()


def legacy_example() -> None:
    # entry point of the v0.4 "chameleon-example" command; remove in v0.6.0
    print_deprecation("chameleon-example", "chameleon example")
    create_example()
