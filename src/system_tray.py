"""
Modo Bandeja del Sistema
Permite minimizar la aplicacion a la bandeja de Windows en lugar de cerrarla.
"""

import logging
import os
import sys
import threading
from typing import Optional, Callable, List

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

logger = logging.getLogger(__name__)


class TrayManager:
    """
    Gestiona el icono y menu de la bandeja del sistema.
    Permite que la aplicacion corra en segundo plano.
    """

    def __init__(self, app_name: str = "DualSense Controller"):
        self.app_name = app_name
        self.icon: Optional['pystray.Icon'] = None
        self._visible = False
        self._status_text = "Desconectado"
        self._battery_text = ""
        self._profile_text = ""

        # Callbacks
        self._on_show_window: List[Callable[[], None]] = []
        self._on_exit: List[Callable[[], None]] = []
        self._on_profile_select: List[Callable[[str], None]] = []

        # Perfiles para el menu
        self._profiles: List[tuple[str, str]] = []
        self._current_profile: Optional[str] = None

    # ===== Callbacks =====

    def on_show_window(self, callback: Callable[[], None]) -> None:
        """Registra callback para mostrar la ventana principal."""
        self._on_show_window.append(callback)

    def on_exit(self, callback: Callable[[], None]) -> None:
        """Registra callback para salir de la aplicacion."""
        self._on_exit.append(callback)

    def on_profile_select(self, callback: Callable[[str], None]) -> None:
        """Registra callback para seleccion de perfil desde tray."""
        self._on_profile_select.append(callback)

    # ===== Estado =====

    def set_status(self, text: str) -> None:
        """Actualiza el texto de estado."""
        self._status_text = text
        self._update_tooltip()

    def set_battery(self, level: int, charging: bool = False) -> None:
        """Actualiza la informacion de bateria."""
        icon = "🔌" if charging else "🔋"
        self._battery_text = f"{icon} {level}%"
        self._update_tooltip()

    def set_current_profile(self, profile_id: Optional[str]) -> None:
        """Actualiza el perfil actual."""
        self._current_profile = profile_id

    def set_profiles(self, profiles: List[tuple[str, str]]) -> None:
        """Actualiza la lista de perfiles para el menu."""
        self._profiles = profiles
        self._rebuild_menu()

    # ===== Gestión del Icono =====

    def _create_icon_image(self, width: int = 64, height: int = 64) -> 'Image.Image':
        """Crea la imagen del icono de la bandeja."""
        # Crear imagen con fondo transparente
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Dibujar un icono de control estilizado
        margin = 4
        body_color = (0, 150, 255, 255)  # Azul DualSense
        accent_color = (255, 255, 255, 255)

        # Forma del control (simplificada)
        # Cuerpo principal
        body_left = margin
        body_top = height // 4
        body_right = width - margin
        body_bottom = height - margin

        draw.rounded_rectangle(
            [body_left, body_top, body_right, body_bottom],
            radius=8,
            fill=body_color
        )

        # Botones (representados como circulos)
        btn_y = body_top + (body_bottom - body_top) // 3
        btn_radius = 4

        # Boton izquierdo
        draw.ellipse(
            [body_left + 8, btn_y - btn_radius,
             body_left + 8 + btn_radius * 2, btn_y + btn_radius],
            fill=accent_color
        )

        # Boton derecho
        draw.ellipse(
            [body_right - 8 - btn_radius * 2, btn_y - btn_radius,
             body_right - 8, btn_y + btn_radius],
            fill=accent_color
        )

        # Stick analogico
        stick_y = body_top + 2 * (body_bottom - body_top) // 3
        draw.ellipse(
            [width // 2 - 6, stick_y - 6,
             width // 2 + 6, stick_y + 6],
            fill=accent_color
        )

        return image

    def _update_tooltip(self) -> None:
        """Actualiza el tooltip del icono."""
        if self.icon:
            tooltip = f"{self.app_name}\n{self._status_text}"
            if self._battery_text:
                tooltip += f"\n{self._battery_text}"
            if self._profile_text:
                tooltip += f"\nPerfil: {self._profile_text}"
            self.icon.title = tooltip

    def _separator(self):
        """Crea un item separador para el menu."""
        return pystray.MenuItem('', lambda: None, enabled=False)

    def _build_menu(self) -> 'pystray.Menu':
        """Construye el menu contextual de la bandeja."""
        items = []

        # Estado
        items.append(pystray.MenuItem(
            f"Estado: {self._status_text}",
            lambda: None,
            enabled=False
        ))

        if self._battery_text:
            items.append(pystray.MenuItem(
                self._battery_text,
                lambda: None,
                enabled=False
            ))

        items.append(self._separator())

        # Perfiles (submenu)
        if self._profiles:
            profile_items = []
            for profile_id, profile_name in self._profiles:
                is_current = profile_id == self._current_profile
                label = f"{'✓ ' if is_current else ''}{profile_name}"
                profile_items.append(pystray.MenuItem(
                    label,
                    lambda pid=profile_id: self._select_profile(pid)
                ))

            items.append(pystray.MenuItem("Perfiles", pystray.Menu(*profile_items)))
            items.append(self._separator())

        # Mostrar ventana
        items.append(pystray.MenuItem(
            "Mostrar Ventana",
            self._show_window
        ))

        items.append(self._separator())

        # Salir
        items.append(pystray.MenuItem(
            "Salir",
            self._exit_app
        ))

        return pystray.Menu(*items)

    def _rebuild_menu(self) -> None:
        """Reconstruye el menu del icono."""
        if self.icon:
            try:
                self.icon.menu = self._build_menu()
                if hasattr(self.icon, 'update_menu'):
                    self.icon.update_menu()
            except Exception as e:
                logger.debug(f"No se pudo reconstruir menu: {e}")

    # ===== Acciones =====

    def _show_window(self) -> None:
        """Muestra la ventana principal."""
        for callback in self._on_show_window:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error en callback show_window: {e}")

    def _exit_app(self) -> None:
        """Cierra la aplicacion completamente."""
        self.stop()
        for callback in self._on_exit:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error en callback exit: {e}")

    def _select_profile(self, profile_id: str) -> None:
        """Selecciona un perfil desde el menu de la bandeja."""
        for callback in self._on_profile_select:
            try:
                callback(profile_id)
            except Exception as e:
                logger.error(f"Error en callback profile_select: {e}")

    # ===== Ciclo de Vida =====

    def start(self) -> None:
        """Inicia el icono de la bandeja."""
        if not PYSTRAY_AVAILABLE:
            logger.warning("pystray no disponible. Modo bandeja desactivado.")
            return

        if self._visible:
            return

        try:
            icon_image = self._create_icon_image()
            self.icon = pystray.Icon(
                "dualsense_controller",
                icon_image,
                title=self.app_name,
                menu=self._build_menu()
            )

            # Iniciar en un hilo separado
            tray_thread = threading.Thread(
                target=self.icon.run,
                name="SystemTray",
                daemon=True
            )
            tray_thread.start()

            self._visible = True
            logger.info("Icono de bandeja iniciado")

        except Exception as e:
            logger.error(f"Error iniciando bandeja del sistema: {e}")

    def stop(self) -> None:
        """Detiene el icono de la bandeja."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None

        self._visible = False
        logger.info("Icono de bandeja detenido")

    def is_visible(self) -> bool:
        """Indica si el icono de la bandeja esta visible."""
        return self._visible

    def update(self) -> None:
        """Actualiza el menu y tooltip del icono."""
        self._rebuild_menu()
        self._update_tooltip()
