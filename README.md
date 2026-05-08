# DualSense Controller - Panel de Control para Windows

Aplicacion de escritorio para controlar y personalizar el mando **PlayStation 5 DualSense** en Windows. Soporta conexion USB y Bluetooth con efectos de gatillo haptico, perfiles de armas, monitoreo de bateria y mas.

![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)


## Caracteristicas

* **Conexion Automatica**: Detecta si el DualSense esta conectado por USB o Bluetooth automaticamente
* **Efectos de Gatillo**: Motor completo de efectos hapticos para L2 y R2
* **Perfiles de Armas**: 8 perfiles preconfigurados (Rifle de Asalto, Francotirador, Arco, Escopeta, etc.)
* **Monitor de Bateria**: Muestra porcentaje y estado de carga en tiempo real
* **Interfaz Moderna**: UI con modo oscuro, esquinas redondeadas y tema azul
* **Modo Bandeja**: Se minimiza a la bandeja del sistema para correr en segundo plano
* **Guardado de Configuracion**: Perfiles y ajustes se guardan automaticamente en JSON
* **Limpieza Bluetooth**: Reinicia el servicio Bluetooth de Windows desde la app
* **Empaquetado**: Se puede convertir a un solo archivo .exe ejecutable

## Requisitos

* Windows 10 o Windows 11
* Python 3.8 o superior (solo para desarrollo)
* DualSense conectado via USB o Bluetooth

## Instalacion Rapida

### Opcion 1: Desde codigo fuente

1. **Clona o descarga** este repositorio
2. **Ejecuta** `install.bat` como Administrador:

```cmd
   install.bat
   ```

3. **Inicia** la aplicacion:

```cmd
   python main.py
   ```

### Opcion 2: Ejecutable .exe

1. Despues de instalar dependencias, ejecuta:

```cmd
   python build.py
   ```

2. El ejecutable estara en `dist/DualSenseController/`
3. Para un solo archivo .exe:

```cmd
   python build.py --onefile
   ```

## Uso

### Interfaz Grafica (por defecto)

```cmd
python main.py
```

### Opciones de linea de comandos

```cmd
python main.py --help

Opciones:
  -m, --minimized    Inicia minimizado a la bandeja del sistema
  -c, --no-gui       Modo consola (sin interfaz grafica)
  -p, --profile      Aplica un perfil al conectar (ej: --profile sniper)
  --reset-bt         Reinicia el Bluetooth al inicio
  -d, --debug        Modo debug con logging verboso
```

### Controles en Modo Consola

Cuando ejecutas con `--no-gui`, puedes usar estos comandos:

```
dualsense> connect        - Intentar conectar el control
dualsense> disconnect     - Desconectar el control
dualsense> status         - Mostrar estado actual
dualsense> battery        - Nivel de bateria
dualsense> profiles       - Listar perfiles disponibles
dualsense> apply sniper   - Aplicar perfil de francotirador
dualsense> reset-bt       - Reiniciar Bluetooth
dualsense> led 255 0 0    - Cambiar LED a rojo
dualsense> exit           - Salir
```

## Perfiles de Armas Incluidos

|Perfil|Categoria|Descripcion|
|-|-|-|
|**Rifle de Asalto**|Automaticas|Gatillazo rapido con ligera vibracion|
|**Francotirador**|Precision|Mucha dureza inicial y quiebre seco|
|**Arco**|Precision|Tension que aumenta gradualmente|
|**Pistola**|Pistolas|Gatillo corto y firme, respuesta inmediata|
|**Escopeta**|Pesadas|Resistencia maxima con vibracion de retroceso|
|**Subfusil**|Automaticas|Vibracion rapida y constante|
|**Ametralladora**|Pesadas|Resistencia creciente, simula calentamiento|

## Estructura del Proyecto

```
dualsense-controller/
├── main.py                  # Punto de entrada principal
├── requirements.txt         # Dependencias de Python
├── build.py                 # Script de empaquetado PyInstaller
├── install.bat              # Instalador rapido para Windows
├── assets/                  # Iconos e imagenes
├── config/                  # Archivos de configuracion JSON
├── src/
│   ├── \_\_init\_\_.py
│   ├── connection\_manager.py    # Gestor de conexion USB/Bluetooth
│   ├── trigger\_engine.py        # Motor de efectos de gatillo
│   ├── profile\_manager.py       # Guardado/carga de configuraciones
│   ├── bluetooth\_utils.py       # Utilidades Bluetooth (PowerShell)
│   └── system\_tray.py           # Modo bandeja del sistema
└── gui/
    ├── \_\_init\_\_.py
    └── app.py                   # Interfaz grafica (CustomTkinter)
```

## Solucion de Problemas

### El control no se detecta

1. Asegurate de que el DualSense este emparejado en Bluetooth o conectado por USB
2. Prueba reiniciar el Bluetooth: `python main.py --reset-bt`
3. Verifica que los drivers del DualSense esten instalados

### Error al importar pydualsense

```cmd
pip install pydualsense hidapi
```

### La app no inicia

* Verifica que tengas Python 3.8+
* Ejecuta con `--debug` para ver logs detallados:

```cmd
  python main.py --debug
  ```

* Revisa los logs en: `%APPDATA%\\DualSenseController\\logs\\`

### Bluetooth no funciona correctamente

* La app incluye una herramienta de reinicio de Bluetooth que requiere permisos de administrador
* Tambien puedes reiniciar manualmente desde la pestaña Configuracion

## Dependencias

* **pydualsense**: Comunicacion con el DualSense
* **customtkinter**: Interfaz grafica moderna
* **pillow**: Manipulacion de imagenes
* **pystray**: Icono en bandeja del sistema
* **pywin32**: Integracion con Windows
* **pyinstaller**: Empaquetado a .exe

## Licencia

Proyecto educativo / proof-of-concept. Usar bajo tu propia responsabilidad.
Sony, PlayStation y DualSense son marcas registradas de Sony Interactive Entertainment.

---

## Creditos y Referencias

- [MinHook](https://github.com/TsudaKageyu/minhook) por Tsuda Kageyu
- [HIDAPI](https://github.com/libusb/hidapi) por libusb/hidapi contributors
- [ViGEmBus](https://github.com/ViGEm/ViGEmBus) por Nefarius
- [DSX](https://dsx.ds4windows.com/) por Paliverse / DSX Team (inspiracion de funcionalidad)
- Protocolo DualSense reverse-engineering por la comunidad de PS4/PS5 homebrew


