from collections.abc import Callable
from functools import partial

import pandas as pd
from faker import Faker

from chameleon_data.fakers import FAKE_GENERATORS, MASKING, NAME_TYPES, fake_person


def mask_column(
    series: pd.Series,
    fake_type: str,
    fake: Faker,
    on_row: Callable[[], None] | None = None,
) -> pd.Series:
    if fake_type == MASKING:

        def generate(value: str) -> str:
            return "*" * len(value)

    else:
        generator = FAKE_GENERATORS[fake_type]

        def generate(value: str) -> str:
            return generator(fake)

    # same original value -> same replacement, so relations between rows are kept
    replaced: dict[str, str] = {}

    def replace(value: str) -> str:
        if on_row is not None:
            on_row()
        if pd.isna(value):
            return value
        if value not in replaced:
            replaced[value] = generate(value)
        return replaced[value]

    return series.map(replace)


def mask_name_columns(
    df: pd.DataFrame,
    fake_types: dict[str, str],
    fake: Faker,
    on_row: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    # one fake person per row; same original names -> same person
    columns = [column for column, t in fake_types.items() if t in NAME_TYPES]
    persons: dict[tuple, dict[str, str]] = {}
    masked = df[columns].copy()

    for index, row in df[columns].iterrows():
        key = tuple(None if pd.isna(v) else v for v in row)
        if any(v is not None for v in key):
            if key not in persons:
                persons[key] = fake_person(fake)
            for column, value in zip(columns, key):
                if value is not None:
                    masked.at[index, column] = persons[key][fake_types[column]]
        if on_row is not None:
            for column in columns:
                on_row(column)
    return masked


def apply_masks(
    df: pd.DataFrame,
    fake_types: dict[str, str],
    fake: Faker,
    on_advance: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    # name columns are replaced together only when two or more of them are selected
    masked = df.copy()
    name_columns = [c for c, t in fake_types.items() if t in NAME_TYPES]
    if len(name_columns) > 1:
        masked[name_columns] = mask_name_columns(df, fake_types, fake, on_advance)
    else:
        name_columns = []
    for column, fake_type in fake_types.items():
        if column in name_columns:
            continue
        on_row = None if on_advance is None else partial(on_advance, column)
        masked[column] = mask_column(df[column], fake_type, fake, on_row)
    return masked
