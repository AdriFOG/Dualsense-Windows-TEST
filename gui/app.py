"""
Interfaz Grafica - DualSense Controller
Aplicacion de escritorio moderna usando CustomTkinter.
Modo oscuro, esquinas redondeadas, indicadores visuales en tiempo real.
"""

import logging
import math
import time
import tkinter as tk
from tkinter import messagebox, filedialog, colorchooser
from typing import Optional, Callable, Dict, List

try:
    import customtkinter as ctk
    from customtkinter import (
        CTk, CTkFrame, CTkLabel, CTkButton, CTkSlider, CTkSwitch,
        CTkProgressBar, CTkOptionMenu, CTkTabview, CTkSegmentedButton, CTkEntry,
        CTkScrollableFrame, CTkImage
    )
    CUSTOMTK_AVAILABLE = True
except ImportError:
    CUSTOMTK_AVAILABLE = False
    # Fallback a tkinter estandar
    from tkinter import ttk
    CTk = tk.Tk
    CTkFrame = tk.Frame
    CTkLabel = tk.Label
    CTkButton = tk.Button
    CTkSlider = tk.Scale
    CTkSwitch = tk.Checkbutton
    CTkProgressBar = ttk.Progressbar
    CTkOptionMenu = ttk.Combobox
    CTkTabview = ttk.Notebook
    CTkEntry = tk.Entry
    CTkScrollableFrame = tk.Frame

from PIL import Image, ImageDraw, ImageFont
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

logger = logging.getLogger(__name__)


