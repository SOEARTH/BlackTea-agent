import json
import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def fixture_loader():
    """加载 fixtures/{api_name}/{file}.json。"""
    def _load(api: str, name: str) -> dict:
        p = FIXTURES_DIR / api / f"{name}.json"
        return json.loads(p.read_text(encoding="utf-8"))
    return _load
