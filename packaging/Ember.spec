# Build on the target Mac architecture with requirements-desktop.lock installed.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
datas = [(str(root / "ember" / directory), "ember/" + directory)
         for directory in ("static", "data", "migrations")]
datas += collect_data_files("webview")
analysis = Analysis([str(root / "packaging" / "desktop_entry.py")],
    pathex=[str(root)], datas=datas,
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("webview.platforms.cocoa"),
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "tkinter", "webview.platforms.gtk", "webview.platforms.qt"])
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="Ember", console=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name="Ember")
app = BUNDLE(collection, name="Ember.app", icon=str(root / "build" / "Ember.icns"),
    bundle_identifier="me.lemien.ember", info_plist={
        "CFBundleShortVersionString": "2.2.0", "CFBundleVersion": "220",
        "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "10.15",
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "NSHumanReadableCopyright": "Ember personal collection tool. Pokémon artwork belongs to its respective rights holders."})
