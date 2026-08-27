import re
import tomllib
from pathlib import Path

from airidl import __version__


def test_python_version_contract() -> None:
    assert __version__ == "0.1.0.dev1"


def test_version_is_consistent_across_build_boundaries() -> None:
    root = Path(__file__).parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    policy = tomllib.loads((root / "env/versions.toml").read_text())
    cpp = (root / "cpp/runtime/version.cpp").read_text()
    cmake = (root / "CMakeLists.txt").read_text()
    assert pyproject["project"]["version"] == policy["project"]["version"] == __version__
    assert f'"{__version__}"' in cpp
    assert re.search(r"project\(AiriDL VERSION 0\.1\.0 ", cmake)
