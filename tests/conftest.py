import os
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.fixture
def golden():
    # CHAMELEON_UPDATE_GOLDEN=1 rewrites the golden file instead of comparing
    def check(name: str, actual: Path) -> None:
        expected = GOLDEN_DIR / name
        text = actual.read_text(encoding="utf-8")
        if os.environ.get("CHAMELEON_UPDATE_GOLDEN") == "1":
            GOLDEN_DIR.mkdir(exist_ok=True)
            expected.write_text(text, encoding="utf-8", newline="\n")
            return
        assert expected.exists(), f"{expected} is missing; run with CHAMELEON_UPDATE_GOLDEN=1"
        assert text.splitlines() == expected.read_text(encoding="utf-8").splitlines()

    return check
