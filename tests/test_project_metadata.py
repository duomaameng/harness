"""Project metadata consistency tests."""

import pathlib
import tomllib


def test_pyproject_readme_reference_exists():
    pyproject = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
    readme = pyproject["project"].get("readme")

    if readme:
        assert pathlib.Path(readme).exists()
