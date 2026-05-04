@echo off
chcp 65001 >nul
echo ==========================================
echo  DualSense Controller - Instalador
echo ==========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH
    echo.
    echo Por favor instala Python 3.8 o superior:
    echo   https://www.python.org/downloads/
    echo.
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado
echo.

REM Actualizar pip
echo [1/4] Actualizando pip...
python -m pip install --upgrade pip >nul 2>&1
echo [OK] Pip actualizado
echo.

REM Instalar dependencias
echo [2/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias
    echo Intenta ejecutar como Administrador.
    pause
    exit /b 1
)

echo.
echo [OK] Dependencias instaladas
echo.

REM Verificar pydualsense
echo [3/4] Verificando pydualsense...
python -c "import pydualsense; print('[OK] pydualsense funcionando')" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] pydualsense podria necesitar drivers adicionales
    echo Asegurate de tener los drivers del DualSense instalados.
)
echo.

REM Crear directorio de configuracion
echo [4/4] Creando directorio de configuracion...
if not exist "%APPDATA%\DualSenseController" mkdir "%APPDATA%\DualSenseController"
echo [OK] Listo
echo.

echo ==========================================
echo  INSTALACION COMPLETADA
echo ==========================================
echo.
echo  Para iniciar la aplicacion:
echo    python main.py
echo.
echo  Para iniciar minimizado a bandeja:
echo    python main.py --minimized
echo.
echo  Para empaquetar como ejecutable .exe:
echo    python build.py
echo.
echo  Para ayuda:
echo    python main.py --help
echo.
echo ==========================================
pause
