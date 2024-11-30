# Troubleshooting

## Linux
You might have to install (some of) the dependencies for connecting to the X11 server:
- https://doc.qt.io/qt-6/linux-requirements.html
- https://doc.qt.io/qt-6/linux.html

## Windows
`OpenHRV` has been tested on Windows 10, but there seem to be Bluetooth problems on Windows 11.
Have a look at the issues (open and closed) labeled with `Windows`.

## MacOS
:warning: Those instructions aren't verified for releases > [0.2.0](https://github.com/JanCBrammer/OpenHRV/releases/tag/v0.2.0) :warning:

Clone the repository and run `pyinstaller mac_os_app.spec --clean --noconfirm` from the project root
in a Python environment that contains the dependencies specified in 
[pyproject.toml](https://github.com/JanCBrammer/OpenHRV/blob/main/pyproject.toml) (including `build` dependencies).
The `mac_os_app.spec` file should look as follows:

```
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["openhrv/app.py"],
    pathex=["./openhrv"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="app",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="app",
)
app = BUNDLE(
    coll,
    name="openhrv.app",
    icon="docs/logo.icns",
    bundle_identifier=None,
    info_plist={
        "NSBluetoothAlwaysUsageDescription": "This application uses a bluetooth sensor"
    },
)
```

A macOS app bundle will be created at `OpenHRV/dist/openhrv.app`.
This can be loaded directly by clicking on it, or if you wish to see terminal debug messages,
you can execute from the project root `./dist/openhrv.app/Contents/MacOS/app`.
The first run takes extra time.

Also look at the issues (open and closed) labeled with `macOS`.
