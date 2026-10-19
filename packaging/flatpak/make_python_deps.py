"""Write python-deps.json, the Flatpak module with Arbor's Python dependencies.

Usage: python packaging/flatpak/make_python_deps.py

Rerun it after `uv lock` changes the runtime dependencies; tests/test_flatpak.py
fails while the checked-in file is stale. The module installs the exact wheels
uv.lock pins, with their hashes, so the Flatpak builds offline (as Flathub
requires) and matches the other platforms' bundles.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_FILE = ROOT / "uv.lock"
OUTPUT = Path(__file__).with_name("python-deps.json")

PROJECT = "arbor"
# The Python of the Flatpak runtime (org.freedesktop.Platform 25.08).
PYTHON_VERSION = (3, 13)
# Flatpak architecture names, which are also the wheels' platform tag suffixes.
ARCHES = ["x86_64", "aarch64"]
PURE_PLATFORM = "any"

SITE_PACKAGES = f"/lib/python{PYTHON_VERSION[0]}.{PYTHON_VERSION[1]}/site-packages"
# Parts of the Qt wheel Arbor never loads: no QTranslator is installed, and the
# app has no QML.
CLEANUP = [f"{SITE_PACKAGES}/PyQt6/Qt6/{part}" for part in ("translations", "qml")]


def runtime_packages(lock: dict) -> list[dict]:
    """The locked packages Arbor needs at run time, without dev dependencies."""
    packages = {package["name"]: package for package in lock["package"]}
    needed: dict[str, dict] = {}
    pending = [dep["name"] for dep in packages[PROJECT].get("dependencies", [])]
    while pending:
        name = pending.pop()
        if name in needed:
            continue
        needed[name] = packages[name]
        pending.extend(dep["name"] for dep in packages[name].get("dependencies", []))
    return [needed[name] for name in sorted(needed)]


def python_compatible(python_tag: str, abi_tag: str) -> bool:
    major, minor = PYTHON_VERSION
    for tag in python_tag.split("."):
        if tag in (f"py{major}", f"cp{major}{minor}"):
            return True
        if abi_tag == "abi3" and tag.startswith(f"cp{major}"):
            if int(tag.removeprefix(f"cp{major}")) <= minor:
                return True
    return False


def wheel_platform(filename: str) -> str | None:
    """The Flatpak arch a wheel is for, PURE_PLATFORM, or None if it doesn't fit."""
    _name, _version, python_tag, abi_tag, platforms = filename.removesuffix(".whl").split("-")
    if not python_compatible(python_tag, abi_tag):
        return None
    for platform in platforms.split("."):
        if platform == PURE_PLATFORM:
            return PURE_PLATFORM
        for arch in ARCHES:
            if platform.startswith("manylinux") and platform.endswith(f"_{arch}"):
                return arch
    return None


def wheel_sources(package: dict) -> list[dict]:
    by_platform: dict[str, dict] = {}
    for wheel in package.get("wheels", []):
        platform = wheel_platform(wheel["url"].rsplit("/", 1)[1])
        if platform is not None:
            by_platform.setdefault(platform, wheel)
    if PURE_PLATFORM in by_platform:
        wanted = {PURE_PLATFORM: by_platform[PURE_PLATFORM]}
    else:
        missing = [arch for arch in ARCHES if arch not in by_platform]
        if missing:
            raise SystemExit(f"{package['name']}: no wheel for {', '.join(missing)}")
        wanted = {arch: by_platform[arch] for arch in ARCHES}
    sources = []
    for platform, wheel in wanted.items():
        source = {
            "type": "file",
            "url": wheel["url"],
            "sha256": wheel["hash"].removeprefix("sha256:"),
        }
        if platform != PURE_PLATFORM:
            source["only-arches"] = [platform]
        sources.append(source)
    return sources


def module() -> dict:
    lock = tomllib.loads(LOCK_FILE.read_text(encoding="utf-8"))
    return {
        "name": "python-deps",
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --no-index --no-deps --prefix="${FLATPAK_DEST}" *.whl'
        ],
        "cleanup": CLEANUP,
        "sources": [
            source for package in runtime_packages(lock) for source in wheel_sources(package)
        ],
    }


def render() -> str:
    return json.dumps(module(), indent=2) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
