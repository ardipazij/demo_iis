# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec файл для сборки в ОДИН exe файл с встроенным Graphviz.
Graphviz будет распаковываться при первом запуске.
"""

import os
import glob
import shutil

block_cipher = None

# Собираем все файлы Graphviz для встраивания
graphviz_bin_path = 'Graphviz-14.1.1-win32/bin'
graphviz_files = []

if os.path.exists(graphviz_bin_path):
    # Добавляем все exe и dll файлы
    for ext in ['*.exe', '*.dll']:
        for file in glob.glob(os.path.join(graphviz_bin_path, ext)):
            # Сохраняем относительный путь для распаковки
            rel_path = os.path.relpath(file, graphviz_bin_path)
            graphviz_files.append((file, f'graphviz_bin/{rel_path}'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=graphviz_files,
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'networkx',
        'pydot',
        'petri_model',
        'petri_format',
        'petri_logging',
        'petri_widget',
        'petri_app',
        'petri_save',
        'graphviz_extractor',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PetriNetApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консоли (GUI приложение)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

