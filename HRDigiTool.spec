# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('LOGO.png', '.'), ('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtNetwork', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtBluetooth', 'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtXml', 'PyQt6.QtSvg', 'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtTextToSpeech', 'PyQt6.QtWebSockets', 'PyQt6.QtDBus', 'PyQt6.QtPrintSupport', 'PyQt6.QtVirtualKeyboard', 'PyQt6.Qt3DCore', 'tkinter', 'unittest', 'email', 'pydoc', 'doctest', 'pdb', 'xmlrpc', 'sqlite3', 'numpy', 'pandas', 'matplotlib', 'IPython', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HRDigiTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['LOGO.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='HRDigiTool',
)
app = BUNDLE(
    coll,
    name='HRDigiTool.app',
    icon='LOGO.icns',
    bundle_identifier=None,
)
