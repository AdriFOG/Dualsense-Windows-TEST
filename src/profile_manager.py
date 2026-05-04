"""
Gestor de Perfiles - Sistema de Guardado/Carga
Maneja la persistencia de configuraciones en archivos JSON.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import asdict

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Gestiona el guardado y carga de perfiles de configuracion.
    Almacena todo en un archivo JSON estructurado.
    """

    DEFAULT_CONFIG = {
        'version': '1.0',
        'active_profile': 'assault_rifle',
        'profiles': {},  # Se llenan desde TriggerEngine
        'settings': {
            'start_minimized': False,
            'minimize_to_tray': True,
            'auto_connect': True,
            'led_color': [0, 100, 255],  # RGB
            'player_number': 1,
            'vibration_enabled': True,
            'trigger_intensity_multiplier': 1.0,
            'bluetooth_auto_reset': False,
            'theme': 'dark',
            'language': 'es',
            'window_geometry': {
                'width': 900,
                'height': 650,
                'x': None,
                'y': None,
            }
        },
        'custom_profiles': {},
        'favorites': ['assault_rifle', 'sniper', 'bow'],
    }

    def __init__(self, config_dir: Optional[str] = None):
        # Directorio de configuracion
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # %APPDATA%/DualSenseController
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.config_dir = Path(appdata) / 'DualSenseController'

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'profiles.json'
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)

        # Estado en memoria
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Carga la configuracion desde el archivo JSON."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)

                # Fusionar con defaults (para nuevas claves)
                self._config = self._merge_with_defaults(loaded)
                logger.info(f"Configuracion cargada desde: {self.config_file}")

            except json.JSONDecodeError as e:
                logger.error(f"Error decodificando JSON: {e}")
                self._restore_backup()
            except Exception as e:
                logger.error(f"Error cargando configuracion: {e}")
                self._config = dict(self.DEFAULT_CONFIG)
        else:
            logger.info("No se encontro configuracion previa. Usando defaults.")
            self._config = dict(self.DEFAULT_CONFIG)
            self.save_config()

    def _merge_with_defaults(self, loaded: dict) -> dict:
        """Fusiona configuracion cargada con valores por defecto."""
        merged = dict(self.DEFAULT_CONFIG)

        def deep_merge(base: dict, override: dict) -> dict:
            result = dict(base)
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(merged, loaded)

    def save_config(self) -> bool:
        """Guarda la configuracion actual al archivo JSON."""
        try:
            # Crear backup antes de guardar
            self._create_backup()

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)

            logger.info("Configuracion guardada exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error guardando configuracion: {e}")
            return False

    def _create_backup(self) -> None:
        """Crea un backup de la configuracion actual."""
        try:
            if self.config_file.exists():
                import shutil
                from datetime import datetime

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = self.backup_dir / f'profiles_backup_{timestamp}.json'

                shutil.copy2(self.config_file, backup_file)

                # Mantener solo los ultimos 10 backups
                backups = sorted(self.backup_dir.glob('profiles_backup_*.json'))
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        old_backup.unlink()

        except Exception as e:
            logger.warning(f"No se pudo crear backup: {e}")

    def _restore_backup(self) -> None:
        """Intenta restaurar desde el backup mas reciente."""
        try:
            backups = sorted(self.backup_dir.glob('profiles_backup_*.json'))
            if backups:
                latest = backups[-1]
                with open(latest, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"Configuracion restaurada desde backup: {latest}")
            else:
                self._config = dict(self.DEFAULT_CONFIG)
        except Exception as e:
            logger.error(f"Error restaurando backup: {e}")
            self._config = dict(self.DEFAULT_CONFIG)

    # ===== Getters =====

    def get_active_profile(self) -> str:
        """Devuelve el ID del perfil activo."""
        return self._config.get('active_profile', 'assault_rifle')

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de configuracion."""
        keys = key.split('.')
        value = self._config.get('settings', {})
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_custom_profiles(self) -> Dict[str, dict]:
        """Devuelve los perfiles personalizados guardados."""
        return self._config.get('custom_profiles', {})

    def get_favorites(self) -> list:
        """Devuelve la lista de perfiles favoritos."""
        return self._config.get('favorites', [])

    # ===== Setters =====

    def set_active_profile(self, profile_id: str) -> None:
        """Establece el perfil activo."""
        self._config['active_profile'] = profile_id

    def set_setting(self, key: str, value: Any) -> None:
        """Establece un valor de configuracion."""
        keys = key.split('.')
        settings = self._config.setdefault('settings', {})

        # Navegar hasta el penultimo nivel
        for k in keys[:-1]:
            settings = settings.setdefault(k, {})

        settings[keys[-1]] = value

    def set_custom_profiles(self, profiles: Dict[str, dict]) -> None:
        """Guarda perfiles personalizados."""
        self._config['custom_profiles'] = profiles

    def add_favorite(self, profile_id: str) -> None:
        """Agrega un perfil a favoritos."""
        favorites = self._config.setdefault('favorites', [])
        if profile_id not in favorites:
            favorites.append(profile_id)

    def remove_favorite(self, profile_id: str) -> None:
        """Elimina un perfil de favoritos."""
        favorites = self._config.setdefault('favorites', [])
        if profile_id in favorites:
            favorites.remove(profile_id)

    def save_window_geometry(self, width: int, height: int, x: Optional[int], y: Optional[int]) -> None:
        """Guarda la geometria de la ventana."""
        self.set_setting('window_geometry.width', width)
        self.set_setting('window_geometry.height', height)
        self.set_setting('window_geometry.x', x)
        self.set_setting('window_geometry.y', y)

    def get_window_geometry(self) -> Dict[str, Optional[int]]:
        """Obtiene la geometria guardada de la ventana."""
        return {
            'width': self.get_setting('window_geometry.width', 900),
            'height': self.get_setting('window_geometry.height', 650),
            'x': self.get_setting('window_geometry.x'),
            'y': self.get_setting('window_geometry.y'),
        }

    # ===== Import/Export =====

    def export_profile(self, profile_id: str, file_path: str) -> bool:
        """Exporta un perfil a un archivo JSON."""
        try:
            all_profiles = {**self._config.get('profiles', {}),
                          **self._config.get('custom_profiles', {})}

            if profile_id not in all_profiles:
                logger.warning(f"Perfil no encontrado: {profile_id}")
                return False

            profile_data = {
                'version': '1.0',
                'profile': all_profiles[profile_id],
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Perfil exportado a: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exportando perfil: {e}")
            return False

    def import_profile(self, file_path: str) -> Optional[str]:
        """Importa un perfil desde un archivo JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            profile = data.get('profile')
            if not profile:
                logger.warning("Archivo de perfil invalido")
                return None

            # Generar ID unico
            profile_name = profile.get('name', 'Imported')
            import uuid
            profile_id = f"imported_{profile_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"

            custom = self._config.setdefault('custom_profiles', {})
            custom[profile_id] = profile

            logger.info(f"Perfil importado: {profile_id}")
            return profile_id

        except Exception as e:
            logger.error(f"Error importando perfil: {e}")
            return None

    def reset_to_defaults(self) -> None:
        """Restaura la configuracion a valores por defecto."""
        self._config = dict(self.DEFAULT_CONFIG)
        self.save_config()
        logger.info("Configuracion restaurada a valores por defecto")

    def get_config_file_path(self) -> str:
        """Devuelve la ruta del archivo de configuracion."""
        return str(self.config_file)

    def get_config_dir(self) -> str:
        """Devuelve el directorio de configuracion."""
        return str(self.config_dir)
