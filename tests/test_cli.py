import shutil
import sys
from pathlib import Path

import pytest

from chameleon_data import cli

GOLDEN_DIR = Path(__file__).parent / "golden"


def test_main_end_to_end(tmp_path, monkeypatch, golden):
    # prompts are replaced; everything else (reading, seeding, progress, writing) runs as is
    fake_types = {
        "first_name": "first_name",
        "last_name": "last_name",
        "zipcode": "zipcode",
        "address": "full_address",
        "phone_number": "masking",
    }
    input_path = tmp_path / "example.csv"
    shutil.copy(GOLDEN_DIR / "example.csv", input_path)
    monkeypatch.setattr(sys, "argv", ["chameleon", "-f", str(input_path), "-s", "42"])
    monkeypatch.setattr(cli, "ask_columns", lambda headers, prompts: list(fake_types))
    monkeypatch.setattr(
        cli, "ask_fake_types", lambda columns, df, samples, prompts: fake_types
    )

    cli.main()

    golden("masked_names.csv", tmp_path / "example_masked.csv")


def test_main_rejects_unknown_suffix(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["chameleon", "-f", "data.txt"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
