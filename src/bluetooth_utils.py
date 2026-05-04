"""
Utilidades Bluetooth para DualSense Controller
Gestiona la limpieza de cache y reinicio del servicio Bluetooth de Windows
via PowerShell para resolver problemas de conexion.
"""

import subprocess
import logging
import time
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class BluetoothManager:
    """Gestiona operaciones Bluetooth via PowerShell."""

    def __init__(self):
        self._cleanup_in_progress = False
        self._last_cleanup_time: Optional[float] = None
        self._status_callback: Optional[Callable[[str], None]] = None

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Registra un callback para recibir actualizaciones de estado."""
        self._status_callback = callback

    def _report_status(self, message: str) -> None:
        """Reporta estado via callback si esta disponible."""
        logger.info(message)
        if self._status_callback:
            try:
                self._status_callback(message)
            except Exception:
                pass

    def _run_powershell(self, command: str, description: str) -> tuple[bool, str]:
        """Ejecuta un comando PowerShell de forma segura."""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                self._report_status(f"✓ {description}")
                return True, result.stdout.strip()
            else:
                error_msg = result.stderr.strip() if result.stderr else "Error desconocido"
                self._report_status(f"✗ {description}: {error_msg}")
                return False, error_msg
        except subprocess.TimeoutExpired:
            self._report_status(f"✗ {description}: Timeout")
            return False, "Timeout"
        except Exception as e:
            self._report_status(f"✗ {description}: {str(e)}")
            return False, str(e)

    def restart_bluetooth_service(self) -> bool:
        """Reinicia el servicio de soporte Bluetooth de Windows."""
        self._report_status("Reiniciando servicio Bluetooth...")

        # Detener el servicio
        success, _ = self._run_powershell(
            "Stop-Service -Name 'bthserv' -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2",
            "Servicio Bluetooth detenido"
        )

        time.sleep(2)

        # Iniciar el servicio
        success, _ = self._run_powershell(
            "Start-Service -Name 'bthserv' -ErrorAction SilentlyContinue",
            "Servicio Bluetooth iniciado"
        )

        return success

    def remove_dualsense_pairing(self) -> bool:
        """Elimina el emparejamiento existente del DualSense."""
        self._report_status("Buscando emparejamientos de DualSense...")

        # Buscar dispositivos DualSense emparejados
        success, output = self._run_powershell(
            "Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -like '*DualSense*' -or $_.FriendlyName -like '*Wireless Controller*' } | Select-Object -ExpandProperty InstanceId",
            "Busqueda de DualSense emparentado"
        )

        if success and output:
            # Remover el dispositivo
            success, _ = self._run_powershell(
                f"Get-PnpDevice -Class Bluetooth | Where-Object {{ $_.FriendlyName -like '*DualSense*' -or $_.FriendlyName -like '*Wireless Controller*' }} | Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue",
                "Dispositivo DualSense deshabilitado"
            )
            time.sleep(1)
            success, _ = self._run_powershell(
                f"Get-PnpDevice -Class Bluetooth | Where-Object {{ $_.FriendlyName -like '*DualSense*' -or $_.FriendlyName -like '*Wireless Controller*' }} | Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue",
                "Dispositivo DualSense habilitado"
            )

        return success

    def clear_bluetooth_cache(self) -> bool:
        """Limpia la cache de dispositivos Bluetooth."""
        self._report_status("Limpiando cache Bluetooth...")

        commands = [
            ("Remove-Item -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys\\*' -Recurse -Force -ErrorAction SilentlyContinue", "Cache de claves limpiada"),
            ("Remove-Item -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Devices\\*' -Recurse -Force -ErrorAction SilentlyContinue", "Cache de dispositivos limpiada"),
        ]

        all_success = True
        for cmd, desc in commands:
            success, _ = self._run_powershell(cmd, desc)
            if not success:
                all_success = False

        return all_success

    def full_bluetooth_reset(self, callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Realiza un reinicio completo del Bluetooth:
        1. Remueve emparejamiento del DualSense
        2. Limpia cache
        3. Reinicia servicio
        """
        if self._cleanup_in_progress:
            self._report_status("Limpieza ya en progreso...")
            return False

        if callback:
            self._status_callback = callback

        self._cleanup_in_progress = True
        self._report_status("=== INICIANDO REINICIO BLUETOOTH ===")

        try:
            # Paso 1: Remover emparejamiento
            self.remove_dualsense_pairing()
            time.sleep(2)

            # Paso 2: Limpiar cache
            self.clear_bluetooth_cache()
            time.sleep(2)

            # Paso 3: Reiniciar servicio
            success = self.restart_bluetooth_service()
            time.sleep(3)

            self._last_cleanup_time = time.time()

            if success:
                self._report_status("=== REINICIO BLUETOOTH COMPLETADO ===")
            else:
                self._report_status("=== REINICIO BLUETOOTH CON ADVERTENCIAS ===")

            return success

        except Exception as e:
            self._report_status(f"Error en reinicio Bluetooth: {str(e)}")
            return False
        finally:
            self._cleanup_in_progress = False

    def is_cleanup_in_progress(self) -> bool:
        """Indica si una limpieza esta en progreso."""
        return self._cleanup_in_progress

    def get_last_cleanup_time(self) -> Optional[float]:
        """Devuelve el timestamp de la ultima limpieza."""
        return self._last_cleanup_time
