# PyInstaller spec for the Arbor app bundle.
#
# Build from the repository root:
#     uv run --with pyinstaller pyinstaller --noconfirm packaging/arbor.spec
#
# Arbor only uses QtCore, QtGui and QtWidgets, but PyInstaller's PyQt6 hooks
# still collect every Qt plugin of those modules along with the libraries the
# plugins link. The filters below drop the ones the app never loads.
import plistlib
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

# The app icon is rendered from the layer SVGs in packaging/icon at build time:
# an .icns on macOS (it needs iconutil) and an .ico on Windows.
ICNS_SCRIPT = Path(SPECPATH, "icon", "make_icns.py")
ICO_SCRIPT = Path(SPECPATH, "icon", "make_ico.py")

# The window icon PNGs (see arbor/icon.py), unused on macOS. The Linux build
# also installs them, with arbor.desktop, under share/ in the bundle, laid out
# so that copying share/ into ~/.local adds Arbor to the desktop's app list.
WINDOW_ICONS = Path(SPECPATH).parent / "src" / "arbor" / "icons"
WINDOW_ICONS_DEST = "arbor/icons"
DESKTOP_FILE = Path(SPECPATH, "linux", "arbor.desktop")

# The Icon Composer icon, which gives macOS 26+ the Liquid Glass icon and its
# dark, clear and tinted variants. Compiling it into Assets.car needs the actool
# of Xcode 26 or later; without it the app only gets the .icns above.
ICON_COMPOSER = Path(SPECPATH, "icon", "Arbor.icon")
ICON_NAME = ICON_COMPOSER.stem  # actool's --app-icon, and CFBundleIconName
ICON_COMPOSER_XCODE = 26
# Deployment target for actool, low enough that Assets.car also carries flat
# renditions for macOS versions before 26.
ICON_MIN_MACOS = "11.0"


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
    datas=[] if sys.platform == "darwin" else [(str(WINDOW_ICONS), WINDOW_ICONS_DEST)],
    excludes=["tkinter", *UNUSED_BINDINGS],
)
a.binaries = [stripped_libpython(entry) for entry in a.binaries if not is_unused(entry[0])]
a.datas = [entry for entry in a.datas if not is_unused(entry[0])]

pyz = PYZ(a.pure)


def make_icns():
    """Render the macOS app icon into the build directory and return its path."""
    if sys.platform != "darwin":
        return None
    icns = Path(workpath, "Arbor.icns")
    subprocess.run([sys.executable, ICNS_SCRIPT, icns], check=True)
    return str(icns)


def make_ico():
    """Render the Windows exe icon into the build directory and return its path."""
    if sys.platform != "win32":
        return None
    ico = Path(workpath, "Arbor.ico")
    subprocess.run([sys.executable, ICO_SCRIPT, ico], check=True)
    return str(ico)


def install_desktop_entry(bundle):
    """Add arbor.desktop and the hicolor icons to the Linux bundle's share/."""
    if not sys.platform.startswith("linux"):
        return
    share = Path(bundle, "share")
    shutil.rmtree(share, ignore_errors=True)
    applications = share / "applications"
    applications.mkdir(parents=True)
    shutil.copy(DESKTOP_FILE, applications)
    for png in WINDOW_ICONS.glob("arbor-*.png"):
        size = png.stem.removeprefix("arbor-")
        apps = share / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        apps.mkdir(parents=True)
        shutil.copy(png, apps / "arbor.png")


def actool_major_version():
    """Major version of Xcode's actool, or None if only the Command Line Tools are installed."""
    if subprocess.run(["xcrun", "--find", "actool"], capture_output=True).returncode != 0:
        return None
    result = subprocess.run(
        ["xcrun", "actool", "--version", "--output-format", "xml1"],
        capture_output=True,
        check=True,
    )
    version = plistlib.loads(result.stdout)["com.apple.actool.version"]["short-bundle-version"]
    return int(version.split(".")[0])


def compile_asset_catalog():
    """Compile Arbor.icon into an Assets.car in the build directory and return its path.

    Returns None off macOS, or when no Xcode with Icon Composer support is installed.
    """
    if sys.platform != "darwin":
        return None
    version = actool_major_version()
    if version is None or version < ICON_COMPOSER_XCODE:
        print(f"Xcode {ICON_COMPOSER_XCODE}+ actool not found; Arbor.app gets only the .icns icon")
        return None
    out = Path(workpath, "assets")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    subprocess.run(
        [
            "xcrun", "actool", ICON_COMPOSER,
            "--compile", out,
            "--app-icon", ICON_NAME,
            "--platform", "macosx",
            "--target-device", "mac",
            "--minimum-deployment-target", ICON_MIN_MACOS,
            "--output-partial-info-plist", out / "partial.plist",
            "--errors", "--warnings",
        ],
        check=True,
    )
    return out / "Assets.car"


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Arbor",
    strip=STRIP,
    console=False,
    icon=make_ico(),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=STRIP, name="Arbor")
install_desktop_entry(Path(DISTPATH, "Arbor"))

# With an Assets.car, macOS takes the icon named by CFBundleIconName from it;
# the .icns (CFBundleIconFile, which BUNDLE sets from `icon`) stays as the
# fallback for builds without one.
asset_catalog = compile_asset_catalog()
app = BUNDLE(
    coll,
    [("Assets.car", str(asset_catalog), "DATA")] if asset_catalog else [],
    name="Arbor.app",
    icon=make_icns(),
    info_plist={"CFBundleIconName": ICON_NAME} if asset_catalog else None,
    bundle_identifier=None,
)
