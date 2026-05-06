"""
Motor de Emulacion de Controles
Traduce las entradas fisicas del DualSense a un control virtual de Xbox 360 o PS4 usando ViGEmBus (via vgamepad).
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
        if not VGAMEPAD_AVAILABLE:
            logger.error("No se puede emular: vgamepad no esta instalado.")
            return False

        if self.gamepad:
            try:
                self.gamepad.update() 
                del self.gamepad
                self.gamepad = None
            except Exception as e:
                pass

        self.mode = mode
        self.is_active = False

        if mode == EmulationMode.NONE:
            return True

        try:
            if mode == EmulationMode.XBOX:
                self.gamepad = vg.VX360Gamepad()
            elif mode == EmulationMode.PS4:
                self.gamepad = vg.VDS4Gamepad()
                
            self.is_active = True
            return True
        except Exception as e:
            logger.error(f"Error creando control virtual: {e}")
            self.mode = EmulationMode.NONE
            return False

    def update_from_dualsense(self, state) -> None:
        if not self.is_active or not self.gamepad:
            return

        try:
            if self.mode == EmulationMode.XBOX:
                self._update_xbox(state)
            elif self.mode == EmulationMode.PS4:
                self._update_ps4(state)
        except Exception:
            pass

    def _update_xbox(self, state):
        gp = self.gamepad

        try:
            if state.buttons.get('cross'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
            if state.buttons.get('circle'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
            if state.buttons.get('square'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
            if state.buttons.get('triangle'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)

            if state.buttons.get('L1'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
            if state.buttons.get('R1'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
            if state.buttons.get('L3'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
            if state.buttons.get('R3'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)

            if state.buttons.get('options'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_START)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_START)
            if state.buttons.get('create'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)

            if state.buttons.get('dpad_up'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
            if state.buttons.get('dpad_down'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
            if state.buttons.get('dpad_left'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
            if state.buttons.get('dpad_right'): gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
            else: gp.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
        except: pass

        try:
            gp.left_trigger(value=int(max(0, min(255, state.left_trigger))))
            gp.right_trigger(value=int(max(0, min(255, state.right_trigger))))
        except: pass

        try:
            # Multiplicamos para mapear el 0-255 a la escala gigante de Xbox. 
            # Xbox tiene el eje Y invertido, se resta de 128 para invertirlo.
            lx = int((state.left_stick_x - 128) * 256)
            ly = int((128 - state.left_stick_y) * 256) 
            rx = int((state.right_stick_x - 128) * 256)
            ry = int((128 - state.right_stick_y) * 256)

            gp.left_joystick(x_value=max(-32768, min(32767, lx)), y_value=max(-32768, min(32767, ly)))
            gp.right_joystick(x_value=max(-32768, min(32767, rx)), y_value=max(-32768, min(32767, ry)))
        except: pass

        try: gp.update()
        except: pass

    def _update_ps4(self, state):
        gp = self.gamepad

        try:
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
        except: pass

        try:
            gp.left_trigger(value=int(max(0, min(255, state.left_trigger))))
            gp.right_trigger(value=int(max(0, min(255, state.right_trigger))))
        except: pass
            
        try:
            gp.left_joystick(x_value=int(max(0, min(255, state.left_stick_x))), y_value=int(max(0, min(255, state.left_stick_y))))
            gp.right_joystick(x_value=int(max(0, min(255, state.right_stick_x))), y_value=int(max(0, min(255, state.right_stick_y))))
        except: pass

        try: gp.update()
        except: pass
