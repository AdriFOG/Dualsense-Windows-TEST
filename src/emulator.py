"""
Motor de Emulacion de Controles
Traduce las entradas fisicas del DualSense a un control virtual de Xbox 360 o PS4
usando ViGEmBus (via vgamepad).
"""

import logging
from enum import Enum

try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    VGAMEPAD_AVAILABLE = False
    logging.warning("Libreria vgamepad no encontrada. La emulacion estara desactivada.")

logger = logging.getLogger(__name__)


class EmulationMode(Enum):
    NONE = "none"
    XBOX = "xbox"
    PS4 = "ps4"


class EmulatorManager:
    def __init__(self):
        self.mode = EmulationMode.NONE
        self.gamepad = None
        self.is_active = False

    def set_mode(self, mode: EmulationMode) -> bool:
        """Cambia el tipo de control virtual emulado."""
        if not VGAMEPAD_AVAILABLE:
            logger.error("No se puede emular: vgamepad no esta instalado.")
            return False

        # Si ya estabamos emulando, desconectamos el anterior
        if self.gamepad:
            try:
                self.gamepad.update() # Forzar liberacion
                del self.gamepad
                self.gamepad = None
            except Exception as e:
                logger.error(f"Error cerrando gamepad virtual: {e}")

        self.mode = mode
        self.is_active = False

        if mode == EmulationMode.NONE:
            logger.info("Emulacion desactivada.")
            return True

        try:
            if mode == EmulationMode.XBOX:
                self.gamepad = vg.VX360Gamepad()
                logger.info("Control virtual de Xbox 360 creado.")
            elif mode == EmulationMode.PS4:
                self.gamepad = vg.VDS4Gamepad()
                logger.info("Control virtual de PS4 creado.")
            
            self.is_active = True
            return True
        except Exception as e:
            logger.error(f"Error creando control virtual (¿Falta ViGEmBus?): {e}")
            self.mode = EmulationMode.NONE
            return False

    def update_from_dualsense(self, state) -> None:
        """Recibe el estado real del DualSense y lo inyecta en el control virtual."""
        if not self.is_active or not self.gamepad:
            return

        try:
            if self.mode == EmulationMode.XBOX:
                self._update_xbox(state)
            elif self.mode == EmulationMode.PS4:
                self._update_ps4(state)
        except Exception as e:
            pass # Silenciar para no inundar la consola a 60 FPS

    def _update_xbox(self, state):
        """Mapeo matematico de DualSense a Xbox 360"""
        gp = self.gamepad

        # 1. Botones principales
        if state.buttons.get('cross'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)

        if state.buttons.get('circle'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)

        if state.buttons.get('square'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)

        if state.buttons.get('triangle'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)

        # 2. Bumpers y Sticks (clicks)
        if state.buttons.get('L1'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)

        if state.buttons.get('R1'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)

        if state.buttons.get('L3'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)

        if state.buttons.get('R3'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)

        # 3. Botones de Menu
        if state.buttons.get('options'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_START)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_START)

        if state.buttons.get('create'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)

        # 4. D-PAD (Cruceta)
        if state.buttons.get('dpad_up'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)

        if state.buttons.get('dpad_down'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)

        if state.buttons.get('dpad_left'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)

        if state.buttons.get('dpad_right'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
        else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)

        # 5. Gatillos (Convertir 0-255 a flotante 0.0 - 1.0)
        gp.left_trigger_float(value_float=state.left_trigger / 255.0)
        gp.right_trigger_float(value_float=state.right_trigger / 255.0)

        # 6. Joysticks (Convertir 0-255 de PlayStation a -32768 a 32767 de Xbox)
        lx_val = int((state.left_stick_x / 255.0) * 65535) - 32768
        ly_val = int((state.left_stick_y / 255.0) * 65535) - 32768
        rx_val = int((state.right_stick_x / 255.0) * 65535) - 32768
        ry_val = int((state.right_stick_y / 255.0) * 65535) - 32768

        # En Xbox, el eje Y esta invertido respecto al DualSense
        gp.left_joystick(x_value=lx_val, y_value=-ly_val - 1)
        gp.right_joystick(x_value=rx_val, y_value=-ry_val - 1)

        # ENVIAR ESTADO AL SISTEMA OPERATIVO
        gp.update()

    def _update_ps4(self, state):
        """Mapeo matematico de DualSense a DualShock 4"""
        gp = self.gamepad

        # El mapeo de PS5 a PS4 es 1 a 1 casi directo
        if state.buttons.get('cross'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CROSS)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CROSS)

        if state.buttons.get('circle'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE)

        if state.buttons.get('square'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SQUARE)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SQUARE)

        if state.buttons.get('triangle'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)

        if state.buttons.get('L1'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT)

        if state.buttons.get('R1'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT)

        if state.buttons.get('options'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS)

        if state.buttons.get('create'): gp.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHARE)
        else: gp.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_SHARE)
        
        # D-PAD especial en PS4
        if state.buttons.get('dpad_up'):
            if state.buttons.get('dpad_right'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST)
            elif state.buttons.get('dpad_left'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST)
            else: gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH)
        elif state.buttons.get('dpad_down'):
            if state.buttons.get('dpad_right'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST)
            elif state.buttons.get('dpad_left'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST)
            else: gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH)
        elif state.buttons.get('dpad_right'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST)
        elif state.buttons.get('dpad_left'): gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST)
        else: gp.directional_pad(direction=vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE)

        # Gatillos y Joysticks (Escala 0-255 directa)
        gp.left_trigger(value=state.left_trigger)
        gp.right_trigger(value=state.right_trigger)
        
        gp.left_joystick(x_value=state.left_stick_x, y_value=state.left_stick_y)
        gp.right_joystick(x_value=state.right_stick_x, y_value=state.right_stick_y)

        gp.update()