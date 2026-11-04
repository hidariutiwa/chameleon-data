import shutil
from pathlib import Path

import pandas as pd
import pytest

from chameleon_data import cli
from chameleon_data.table_io import read_table

GOLDEN_DIR = Path(__file__).parent / "golden"

FAKE_TYPES = {
    "first_name": "first_name",
    "last_name": "last_name",
    "zipcode": "zipcode",
    "address": "full_address",
    "phone_number": "masking",
}


@pytest.fixture
def example_input(tmp_path, monkeypatch):
    # prompts are replaced; everything else (reading, seeding, progress, writing) runs as is
    input_path = tmp_path / "example.csv"
    shutil.copy(GOLDEN_DIR / "example.csv", input_path)
    monkeypatch.setattr(cli, "ask_columns", lambda df, prompts: list(FAKE_TYPES))
    monkeypatch.setattr(
        cli, "ask_fake_types", lambda columns, df, samples, prompts, labels: FAKE_TYPES
    )
    return input_path


def test_mask_end_to_end(tmp_path, example_input, golden, capsys):
    cli.main(["mask", "-f", str(example_input), "-s", "42"])

    golden("masked_names.csv", tmp_path / "example_masked.csv")
    assert "deprecated" not in capsys.readouterr().out


def test_legacy_mask_form_still_works(tmp_path, example_input, golden, capsys):
    # v0.4 form without the subcommand; remove with normalize_argv() in v0.6.0
    cli.main(["-f", str(example_input), "-s", "42"])

    golden("masked_names.csv", tmp_path / "example_masked.csv")
    assert "deprecated" in capsys.readouterr().out


def test_mask_rejects_unknown_suffix():
    with pytest.raises(SystemExit) as exc:
        cli.main(["mask", "-f", "data.txt"])
    assert exc.value.code == 1


def test_example_command(tmp_path, monkeypatch, golden):
    monkeypatch.chdir(tmp_path)
    cli.main(["example"])
    golden("example.csv", tmp_path / "example" / "example.csv")


def test_legacy_example_entry_point(tmp_path, monkeypatch, golden, capsys):
    monkeypatch.chdir(tmp_path)
    cli.legacy_example()
    golden("example.csv", tmp_path / "example" / "example.csv")
    assert "deprecated" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("argv", "expected", "legacy"),
    [
        (["mask", "-f", "a.csv"], ["mask", "-f", "a.csv"], False),
        (["example"], ["example"], False),
        (["-f", "a.csv"], ["mask", "-f", "a.csv"], True),
        (["-l", "en_US", "-f", "a.csv"], ["mask", "-l", "en_US", "-f", "a.csv"], True),
        (["-h"], ["-h"], False),
        (["--version"], ["--version"], False),
        ([], [], False),
    ],
)
def test_normalize_argv(argv, expected, legacy):
    assert cli.normalize_argv(argv) == (expected, legacy)


def test_subcommand_is_required():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


def test_mask_requires_filepath():
    with pytest.raises(SystemExit) as exc:
        cli.main(["mask"])
    assert exc.value.code == 2


def test_mask_does_not_fall_through_to_other_commands(example_input, capsys):
    cli.main(["mask", "-f", str(example_input)])
    assert "command not found" not in capsys.readouterr().out


# same types as GENERATE_TYPES in test_golden.py, so the output matches generated.csv
GENERATE_TYPES = {
    "no": "number",
    "first_name": "first_name",
    "last_name": "last_name",
    "zipcode": "zipcode",
    "address": "full_address",
    "phone_number": "phone_number",
}


@pytest.fixture
def generate_prompts(monkeypatch):
    # records what the prompts were asked, and answers with GENERATE_TYPES
    asked: dict[str, object] = {}

    def fake_ask_fake_types(columns, df, samples, prompts, labels):
        asked["columns"] = columns
        asked["df"] = df
        return {column: GENERATE_TYPES[column] for column in columns}

    def fake_ask_new_columns(samples, prompts, labels):
        asked["new_columns"] = True
        return GENERATE_TYPES

    monkeypatch.setattr(cli, "ask_fake_types", fake_ask_fake_types)
    monkeypatch.setattr(cli, "ask_new_columns", fake_ask_new_columns)
    return asked


def test_generate_from_template_end_to_end(tmp_path, generate_prompts, golden):
    template = tmp_path / "example.csv"
    shutil.copy(GOLDEN_DIR / "example.csv", template)

    cli.main(["generate", "-f", str(template), "-n", "10", "-s", "42"])

    # every header column is asked, with no original values (no masking choice)
    assert generate_prompts["columns"] == list(GENERATE_TYPES)
    assert generate_prompts["df"] is None
    golden("generated.csv", tmp_path / "example_fake.csv")


def test_generate_without_template_end_to_end(tmp_path, monkeypatch, generate_prompts):
    monkeypatch.chdir(tmp_path)

    cli.main(["generate", "-s", "42"])

    assert generate_prompts["new_columns"]
    df = pd.read_csv(tmp_path / "fake_data.csv", dtype=str)
    assert list(df.columns) == list(GENERATE_TYPES)
    assert len(df) == cli.DEFAULT_GENERATE_ROWS


@pytest.mark.parametrize("fmt", ["tsv", "xlsx", "json"])
def test_generate_format(tmp_path, monkeypatch, generate_prompts, fmt):
    monkeypatch.chdir(tmp_path)

    cli.main(["generate", "-n", "3", "--format", fmt])

    path = tmp_path / f"fake_data.{fmt}"
    df = pd.read_json(path, dtype=False) if fmt == "json" else read_table(path)
    assert list(df.columns) == list(GENERATE_TYPES)
    assert len(df) == 3


def test_generate_output_suffix_decides_format(tmp_path, generate_prompts):
    output = tmp_path / "out.json"
    cli.main(["generate", "-n", "2", "-o", str(output)])
    assert len(pd.read_json(output, dtype=False)) == 2


def test_generate_rejects_format_mismatch(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["generate", "-o", str(tmp_path / "out.csv"), "--format", "json"])
    assert exc.value.code == 1


def test_generate_rejects_missing_template(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["generate", "-f", str(tmp_path / "missing.csv")])
    assert exc.value.code == 1


@pytest.mark.parametrize("rows", ["0", "-1", "abc"])
def test_generate_rejects_invalid_rows(rows):
    with pytest.raises(SystemExit) as exc:
        cli.main(["generate", "-n", rows])
    assert exc.value.code == 2
