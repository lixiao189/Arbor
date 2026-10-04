# PyInstaller spec for the Arbor app bundle.
#
# Build from the repository root:
#     uv run --with pyinstaller pyinstaller --noconfirm packaging/arbor.spec
#
# Arbor only uses QtCore, QtGui and QtWidgets, but PyInstaller's PyQt6 hooks
# still collect every Qt plugin of those modules along with the libraries the
# plugins link. The filters below drop the ones the app never loads.
from pathlib import PurePath

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


a = Analysis(
    ["launcher.py"],
    excludes=["tkinter"],
)
a.binaries = [entry for entry in a.binaries if not is_unused(entry[0])]
a.datas = [entry for entry in a.datas if not is_unused(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Arbor",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Arbor")
app = BUNDLE(coll, name="Arbor.app", bundle_identifier=None)
