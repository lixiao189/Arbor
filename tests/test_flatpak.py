import importlib.util
from pathlib import Path

from arbor import icon

FLATPAK_DIR = Path(__file__).resolve().parents[1] / "packaging" / "flatpak"


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "make_python_deps", FLATPAK_DIR / "make_python_deps.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_deps_match_lock_file():
    generator = load_generator()
    assert generator.OUTPUT.read_text(encoding="utf-8") == generator.render(), (
        "python-deps.json is stale; run: uv run python packaging/flatpak/make_python_deps.py"
    )


def test_desktop_file_is_named_after_app_id():
    assert (FLATPAK_DIR / f"{icon.DESKTOP_FILE_NAME}.desktop").is_file()
    assert (FLATPAK_DIR / f"{icon.DESKTOP_FILE_NAME}.yml").is_file()
