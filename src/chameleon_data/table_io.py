import codecs
import csv
from collections.abc import Callable
from pathlib import Path

import pandas as pd

UTF8 = "utf-8"
# files saved by Excel on Japanese Windows are often Shift_JIS (cp932)
FALLBACK_ENCODING = "cp932"
# output of a text file that was not plain UTF-8; the BOM lets Excel open it as UTF-8
EXCEL_UTF8 = "utf-8-sig"

Reader = Callable[[Path, str], pd.DataFrame]
Writer = Callable[[pd.DataFrame, Path, str], None]


class TableIOError(Exception):
    """A file that has an allowed suffix but cannot be read or written."""


# suffix -> (reader, writer); readers and writers take the text encoding (xlsx ignores it)
# dtype=str keeps leading zeros of zip codes and phone numbers
# tsv uses no quoting: a value may contain '"' as is, so quoting would eat or add quotes
TABLE_FORMATS: dict[str, tuple[Reader, Writer]] = {
    ".csv": (
        lambda path, enc: pd.read_csv(path, dtype=str, encoding=enc),
        lambda df, path, enc: df.to_csv(path, index=False, encoding=enc),
    ),
    ".tsv": (
        lambda path, enc: pd.read_csv(
            path, sep="\t", dtype=str, encoding=enc, quoting=csv.QUOTE_NONE
        ),
        lambda df, path, enc: df.to_csv(
            path, sep="\t", index=False, encoding=enc, quoting=csv.QUOTE_NONE
        ),
    ),
    ".xlsx": (
        lambda path, enc: pd.read_excel(path, dtype=str),
        lambda df, path, enc: df.to_excel(path, index=False),
    ),
}

ALLOWED_SUFFIXES = tuple(TABLE_FORMATS)
TEXT_SUFFIXES = (".csv", ".tsv")

# suffix -> header reader; nrows=0 reads only the column names
HEADER_READERS: dict[str, Reader] = {
    ".csv": lambda path, enc: pd.read_csv(path, nrows=0, encoding=enc),
    ".tsv": lambda path, enc: pd.read_csv(
        path, sep="\t", nrows=0, encoding=enc, quoting=csv.QUOTE_NONE
    ),
    ".xlsx": lambda path, enc: pd.read_excel(path, nrows=0),
}

# writers for output; json is write-only, so mask (same format in and out) skips it
OUTPUT_FORMATS: dict[str, Writer] = {
    **{suffix: writer for suffix, (_, writer) in TABLE_FORMATS.items()},
    ".json": lambda df, path, enc: df.to_json(
        path, orient="records", force_ascii=False, indent=2
    ),
}

OUTPUT_SUFFIXES = tuple(OUTPUT_FORMATS)


def table_suffix(path: Path) -> str:
    # ".TSV" saved by some tools is the same format as ".tsv"
    return path.suffix.lower()


def detect_encoding(path: Path) -> str:
    # BOM first (Excel "Unicode text" is UTF-16), then strict UTF-8, else cp932
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    if raw.startswith(codecs.BOM_UTF8):
        return EXCEL_UTF8
    try:
        raw.decode(UTF8)
    except UnicodeDecodeError:
        return FALLBACK_ENCODING
    return UTF8


def output_encoding(input_path: Path) -> str:
    # UTF-8 as before; a BOM when the input was not plain UTF-8 (likely made in Excel)
    if (
        table_suffix(input_path) in TEXT_SUFFIXES
        and detect_encoding(input_path) != UTF8
    ):
        return EXCEL_UTF8
    return UTF8


def _check_suffix(path: Path, allowed: tuple[str, ...]) -> str:
    suffix = table_suffix(path)
    if suffix not in allowed:
        raise ValueError(f"{path.suffix} is not allowed.")
    return suffix


def _read(reader: Reader, path: Path) -> pd.DataFrame:
    encoding = detect_encoding(path) if table_suffix(path) in TEXT_SUFFIXES else UTF8
    try:
        return reader(path, encoding)
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        raise TableIOError(
            f"{path.name} could not be read ({encoding}): {str(e).strip()}"
        ) from e


def read_table(path: Path) -> pd.DataFrame:
    reader, _ = TABLE_FORMATS[_check_suffix(path, ALLOWED_SUFFIXES)]
    return _read(reader, path)


def read_header(path: Path) -> list[str]:
    reader = HEADER_READERS[_check_suffix(path, ALLOWED_SUFFIXES)]
    return [str(column) for column in _read(reader, path).columns]


def write_table(df: pd.DataFrame, path: Path, encoding: str = UTF8) -> None:
    writer = OUTPUT_FORMATS[_check_suffix(path, OUTPUT_SUFFIXES)]
    try:
        writer(df, path, encoding)
    except csv.Error as e:
        # tsv without quoting cannot hold a tab or newline inside a value
        raise TableIOError(f"{path.name} could not be written: {e}") from e
