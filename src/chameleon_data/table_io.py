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


def _table_format(
    path: Path,
) -> tuple[Callable[[Path], pd.DataFrame], Callable[[pd.DataFrame, Path], None]]:
    if path.suffix not in TABLE_FORMATS:
        raise ValueError(f"{path.suffix} is not allowed.")
    return TABLE_FORMATS[path.suffix]


def read_table(path: Path) -> pd.DataFrame:
    reader, _ = _table_format(path)
    return reader(path)


def write_table(df: pd.DataFrame, path: Path) -> None:
    _, writer = _table_format(path)
    writer(df, path)
