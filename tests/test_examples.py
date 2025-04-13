import runpy
from pathlib import Path

import pytest


def example_files() -> list[Path]:
    current_dir = Path(__file__).parent
    examples_dir = current_dir / ".." / "examples"
    return list(examples_dir.rglob("*.py"))


@pytest.mark.parametrize("example_script", example_files())
def test_example_scripts_run_without_raise(example_script):
    runpy.run_path(example_script.as_posix())
