# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for building the HR DigiTool macOS Application Bundle.

This specification file handles:
- Bundling required static assets (icons and QSS stylesheets).
- Excluding unused heavy dependencies (PyQt6 modules, data science libraries) to reduce build size.
- Enabling 'argv_emulation' for native macOS OS-level file passing.
- Registering PDF document handling in the macOS Info.plist for "Open With..." support.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # 1. Bundled resources: App logo and asset directory
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
    strip=True,               # Strips debug symbols from dynamic binaries
    upx=True,                 # Compress binaries if UPX is installed
    console=False,            # Suppress terminal/console window
    disable_windowed_traceback=False,
    argv_emulation=True,      # CRITICAL: Enables macOS file open events to be passed to sys.argv
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['LOGO.icns'],       # Application icon
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

# macOS Application Bundle Configuration
app = BUNDLE(
    coll,
    name='HRDigiTool.app',
    icon='LOGO.icns',
    bundle_identifier='com.hrdigitool.app',
    info_plist={
        # Registers PDF document types to support default application assignment ("Open With...")
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'PDF Document',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['com.adobe.pdf'],
                'CFBundleTypeExtensions': ['pdf']
            }
        ]
    }
)