class DualSenseGUI:
    """
    Interfaz grafica principal para el controlador DualSense.
    """

    # Colores del tema
    COLORS = {
        'bg_primary': '#0d1117',
        'bg_secondary': '#161b22',
        'bg_card': '#1c2128',
        'accent': '#2f81f7',
        'accent_hover': '#388bfd',
        'success': '#3fb950',
        'warning': '#d29922',
        'danger': '#f85149',
        'text_primary': '#e6edf3',
        'text_secondary': '#8b949e',
        'border': '#30363d',
        'battery_high': '#3fb950',
        'battery_medium': '#d29922',
        'battery_low': '#f85149',
    }

    def __init__(self, connection_manager=None, trigger_engine=None, profile_manager=None, tray_manager=None):
        self.connection_manager = connection_manager
        self.trigger_engine = trigger_engine
        self.profile_manager = profile_manager
        self.tray_manager = tray_manager

        # Estado de la UI
        self._running = False
        self._minimized_to_tray = False
        self._update_interval = 50  # ms
        self._after_id: Optional[str] = None

        # Callbacks para comunicacion con main
        self._on_close: List[Callable[[], None]] = []
        self._on_minimize_tray: List[Callable[[], None]] = []

        # Inicializar ventana
        self._init_window()
        self._build_ui()
        self._setup_callbacks()

    def _init_window(self) -> None:
        """Inicializa la ventana principal."""
        if CUSTOMTK_AVAILABLE:
            # Configurar tema oscuro de CustomTkinter
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")

            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()
            self.root.configure(bg=self.COLORS['bg_primary'])

        self.root.title("DualSense Controller - Panel de Control")
        self.root.geometry("950x700")
        self.root.minsize(800, 600)

        # Centrar ventana
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Icono de la ventana (dibujado proceduralmente)
        self._set_window_icon()

        # Protocolo de cierre
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _set_window_icon(self) -> None:
        """Crea y establece un icono para la ventana."""
        try:
            if ImageTk is None:
                return

            icon = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(icon)

            # Forma del control
            draw.rounded_rectangle([4, 16, 60, 56], radius=8, fill=(0, 150, 255, 255))
            draw.ellipse([12, 24, 22, 34], fill=(255, 255, 255, 255))  # Boton izq
            draw.ellipse([42, 24, 52, 34], fill=(255, 255, 255, 255))  # Boton der
            draw.ellipse([26, 36, 38, 48], fill=(255, 255, 255, 255))  # Stick

            photo = ImageTk.PhotoImage(icon)
            self.root.iconphoto(True, photo)
            self._icon_photo = photo  # Mantener referencia para evitar GC
        except Exception:
            pass

    def _build_ui(self) -> None:
        """Construye todos los elementos de la interfaz."""
        # Frame principal
        if CUSTOMTK_AVAILABLE:
            self.main_frame = ctk.CTkFrame(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            self.main_frame = tk.Frame(self.root, bg=self.COLORS['bg_primary'])

        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ===== Header =====
        self._build_header()

        # ===== Contenido Principal (Tabs) =====
        self._build_tabs()

        # ===== Barra de Estado =====
        self._build_status_bar()

    def _build_header(self) -> None:
        """Construye el header con titulo e indicadores de estado."""
        header = CTkFrame(self.main_frame, fg_color=self.COLORS['bg_secondary'],
                         corner_radius=12, height=70)
        header.pack(fill=tk.X, pady=(0, 10))
        header.pack_propagate(False)

        # Titulo
        title_frame = CTkFrame(header, fg_color="transparent")
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)

        CTkLabel(title_frame, text="🎮", font=("Arial", 24)).pack(side=tk.LEFT)

        title_label = CTkLabel(
            title_frame,
            text="DualSense Controller",
            font=("Segoe UI", 18, "bold"),
            text_color=self.COLORS['text_primary']
        )
        title_label.pack(side=tk.LEFT, padx=(5, 0))

        version_label = CTkLabel(
            title_frame,
            text="v1.0",
            font=("Segoe UI", 10),
            text_color=self.COLORS['text_secondary']
        )
        version_label.pack(side=tk.LEFT, padx=(10, 0))

        # Indicadores de estado (derecha)
        self.indicators_frame = CTkFrame(header, fg_color="transparent")
        self.indicators_frame.pack(side=tk.RIGHT, padx=15, pady=10)

        # Indicador de conexion
        self.connection_indicator = self._create_indicator(
            self.indicators_frame, "●", "Desconectado", self.COLORS['danger']
        )
        self.connection_indicator.pack(side=tk.LEFT, padx=5)

        # Indicador de tipo de conexion
        self.type_indicator = self._create_indicator(
            self.indicators_frame, "", "", self.COLORS['text_secondary']
        )
        self.type_indicator.pack(side=tk.LEFT, padx=5)

        # Indicador de bateria
        self.battery_frame = CTkFrame(self.indicators_frame, fg_color="transparent")
        self.battery_frame.pack(side=tk.LEFT, padx=10)

        self.battery_icon = CTkLabel(
            self.battery_frame, text="🔋",
            font=("Arial", 14), text_color=self.COLORS['text_secondary']
        )
        self.battery_icon.pack(side=tk.LEFT)

        self.battery_label = CTkLabel(
            self.battery_frame, text="--%",
            font=("Segoe UI", 12, "bold"),
            text_color=self.COLORS['text_secondary']
        )
        self.battery_label.pack(side=tk.LEFT, padx=(3, 0))

        self.battery_bar = CTkProgressBar(
            self.battery_frame, width=50, height=8,
            progress_color=self.COLORS['battery_high'],
            fg_color=self.COLORS['bg_card']
        )
        self.battery_bar.pack(side=tk.LEFT, padx=(5, 0))
        self.battery_bar.set(0)

    def _create_indicator(self, parent, symbol: str, text: str, color: str):
        """Crea un indicador visual de estado."""
        frame = CTkFrame(parent, fg_color="transparent")

        dot = CTkLabel(
            frame, text=symbol,
            font=("Arial", 16), text_color=color
        )
        dot.pack(side=tk.LEFT)

        label = CTkLabel(
            frame, text=text,
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        )
        label.pack(side=tk.LEFT, padx=(2, 0))

        # Guardar referencias para actualizacion
        frame.dot = dot
        frame.label = label

        return frame

    def _build_tabs(self) -> None:
        """Construye el sistema de pestañas."""
        if CUSTOMTK_AVAILABLE:
            self.tabs = ctk.CTkTabview(
                self.main_frame,
                fg_color=self.COLORS['bg_secondary'],
                segmented_button_fg_color=self.COLORS['bg_card'],
                segmented_button_selected_color=self.COLORS['accent'],
                segmented_button_selected_hover_color=self.COLORS['accent_hover'],
                segmented_button_unselected_color=self.COLORS['bg_card'],
                segmented_button_unselected_hover_color=self.COLORS['border'],
                text_color=self.COLORS['text_primary'],
                corner_radius=12,
            )
        else:
            style = ttk.Style()
            style.configure('Custom.TNotebook', background=self.COLORS['bg_primary'])
            self.tabs = ttk.Notebook(self.main_frame)

        self.tabs.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # ===== Tab: Perfiles =====
        self._build_profiles_tab()

        # ===== Tab: Gatillos =====
        self._build_triggers_tab()

        # ===== Tab: Configuracion =====
        self._build_settings_tab()

    def _build_profiles_tab(self) -> None:
        """Construye la pestaña de perfiles de armas."""
        if CUSTOMTK_AVAILABLE:
            profiles_tab = self.tabs.add("Perfiles")
        else:
            profiles_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Header de la pestaña
        header_frame = CTkFrame(profiles_tab, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=15, pady=15)

        CTkLabel(
            header_frame,
            text="Perfiles de Armas",
            font=("Segoe UI", 20, "bold"),
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        CTkLabel(
            header_frame,
            text="Selecciona un perfil para aplicar sus efectos de gatillo",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        ).pack(side=tk.LEFT, padx=(15, 0))

        # Grid de perfiles
        self.profiles_grid = CTkScrollableFrame(
            profiles_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent']
        )
        self.profiles_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Frame de info del perfil activo
        self.profile_info_frame = CTkFrame(
            profiles_tab,
            fg_color=self.COLORS['bg_card'],
            corner_radius=12
        )
        self.profile_info_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.active_profile_label = CTkLabel(
            self.profile_info_frame,
            text="Perfil activo: Ninguno",
            font=("Segoe UI", 13, "bold"),
            text_color=self.COLORS['text_primary']
        )
        self.active_profile_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.profile_desc_label = CTkLabel(
            self.profile_info_frame,
            text="Selecciona un perfil para ver su descripcion",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        )
        self.profile_desc_label.pack(side=tk.LEFT, padx=15, pady=10)

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(profiles_tab, text="Perfiles")

        # Poblar perfiles
        self._populate_profiles_grid()

    def _populate_profiles_grid(self) -> None:
        """Llena la grid con las tarjetas de perfiles."""
        if not self.trigger_engine:
            return

        # Limpiar grid existente
        for widget in self.profiles_grid.winfo_children():
            widget.destroy()

        profiles = self.trigger_engine.get_all_profiles()
        categories: Dict[str, List] = {}

        # Agrupar por categoria
        for pid, profile in profiles.items():
            cat = profile.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((pid, profile))

        row = 0
        for category, profile_list in sorted(categories.items()):
            # Titulo de categoria
            cat_label = CTkLabel(
                self.profiles_grid,
                text=category,
                font=("Segoe UI", 14, "bold"),
                text_color=self.COLORS['accent']
            )
            cat_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 5), padx=5)
            row += 1

            # Tarjetas de perfiles (3 por fila)
            col = 0
            for pid, profile in profile_list:
                card = self._create_profile_card(self.profiles_grid, pid, profile)
                card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

                col += 1
                if col >= 3:
                    col = 0
                    row += 1

            if col > 0:
                row += 1

        # Configurar pesos de columnas
        for i in range(3):
            self.profiles_grid.grid_columnconfigure(i, weight=1)

    def _create_profile_card(self, parent, profile_id: str, profile) -> CTkFrame:
        """Crea una tarjeta visual para un perfil."""
        card = CTkFrame(
            parent,
            fg_color=self.COLORS['bg_card'],
            corner_radius=12,
            border_width=2,
            border_color=self.COLORS['border']
        )

        # Icono y nombre
        top_frame = CTkFrame(card, fg_color="transparent")
        top_frame.pack(fill=tk.X, padx=12, pady=(12, 5))

        CTkLabel(
            top_frame,
            text=profile.icon,
            font=("Arial", 28)
        ).pack(side=tk.LEFT)

        CTkLabel(
            top_frame,
            text=profile.name,
            font=("Segoe UI", 14, "bold"),
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Descripcion
        desc = CTkLabel(
            card,
            text=profile.description,
            font=("Segoe UI", 10),
            text_color=self.COLORS['text_secondary'],
            wraplength=200,
            justify="left"
        )
        desc.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Info de efectos
        effects_frame = CTkFrame(card, fg_color="transparent")
        effects_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        CTkLabel(
            effects_frame,
            text=f"L2: {profile.left_trigger.name}",
            font=("Segoe UI", 9),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w")

        CTkLabel(
            effects_frame,
            text=f"R2: {profile.right_trigger.name}",
            font=("Segoe UI", 9),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w")

        # Barra de intensidad
        intensity_label = CTkLabel(
            card,
            text=f"Vibracion: {profile.rumble_intensity}/255",
            font=("Segoe UI", 9),
            text_color=self.COLORS['text_secondary']
        )
        intensity_label.pack(anchor="w", padx=12, pady=(0, 5))

        intensity_bar = CTkProgressBar(
            card, height=4,
            progress_color=self.COLORS['accent'],
            fg_color=self.COLORS['bg_secondary']
        )
        intensity_bar.pack(fill=tk.X, padx=12, pady=(0, 10))
        intensity_bar.set(profile.rumble_intensity / 255)

        # Boton de aplicar
        apply_btn = CTkButton(
            card,
            text="Aplicar",
            font=("Segoe UI", 11, "bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            height=32,
            command=lambda pid=profile_id: self._apply_profile(pid)
        )
        apply_btn.pack(fill=tk.X, padx=12, pady=(0, 12))

        # Guardar referencia para resaltar activo
        card.profile_id = profile_id
        card.apply_btn = apply_btn

        return card

    def _build_triggers_tab(self) -> None:
        """Construye la pestaña de control manual de gatillos."""
        if CUSTOMTK_AVAILABLE:
            triggers_tab = self.tabs.add("Gatillos")
        else:
            triggers_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Layout: dos columnas (L2 y R2)
        triggers_tab.grid_columnconfigure(0, weight=1)
        triggers_tab.grid_columnconfigure(1, weight=1)

        # ===== Panel L2 =====
        l2_frame = CTkFrame(triggers_tab, fg_color=self.COLORS['bg_card'], corner_radius=12)
        l2_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        CTkLabel(
            l2_frame,
            text="L2 (Gatillo Izquierdo)",
            font=("Segoe UI", 16, "bold"),
            text_color=self.COLORS['text_primary']
        ).pack(pady=(15, 10))

        # Visualizador de posicion
        self.l2_position_bar = CTkProgressBar(
            l2_frame, width=200, height=20,
            progress_color=self.COLORS['accent'],
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=10
        )
        self.l2_position_bar.pack(pady=5)
        self.l2_position_bar.set(0)

        self.l2_position_label = CTkLabel(
            l2_frame, text="Posicion: 0",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        )
        self.l2_position_label.pack(pady=(0, 10))

        # Selector de efecto
        CTkLabel(
            l2_frame, text="Efecto:",
            font=("Segoe UI", 12),
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.l2_effect_var = tk.StringVar(value="off")
        self.l2_effect_menu = CTkOptionMenu(
            l2_frame,
            values=["off", "rigid", "pulse", "continuous_vibration", "sections"],
            variable=self.l2_effect_var,
            command=lambda v: self._on_effect_change('left', v),
            font=("Segoe UI", 11),
            dropdown_font=("Segoe UI", 11),
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        self.l2_effect_menu.pack(fill=tk.X, padx=15, pady=5)

        # Sliders de configuracion
        self._build_trigger_sliders(l2_frame, 'left')

        # ===== Panel R2 =====
        r2_frame = CTkFrame(triggers_tab, fg_color=self.COLORS['bg_card'], corner_radius=12)
        r2_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        CTkLabel(
            r2_frame,
            text="R2 (Gatillo Derecho)",
            font=("Segoe UI", 16, "bold"),
            text_color=self.COLORS['text_primary']
        ).pack(pady=(15, 10))

        # Visualizador de posicion
        self.r2_position_bar = CTkProgressBar(
            r2_frame, width=200, height=20,
            progress_color=self.COLORS['accent'],
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=10
        )
        self.r2_position_bar.pack(pady=5)
        self.r2_position_bar.set(0)

        self.r2_position_label = CTkLabel(
            r2_frame, text="Posicion: 0",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        )
        self.r2_position_label.pack(pady=(0, 10))

        # Selector de efecto
        CTkLabel(
            r2_frame, text="Efecto:",
            font=("Segoe UI", 12),
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.r2_effect_var = tk.StringVar(value="off")
        self.r2_effect_menu = CTkOptionMenu(
            r2_frame,
            values=["off", "rigid", "pulse", "continuous_vibration", "sections"],
            variable=self.r2_effect_var,
            command=lambda v: self._on_effect_change('right', v),
            font=("Segoe UI", 11),
            dropdown_font=("Segoe UI", 11),
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        self.r2_effect_menu.pack(fill=tk.X, padx=15, pady=5)

        # Sliders de configuracion
        self._build_trigger_sliders(r2_frame, 'right')

        # Boton de reset
        reset_btn = CTkButton(
            triggers_tab,
            text="Resetear Ambos Gatillos",
            font=("Segoe UI", 12, "bold"),
            fg_color=self.COLORS['danger'],
            hover_color='#ff6b6b',
            corner_radius=10,
            height=40,
            command=self._reset_triggers
        )
        reset_btn.grid(row=1, column=0, columnspan=2, pady=15)

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(triggers_tab, text="Gatillos")

    def _build_trigger_sliders(self, parent, trigger: str) -> None:
        """Construye los sliders de configuracion para un gatillo."""
        # Intensidad
        CTkLabel(
            parent, text="Intensidad:",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        intensity_frame = CTkFrame(parent, fg_color="transparent")
        intensity_frame.pack(fill=tk.X, padx=15, pady=5)

        intensity_slider = CTkSlider(
            intensity_frame,
            from_=0, to=255,
            number_of_steps=255,
            command=lambda v, t=trigger: self._on_intensity_change(t, v),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        intensity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        intensity_slider.set(128)

        intensity_value = CTkLabel(
            intensity_frame, text="128",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_primary'],
            width=35
        )
        intensity_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_intensity_slider', intensity_slider)
        setattr(self, f'{trigger}_intensity_value', intensity_value)

        # Posicion de inicio
        CTkLabel(
            parent, text="Posicion Inicio:",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        start_frame = CTkFrame(parent, fg_color="transparent")
        start_frame.pack(fill=tk.X, padx=15, pady=5)

        start_slider = CTkSlider(
            start_frame,
            from_=0, to=9,
            number_of_steps=9,
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        start_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        start_slider.set(0)

        start_value = CTkLabel(
            start_frame, text="0",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_primary'],
            width=35
        )
        start_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_start_slider', start_slider)
        setattr(self, f'{trigger}_start_value', start_value)

        # Posicion de fin
        CTkLabel(
            parent, text="Posicion Fin:",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        end_frame = CTkFrame(parent, fg_color="transparent")
        end_frame.pack(fill=tk.X, padx=15, pady=5)

        end_slider = CTkSlider(
            end_frame,
            from_=0, to=9,
            number_of_steps=9,
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        end_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        end_slider.set(9)

        end_value = CTkLabel(
            end_frame, text="9",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_primary'],
            width=35
        )
        end_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_end_slider', end_slider)
        setattr(self, f'{trigger}_end_value', end_value)

        # Frecuencia (para efectos pulsados)
        CTkLabel(
            parent, text="Frecuencia:",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        freq_frame = CTkFrame(parent, fg_color="transparent")
        freq_frame.pack(fill=tk.X, padx=15, pady=5)

        freq_slider = CTkSlider(
            freq_frame,
            from_=0, to=20,
            number_of_steps=20,
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        freq_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        freq_slider.set(5)

        freq_value = CTkLabel(
            freq_frame, text="5",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_primary'],
            width=35
        )
        freq_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_freq_slider', freq_slider)
        setattr(self, f'{trigger}_freq_value', freq_value)

    def _build_settings_tab(self) -> None:
        """Construye la pestaña de configuracion."""
        if CUSTOMTK_AVAILABLE:
            settings_tab = self.tabs.add("Configuracion")
        else:
            settings_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Scrollable frame
        scroll_frame = CTkScrollableFrame(
            settings_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
        )
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ===== Seccion: General =====
        general_frame = self._create_settings_section(scroll_frame, "General")
        general_frame.pack(fill=tk.X, pady=(0, 15))

        # Auto-conectar
        self.auto_connect_switch = self._create_switch_setting(
            general_frame, "Conexion automatica al inicio",
            self.profile_manager.get_setting('auto_connect', True) if self.profile_manager else True
        )
        self.auto_connect_switch.pack(fill=tk.X, padx=10, pady=5)

        # Minimizar a bandeja
        self.minimize_tray_switch = self._create_switch_setting(
            general_frame, "Minimizar a bandeja al cerrar",
            self.profile_manager.get_setting('minimize_to_tray', True) if self.profile_manager else True
        )
        self.minimize_tray_switch.pack(fill=tk.X, padx=10, pady=5)

        # ===== Seccion: LED =====
        led_frame = self._create_settings_section(scroll_frame, "LED y Apariencia")
        led_frame.pack(fill=tk.X, pady=(0, 15))

        # Color del LED
        color_frame = CTkFrame(led_frame, fg_color="transparent")
        color_frame.pack(fill=tk.X, padx=10, pady=5)

        CTkLabel(
            color_frame, text="Color LED Touchpad:",
            font=("Segoe UI", 12),
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.led_color_btn = CTkButton(
            color_frame,
            text="Elegir Color",
            font=("Segoe UI", 11),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._choose_led_color
        )
        self.led_color_btn.pack(side=tk.RIGHT)

        # Preview del color
        self.led_preview = CTkFrame(
            color_frame, width=30, height=30,
            fg_color="#0064ff", corner_radius=15
        )
        self.led_preview.pack(side=tk.RIGHT, padx=10)

        # Numero de jugador
        player_frame = CTkFrame(led_frame, fg_color="transparent")
        player_frame.pack(fill=tk.X, padx=10, pady=5)

        CTkLabel(
            player_frame, text="Numero de jugador:",
            font=("Segoe UI", 12),
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.player_var = tk.StringVar(value="1")
        player_menu = CTkOptionMenu(
            player_frame,
            values=["0 (Apagado)", "1", "2", "3", "4"],
            variable=self.player_var,
            command=self._on_player_change,
            width=120,
            font=("Segoe UI", 11),
        )
        player_menu.pack(side=tk.RIGHT)

        # ===== Seccion: Bluetooth =====
        bt_frame = self._create_settings_section(scroll_frame, "Bluetooth")
        bt_frame.pack(fill=tk.X, pady=(0, 15))

        # Boton de reinicio Bluetooth
        self.reset_bt_btn = CTkButton(
            bt_frame,
            text="Reiniciar Bluetooth",
            font=("Segoe UI", 12, "bold"),
            fg_color=self.COLORS['warning'],
            hover_color='#e6a700',
            corner_radius=10,
            command=self._reset_bluetooth
        )
        self.reset_bt_btn.pack(fill=tk.X, padx=10, pady=10)

        # Auto-reset Bluetooth
        self.auto_reset_bt_switch = self._create_switch_setting(
            bt_frame, "Auto-reset Bluetooth al conectar",
            self.profile_manager.get_setting('bluetooth_auto_reset', False) if self.profile_manager else False
        )
        self.auto_reset_bt_switch.pack(fill=tk.X, padx=10, pady=5)

        # ===== Seccion: Perfiles =====
        profiles_frame = self._create_settings_section(scroll_frame, "Gestion de Perfiles")
        profiles_frame.pack(fill=tk.X, pady=(0, 15))

        # Importar/Exportar botones
        btn_frame = CTkFrame(profiles_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        CTkButton(
            btn_frame,
            text="Importar Perfil",
            font=("Segoe UI", 11),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._import_profile
        ).pack(side=tk.LEFT, padx=(0, 5))

        CTkButton(
            btn_frame,
            text="Exportar Perfil",
            font=("Segoe UI", 11),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._export_profile
        ).pack(side=tk.LEFT, padx=5)

        CTkButton(
            btn_frame,
            text="Restaurar Defaults",
            font=("Segoe UI", 11),
            fg_color=self.COLORS['danger'],
            hover_color='#ff6b6b',
            corner_radius=8,
            command=self._reset_defaults
        ).pack(side=tk.RIGHT)

        # ===== Seccion: Acerca de =====
        about_frame = self._create_settings_section(scroll_frame, "Acerca de")
        about_frame.pack(fill=tk.X)

        CTkLabel(
            about_frame,
            text="DualSense Controller v1.0\nPanel de control para PlayStation 5 DualSense en Windows",
            font=("Segoe UI", 11),
            text_color=self.COLORS['text_secondary'],
            justify="left"
        ).pack(padx=10, pady=10, anchor="w")

        CTkLabel(
            about_frame,
            text="Desarrollado con Python, pydualsense y CustomTkinter\nRequiere control conectado via USB o Bluetooth",
            font=("Segoe UI", 10),
            text_color=self.COLORS['text_secondary'],
            justify="left"
        ).pack(padx=10, pady=(0, 10), anchor="w")

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(settings_tab, text="Configuracion")

    def _create_settings_section(self, parent, title: str) -> CTkFrame:
        """Crea una seccion de configuracion con titulo."""
        section = CTkFrame(parent, fg_color=self.COLORS['bg_card'], corner_radius=12)

        CTkLabel(
            section,
            text=title,
            font=("Segoe UI", 14, "bold"),
            text_color=self.COLORS['accent']
        ).pack(anchor="w", padx=15, pady=(12, 5))

        # Separador
        separator = CTkFrame(section, height=2, fg_color=self.COLORS['border'])
        separator.pack(fill=tk.X, padx=15, pady=(0, 8))

        return section

    def _create_switch_setting(self, parent, text: str, default: bool) -> CTkFrame:
        """Crea un frame con label y switch."""
        frame = CTkFrame(parent, fg_color="transparent")

        CTkLabel(
            frame, text=text,
            font=("Segoe UI", 12),
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        switch_var = tk.BooleanVar(value=default)
        switch = CTkSwitch(
            frame,
            text="",
            variable=switch_var,
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text_primary'],
        )
        switch.pack(side=tk.RIGHT)
        switch.var = switch_var

        return frame

    def _build_status_bar(self) -> None:
        """Construye la barra de estado inferior."""
        self.status_bar = CTkFrame(
            self.main_frame,
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=8,
            height=30
        )
        self.status_bar.pack(fill=tk.X, pady=(0, 0))
        self.status_bar.pack_propagate(False)

        self.status_label = CTkLabel(
            self.status_bar,
            text="Iniciando...",
            font=("Segoe UI", 10),
            text_color=self.COLORS['text_secondary']
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.fps_label = CTkLabel(
            self.status_bar,
            text="",
            font=("Segoe UI", 9),
            text_color=self.COLORS['text_secondary']
        )
        self.fps_label.pack(side=tk.RIGHT, padx=10)

    # ===== Callbacks y Eventos =====

    def _setup_callbacks(self) -> None:
        """Configura los callbacks del sistema."""
        if self.connection_manager:
            self.connection_manager.on_connect(self._on_controller_connected)
            self.connection_manager.on_disconnect(self._on_controller_disconnected)
            self.connection_manager.on_battery_change(self._on_battery_change)
            self.connection_manager.on_state_update(self._on_state_update)
            self.connection_manager.on_error(self._on_connection_error)

        if self.trigger_engine:
            self.trigger_engine.on_profile_change(self._on_profile_applied)

    def _on_window_close(self) -> None:
        """Maneja el evento de cierre de ventana."""
        minimize_to_tray = False

        if self.profile_manager:
            minimize_to_tray = self.profile_manager.get_setting('minimize_to_tray', True)

        if minimize_to_tray and not self._minimized_to_tray:
            self.hide_window()
        else:
            self.exit_app()

    def hide_window(self) -> None:
        """Oculta la ventana principal (modo bandeja)."""
        self._minimized_to_tray = True
        self.root.withdraw()

        if self.tray_manager:
            self.tray_manager.set_status("Ejecutando en segundo plano")

        self._set_status("Minimizado a bandeja. Haz clic en el icono para restaurar.")
        logger.info("Ventana minimizada a bandeja")

    def show_window(self) -> None:
        """Muestra la ventana principal."""
        self._minimized_to_tray = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit_app(self) -> None:
        """Cierra completamente la aplicacion."""
        self._running = False

        # Cancelar after pendientes
        if self._after_id:
            self.root.after_cancel(self._after_id)

        # Guardar configuracion
        if self.profile_manager:
            geo = self._get_window_geometry()
            self.profile_manager.save_window_geometry(**geo)
            self.profile_manager.save_config()

        # Detener modulos
        if self.trigger_engine:
            self.trigger_engine.stop()

        if self.connection_manager:
            self.connection_manager.stop()

        if self.tray_manager:
            self.tray_manager.stop()

        # Destruir ventana
        self.root.destroy()

        # Notificar a main
        for callback in self._on_close:
            try:
                callback()
            except Exception:
                pass

        logger.info("Aplicacion cerrada")

    def on_close(self, callback: Callable[[], None]) -> None:
        """Registra callback para cierre de aplicacion."""
        self._on_close.append(callback)

    # ===== Acciones =====

    def _apply_profile(self, profile_id: str) -> None:
        """Aplica un perfil de arma."""
        if self.trigger_engine:
            success = self.trigger_engine.apply_profile(profile_id)
            if success:
                self._set_status(f"Perfil aplicado: {profile_id}")
                # Guardar como activo
                if self.profile_manager:
                    self.profile_manager.set_active_profile(profile_id)
            else:
                self._set_status("Error aplicando perfil")

    def _on_effect_change(self, trigger: str, effect_type: str) -> None:
        """Maneja cambio de efecto desde el dropdown."""
        if not self.trigger_engine:
            return

        from src.trigger_engine import TriggerEffect, TriggerEffectType

        effect_map = {
            'off': TriggerEffectType.OFF,
            'rigid': TriggerEffectType.RIGID,
            'pulse': TriggerEffectType.PULSE,
            'continuous_vibration': TriggerEffectType.CONTINUOUS_VIBRATION,
            'sections': TriggerEffectType.SECTIONS,
        }

        effect = TriggerEffect(
            name=effect_type,
            effect_type=effect_map.get(effect_type, TriggerEffectType.OFF),
            intensity=int(getattr(self, f'{trigger}_intensity_slider').get()),
            start_position=int(getattr(self, f'{trigger}_start_slider').get()),
            end_position=int(getattr(self, f'{trigger}_end_slider').get()),
            frequency=int(getattr(self, f'{trigger}_freq_slider').get()),
        )

        self.trigger_engine.apply_effect(trigger, effect)
        self._set_status(f"Efecto {effect_type} aplicado a {trigger}")

    def _on_intensity_change(self, trigger: str, value: float) -> None:
        """Actualiza el label de intensidad."""
        label = getattr(self, f'{trigger}_intensity_value')
        label.configure(text=f"{int(value)}")

    def _reset_triggers(self) -> None:
        """Resetea ambos gatillos."""
        if self.trigger_engine:
            self.trigger_engine.reset_triggers()
            self._set_status("Gatillos reseteados")

    def _choose_led_color(self) -> None:
        """Abre selector de color para el LED."""
        color = colorchooser.askcolor(title="Elegir color LED")
        if color[0]:
            r, g, b = int(color[0][0]), int(color[0][1]), int(color[0][2])
            self.led_preview.configure(fg_color=color[1])

            if self.connection_manager:
                self.connection_manager.set_led_color(r, g, b)

            if self.profile_manager:
                self.profile_manager.set_setting('led_color', [r, g, b])

    def _on_player_change(self, value: str) -> None:
        """Maneja cambio de numero de jugador."""
        try:
            player = int(value.split()[0])
        except (ValueError, IndexError):
            player = 1

        if self.connection_manager:
            self.connection_manager.set_player_led(player)

        if self.profile_manager:
            self.profile_manager.set_setting('player_number', player)

    def _reset_bluetooth(self) -> None:
        """Reinicia el Bluetooth."""
        self._set_status("Reiniciando Bluetooth...")
        self.reset_bt_btn.configure(state="disabled")

        def do_reset():
            if self.connection_manager:
                success = self.connection_manager.perform_bluetooth_reset()
                self.root.after(0, lambda: self._on_bluetooth_reset_done(success))

        import threading
        thread = threading.Thread(target=do_reset, daemon=True)
        thread.start()

    def _on_bluetooth_reset_done(self, success: bool) -> None:
        """Callback cuando termina el reinicio de Bluetooth."""
        self.reset_bt_btn.configure(state="normal")
        if success:
            self._set_status("Bluetooth reiniciado exitosamente")
        else:
            self._set_status("Error reiniciando Bluetooth. Revisa permisos de administrador.")

    def _import_profile(self) -> None:
        """Importa un perfil desde archivo JSON."""
        file_path = filedialog.askopenfilename(
            title="Importar Perfil",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path and self.profile_manager:
            profile_id = self.profile_manager.import_profile(file_path)
            if profile_id:
                self._set_status(f"Perfil importado: {profile_id}")
                self._populate_profiles_grid()
            else:
                messagebox.showerror("Error", "No se pudo importar el perfil")

    def _export_profile(self) -> None:
        """Exporta el perfil activo a archivo JSON."""
        if not self.profile_manager or not self.trigger_engine:
            return

        profile_id = self.trigger_engine.get_current_profile()
        if not profile_id:
            messagebox.showwarning("Advertencia", "No hay perfil activo para exportar")
            return

        file_path = filedialog.asksaveasfilename(
            title="Exportar Perfil",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            success = self.profile_manager.export_profile(profile_id, file_path)
            if success:
                self._set_status(f"Perfil exportado a: {file_path}")
            else:
                messagebox.showerror("Error", "No se pudo exportar el perfil")

    def _reset_defaults(self) -> None:
        """Restaura configuracion por defecto."""
        result = messagebox.askyesno(
            "Confirmar",
            "Esto eliminara todos tus perfiles personalizados y restaurara la configuracion original. ¿Continuar?"
        )
        if result and self.profile_manager:
            self.profile_manager.reset_to_defaults()
            self._set_status("Configuracion restaurada a valores por defecto")
            self._populate_profiles_grid()

    # ===== Actualizaciones de UI =====

    def _on_controller_connected(self, connection_type) -> None:
        """Callback cuando se conecta el control."""
        conn_type_str = "USB" if connection_type.value == "usb" else "BLUETOOTH"
        color = self.COLORS['success'] if connection_type.value == "usb" else self.COLORS['accent']

        self.connection_indicator.dot.configure(text_color=color)
        self.connection_indicator.label.configure(text="Conectado")

        self.type_indicator.dot.configure(text_color=color)
        self.type_indicator.label.configure(text=f"{conn_type_str}")

        self._set_status(f"DualSense conectado via {conn_type_str}")

        # Aplicar perfil guardado
        if self.trigger_engine and self.profile_manager:
            active = self.profile_manager.get_active_profile()
            self.trigger_engine.apply_profile(active)

    def _on_controller_disconnected(self) -> None:
        """Callback cuando se desconecta el control."""
        self.connection_indicator.dot.configure(text_color=self.COLORS['danger'])
        self.connection_indicator.label.configure(text="Desconectado")

        self.type_indicator.dot.configure(text_color=self.COLORS['text_secondary'])
        self.type_indicator.label.configure(text="")

        self.battery_icon.configure(text_color=self.COLORS['text_secondary'])
        self.battery_label.configure(text="--%", text_color=self.COLORS['text_secondary'])
        self.battery_bar.set(0)

        self._set_status("DualSense desconectado")

    def _on_battery_change(self, level: int, status) -> None:
        """Callback cuando cambia el estado de bateria."""
        # Color segun nivel
        if level >= 60:
            color = self.COLORS['battery_high']
        elif level >= 20:
            color = self.COLORS['battery_medium']
        else:
            color = self.COLORS['battery_low']

        # Icono
        charging = status.value in ['cargando', 'cargado completo']
        icon = "🔌" if charging else "🔋"

        self.battery_icon.configure(text_color=color)
        self.battery_label.configure(text=f"{level}%", text_color=color)
        self.battery_bar.configure(progress_color=color)
        self.battery_bar.set(level / 100)

        # Actualizar tray
        if self.tray_manager:
            self.tray_manager.set_battery(level, charging)

    def _on_state_update(self, state) -> None:
        """Callback para actualizacion de estado del control."""
        # Actualizar posicion de gatillos
        l2_pos = state.left_trigger / 255
        r2_pos = state.right_trigger / 255

        self.l2_position_bar.set(l2_pos)
        self.l2_position_label.configure(text=f"Posicion: {state.left_trigger}")

        self.r2_position_bar.set(r2_pos)
        self.r2_position_label.configure(text=f"Posicion: {state.right_trigger}")

    def _on_connection_error(self, message: str) -> None:
        """Callback para errores de conexion."""
        self._set_status(f"Error: {message}")

    def _on_profile_applied(self, profile_id: str) -> None:
        """Callback cuando se aplica un perfil."""
        if self.trigger_engine:
            profile = self.trigger_engine.get_profile(profile_id)
            if profile:
                self.active_profile_label.configure(text=f"Perfil activo: {profile.name}")
                self.profile_desc_label.configure(text=profile.description)

        # Actualizar tray
        if self.tray_manager:
            self.tray_manager.set_current_profile(profile_id)

    def _set_status(self, message: str) -> None:
        """Actualiza el texto de la barra de estado."""
        self.status_label.configure(text=message)
        logger.info(f"Status: {message}")

    def _get_window_geometry(self) -> dict:
        """Obtiene la geometria actual de la ventana."""
        self.root.update_idletasks()
        return {
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y(),
        }

    # ===== Ciclo de Vida =====

    def start(self) -> None:
        """Inicia la interfaz grafica."""
        self._running = True
        self._set_status("Listo - Conecta tu DualSense")
        self._schedule_update()

    def _schedule_update(self) -> None:
        """Programa la proxima actualizacion de UI."""
        if not self._running:
            return

        self._update_ui()
        self._after_id = self.root.after(self._update_interval, self._schedule_update)

    def _update_ui(self) -> None:
        """Actualizacion periodica de la interfaz."""
        pass  # Las actualizaciones se hacen via callbacks

    def run(self) -> None:
        """Ejecuta el loop principal de la interfaz."""
        self.start()

        # Restaurar geometria guardada
        if self.profile_manager:
            geo = self.profile_manager.get_window_geometry()
            if geo['x'] is not None and geo['y'] is not None:
                self.root.geometry(f"{geo['width']}x{geo['height']}+{geo['x']}+{geo['y']}")

            # Minimizar al inicio si esta configurado
            if self.profile_manager.get_setting('start_minimized', False):
                self.hide_window()

        self.root.mainloop()

    def stop(self) -> None:
        """Detiene la interfaz grafica."""
        self._running = False
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
