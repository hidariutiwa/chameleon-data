from collections.abc import Callable

import pandas as pd
from faker import Faker

from chameleon_data.fakers import FAKE_GENERATORS, NAME_TYPES, fake_person


def generate_table(
    fake_types: dict[str, str],
    rows: int,
    fake: Faker,
    on_advance: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    # name columns describe one person per row only when two or more are selected,
    # the same rule as apply_masks()
    name_columns = [c for c, t in fake_types.items() if t in NAME_TYPES]
    if len(name_columns) < 2:
        name_columns = []

    data: dict[str, list[str]] = {column: [] for column in fake_types}
    if name_columns:
        for _ in range(rows):
            person = fake_person(fake)
            for column in name_columns:
                data[column].append(person[fake_types[column]])
                if on_advance is not None:
                    on_advance(column)

    for column, fake_type in fake_types.items():
        if column in name_columns:
            continue
        generator = FAKE_GENERATORS[fake_type]
        for _ in range(rows):
            data[column].append(generator(fake))
            if on_advance is not None:
                on_advance(column)

    return pd.DataFrame(data, columns=list(fake_types))
