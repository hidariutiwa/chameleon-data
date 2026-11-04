import shutil
from pathlib import Path

import pytest

from chameleon_data import cli

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
