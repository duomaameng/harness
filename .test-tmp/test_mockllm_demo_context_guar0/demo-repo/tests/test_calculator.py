import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from calculator import add, divide


def test_add():
    assert add(2, 3) == 5


def test_divide():
    assert divide(6, 2) == 3
