# PyInstaller spec for the Arbor app bundle.
#
# Build from the repository root:
#     uv run --with pyinstaller pyinstaller --noconfirm packaging/arbor.spec
#
# Arbor only uses QtCore, QtGui and QtWidgets, but PyInstaller's PyQt6 hooks
# still collect every Qt plugin of those modules along with the libraries the
# plugins link. The filters below drop the ones the app never loads.
import shutil
import subprocess
import sys
from pathlib import Path, PurePath

# Qt plugins (by "<category>/<name>" without lib prefix or extension) and plugin
# categories that are not needed. The PDF image format alone drags in QtPdf and
# QtNetwork; the TUIO touch plugin also links QtNetwork.
UNUSED_PLUGIN_CATEGORIES = {"imageformats"}
KEPT_PLUGINS = {"imageformats/qsvg"}  # SVG icons from the platform icon theme
UNUSED_PLUGINS = {
    "generic/qtuiotouchplugin",
    "platforms/qminimal",
    "platforms/qoffscreen",
    "platforms/qvnc",  # Linux; links QtNetwork
}

# Qt libraries that only the dropped plugins depend on.
UNUSED_QT_LIBS = {"QtPdf", "QtNetwork"}

# PyQt6 binding modules the app never imports. The hooks collect the QtDBus
# binding because QtGui links the QtDBus library, which itself must stay.
UNUSED_BINDINGS = ["PyQt6.QtDBus"]

# Strip symbols from collected binaries (PyInstaller uses `strip -S` on macOS).
# GNU strip on Windows can corrupt MSVC-built DLLs, so skip it there.
STRIP = sys.platform != "win32"

# `strip -S` leaves the local symbols in libpython on macOS; dropping them too
# saves about 1.4 MB. PyInstaller has no option for it, so the spec strips a
# copy itself (PyInstaller re-signs it ad hoc afterwards).
LIBPYTHON_STRIP_ARGS = ["-x"] if sys.platform == "darwin" else None


def qt_lib_name(part):
    """'QtPdf.framework' / 'libQt6Pdf.so.6' / 'Qt6Pdf.dll' -> 'QtPdf'."""
    stem = part.split(".")[0].removeprefix("lib")
    return stem.replace("Qt6", "Qt", 1)


def is_unused(dest):
    parts = PurePath(dest).parts
    if "Qt6" in parts:
        rest = parts[parts.index("Qt6") + 1:]
        if rest and rest[0] == "translations":
            return True  # no QTranslator is installed
        if rest and rest[0] == "plugins" and len(rest) >= 3:
            plugin = f"{rest[1]}/{rest[2].split('.')[0].removeprefix('lib')}"
            if plugin in KEPT_PLUGINS:
                return False
            if rest[1] in UNUSED_PLUGIN_CATEGORIES or plugin in UNUSED_PLUGINS:
                return True
    return any(qt_lib_name(part) in UNUSED_QT_LIBS for part in parts)


def stripped_libpython(entry):
    """Replace a libpython binary entry with a copy stripped by LIBPYTHON_STRIP_ARGS."""
    dest, src, typecode = entry
    if LIBPYTHON_STRIP_ARGS is None or not PurePath(dest).name.startswith("libpython"):
        return entry
    copy = Path(workpath, "stripped", PurePath(dest).name)
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, copy)
    subprocess.run(["strip", *LIBPYTHON_STRIP_ARGS, copy], check=True)
    return dest, str(copy), typecode


a = Analysis(
    ["launcher.py"],
    excludes=["tkinter", *UNUSED_BINDINGS],
)
a.binaries = [stripped_libpython(entry) for entry in a.binaries if not is_unused(entry[0])]
a.datas = [entry for entry in a.datas if not is_unused(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Arbor",
    strip=STRIP,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=STRIP, name="Arbor")
app = BUNDLE(coll, name="Arbor.app", bundle_identifier=None)
