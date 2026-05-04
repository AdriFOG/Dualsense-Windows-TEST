"""
DualSense Controller - Punto de Entrada Principal
Aplicacion de control para PlayStation 5 DualSense en Windows.

Funcionalidades:
  - Deteccion automatica de conexion USB/Bluetooth
  - Monitor de bateria y estado de carga
  - Motor de efectos de gatillo (haptic feedback)
  - Perfiles de armas preconfigurados
  - Interfaz grafica moderna (modo oscuro)
  - Guardado de configuraciones en JSON
  - Modo bandeja del sistema
  - Limpieza de cache Bluetooth via PowerShell

Uso:
    python main.py
    python main.py --minimized  (Inicia minimizado a bandeja)
    python main.py --no-gui     (Modo consola solo)
"""

import argparse
import logging
import os
import sys
import time
import signal
from pathlib import Path

# Agregar directorio src al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Configura el sistema de logging."""
    log_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'DualSenseController' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f'dualsense_{time.strftime("%Y%m%d")}.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def parse_arguments():
    """Parsea los argumentos de linea de comandos."""
    parser = argparse.ArgumentParser(
        description='DualSense Controller - Panel de Control para PS5 en Windows'
    )
    parser.add_argument(
        '--minimized', '-m',
        action='store_true',
        help='Inicia la aplicacion minimizada a la bandeja del sistema'
    )
    parser.add_argument(
        '--no-gui', '-c',
        action='store_true',
        help='Ejecuta en modo consola sin interfaz grafica'
    )
    parser.add_argument(
        '--profile', '-p',
        type=str,
        default=None,
        help='ID del perfil a aplicar automaticamente al conectar'
    )
    parser.add_argument(
        '--reset-bt',
        action='store_true',
        help='Reinicia el Bluetooth al inicio'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Activa el modo debug con logging verboso'
    )
    return parser.parse_args()


