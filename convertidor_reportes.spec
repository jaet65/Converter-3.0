# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

# Módulos que la app no usa pero PyInstaller suele arrastrar por dependencias transitivas.
_unused_modules = [
    # Herramientas de desarrollo / empaquetado
    'pip', 'setuptools', 'wheel', 'pkg_resources', '_pytest', 'pytest',
    'PyInstaller', 'distutils',

    # Notebooks e IPython
    'IPython', 'ipykernel', 'jupyter', 'jupyter_client', 'jupyter_core',
    'notebook', 'nbconvert', 'nbformat', 'qtconsole', 'ipywidgets',

    # Visualización y ciencia de datos no usadas
    'matplotlib', 'matplotlib.backends', 'matplotlib.pyplot', 'matplotlib.figure',
    'scipy', 'sympy', 'numba', 'bottleneck', 'sklearn', 'skimage', 'cv2',
    'plotly', 'bokeh', 'seaborn', 'altair',

    # Frameworks web, HTTP alternativos y cloud
    'requests', 'urllib3', 'httpx', 'aiohttp', 'flask', 'django', 'fastapi',
    'starlette', 'uvicorn', 'gunicorn', 'werkzeug',
    'boto3', 'botocore', 's3transfer', 'google', 'grpc',

    # ORM y bases de datos no usadas (solo psycopg2)
    'sqlalchemy', 'pymongo', 'pymysql', 'mysql', 'mysqlconnector',
    'sqlite3', 'cx_Oracle', 'oracledb', 'redis', 'cassandra',

    # Backends de pandas no usados
    'pyarrow', 'fastparquet', 'tables', 'h5py', 'feather',
    'pandas.tests', 'pandas.plotting._matplotlib',

    # Lectores/escritores Excel alternativos (solo openpyxl)
    'xlrd', 'xlsxwriter', 'xlwt', 'odf', 'pyxlsb',

    # GUIs alternativas
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PySide', 'wx', 'kivy', 'gtk',

    # Async (la app es síncrona)
    'asyncio', 'aiofiles', 'anyio', 'trio', 'tornado', 'zmq',

    # Numpy innecesario en runtime
    'numpy.distutils', 'numpy.f2py', 'numpy.testing',

    # Stdlib poco usada en esta app de escritorio
    'tkinter.test', 'turtle', 'idlelib', 'curses', 'readline',
    'lib2to3', 'pydoc', 'pydoc_data', 'doctest', 'unittest',
    'multiprocessing.dummy',
    'xmlrpc', 'xmlrpc.client', 'xmlrpc.server',
    'ftplib', 'poplib', 'imaplib', 'smtplib', 'nntplib', 'telnetlib',
    'sndhdr', 'sunau', 'wave', 'aifc', 'audioop', 'chunk',
    'crypt', 'nis', 'spwd', 'mailcap', 'mailbox',
    'ensurepip', 'venv', 'compileall', 'tabnanny', 'trace',

    # PIL: solo se usan PNG/ICO en logos; excluir plugins de formatos exóticos
    'PIL.ImageQt', 'PIL.ImageShow',
    'PIL.BlpImagePlugin', 'PIL.BufrImagePlugin', 'PIL.DdsImagePlugin',
    'PIL.EpsImagePlugin', 'PIL.FitsImagePlugin', 'PIL.FliImagePlugin',
    'PIL.FpxImagePlugin', 'PIL.FtexImagePlugin', 'PIL.GbrImagePlugin',
    'PIL.GribImagePlugin', 'PIL.Hdf5StubImagePlugin', 'PIL.IcnsImagePlugin',
    'PIL.ImImagePlugin', 'PIL.ImtImagePlugin', 'PIL.IptcImagePlugin',
    'PIL.McIdasImagePlugin', 'PIL.MicImagePlugin', 'PIL.MpegImagePlugin',
    'PIL.MpoImagePlugin', 'PIL.MspImagePlugin', 'PIL.PalmImagePlugin',
    'PIL.PcdImagePlugin', 'PIL.PixarImagePlugin', 'PIL.PsdImagePlugin',
    'PIL.QoiImagePlugin', 'PIL.SgiImagePlugin', 'PIL.SpiderImagePlugin',
    'PIL.SunImagePlugin', 'PIL.TgaImagePlugin', 'PIL.WebPImagePlugin',
    'PIL.WmfImagePlugin', 'PIL.XVThumbImagePlugin', 'PIL.XbmImagePlugin',
    'PIL.XpmImagePlugin',
]

# Importaciones dinámicas (lazy imports / Cython) que el analizador estático no detecta.
_pandas_internals = collect_submodules('pandas._config')
_lazy_imports = [
    'reportlab',
    'reportlab.lib.pagesizes',
    'reportlab.platypus',
    'reportlab.lib.styles',
    'reportlab.lib.colors',
    'PIL.Image',
    'PIL.ImageTk',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    *_pandas_internals,
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('logo.png', '.'),
        ('logo_TrackSIM.png', '.'),
        ('Icon.ico', '.'),
        ('config.json', '.'),  # Vuelve a incluirse para llevar la versión base
        ('config.ini', '.'),
    ],
    hiddenimports=_lazy_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_unused_modules,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Activa la compilación por carpetas (onedir)
    name='TrackSIM_Tools',
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
    icon=['Icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # UPX en extensiones nativas grandes suele fallar o disparar falsos positivos AV
        'python*.dll',
        'vcruntime*.dll',
        'MSVCP*.dll',
        'libcrypto*.dll',
        'libssl*.dll',
        'numpy*.pyd',
        'pandas*.pyd',
        'psycopg2*.pyd',
        '_psycopg*.pyd',
    ],
    name='TrackSIM_Tools',  # Nombre del directorio en 'dist/'
)
