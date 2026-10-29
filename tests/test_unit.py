import pandas as pd
import pytest
from faker import Faker
from rich.cells import cell_len

from chameleon_data.fakers import (
    FAKE_GENERATORS,
    FAKE_GROUPS,
    MASKING,
    NAME_TYPES,
    sample_fake_values,
)
from chameleon_data.masking import apply_masks, mask_column, mask_name_columns
from chameleon_data.prompts import (
    COLUMN_SAMPLE_WIDTH,
    PROMPTS,
    TYPE_LABELS,
    build_column_choices,
    build_type_choices,
    get_prompts,
    get_type_labels,
)
from chameleon_data.table_io import read_table, write_table


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


def test_table_rejects_unknown_suffix(tmp_path):
    with pytest.raises(ValueError, match=r"\.txt is not allowed"):
        read_table(tmp_path / "t.txt")
    with pytest.raises(ValueError, match=r"\.txt is not allowed"):
        write_table(pd.DataFrame(), tmp_path / "t.txt")


def test_apply_masks_reports_every_row_per_column():
    df = pd.DataFrame(
        {"first": ["太郎", "花子"], "last": ["山田", "鈴木"], "city": ["a", None]}
    )
    fake_types = {"first": "first_name", "last": "last_name", "city": "city"}
    advanced: list[str] = []
    masked = apply_masks(df, fake_types, Faker("ja_JP"), advanced.append)
    assert sorted(advanced) == ["city", "city", "first", "first", "last", "last"]
    assert df.loc[0, "first"] == "太郎"  # input is not mutated
    assert pd.isna(masked.loc[1, "city"])


def test_get_prompts_falls_back_to_english():
    assert get_prompts("ja_JP") is PROMPTS["ja"]
    assert get_prompts("zh_TW") is PROMPTS["zh"]
    assert get_prompts("fr_FR") is PROMPTS["en"]


def test_build_column_choices_shows_samples():
    df = pd.DataFrame(
        {
            "id": ["1", "1", None, "2", "3", "4"],
            "住所": ["東京都" * 20, None, None, None, None, None],
            "empty": [None] * 6,
        }
    )
    choices = build_column_choices(df)
    titles = [str(choice.title) for choice in choices]
    assert [choice.value for choice in choices] == ["id", "住所", "empty"]
    # NaN and duplicates are skipped, at most three values
    assert titles[0].endswith("1, 2, 3")
    assert titles[2].endswith("-")
    # long values are cut to the width, full-width names keep samples aligned
    assert titles[1].endswith("…")
    assert cell_len(titles[1]) <= cell_len("empty  ") + COLUMN_SAMPLE_WIDTH
    assert cell_len(titles[1].split("東")[0]) == cell_len("empty  ")


def test_type_labels_cover_every_type_and_group():
    names = {MASKING, *FAKE_GENERATORS, *FAKE_GROUPS}
    for labels in TYPE_LABELS.values():
        assert labels.keys() == names


def test_get_type_labels_falls_back_to_plain_names():
    assert get_type_labels("ja_JP") is TYPE_LABELS["ja"]
    assert get_type_labels("en_US") == {}


def test_build_type_choices_shows_labels():
    samples = {"person": {"full_name": "山田 太郎", "email": "a@example.com"}}
    series = pd.Series(["山田"])

    ja = build_type_choices(samples, series, TYPE_LABELS["ja"])
    titles = [str(choice.title) for choice in ja]
    assert titles[1] == "── 個人 ──"
    assert titles[2].startswith("氏名 (full_name)")
    assert ja[2].value == "full_name"  # values stay type names
    # samples start at the same cell in every row
    samples_shown = {0: "**", 2: "山田 太郎", 3: "a@example.com"}
    starts = {cell_len(titles[i]) - cell_len(s) for i, s in samples_shown.items()}
    assert len(starts) == 1

    en = build_type_choices(samples, series, {})
    assert str(en[1].title) == "── person ──"
    assert str(en[2].title).startswith("full_name ")


def test_name_types_are_person_generators():
    assert NAME_TYPES <= FAKE_GROUPS["person"].keys()


def test_sample_fake_values_drops_unsupported():
    ja = sample_fake_values(Faker("ja_JP"))
    en = sample_fake_values(Faker("en_US"))
    assert "full_name_kana" in ja["person"]
    assert "full_name_kana" not in en["person"]