class DualSenseApp:
    """
    Aplicacion principal que orquesta todos los modulos.
    """

    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)

        # Modulos
        self.connection_manager = None
        self.trigger_engine = None
        self.profile_manager = None
        self.tray_manager = None
        self.gui = None

        self._running = False
        self._shutdown_requested = False

    def initialize(self):
        """Inicializa todos los modulos de la aplicacion."""
        self.logger.info("=" * 50)
        self.logger.info("DualSense Controller v1.0 - Iniciando")
        self.logger.info("=" * 50)

        try:
            from src.connection_manager import ConnectionManager
            from src.trigger_engine import TriggerEngine
            from src.profile_manager import ProfileManager
            from src.system_tray import TrayManager

            # 1. Profile Manager (primero para cargar configuracion)
            self.logger.info("Inicializando ProfileManager...")
            self.profile_manager = ProfileManager()

            # 2. Connection Manager
            self.logger.info("Inicializando ConnectionManager...")
            self.connection_manager = ConnectionManager()

            # 3. Trigger Engine
            self.logger.info("Inicializando TriggerEngine...")
            self.trigger_engine = TriggerEngine(self.connection_manager)

            # 4. System Tray
            self.logger.info("Inicializando TrayManager...")
            self.tray_manager = TrayManager()

            # 5. Cargar perfiles personalizados guardados
            custom_profiles = self.profile_manager.get_custom_profiles()
            if custom_profiles:
                self.logger.info(f"Cargando {len(custom_profiles)} perfiles personalizados")
                self.trigger_engine.load_profiles_from_dict(custom_profiles)

            self.logger.info("Todos los modulos inicializados correctamente")
            return True

        except Exception as e:
            self.logger.error(f"Error inicializando modulos: {e}", exc_info=True)
            return False

    def start(self):
        """Inicia la aplicacion."""
        if not self.initialize():
            self.logger.error("No se pudieron inicializar los modulos. Saliendo.")
            sys.exit(1)

        self._running = True

        # Configurar signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Iniciar modulos de backend
        self.connection_manager.start()
        self.tray_manager.start()

        # Cargar perfiles en el tray menu
        if self.trigger_engine:
            profiles = self.trigger_engine.get_profile_names()
            self.tray_manager.set_profiles(profiles)

        # Reiniciar Bluetooth si se solicito
        if self.args.reset_bt:
            self.logger.info("Reiniciando Bluetooth como se solicito...")
            self.connection_manager.perform_bluetooth_reset()

        # Iniciar GUI o modo consola
        if self.args.no_gui:
            self._run_console_mode()
        else:
            self._run_gui_mode()

    def _run_gui_mode(self):
        """Ejecuta en modo grafico."""
        try:
            from gui.app import DualSenseGUI

            self.logger.info("Iniciando interfaz grafica...")

            self.gui = DualSenseGUI(
                connection_manager=self.connection_manager,
                trigger_engine=self.trigger_engine,
                profile_manager=self.profile_manager,
                tray_manager=self.tray_manager
            )

            # Conectar tray callbacks
            self.tray_manager.on_show_window(self.gui.show_window)
            self.tray_manager.on_exit(self.shutdown)
            self.tray_manager.on_profile_select(
                lambda pid: self.trigger_engine.apply_profile(pid) if self.trigger_engine else None
            )

            self.gui.on_close(self.shutdown)

            # Aplicar perfil por linea de comandos o el guardado
            target_profile = self.args.profile or self.profile_manager.get_active_profile()
            if target_profile and self.trigger_engine:
                # Esperar un momento para que se conecte
                def apply_after_connect():
                    time.sleep(2)
                    if self.connection_manager.is_connected:
                        self.trigger_engine.apply_profile(target_profile)

                import threading
                threading.Thread(target=apply_after_connect, daemon=True).start()

            # Si se solicito minimizado
            if self.args.minimized:
                self.logger.info("Iniciando minimizado a bandeja")
                self.gui.root.after(100, self.gui.hide_window)

            # Ejecutar interfaz
            self.gui.run()

        except Exception as e:
            self.logger.error(f"Error en modo grafico: {e}", exc_info=True)
            self.logger.info("Cayendo a modo consola...")
            self._run_console_mode()

    def _run_console_mode(self):
        """Ejecuta en modo consola (sin GUI)."""
        self.logger.info("Ejecutando en modo consola")
        print("\n" + "=" * 50)
        print("DualSense Controller - Modo Consola")
        print("=" * 50)
        print("Comandos disponibles:")
        print("  connect    - Intentar conectar el control")
        print("  disconnect - Desconectar el control")
        print("  status     - Mostrar estado actual")
        print("  battery    - Mostrar nivel de bateria")
        print("  profiles   - Listar perfiles disponibles")
        print("  apply <id> - Aplicar un perfil")
        print("  reset-bt   - Reiniciar Bluetooth")
        print("  led <r> <g> <b> - Cambiar color LED")
        print("  exit       - Salir")
        print("=" * 50 + "\n")

        # Esperar conexion automatica si esta configurada
        if self.profile_manager.get_setting('auto_connect', True):
            print("Esperando conexion automatica del DualSense...")

        # Callbacks para mostrar en consola
        self.connection_manager.on_connect(self._on_console_connect)
        self.connection_manager.on_disconnect(self._on_console_disconnect)
        self.connection_manager.on_battery_change(self._on_console_battery)

        # Bucle de comandos
        while self._running:
            try:
                command = input("dualsense> ").strip().lower()

                if command == 'exit':
                    break
                elif command == 'connect':
                    print("Intentando conectar...")
                elif command == 'disconnect':
                    self.connection_manager.stop()
                    print("Desconectado.")
                elif command == 'status':
                    self._print_status()
                elif command == 'battery':
                    level, status = self.connection_manager.get_battery_info()
                    print(f"Bateria: {level}% - {status.value}")
                elif command == 'profiles':
                    self._print_profiles()
                elif command.startswith('apply '):
                    profile_id = command.split(' ', 1)[1]
                    if self.trigger_engine:
                        success = self.trigger_engine.apply_profile(profile_id)
                        print(f"Perfil {'aplicado' if success else 'no encontrado'}")
                elif command == 'reset-bt':
                    print("Reiniciando Bluetooth...")
                    self.connection_manager.perform_bluetooth_reset()
                elif command.startswith('led '):
                    parts = command.split()
                    if len(parts) == 4:
                        r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                        self.connection_manager.set_led_color(r, g, b)
                        print(f"LED establecido a RGB({r},{g},{b})")
                elif command == '':
                    continue
                else:
                    print(f"Comando desconocido: {command}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

        self.shutdown()

    def _print_status(self):
        """Imprime el estado actual en consola."""
        state = self.connection_manager.state
        print(f"\nConectado: {'Si' if state.connected else 'No'}")
        print(f"Tipo: {state.connection_type.value}")
        print(f"Bateria: {state.battery_level}% - {state.charging_status.value}")
        print(f"L2: {state.left_trigger}/255")
        print(f"R2: {state.right_trigger}/255")
        print()

    def _print_profiles(self):
        """Imprime los perfiles disponibles en consola."""
        if not self.trigger_engine:
            return

        print("\nPerfiles disponibles:")
        for pid, name in self.trigger_engine.get_profile_names():
            profile = self.trigger_engine.get_profile(pid)
            current = " [ACTIVO]" if pid == self.trigger_engine.get_current_profile() else ""
            print(f"  {pid:<20} - {name}{current}")
            if profile:
                print(f"      {profile.description}")
        print()

    def _on_console_connect(self, connection_type):
        """Callback de conexion para modo consola."""
        print(f"\n[+] DualSense conectado via {connection_type.value.upper()}")

        # Aplicar perfil por defecto
        if self.trigger_engine:
            target = self.args.profile or self.profile_manager.get_active_profile()
            self.trigger_engine.apply_profile(target)
            print(f"[+] Perfil aplicado: {target}")

    def _on_console_disconnect(self):
        """Callback de desconexion para modo consola."""
        print("\n[-] DualSense desconectado")

    def _on_console_battery(self, level, status):
        """Callback de bateria para modo consola."""
        print(f"\n[Battery] {level}% - {status.value}")

    def _signal_handler(self, signum, frame):
        """Maneja señales de sistema."""
        self.logger.info(f"Señal recibida: {signum}")
        self._shutdown_requested = True
        self.shutdown()

    def shutdown(self):
        """Apaga la aplicacion de forma ordenada."""
        if not self._running:
            return

        self.logger.info("Cerrando aplicacion...")
        self._running = False

        try:
            # Guardar estado
            if self.profile_manager:
                self.profile_manager.save_config()

            # Detener modulos
            if self.gui:
                self.gui.stop()

            if self.trigger_engine:
                self.trigger_engine.stop()

            if self.connection_manager:
                self.connection_manager.stop()

            if self.tray_manager:
                self.tray_manager.stop()

            self.logger.info("Aplicacion cerrada correctamente")

        except Exception as e:
            self.logger.error(f"Error durante cierre: {e}")

        finally:
            sys.exit(0)


def main():
    """Punto de entrada principal."""
    args = parse_arguments()

    # Configurar logging
    logger = setup_logging()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Modo DEBUG activado")

    # Verificar que estamos en Windows
    if sys.platform != 'win32':
        logger.warning("Esta aplicacion esta diseñada para Windows. Algunas funciones pueden no funcionar.")

    # Crear y ejecutar aplicacion
    app = DualSenseApp(args)

    try:
        app.start()
    except Exception as e:
        logger.critical(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
