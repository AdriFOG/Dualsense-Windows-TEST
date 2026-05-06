"""
Gestor de Conexion DualSense
Maneja la deteccion automatica de conexion USB/Bluetooth, monitoreo de bateria y estado del control.
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
from .emulator import EmulatorManager, EmulationMode

logger = logging.getLogger(__name__)

class ConnectionType(Enum):
    NONE = "none"
    USB = "usb"
    BLUETOOTH = "bluetooth"
    UNKNOWN = "unknown"

class ChargingStatus(Enum):
    DISCHARGING = "descargando"
    CHARGING = "cargando"
    CHARGED = "cargado completo"
    UNKNOWN = "desconocido"

@dataclass
class ControllerState:
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
    CONNECTION_POLL_INTERVAL = 2.0
    STATE_POLL_INTERVAL = 0.016

    def __init__(self):
        self.dualsense: Optional['pydualsense'] = None
        self.bluetooth_manager = BluetoothManager()
        self.emulator = EmulatorManager()
        self._state = ControllerState()
        self._connected = False
        self._connection_type = ConnectionType.NONE
        self._running = False

        self._on_connect: List[Callable[[ConnectionType], None]] = []
        self._on_disconnect: List[Callable[[], None]] = []
        self._on_state_update: List[Callable[[ControllerState], None]] = []
        self._on_battery_change: List[Callable[[int, ChargingStatus], None]] = []
        self._on_error: List[Callable[[str], None]] = []

        self._connection_thread: Optional[threading.Thread] = None
        self._state_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    def on_connect(self, callback: Callable[[ConnectionType], None]) -> None:
        self._on_connect.append(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        self._on_disconnect.append(callback)

    def on_state_update(self, callback: Callable[[ControllerState], None]) -> None:
        self._on_state_update.append(callback)

    def on_battery_change(self, callback: Callable[[int, ChargingStatus], None]) -> None:
        self._on_battery_change.append(callback)

    def on_error(self, callback: Callable[[str], None]) -> None:
        self._on_error.append(callback)

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def connection_type(self) -> ConnectionType:
        with self._lock:
            return self._connection_type

    @property
    def state(self) -> ControllerState:
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
        return self.dualsense

    def set_emulation_mode(self, mode: EmulationMode) -> bool:
        return self.emulator.set_mode(mode)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._connection_thread = threading.Thread(target=self._connection_loop, name="ConnectionMonitor", daemon=True)
        self._connection_thread.start()
        self._state_thread = threading.Thread(target=self._state_loop, name="StateMonitor", daemon=True)
        self._state_thread.start()
        logger.info("ConnectionManager iniciado")

    def stop(self) -> None:
        self._running = False
        if self._connection_thread and self._connection_thread.is_alive():
            self._connection_thread.join(timeout=3)
        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=3)
        self.emulator.set_mode(EmulationMode.NONE)
        self._disconnect()
        logger.info("ConnectionManager detenido")

    def _connection_loop(self) -> None:
        while self._running:
            try:
                if not self._connected:
                    self._try_connect()
                else:
                    if not self._verify_connection():
                        self._disconnect()
                time.sleep(self.CONNECTION_POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error en bucle de conexion: {e}")
                time.sleep(self.CONNECTION_POLL_INTERVAL * 2)

    def _try_connect(self) -> bool:
        if not PYDUALSENSE_AVAILABLE:
            return False
        try:
            self.dualsense = pydualsense()
            self.dualsense.init()
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
            if self.dualsense:
                try: self.dualsense.close()
                except Exception: pass
                self.dualsense = None
            return False

    def _detect_connection_type(self) -> ConnectionType:
        if not self.dualsense: return ConnectionType.UNKNOWN
        try:
            device = self.dualsense.device
            if device:
                try:
                    device_info = device.get_manufacturer_string() if hasattr(device, 'get_manufacturer_string') else ""
                    product_info = device.get_product_string() if hasattr(device, 'get_product_string') else ""
                    info_str = f"{device_info} {product_info}".lower()
                    if "bluetooth" in info_str or "bt" in info_str: return ConnectionType.BLUETOOTH
                    elif "usb" in info_str: return ConnectionType.USB
                except Exception: pass
                try:
                    path = device.path.decode('utf-8') if isinstance(device.path, bytes) else str(device.path)
                    if "bluetooth" in path.lower() or "{00001124" in path: return ConnectionType.BLUETOOTH
                    elif "usb" in path.lower() or "hid" in path.lower(): return ConnectionType.USB
                except Exception: pass
            return ConnectionType.USB
        except Exception:
            return ConnectionType.UNKNOWN

    def _verify_connection(self) -> bool:
        if not self.dualsense: return False
        try: return self.dualsense.state is not None
        except Exception: return False

    def _disconnect(self) -> None:
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._connection_type = ConnectionType.NONE
            self._state.connected = False
            self._state.connection_type = ConnectionType.NONE
        if self.dualsense:
            try:
                self._reset_controller_state()
                self.dualsense.close()
            except Exception: pass
            finally: self.dualsense = None
        if was_connected:
            logger.info("DualSense desconectado")
            self._notify_disconnect()

    def _reset_controller_state(self) -> None:
        if not self.dualsense: return
        try:
            from pydualsense import TriggerModes
            self.dualsense.triggerL.setMode(TriggerModes.Off)
            self.dualsense.triggerR.setMode(TriggerModes.Off)
            self.dualsense.light.setColorI(0, 0, 0)
            self.dualsense.setLeftMotor(0)
            self.dualsense.setRightMotor(0)
        except Exception: pass

    def _state_loop(self) -> None:
        while self._running:
            try:
                if self._connected and self.dualsense:
                    self._read_controller_state()
                    time.sleep(self.STATE_POLL_INTERVAL)
                else:
                    time.sleep(self.CONNECTION_POLL_INTERVAL)
            except Exception as e:
                time.sleep(0.5)

    def _read_controller_state(self) -> None:
        if not self.dualsense or not self.dualsense.state: return
        try:
            ds_state = self.dualsense.state
            
            with self._lock:
                old_battery = self._state.battery_level
                old_charging = self._state.charging_status

                # --- LECTURA SEGURA DE GATILLOS ---
                lt_raw = getattr(ds_state, 'L2_value', getattr(ds_state, 'L2', 0))
                rt_raw = getattr(ds_state, 'R2_value', getattr(ds_state, 'R2', 0))
                
                if isinstance(lt_raw, bool): self._state.left_trigger = 255 if lt_raw else 0
                else: self._state.left_trigger = lt_raw
                
                if isinstance(rt_raw, bool): self._state.right_trigger = 255 if rt_raw else 0
                else: self._state.right_trigger = rt_raw

                # --- LECTURA SEGURA Y ESCALADO DE PALANCAS ---
                lx_raw = getattr(ds_state, 'LX', 0)
                ly_raw = getattr(ds_state, 'LY', 0)
                rx_raw = getattr(ds_state, 'RX', 0)
                ry_raw = getattr(ds_state, 'RY', 0)

                # Pydualsense lee de -128 a 127. Sumamos 128 para mapearlo perfecto a 0-255.
                def escalar_stick(val):
                    try:
                        return int(max(0, min(255, float(val) + 128)))
                    except:
                        return 128

                self._state.left_stick_x = escalar_stick(lx_raw)
                self._state.left_stick_y = escalar_stick(ly_raw)
                self._state.right_stick_x = escalar_stick(rx_raw)
                self._state.right_stick_y = escalar_stick(ry_raw)

                self._state.timestamp = time.time()
                self._state.buttons = {
                    'cross': getattr(ds_state, 'cross', False),
                    'circle': getattr(ds_state, 'circle', False),
                    'square': getattr(ds_state, 'square', False),
                    'triangle': getattr(ds_state, 'triangle', False),
                    'L1': getattr(ds_state, 'L1', False),
                    'R1': getattr(ds_state, 'R1', False),
                    'L2_btn': getattr(ds_state, 'L2Btn', getattr(ds_state, 'l2_btn', False)),
                    'R2_btn': getattr(ds_state, 'R2Btn', getattr(ds_state, 'r2_btn', False)),
                    'L3': getattr(ds_state, 'L3', getattr(ds_state, 'l3', False)),
                    'R3': getattr(ds_state, 'R3', getattr(ds_state, 'r3', False)),
                    'create': getattr(ds_state, 'create', getattr(ds_state, 'share', False)),
                    'options': getattr(ds_state, 'options', getattr(ds_state, 'start', False)),
                    'ps': getattr(ds_state, 'PS', getattr(ds_state, 'ps', False)),
                    'touchpad': getattr(ds_state, 'touchBtn', getattr(ds_state, 'touchpad', False)),
                    'mute': getattr(ds_state, 'mute', False),
                    'dpad_up': getattr(ds_state, 'DpadUp', getattr(ds_state, 'dpad_up', False)),
                    'dpad_down': getattr(ds_state, 'DpadDown', getattr(ds_state, 'dpad_down', False)),
                    'dpad_left': getattr(ds_state, 'DpadLeft', getattr(ds_state, 'dpad_left', False)),
                    'dpad_right': getattr(ds_state, 'DpadRight', getattr(ds_state, 'dpad_right', False)),
                }

                try:
                    bat_level = self._state.battery_level 
                    if hasattr(self.dualsense, 'battery'):
                        b_obj = self.dualsense.battery
                        raw_val = None
                        for attr in ['Level', 'level', 'Value', 'value', 'Capacity', 'capacity']:
                            if hasattr(b_obj, attr):
                                val = getattr(b_obj, attr)
                                if val is not None:
                                    try:
                                        raw_val = int(val)
                                        break
                                    except (ValueError, TypeError): pass
                        if raw_val is not None:
                            if raw_val <= 10: bat_level = raw_val * 10
                            elif raw_val in (11, 13, 14): bat_level = 100
                            elif raw_val == 15:
                                if self._connection_type == ConnectionType.USB: bat_level = 100
                            else: bat_level = min(100, raw_val)
                    self._state.battery_level = bat_level

                    if self._connection_type == ConnectionType.USB:
                        self._state.charging_status = ChargingStatus.CHARGED if bat_level >= 95 else ChargingStatus.CHARGING
                    else:
                        self._state.charging_status = ChargingStatus.DISCHARGING
                except Exception: pass

            if (old_battery != self._state.battery_level or old_charging != self._state.charging_status):
                self._notify_battery_change(self._state.battery_level, self._state.charging_status)

            self._notify_state_update(self.state)
            self.emulator.update_from_dualsense(self.state)

        except Exception: pass

    def _notify_connect(self, conn_type: ConnectionType) -> None:
        for callback in self._on_connect:
            try: callback(conn_type)
            except Exception: pass

    def _notify_disconnect(self) -> None:
        for callback in self._on_disconnect:
            try: callback()
            except Exception: pass

    def _notify_state_update(self, state: ControllerState) -> None:
        for callback in self._on_state_update:
            try: callback(state)
            except Exception: pass

    def _notify_battery_change(self, level: int, status: ChargingStatus) -> None:
        for callback in self._on_battery_change:
            try: callback(level, status)
            except Exception: pass

    def _notify_error(self, message: str) -> None:
        for callback in self._on_error:
            try: callback(message)
            except Exception: pass

    def get_battery_info(self) -> tuple[int, ChargingStatus]:
        with self._lock: return self._state.battery_level, self._state.charging_status

    def perform_bluetooth_reset(self) -> bool:
        return self.bluetooth_manager.full_bluetooth_reset()

    def set_led_color(self, r: int, g: int, b: int) -> None:
        if self.dualsense:
            try: self.dualsense.light.setColorI(r, g, b)
            except Exception: pass

    def set_player_led(self, player: int) -> None: pass

    def set_rumble(self, left_motor: int, right_motor: int) -> None:
        if self.dualsense:
            try:
                self.dualsense.setLeftMotor(left_motor)
                self.dualsense.setRightMotor(right_motor)
            except Exception: pass
