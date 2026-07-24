# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for building the HR DigiTool Windows Executable.

This specification file handles:
- Bundling required static assets (icons and QSS stylesheets) using Windows path separators (;).
- Excluding unused heavy dependencies (PyQt6 modules, data science libraries) to reduce build size.
- Packaging as a windowed application without a command prompt window.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # 1. Bundled resources: App logo and asset directory (Windows uses ';' separator)
    datas=[
        ('LOGO.png', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 2. Excluded unused heavy modules to optimize binary footprint
    excludes=[
        'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtSql', 'PyQt6.QtTest',
        'PyQt6.QtNetwork', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtBluetooth',
        'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
        'PyQt6.QtXml', 'PyQt6.QtSvg', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
        'PyQt6.QtTextToSpeech', 'PyQt6.QtWebSockets', 'PyQt6.QtDBus',
        'PyQt6.QtPrintSupport', 'PyQt6.QtVirtualKeyboard', 'PyQt6.Qt3DCore',
        'tkinter', 'unittest', 'email', 'pydoc', 'doctest', 'pdb', 'xmlrpc',
        'sqlite3', 'numpy', 'pandas', 'matplotlib', 'IPython', 'scipy'
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HRDigiTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,              # Disabled on Windows (strip is primarily for ELF/Mach-O binaries)
    upx=True,                 # Compresses binaries using UPX if installed
    console=False,            # Suppress command prompt window
    disable_windowed_traceback=False,
    argv_emulation=False,     # macOS specific option (must be False on Windows)
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['LOGO.ico'],        # Windows icon (.ico format required)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HRDigiTool',
)