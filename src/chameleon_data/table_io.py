from collections.abc import Callable
from pathlib import Path

import pandas as pd

# suffix -> (reader, writer); dtype=str keeps leading zeros of zip codes and phone numbers
TABLE_FORMATS: dict[
    str,
    tuple[Callable[[Path], pd.DataFrame], Callable[[pd.DataFrame, Path], None]],
] = {
    ".csv": (
        lambda path: pd.read_csv(path, dtype=str),
        lambda df, path: df.to_csv(path, index=False),
    ),
    ".tsv": (
        lambda path: pd.read_csv(path, sep="\t", dtype=str),
        lambda df, path: df.to_csv(path, sep="\t", index=False),
    ),
    ".xlsx": (
        lambda path: pd.read_excel(path, dtype=str),
        lambda df, path: df.to_excel(path, index=False),
    ),
}

ALLOWED_SUFFIXES = tuple(TABLE_FORMATS)

# suffix -> header reader; nrows=0 reads only the column names
HEADER_READERS: dict[str, Callable[[Path], pd.DataFrame]] = {
    ".csv": lambda path: pd.read_csv(path, nrows=0),
    ".tsv": lambda path: pd.read_csv(path, sep="\t", nrows=0),
    ".xlsx": lambda path: pd.read_excel(path, nrows=0),
}

# writers for output; json is write-only, so mask (same format in and out) skips it
OUTPUT_FORMATS: dict[str, Callable[[pd.DataFrame, Path], None]] = {
    **{suffix: writer for suffix, (_, writer) in TABLE_FORMATS.items()},
    ".json": lambda df, path: df.to_json(
        path, orient="records", force_ascii=False, indent=2
    ),
}

OUTPUT_SUFFIXES = tuple(OUTPUT_FORMATS)


def _table_format(
    path: Path,
) -> tuple[Callable[[Path], pd.DataFrame], Callable[[pd.DataFrame, Path], None]]:
    if path.suffix not in TABLE_FORMATS:
        raise ValueError(f"{path.suffix} is not allowed.")
    return TABLE_FORMATS[path.suffix]


def read_table(path: Path) -> pd.DataFrame:
    reader, _ = _table_format(path)
    return reader(path)


def read_header(path: Path) -> list[str]:
    if path.suffix not in HEADER_READERS:
        raise ValueError(f"{path.suffix} is not allowed.")
    return [str(column) for column in HEADER_READERS[path.suffix](path).columns]


def write_table(df: pd.DataFrame, path: Path) -> None:
    if path.suffix not in OUTPUT_FORMATS:
        raise ValueError(f"{path.suffix} is not allowed.")
    OUTPUT_FORMATS[path.suffix](df, path)
