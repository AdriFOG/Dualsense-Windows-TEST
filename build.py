"""
Script de Empaquetado - PyInstaller
Convierte la aplicacion Python en un ejecutable .exe para Windows.

Uso:
    python build.py           # Build estandar
    python build.py --onefile # Build como un solo archivo
    python build.py --clean   # Limpiar builds anteriores
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Build DualSense Controller .exe')
    parser.add_argument('--onefile', action='store_true', help='Crear un solo archivo .exe')
    parser.add_argument('--clean', action='store_true', help='Limpiar builds anteriores')
    parser.add_argument('--console', action='store_true', help='Mantener consola visible')
    return parser.parse_args()


def clean_build():
    """Elimina archivos de builds anteriores."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']

    print("Limpiando builds anteriores...")

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Eliminado: {dir_name}/")

    for pattern in files_to_clean:
        for f in Path('.').glob(pattern):
            f.unlink()
            print(f"  Eliminado: {f}")

    print("Limpieza completada.\n")


def check_dependencies():
    """Verifica que todas las dependencias esten instaladas."""
    print("Verificando dependencias...")

    required = {
        'pydualsense': 'pydualsense',
        'customtkinter': 'customtkinter',
        'PIL': 'pillow',
        'pystray': 'pystray',
        'pywin32': 'pywin32',
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ✗ {package} (NO INSTALADO)")

    if missing:
        print(f"\nFaltan dependencias. Instalar con:")
        print(f"  pip install {' '.join(missing)}")
        return False

    # Verificar PyInstaller
    try:
        import PyInstaller
        print(f"  ✓ pyinstaller")
    except ImportError:
        print(f"  ✗ pyinstaller (NO INSTALADO)")
        print(f"\nInstalar PyInstaller:")
        print(f"  pip install pyinstaller")
        return False

    print("Todas las dependencias estan instaladas.\n")
    return True


def create_icon():
    """Crea el icono de la aplicacion si no existe."""
    icon_path = Path('assets') / 'icon.ico'

    if icon_path.exists():
        return str(icon_path)

    print("Creando icono de la aplicacion...")

    try:
        from PIL import Image, ImageDraw

        # Crear icono en multiples tamaños
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        images = []

        for size in sizes:
            img = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Escalar proporcionalmente
            margin = max(1, size[0] // 8)
            body_top = size[1] // 4

            # Cuerpo del control
            draw.rounded_rectangle(
                [margin, body_top, size[0] - margin, size[1] - margin],
                radius=max(2, size[0] // 8),
                fill=(0, 150, 255, 255)
            )

            # Botones
            btn_radius = max(1, size[0] // 12)
            btn_y = body_top + (size[1] - body_top) // 3

            draw.ellipse(
                [margin + size[0]//6, btn_y - btn_radius,
                 margin + size[0]//6 + btn_radius*2, btn_y + btn_radius],
                fill=(255, 255, 255, 255)
            )
            draw.ellipse(
                [size[0] - margin - size[0]//6 - btn_radius*2, btn_y - btn_radius,
                 size[0] - margin - size[0]//6, btn_y + btn_radius],
                fill=(255, 255, 255, 255)
            )

            images.append(img)

        # Guardar como .ico
        icon_path.parent.mkdir(exist_ok=True)
        images[0].save(icon_path, format='ICO', sizes=sizes)
        print(f"  Icono creado: {icon_path}\n")
        return str(icon_path)

    except Exception as e:
        print(f"  Advertencia: No se pudo crear icono: {e}\n")
        return None


def build_executable(onefile=False, console=False):
    """Ejecuta PyInstaller para crear el .exe."""
    print(f"Iniciando build ({'onefile' if onefile else 'onedir'})...")

    icon_path = create_icon()

    # Construir comando de PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', 'DualSenseController',
        '--noconfirm',
    ]

    if onefile:
        cmd.append('--onefile')
    else:
        cmd.append('--onedir')

    if not console:
        cmd.append('--noconsole')
    else:
        cmd.append('--console')

    if icon_path:
        cmd.extend(['--icon', icon_path])

    # Incluir datos
    cmd.extend([
        '--add-data', f'assets{os.pathsep}assets',
        '--add-data', f'src{os.pathsep}src',
        '--add-data', f'gui{os.pathsep}gui',
        '--add-data', f'config{os.pathsep}config',
    ])

    # Hidden imports
    hidden_imports = [
        'pydualsense',
        'customtkinter',
        'PIL',
        'pystray',
        'win32api',
        'win32gui',
        'win32con',
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

    # Archivo principal
    cmd.append('main.py')

    print(f"Comando: {' '.join(cmd)}\n")

    # Ejecutar
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("BUILD EXITOSO")
        print("=" * 50)

        output_dir = Path('dist') / 'DualSenseController'
        exe_path = output_dir / 'DualSenseController.exe'

        if onefile:
            exe_path = Path('dist') / 'DualSenseController.exe'

        print(f"Ejecutable: {exe_path.absolute()}")
        print(f"\nPara distribuir:")
        if not onefile:
            print(f"  Comprime la carpeta: {output_dir}")
        print(f"  El .exe se puede ejecutar sin Python instalado")
        print("=" * 50)
        return True
    else:
        print("\nBUILD FALLIDO")
        return False


def create_installer_batch():
    """Crea un script batch para instalar dependencias."""
    batch_content = '''@echo off
echo ==========================================
echo  DualSense Controller - Instalador
echo ==========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH
    echo Descarga Python desde: https://python.org
    pause
    exit /b 1
)

echo [1/3] Python detectado
echo.

REM Instalar dependencias
echo [2/3] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias
    pause
    exit /b 1
)

echo.
echo [3/3] Dependencias instaladas correctamente
echo.
echo ==========================================
echo  Instalacion completada!
echo.
echo  Para iniciar la aplicacion:
echo    python main.py
echo.
echo  Para empaquetar como .exe:
echo    python build.py
echo.
echo  Para mas opciones:
echo    python main.py --help
echo ==========================================
pause
'''

    with open('install.bat', 'w') as f:
        f.write(batch_content)

    print("Creado: install.bat")


def main():
    args = parse_args()

    if args.clean:
        clean_build()
        return

    print("=" * 50)
    print("DualSense Controller - Build Script")
    print("=" * 50 + "\n")

    # Verificar dependencias
    if not check_dependencies():
        create_installer_batch()
        print("\nEjecuta 'install.bat' como Administrador para instalar dependencias.")
        sys.exit(1)

    # Build
    success = build_executable(
        onefile=args.onefile,
        console=args.console
    )

    if success:
        create_installer_batch()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
