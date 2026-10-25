import pandas as pd
import pytest
from faker import Faker

from chameleon_data.main import (
    FAKE_GROUPS,
    NAME_TYPES,
    PROMPTS,
    get_prompts,
    mask_column,
    mask_name_columns,
    read_table,
    sample_fake_values,
    write_table,
)


def test_mask_column_keeps_relations_and_nan():
    series = pd.Series(["a", "b", "a", None], dtype=object)
    masked = mask_column(series, "city", Faker("ja_JP"))
    assert masked[0] == masked[2]
    assert masked[0] != "a"
    assert pd.isna(masked[3])


def test_mask_column_masking_keeps_length():
    masked = mask_column(pd.Series(["abc", "de"]), "masking", Faker("ja_JP"))
    assert list(masked) == ["***", "**"]


def test_mask_name_columns_describes_one_person():
    df = pd.DataFrame(
        {
            "full": ["山田 太郎", "鈴木 花子", "山田 太郎"],
            "first": ["太郎", "花子", "太郎"],
            "last": ["山田", "鈴木", "山田"],
            "first_kana": ["タロウ", "ハナコ", "タロウ"],
            "last_kana": ["ヤマダ", "スズキ", "ヤマダ"],
        }
    )
    fake_types = {
        "full": "full_name",
        "first": "first_name",
        "last": "last_name",
        "first_kana": "first_name_kana",
        "last_kana": "last_name_kana",
    }
    masked = mask_name_columns(df, fake_types, Faker("ja_JP"))
    for _, row in masked.iterrows():
        assert row["full"] == f"{row['last']} {row['first']}"
    assert masked.iloc[0].equals(masked.iloc[2])


@pytest.mark.parametrize("suffix", [".csv", ".tsv", ".xlsx"])
def test_table_round_trip_keeps_leading_zeros(tmp_path, suffix):
    df = pd.DataFrame({"zipcode": ["001-0001", "0123"], "phone": ["090", None]})
    path = tmp_path / f"t{suffix}"
    write_table(df, path)
    assert read_table(path).equals(df)


def test_get_prompts_falls_back_to_english():
    assert get_prompts("ja_JP") is PROMPTS["ja"]
    assert get_prompts("zh_TW") is PROMPTS["zh"]
    assert get_prompts("fr_FR") is PROMPTS["en"]


def test_name_types_are_person_generators():
    assert NAME_TYPES <= FAKE_GROUPS["person"].keys()


def test_sample_fake_values_drops_unsupported():
    ja = sample_fake_values(Faker("ja_JP"))
    en = sample_fake_values(Faker("en_US"))
    assert "full_name_kana" in ja["person"]
    assert "full_name_kana" not in en["person"]
