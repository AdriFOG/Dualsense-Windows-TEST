"""
Gestor de Conexion DualSense
Maneja la deteccion automatica de conexion USB/Bluetooth, monitoreo de bateria
y estado del control.
"""

import logging
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, List

try:
    from pydualsense import pydualsense, TriggerModes
    PYDUALSENSE_AVAILABLE = True
except ImportError:
    PYDUALSENSE_AVAILABLE = False
    logging.warning("pydualsense no instalado. El programa funcionara en modo simulacion.")

from .bluetooth_utils import BluetoothManager

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Tipo de conexion del control."""
    NONE = "none"
    USB = "usb"
    BLUETOOTH = "bluetooth"
    UNKNOWN = "unknown"


class ChargingStatus(Enum):
    """Estado de carga del control."""
    DISCHARGING = "descargando"
    CHARGING = "cargando"
    CHARGED = "cargado completo"
    UNKNOWN = "desconocido"


@dataclass
class ControllerState:
    """Representa el estado actual del control."""
    connected: bool = False
    connection_type: ConnectionType = ConnectionType.NONE
    battery_level: int = 0
    charging_status: ChargingStatus = ChargingStatus.UNKNOWN
    left_trigger: int = 0
    right_trigger: int = 0
    left_stick_x: int = 128
    left_stick_y: int = 128
    right_stick_x: int = 128
    right_stick_y: int = 128
    buttons: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ConnectionManager:
    """
    Gestiona la conexion con el DualSense de PS5.
    Detecta automaticamente conexion USB o Bluetooth.
    """

    # Intervalos de sondeo (segundos)
    CONNECTION_POLL_INTERVAL = 2.0
    STATE_POLL_INTERVAL = 0.016  # ~60Hz para lectura de estado

    def __init__(self):
        self.dualsense: Optional['pydualsense'] = None
        self.bluetooth_manager = BluetoothManager()

        # Estado
        self._state = ControllerState()
        self._connected = False
        self._connection_type = ConnectionType.NONE
        self._running = False

        # Callbacks
        self._on_connect: List[Callable[[ConnectionType], None]] = []
        self._on_disconnect: List[Callable[[], None]] = []
        self._on_state_update: List[Callable[[ControllerState], None]] = []
        self._on_battery_change: List[Callable[[int, ChargingStatus], None]] = []
        self._on_error: List[Callable[[str], None]] = []

        # Hilos
        self._connection_thread: Optional[threading.Thread] = None
        self._state_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    # ===== Registro de Callbacks =====

    def on_connect(self, callback: Callable[[ConnectionType], None]) -> None:
        """Registra callback para cuando se conecta el control."""
        self._on_connect.append(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Registra callback para cuando se desconecta el control."""
        self._on_disconnect.append(callback)

    def on_state_update(self, callback: Callable[[ControllerState], None]) -> None:
        """Registra callback para actualizaciones de estado."""
        self._on_state_update.append(callback)

    def on_battery_change(self, callback: Callable[[int, ChargingStatus], None]) -> None:
        """Registra callback para cambios de bateria."""
        self._on_battery_change.append(callback)

    def on_error(self, callback: Callable[[str], None]) -> None:
        """Registra callback para errores."""
        self._on_error.append(callback)

    # ===== Propiedades =====

    @property
    def is_connected(self) -> bool:
        """Indica si hay un control conectado."""
        with self._lock:
            return self._connected

    @property
    def connection_type(self) -> ConnectionType:
        """Devuelve el tipo de conexion actual."""
        with self._lock:
            return self._connection_type

    @property
    def state(self) -> ControllerState:
        """Devuelve una copia del estado actual."""
        with self._lock:
            return ControllerState(
                connected=self._state.connected,
                connection_type=self._state.connection_type,
                battery_level=self._state.battery_level,
                charging_status=self._state.charging_status,
                left_trigger=self._state.left_trigger,
                right_trigger=self._state.right_trigger,
                left_stick_x=self._state.left_stick_x,
                left_stick_y=self._state.left_stick_y,
                right_stick_x=self._state.right_stick_x,
                right_stick_y=self._state.right_stick_y,
                buttons=dict(self._state.buttons),
                timestamp=self._state.timestamp
            )

    @property
    def dualsense_instance(self) -> Optional['pydualsense']:
        """Devuelve la instancia de pydualsense para acceso directo."""
        return self.dualsense

    # ===== Gestión de Conexión =====

    def start(self) -> None:
        """Inicia los hilos de gestion de conexion."""
        if self._running:
            return

        self._running = True

        # Hilo de deteccion de conexion
        self._connection_thread = threading.Thread(
            target=self._connection_loop,
            name="ConnectionMonitor",
            daemon=True
        )
        self._connection_thread.start()

        # Hilo de lectura de estado
        self._state_thread = threading.Thread(
            target=self._state_loop,
            name="StateMonitor",
            daemon=True
        )
        self._state_thread.start()

        logger.info("ConnectionManager iniciado")

    def stop(self) -> None:
        """Detiene los hilos y desconecta el control."""
        self._running = False

        # Esperar a que los hilos terminen
        if self._connection_thread and self._connection_thread.is_alive():
            self._connection_thread.join(timeout=3)
        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=3)

        # Desconectar el control
        self._disconnect()

        logger.info("ConnectionManager detenido")

    def _connection_loop(self) -> None:
        """Bucle principal de deteccion de conexion."""
        while self._running:
            try:
                if not self._connected:
                    self._try_connect()
                else:
                    # Verificar que la conexion sigue viva
                    if not self._verify_connection():
                        self._disconnect()

                time.sleep(self.CONNECTION_POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error en bucle de conexion: {e}")
                self._notify_error(f"Error de conexion: {str(e)}")
                time.sleep(self.CONNECTION_POLL_INTERVAL * 2)

    def _try_connect(self) -> bool:
        """Intenta conectar con el DualSense."""
        if not PYDUALSENSE_AVAILABLE:
            return False

        try:
            # Crear instancia de pydualsense
            self.dualsense = pydualsense()
            self.dualsense.init()

            # Detectar tipo de conexion
            conn_type = self._detect_connection_type()

            with self._lock:
                self._connected = True
                self._connection_type = conn_type
                self._state.connected = True
                self._state.connection_type = conn_type

            logger.info(f"DualSense conectado via {conn_type.value.upper()}")
            self._notify_connect(conn_type)

            return True

        except Exception as e:
            # No se pudo conectar, limpiar
            if self.dualsense:
                try:
                    self.dualsense.close()
                except Exception:
                    pass
                self.dualsense = None

            # Solo loguear periodicamente para no saturar
            if int(time.time()) % 10 == 0:
                logger.debug(f"No se encontro DualSense: {e}")

            return False

    def _detect_connection_type(self) -> ConnectionType:
        """Detecta si la conexion es USB o Bluetooth."""
        if not self.dualsense:
            return ConnectionType.UNKNOWN

        try:
            # En pydualsense, podemos inferir el tipo de conexion
            # por el reporte de estado o propiedades del dispositivo
            device = self.dualsense.device

            if device:
                # Intentar obtener informacion del dispositivo HID
                try:
                    # Los dispositivos USB suelen tener ciertos paths
                    # Bluetooth tiene otros identificadores
                    device_info = device.get_manufacturer_string() if hasattr(device, 'get_manufacturer_string') else ""
                    product_info = device.get_product_string() if hasattr(device, 'get_product_string') else ""

                    info_str = f"{device_info} {product_info}".lower()

                    if "bluetooth" in info_str or "bt" in info_str:
                        return ConnectionType.BLUETOOTH
                    elif "usb" in info_str:
                        return ConnectionType.USB
                except Exception:
                    pass

                # Fallback: intentar por el path del dispositivo
                try:
                    path = device.path.decode('utf-8') if isinstance(device.path, bytes) else str(device.path)
                    if "bluetooth" in path.lower() or "{00001124" in path:
                        return ConnectionType.BLUETOOTH
                    elif "usb" in path.lower() or "hid" in path.lower():
                        return ConnectionType.USB
                except Exception:
                    pass

            # Si no podemos determinar, asumimos USB como default
            # (generalmente mas confiable)
            return ConnectionType.USB

        except Exception as e:
            logger.warning(f"No se pudo detectar tipo de conexion: {e}")
            return ConnectionType.UNKNOWN

    def _verify_connection(self) -> bool:
        """Verifica que la conexion sigue activa."""
        if not self.dualsense:
            return False

        try:
            # Intentar leer el estado - si falla, la conexion se perdio
            state = self.dualsense.state
            return state is not None
        except Exception:
            return False

    def _disconnect(self) -> None:
        """Desconecta el control y limpia recursos."""
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._connection_type = ConnectionType.NONE
            self._state.connected = False
            self._state.connection_type = ConnectionType.NONE

        if self.dualsense:
            try:
                # Apagar LEDs y efectos antes de desconectar
                self._reset_controller_state()
                self.dualsense.close()
            except Exception as e:
                logger.warning(f"Error al cerrar conexion: {e}")
            finally:
                self.dualsense = None

        if was_connected:
            logger.info("DualSense desconectado")
            self._notify_disconnect()

    def _reset_controller_state(self) -> None:
        """Resetea el estado del control (LEDs, gatillos, etc.)"""
        if not self.dualsense:
            return

        try:
            # Apagar LED del player
            self.dualsense.setLEDPlayer(0)

            # Resetear gatillos
            if hasattr(self.dualsense, 'setLeftTriggerMode'):
                self.dualsense.setLeftTriggerMode(TriggerModes.Off)
            if hasattr(self.dualsense, 'setRightTriggerMode'):
                self.dualsense.setRightTriggerMode(TriggerModes.Off)

            # Apagar luz del touchpad
            if hasattr(self.dualsense, 'setTouchpadLED'):
                self.dualsense.setTouchpadLED(0, 0, 0)

        except Exception as e:
            logger.warning(f"Error al resetear estado del control: {e}")

    # ===== Lectura de Estado =====

    def _state_loop(self) -> None:
        """Bucle de lectura continua del estado del control."""
        while self._running:
            try:
                if self._connected and self.dualsense:
                    self._read_controller_state()
                    time.sleep(self.STATE_POLL_INTERVAL)
                else:
                    time.sleep(self.CONNECTION_POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error en lectura de estado: {e}")
                time.sleep(0.5)

    def _read_controller_state(self) -> None:
        """Lee el estado actual del control."""
        if not self.dualsense or not self.dualsense.state:
            return

        try:
            ds_state = self.dualsense.state

            with self._lock:
                old_battery = self._state.battery_level
                old_charging = self._state.charging_status

                # Actualizar estado
                self._state.left_trigger = getattr(ds_state, 'L2', 0)
                self._state.right_trigger = getattr(ds_state, 'R2', 0)
                self._state.left_stick_x = getattr(ds_state, 'LX', 128)
                self._state.left_stick_y = getattr(ds_state, 'LY', 128)
                self._state.right_stick_x = getattr(ds_state, 'RX', 128)
                self._state.right_stick_y = getattr(ds_state, 'RY', 128)
                self._state.timestamp = time.time()

                # Leer botones
                self._state.buttons = {
                    'cross': getattr(ds_state, 'cross', False),
                    'circle': getattr(ds_state, 'circle', False),
                    'square': getattr(ds_state, 'square', False),
                    'triangle': getattr(ds_state, 'triangle', False),
                    'L1': getattr(ds_state, 'L1', False),
                    'R1': getattr(ds_state, 'R1', False),
                    'L2_btn': getattr(ds_state, 'L2Btn', False),
                    'R2_btn': getattr(ds_state, 'R2Btn', False),
                    'L3': getattr(ds_state, 'L3', False),
                    'R3': getattr(ds_state, 'R3', False),
                    'create': getattr(ds_state, 'create', False),
                    'options': getattr(ds_state, 'options', False),
                    'ps': getattr(ds_state, 'PS', False),
                    'touchpad': getattr(ds_state, 'touchBtn', False),
                    'mute': getattr(ds_state, 'mute', False),
                    'dpad_up': getattr(ds_state, 'DpadUp', False),
                    'dpad_down': getattr(ds_state, 'DpadDown', False),
                    'dpad_left': getattr(ds_state, 'DpadLeft', False),
                    'dpad_right': getattr(ds_state, 'DpadRight', False),
                }

                # Leer bateria (si esta disponible)
                try:
                    battery = getattr(ds_state, 'battery', None)
                    if battery is not None:
                        # La bateria suele venir en valor 0-255 o porcentaje
                        if battery <= 100:
                            self._state.battery_level = int(battery)
                        else:
                            self._state.battery_level = min(100, int((battery / 255) * 100))

                    # Estado de carga
                    charging = getattr(ds_state, 'batteryState', None)
                    if charging is not None:
                        if charging == 0x00:
                            self._state.charging_status = ChargingStatus.DISCHARGING
                        elif charging == 0x01:
                            self._state.charging_status = ChargingStatus.CHARGING
                        elif charging == 0x02:
                            self._state.charging_status = ChargingStatus.CHARGED
                    elif self._connection_type == ConnectionType.USB:
                        # Si esta por USB, probablemente este cargando
                        if self._state.battery_level >= 95:
                            self._state.charging_status = ChargingStatus.CHARGED
                        else:
                            self._state.charging_status = ChargingStatus.CHARGING

                except Exception:
                    pass

            # Notificar cambios de bateria
            if (old_battery != self._state.battery_level or
                old_charging != self._state.charging_status):
                self._notify_battery_change(
                    self._state.battery_level,
                    self._state.charging_status
                )

            # Notificar actualizacion de estado
            self._notify_state_update(self.state)

        except Exception as e:
            logger.error(f"Error leyendo estado del control: {e}")

    # ===== Notificaciones =====

    def _notify_connect(self, conn_type: ConnectionType) -> None:
        """Notifica a los listeners que se conecto el control."""
        for callback in self._on_connect:
            try:
                callback(conn_type)
            except Exception as e:
                logger.error(f"Error en callback on_connect: {e}")

    def _notify_disconnect(self) -> None:
        """Notifica a los listeners que se desconecto el control."""
        for callback in self._on_disconnect:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error en callback on_disconnect: {e}")

    def _notify_state_update(self, state: ControllerState) -> None:
        """Notifica actualizacion de estado."""
        for callback in self._on_state_update:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"Error en callback on_state_update: {e}")

    def _notify_battery_change(self, level: int, status: ChargingStatus) -> None:
        """Notifica cambio en el estado de bateria."""
        for callback in self._on_battery_change:
            try:
                callback(level, status)
            except Exception as e:
                logger.error(f"Error en callback on_battery_change: {e}")

    def _notify_error(self, message: str) -> None:
        """Notifica un error."""
        for callback in self._on_error:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error en callback on_error: {e}")

    # ===== Metodos Publicos =====

    def get_battery_info(self) -> tuple[int, ChargingStatus]:
        """Devuelve informacion de la bateria."""
        with self._lock:
            return self._state.battery_level, self._state.charging_status

    def perform_bluetooth_reset(self) -> bool:
        """Realiza un reinicio completo del Bluetooth."""
        return self.bluetooth_manager.full_bluetooth_reset()

    def set_led_color(self, r: int, g: int, b: int) -> None:
        """Establece el color del LED del touchpad."""
        if self.dualsense and hasattr(self.dualsense, 'setTouchpadLED'):
            try:
                self.dualsense.setTouchpadLED(r, g, b)
            except Exception as e:
                logger.warning(f"Error al establecer LED: {e}")

    def set_player_led(self, player: int) -> None:
        """Establece el numero de jugador (1-4, 0 = apagado)."""
        if self.dualsense and hasattr(self.dualsense, 'setLEDPlayer'):
            try:
                self.dualsense.setLEDPlayer(player)
            except Exception as e:
                logger.warning(f"Error al establecer player LED: {e}")

    def set_rumble(self, left_motor: int, right_motor: int) -> None:
        """Establece la intensidad de vibracion (0-255)."""
        if self.dualsense:
            try:
                if hasattr(self.dualsense, 'setLeftMotor'):
                    self.dualsense.setLeftMotor(left_motor)
                if hasattr(self.dualsense, 'setRightMotor'):
                    self.dualsense.setRightMotor(right_motor)
            except Exception as e:
                logger.warning(f"Error al establecer rumble: {e}")
