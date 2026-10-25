from pathlib import Path

import pandas as pd
import pytest
from faker import Faker

from chameleon_data.example import create_example
from chameleon_data.fakers import sample_fake_values
from chameleon_data.masking import apply_masks
from chameleon_data.table_io import read_table, write_table

EXAMPLE_CSV = Path(__file__).parent / "golden" / "example.csv"


def run_masks(df: pd.DataFrame, fake_types: dict[str, str], seed: int) -> pd.DataFrame:
    # same order as main(): samples before seeding
    fake = Faker("ja_JP")
    sample_fake_values(fake)
    Faker.seed(seed)
    return apply_masks(df, fake_types, fake)


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
