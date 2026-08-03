# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect customtkinter themes/assets
ctk_datas = collect_data_files('customtkinter')

_lo_vendor = os.path.join('vendor', 'libreoffice')
_lo_datas = []
if os.path.isdir(_lo_vendor):
    for root, _dirs, files in os.walk(_lo_vendor):
        for fname in files:
            src = os.path.join(root, fname)
            rel = os.path.relpath(src, '.')
            _lo_datas.append((src, os.path.dirname(rel)))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('customtkinter'),
    datas=[
        ('clase-001-firebase-adminsdk-fbsvc-ee190f0bcc.json', '.'),
        ('config.py', '.'),
    ] + ctk_datas + _lo_datas,
    hiddenimports=[
        'customtkinter',
        'PIL._tkinter_finder',
        'firebase_admin',
        'firebase_admin.credentials',
        'firebase_admin.auth',
        'firebase_admin.firestore',
        'google.auth',
        'google.auth.transport.requests',
        'google.oauth2.service_account',
        'google.cloud.firestore',
        'google.cloud.firestore_v1',
        'grpc',
        'openpyxl',
        'openpyxl.cell._writer',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.pool',
        'docx',
        'docx.oxml.ns',
        'tkinter',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.ttk',
        'ui',
        'ui.app',
        'ui.theme',
        'ui.components',
        'ui.pages',
        'ui.pages.dashboard',
        'ui.pages.campaign',
        'ui.pages.team',
        'ui.pages.monitor',
        'ui.pages.stats',
        'ui.pages.database',
        'ui.pages.tracking',
        'ui.pages.alerts',
        'ui.pages.returns',
        'ui.pages.documents',
        'ui.pages.export',
        'ui.pages.sync',
        'ui.pages.notifications',
        'ui.pages.settings',
        'ui.pages.call_center',
        'ui.pages.reparto',
        'services',
        'services.call_center_service',
        'services.reparto_planner',
        'services.firebase_service',
        'services.auth_service',
        'services.update_service',
        'services.campaign_manager',
        'services.database',
        'services.diff_engine',
        'services.excel_parser',
        'services.tramo_engine',
        'services.word_generator',
        'services.word_template_engine',
        'services.letter_exporter',
        'fitz',
        'docx2pdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter',
              'notebook', 'sphinx', 'pytest', 'setuptools'],
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
    name='AntCobranzas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
