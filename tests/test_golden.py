from pathlib import Path

import pandas as pd
import pytest
from faker import Faker

from chameleon_data.main import (
    NAME_TYPES,
    create_example,
    mask_column,
    mask_name_columns,
    read_table,
    sample_fake_values,
    write_table,
)

EXAMPLE_CSV = Path(__file__).parent / "golden" / "example.csv"


def run_masks(df: pd.DataFrame, fake_types: dict[str, str], seed: int) -> pd.DataFrame:
    # same order as main(): samples before seeding, name columns first, then the rest
    fake = Faker("ja_JP")
    sample_fake_values(fake)
    Faker.seed(seed)
    name_columns = [c for c, t in fake_types.items() if t in NAME_TYPES]
    if len(name_columns) > 1:
        df[name_columns] = mask_name_columns(df, fake_types, fake)
    else:
        name_columns = []
    for column, fake_type in fake_types.items():
        if column in name_columns:
            continue
        df[column] = mask_column(df[column], fake_type, fake)
    return df


def test_create_example(tmp_path, monkeypatch, golden):
    monkeypatch.chdir(tmp_path)
    create_example()
    golden("example.csv", tmp_path / "example" / "example.csv")


@pytest.mark.parametrize(
    ("name", "fake_types"),
    [
        (
            "masked_names.csv",
            {
                "first_name": "first_name",
                "last_name": "last_name",
                "zipcode": "zipcode",
                "address": "full_address",
                "phone_number": "masking",
            },
        ),
        (
            "masked_single_name.csv",
            {
                "last_name": "last_name_kana",
                "address": "street",
                "phone_number": "phone_number",
            },
        ),
    ],
)
def test_masking(tmp_path, golden, name, fake_types):
    df = run_masks(read_table(EXAMPLE_CSV), fake_types, seed=42)
    output = tmp_path / name
    write_table(df, output)
    golden(name, output)
