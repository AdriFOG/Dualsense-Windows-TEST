"""
Motor de Gatillos DualSense
Sistema de efectos hapticos en tiempo real para los gatillos L2/R2.
Soporta modos estaticos, animaciones en tiempo real y perfiles de armas.
"""

import logging
import time
import threading
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any

try:
    from pydualsense import TriggerModes
    PYDUALSENSE_AVAILABLE = True
except ImportError:
    PYDUALSENSE_AVAILABLE = False
    # Definir TriggerModes para modo simulacion
    class TriggerModes:
        Off = 0x00
        Rigid = 0x01
        Pulse = 0x02
        Rigid_A = 0x01
        Rigid_B = 0x02
        Rigid_AB = 0x03
        Pulse_A = 0x04
        Pulse_B = 0x05
        Pulse_AB = 0x06
        Calibration = 0xFC

logger = logging.getLogger(__name__)


class TriggerEffectType(Enum):
    """Tipos de efectos disponibles para los gatillos."""
    OFF = "off"
    RIGID = "rigid"
    PULSE = "pulse"
    CONTINUOUS_VIBRATION = "continuous_vibration"
    SECTIONS = "sections"
    WEAPON_SINGLE = "weapon_single"
    WEAPON_AUTOMATIC = "weapon_automatic"
    WEAPON_SNIPER = "weapon_sniper"
    WEAPON_BOW = "weapon_bow"
    CUSTOM = "custom"


@dataclass
class TriggerEffect:
    """Configuracion de un efecto de gatillo."""
    name: str
    effect_type: TriggerEffectType
    # Parametros generales
    intensity: int = 255  # 0-255
    start_position: int = 0  # 0-9 (zona donde inicia el efecto)
    end_position: int = 9   # 0-9 (zona donde termina el efecto)
    frequency: int = 0      # Para efectos pulsados/vibracion

    # Parametros especificos por tipo
    custom_params: Dict[str, Any] = field(default_factory=dict)

    # Animacion
    animated: bool = False
    animation_speed: float = 1.0  # Multiplicador de velocidad
    animation_curve: str = "linear"  # linear, ease_in, ease_out, sine

    def to_dict(self) -> dict:
        """Serializa el efecto a diccionario."""
        return {
            'name': self.name,
            'effect_type': self.effect_type.value,
            'intensity': self.intensity,
            'start_position': self.start_position,
            'end_position': self.end_position,
            'frequency': self.frequency,
            'custom_params': self.custom_params,
            'animated': self.animated,
            'animation_speed': self.animation_speed,
            'animation_curve': self.animation_curve,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TriggerEffect':
        """Deserializa un efecto desde diccionario."""
        return cls(
            name=data.get('name', 'Unknown'),
            effect_type=TriggerEffectType(data.get('effect_type', 'off')),
            intensity=data.get('intensity', 255),
            start_position=data.get('start_position', 0),
            end_position=data.get('end_position', 9),
            frequency=data.get('frequency', 0),
            custom_params=data.get('custom_params', {}),
            animated=data.get('animated', False),
            animation_speed=data.get('animation_speed', 1.0),
            animation_curve=data.get('animation_curve', 'linear'),
        )


@dataclass
class WeaponProfile:
    """Perfil completo de configuracion de armas."""
    name: str
    description: str
    left_trigger: TriggerEffect
    right_trigger: TriggerEffect
    rumble_intensity: int = 128
    icon: str = "🔫"
    category: str = "General"

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'left_trigger': self.left_trigger.to_dict(),
            'right_trigger': self.right_trigger.to_dict(),
            'rumble_intensity': self.rumble_intensity,
            'icon': self.icon,
            'category': self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WeaponProfile':
        return cls(
            name=data.get('name', 'Default'),
            description=data.get('description', ''),
            left_trigger=TriggerEffect.from_dict(data.get('left_trigger', {})),
            right_trigger=TriggerEffect.from_dict(data.get('right_trigger', {})),
            rumble_intensity=data.get('rumble_intensity', 128),
            icon=data.get('icon', '🔫'),
            category=data.get('category', 'General'),
        )


class TriggerEngine:
    """
    Motor de efectos de gatillo para DualSense.
    Gestiona efectos estaticos, animaciones en tiempo real y perfiles.
    """

    # Mapeo de curvas de animacion
    CURVES = {
        'linear': lambda t: t,
        'ease_in': lambda t: t * t,
        'ease_out': lambda t: 1 - (1 - t) * (1 - t),
        'ease_in_out': lambda t: 0.5 - 0.5 * math.cos(t * math.pi),
        'sine': lambda t: 0.5 + 0.5 * math.sin(t * 2 * math.pi - math.pi / 2),
        'bounce': lambda t: abs(math.sin(t * math.pi * 3)) * (1 - t) + t,
    }

    def __init__(self, connection_manager=None):
        self.connection_manager = connection_manager
        self.dualsense = None

        # Estado actual
        self._current_left_effect: Optional[TriggerEffect] = None
        self._current_right_effect: Optional[TriggerEffect] = None
        self._animation_running = False
        self._animation_thread: Optional[threading.Thread] = None
        self._animation_time = 0.0
        self._lock = threading.RLock()

        # Perfiles predefinidos
        self._profiles: Dict[str, WeaponProfile] = {}
        self._current_profile: Optional[str] = None
        self._init_default_profiles()

        # Callbacks
        self._on_effect_change: List[Callable[[str, TriggerEffect], None]] = []
        self._on_profile_change: List[Callable[[str], None]] = []

    def set_connection_manager(self, connection_manager) -> None:
        """Establece el gestor de conexion para enviar comandos al control."""
        self.connection_manager = connection_manager

    def on_effect_change(self, callback: Callable[[str, TriggerEffect], None]) -> None:
        """Registra callback para cambios de efecto."""
        self._on_effect_change.append(callback)

    def on_profile_change(self, callback: Callable[[str], None]) -> None:
        """Registra callback para cambios de perfil."""
        self._on_profile_change.append(callback)

    # ===== Inicialización de Perfiles =====

    def _init_default_profiles(self) -> None:
        """Crea los perfiles de armas predefinidos."""

        # 1. Rifle de Asalto - Gatillazo rapido con vibracion ligera
        self._profiles['assault_rifle'] = WeaponProfile(
            name="Rifle de Asalto",
            description="Gatillazo rapido con ligera resistencia. Ideal para disparos rapidos.",
            left_trigger=TriggerEffect(
                name="Apuntado Ligero",
                effect_type=TriggerEffectType.RIGID,
                intensity=100,
                start_position=0,
                end_position=4,
            ),
            right_trigger=TriggerEffect(
                name="Disparo Rapido",
                effect_type=TriggerEffectType.WEAPON_AUTOMATIC,
                intensity=180,
                start_position=2,
                end_position=7,
                frequency=8,
                animated=True,
                animation_speed=2.0,
            ),
            rumble_intensity=100,
            icon="🔫",
            category="Automaticas"
        )

        # 2. Francotirador - Mucha dureza inicial y quiebre seco
        self._profiles['sniper'] = WeaponProfile(
            name="Francotirador",
            description="Resistencia fuerte que se rompe de golpe. Simula el peso de un disparo pesado.",
            left_trigger=TriggerEffect(
                name="Zoom Tension",
                effect_type=TriggerEffectType.RIGID,
                intensity=200,
                start_position=0,
                end_position=5,
                animated=True,
                animation_speed=0.5,
            ),
            right_trigger=TriggerEffect(
                name="Disparo Pesado",
                effect_type=TriggerEffectType.WEAPON_SINGLE,
                intensity=255,
                start_position=4,
                end_position=9,
                frequency=1,
            ),
            rumble_intensity=200,
            icon="🎯",
            category="Precision"
        )

        # 3. Arco - Tension progresiva
        self._profiles['bow'] = WeaponProfile(
            name="Arco",
            description="Tension que aumenta gradualmente. Siente como se tensa la cuerda.",
            left_trigger=TriggerEffect(
                name="Apuntado Arco",
                effect_type=TriggerEffectType.RIGID,
                intensity=120,
                start_position=0,
                end_position=3,
            ),
            right_trigger=TriggerEffect(
                name="Tension Progresiva",
                effect_type=TriggerEffectType.SECTIONS,
                intensity=255,
                start_position=0,
                end_position=9,
                frequency=5,
                animated=True,
                animation_speed=1.5,
                animation_curve='ease_in',
                custom_params={'sections': [(0, 80), (2, 140), (4, 200), (7, 255)]},
            ),
            rumble_intensity=60,
            icon="🏹",
            category="Precision"
        )

        # 4. Pistola - Respuesta rapida y firme
        self._profiles['pistol'] = WeaponProfile(
            name="Pistola",
            description="Gatillo corto y firme. Respuesta inmediata.",
            left_trigger=TriggerEffect(
                name="Apuntado",
                effect_type=TriggerEffectType.OFF,
            ),
            right_trigger=TriggerEffect(
                name="Disparo Firme",
                effect_type=TriggerEffectType.RIGID,
                intensity=160,
                start_position=1,
                end_position=5,
            ),
            rumble_intensity=80,
            icon="🔫",
            category="Pistolas"
        )

        # 5. Escopeta - Resistencia fuerte y retroceso
        self._profiles['shotgun'] = WeaponProfile(
            name="Escopeta",
            description="Resistencia maxima con vibracion de retroceso.",
            left_trigger=TriggerEffect(
                name="Apuntado",
                effect_type=TriggerEffectType.RIGID,
                intensity=150,
                start_position=0,
                end_position=4,
            ),
            right_trigger=TriggerEffect(
                name="Retroceso",
                effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
                intensity=255,
                start_position=0,
                end_position=9,
                frequency=12,
                animated=True,
                animation_speed=3.0,
                animation_curve='bounce',
            ),
            rumble_intensity=255,
            icon="💥",
            category="Pesadas"
        )

        # 6. SMG - Vibracion rapida continua
        self._profiles['smg'] = WeaponProfile(
            name="Subfusil",
            description="Vibracion rapida y constante. Simula cadencia alta.",
            left_trigger=TriggerEffect(
                name="Apuntado Ligero",
                effect_type=TriggerEffectType.RIGID,
                intensity=80,
                start_position=0,
                end_position=3,
            ),
            right_trigger=TriggerEffect(
                name="Cadencia Rapida",
                effect_type=TriggerEffectType.PULSE,
                intensity=200,
                start_position=1,
                end_position=8,
                frequency=15,
                animated=True,
                animation_speed=4.0,
            ),
            rumble_intensity=120,
            icon="🔫",
            category="Automaticas"
        )

        # 7. LMG - Resistencia creciente
        self._profiles['lmg'] = WeaponProfile(
            name="Ametralladora",
            description="Resistencia que aumenta con el tiempo. Simula calentamiento.",
            left_trigger=TriggerEffect(
                name="Apuntado",
                effect_type=TriggerEffectType.RIGID,
                intensity=130,
                start_position=0,
                end_position=5,
            ),
            right_trigger=TriggerEffect(
                name="Calentamiento",
                effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
                intensity=180,
                start_position=2,
                end_position=9,
                frequency=6,
                animated=True,
                animation_speed=0.8,
                animation_curve='ease_in',
            ),
            rumble_intensity=180,
            icon="🔥",
            category="Pesadas"
        )

        # 8. Apagado - Sin efectos
        self._profiles['off'] = WeaponProfile(
            name="Apagado",
            description="Sin efectos de gatillo. Gatillos libres.",
            left_trigger=TriggerEffect(
                name="Libre",
                effect_type=TriggerEffectType.OFF,
            ),
            right_trigger=TriggerEffect(
                name="Libre",
                effect_type=TriggerEffectType.OFF,
            ),
            rumble_intensity=0,
            icon="○",
            category="General"
        )

        logger.info(f"Inicializados {len(self._profiles)} perfiles de armas")

    def get_all_profiles(self) -> Dict[str, WeaponProfile]:
        """Devuelve todos los perfiles disponibles."""
        return dict(self._profiles)

    def get_profile(self, profile_id: str) -> Optional[WeaponProfile]:
        """Obtiene un perfil por su ID."""
        return self._profiles.get(profile_id)

    def get_profile_names(self) -> List[tuple[str, str]]:
        """Devuelve lista de (id, nombre) de perfiles."""
        return [(k, v.name) for k, v in self._profiles.items()]

    def add_custom_profile(self, profile_id: str, profile: WeaponProfile) -> None:
        """Agrega un perfil personalizado."""
        self._profiles[profile_id] = profile
        logger.info(f"Perfil personalizado agregado: {profile_id}")

    def remove_profile(self, profile_id: str) -> bool:
        """Elimina un perfil (no permite eliminar los predefinidos 'off')."""
        if profile_id in self._profiles and profile_id != 'off':
            del self._profiles[profile_id]
            return True
        return False

    # ===== Aplicación de Efectos =====

    def apply_effect(self, trigger: str, effect: TriggerEffect) -> bool:
        """
        Aplica un efecto a un gatillo.
        trigger: 'left' o 'right'
        """
        if not self._can_send_commands():
            return False

        try:
            ds = self.connection_manager.dualsense_instance
            if not ds:
                return False

            with self._lock:
                if trigger == 'left':
                    self._current_left_effect = effect
                    self._send_trigger_command(ds, 'left', effect)
                elif trigger == 'right':
                    self._current_right_effect = effect
                    self._send_trigger_command(ds, 'right', effect)
                else:
                    logger.warning(f"Gatillo desconocido: {trigger}")
                    return False

            # Notificar cambio
            self._notify_effect_change(trigger, effect)

            # Manejar animacion
            if effect.animated:
                self._start_animation()

            return True

        except Exception as e:
            logger.error(f"Error aplicando efecto: {e}")
            return False

    def apply_profile(self, profile_id: str) -> bool:
        """Aplica un perfil completo de arma."""
        profile = self._profiles.get(profile_id)
        if not profile:
            logger.warning(f"Perfil no encontrado: {profile_id}")
            return False

        try:
            # Aplicar efecto al gatillo izquierdo
            self.apply_effect('left', profile.left_trigger)

            # Aplicar efecto al gatillo derecho
            self.apply_effect('right', profile.right_trigger)

            # Aplicar vibracion base si hay connection manager
            if self.connection_manager and profile.rumble_intensity > 0:
                self.connection_manager.set_rumble(
                    profile.rumble_intensity // 2,
                    profile.rumble_intensity
                )

            self._current_profile = profile_id

            # Notificar
            for callback in self._on_profile_change:
                try:
                    callback(profile_id)
                except Exception:
                    pass

            logger.info(f"Perfil aplicado: {profile.name}")
            return True

        except Exception as e:
            logger.error(f"Error aplicando perfil: {e}")
            return False

    def get_current_profile(self) -> Optional[str]:
        """Devuelve el ID del perfil actual."""
        return self._current_profile

    def reset_triggers(self) -> None:
        """Apaga los efectos de ambos gatillos."""
        off_effect = TriggerEffect("Off", TriggerEffectType.OFF)
        self.apply_effect('left', off_effect)
        self.apply_effect('right', off_effect)
        self._stop_animation()

    # ===== Comandos de Bajo Nivel =====

    def _send_trigger_command(self, ds, trigger: str, effect: TriggerEffect) -> None:
        """Envia el comando de efecto al control."""
        if not PYDUALSENSE_AVAILABLE:
            return

        try:
            # Seleccionar metodo segun el gatillo
            if trigger == 'left':
                set_mode = ds.setLeftTriggerMode if hasattr(ds, 'setLeftTriggerMode') else None
                set_force = ds.setLeftTriggerForce if hasattr(ds, 'setLeftTriggerForce') else None
            else:
                set_mode = ds.setRightTriggerMode if hasattr(ds, 'setRightTriggerMode') else None
                set_force = ds.setRightTriggerForce if hasattr(ds, 'setRightTriggerForce') else None

            if not set_mode:
                return

            # Mapear tipo de efecto a modo del control
            mode = self._map_effect_to_mode(effect)
            set_mode(mode)

            # Aplicar fuerza si el metodo existe
            if set_force:
                # Calcular parametros de fuerza
                force_params = self._calculate_force_params(effect)
                try:
                    if len(force_params) == 1:
                        set_force(force_params[0])
                    elif len(force_params) == 2:
                        set_force(force_params[0], force_params[1])
                    elif len(force_params) >= 3:
                        set_force(force_params[0], force_params[1], force_params[2])
                except TypeError:
                    # Fallback: intentar con un solo parametro
                    set_force(effect.intensity)

        except Exception as e:
            logger.warning(f"Error enviando comando de gatillo: {e}")

    def _map_effect_to_mode(self, effect: TriggerEffect) -> int:
        """Mapea un TriggerEffectType al modo correspondiente del DualSense."""
        mode_map = {
            TriggerEffectType.OFF: TriggerModes.Off,
            TriggerEffectType.RIGID: TriggerModes.Rigid,
            TriggerEffectType.PULSE: TriggerModes.Pulse,
            TriggerEffectType.CONTINUOUS_VIBRATION: TriggerModes.Pulse,
            TriggerEffectType.SECTIONS: TriggerModes.Rigid_AB,
            TriggerEffectType.WEAPON_SINGLE: TriggerModes.Rigid,
            TriggerEffectType.WEAPON_AUTOMATIC: TriggerModes.Pulse,
            TriggerEffectType.WEAPON_SNIPER: TriggerModes.Rigid,
            TriggerEffectType.WEAPON_BOW: TriggerModes.Rigid_AB,
            TriggerEffectType.CUSTOM: TriggerModes.Rigid_AB,
        }
        return mode_map.get(effect.effect_type, TriggerModes.Off)

    def _calculate_force_params(self, effect: TriggerEffect) -> List[int]:
        """Calcula los parametros de fuerza segun el tipo de efecto."""
        params = []

        if effect.effect_type == TriggerEffectType.OFF:
            params = [0]

        elif effect.effect_type == TriggerEffectType.RIGID:
            # Rigid: fuerza uniforme
            start_force = int((effect.intensity / 255) * 9)
            start_force = max(effect.start_position, min(9, start_force))
            params = [start_force, effect.intensity]

        elif effect.effect_type == TriggerEffectType.PULSE:
            # Pulse: fuerza pulsada
            params = [effect.start_position, effect.intensity, effect.frequency]

        elif effect.effect_type == TriggerEffectType.CONTINUOUS_VIBRATION:
            # Vibracion continua: alta frecuencia
            params = [effect.start_position, effect.intensity, max(8, effect.frequency)]

        elif effect.effect_type in (TriggerEffectType.SECTIONS, TriggerEffectType.WEAPON_BOW):
            # Efectos por secciones
            sections = effect.custom_params.get('sections', [])
            if sections:
                # Usar las secciones definidas
                for pos, force in sections[:4]:  # Max 4 secciones
                    params.extend([pos, min(255, force)])
            else:
                # Generar secciones gradiente
                steps = effect.end_position - effect.start_position + 1
                for i in range(min(steps, 4)):
                    pos = effect.start_position + i * 2
                    force = int(effect.intensity * (i + 1) / min(steps, 4))
                    params.extend([pos, force])

        elif effect.effect_type == TriggerEffectType.WEAPON_SINGLE:
            # Disparo unico: resistencia fuerte en la mitad final
            params = [
                effect.start_position,
                effect.intensity // 3,
                effect.start_position + 2,
                effect.intensity,
            ]

        elif effect.effect_type == TriggerEffectType.WEAPON_AUTOMATIC:
            # Automatica: pulsos rapidos
            params = [
                effect.start_position,
                effect.intensity,
                max(5, effect.frequency),
            ]

        elif effect.effect_type == TriggerEffectType.WEAPON_SNIPER:
            # Francotirador: resistencia fuerte, quiebre seco
            params = [
                effect.start_position,
                effect.intensity,
                effect.end_position - 1,
                effect.intensity // 4,
            ]

        else:
            params = [effect.intensity]

        return params

    # ===== Animación en Tiempo Real =====

    def _start_animation(self) -> None:
        """Inicia el hilo de animacion si no esta corriendo."""
        if self._animation_running:
            return

        self._animation_running = True
        self._animation_time = 0.0

        self._animation_thread = threading.Thread(
            target=self._animation_loop,
            name="TriggerAnimation",
            daemon=True
        )
        self._animation_thread.start()
        logger.debug("Animacion de gatillos iniciada")

    def _stop_animation(self) -> None:
        """Detiene el hilo de animacion."""
        self._animation_running = False
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=0.5)
        self._animation_thread = None

    def _animation_loop(self) -> None:
        """Bucle de animacion en tiempo real."""
        last_time = time.time()

        while self._animation_running:
            try:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time

                with self._lock:
                    self._animation_time += dt

                    # Actualizar efectos animados
                    if self._current_left_effect and self._current_left_effect.animated:
                        self._update_animated_effect('left', self._current_left_effect, dt)

                    if self._current_right_effect and self._current_right_effect.animated:
                        self._update_animated_effect('right', self._current_right_effect, dt)

                # 60Hz para animacion
                time.sleep(1 / 60)

            except Exception as e:
                logger.error(f"Error en animacion: {e}")
                time.sleep(0.1)

    def _update_animated_effect(self, trigger: str, effect: TriggerEffect, dt: float) -> None:
        """Actualiza un efecto animado basado en el tiempo."""
        if not self.connection_manager:
            return

        ds = self.connection_manager.dualsense_instance
        if not ds:
            return

        # Calcular progreso de la animacion (0-1 ciclico)
        cycle_duration = 2.0 / effect.animation_speed
        progress = (self._animation_time % cycle_duration) / cycle_duration

        # Aplicar curva
        curve_func = self.CURVES.get(effect.animation_curve, self.CURVES['linear'])
        curved_progress = curve_func(progress)

        # Crear efecto modificado
        modified_effect = TriggerEffect(
            name=effect.name,
            effect_type=effect.effect_type,
            intensity=int(effect.intensity * (0.3 + 0.7 * curved_progress)),
            start_position=effect.start_position,
            end_position=effect.end_position,
            frequency=int(effect.frequency * (0.5 + curved_progress)) if effect.frequency > 0 else 0,
            custom_params=effect.custom_params,
        )

        # Enviar comando actualizado (throttle para no saturar Bluetooth)
        self._send_trigger_command(ds, trigger, modified_effect)

    # ===== Lectura de Posición de Gatillos =====

    def get_trigger_position(self, trigger: str) -> int:
        """
        Obtiene la posicion actual de un gatillo (0-255).
        """
        if not self.connection_manager:
            return 0

        state = self.connection_manager.state
        if trigger == 'left':
            return state.left_trigger
        elif trigger == 'right':
            return state.right_trigger
        return 0

    def is_trigger_pressed(self, trigger: str, threshold: int = 20) -> bool:
        """Verifica si un gatillo esta presionado mas del umbral."""
        return self.get_trigger_position(trigger) > threshold

    # ===== Utilidades =====

    def _can_send_commands(self) -> bool:
        """Verifica si se pueden enviar comandos al control."""
        return (self.connection_manager is not None and
                self.connection_manager.is_connected and
                self.connection_manager.dualsense_instance is not None)

    def _notify_effect_change(self, trigger: str, effect: TriggerEffect) -> None:
        """Notifica cambio de efecto."""
        for callback in self._on_effect_change:
            try:
                callback(trigger, effect)
            except Exception:
                pass

    def get_current_effects(self) -> Dict[str, Optional[TriggerEffect]]:
        """Devuelve los efectos actuales aplicados."""
        with self._lock:
            return {
                'left': self._current_left_effect,
                'right': self._current_right_effect,
            }

    def load_profiles_from_dict(self, profiles_data: Dict[str, dict]) -> None:
        """Carga perfiles desde un diccionario (para importar configuraciones)."""
        for profile_id, data in profiles_data.items():
            try:
                profile = WeaponProfile.from_dict(data)
                self._profiles[profile_id] = profile
            except Exception as e:
                logger.warning(f"Error cargando perfil {profile_id}: {e}")

    def export_profiles_to_dict(self) -> Dict[str, dict]:
        """Exporta todos los perfiles a diccionario (para guardar configuraciones)."""
        result = {}
        for profile_id, profile in self._profiles.items():
            result[profile_id] = profile.to_dict()
        return result

    def stop(self) -> None:
        """Detiene el motor de gatillos y limpia recursos."""
        self._stop_animation()
        self.reset_triggers()
        logger.info("TriggerEngine detenido")
