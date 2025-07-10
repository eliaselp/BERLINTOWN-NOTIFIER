import sys
import os
import pickle
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Configuración global
CONFIG_FILE = "trading_alarm_config.pkl"
SOUND_AVAILABLE = False

try:
    import pygame
    pygame.mixer.init()
    SOUND_AVAILABLE = True
except ImportError:
    print("Advertencia: pygame no está instalado. Las alarmas no tendrán sonido.")

# Pares de Forex principales
FOREX_PAIRS = [
    "EURUSD", "USDJPY", "GBPUSD", 
    "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"
]

# Timeframes disponibles
TIMEFRAMES = {
    "1 minuto": 1,
    "5 minutos": 5
}

class TradingSignalController:
    def __init__(self, symbol="EURUSD", timeframe_min=5, lookback_days=1, 
                 server="MetaQuotes-Demo", login=94099863, password=""):
        self.symbol = symbol
        self.timeframe_min = timeframe_min
        self.timeframe = self._get_mt5_timeframe()
        self.lookback_days = lookback_days
        self.signals = {}
        
        # Validación y conversión del login
        try:
            self.login = int(login)
        except ValueError:
            raise ValueError("El login de MT5 debe ser un número entero")
            
        self.server = server
        self.password = password
        
        # Configuración de sesiones en orden cronológico (horario UTC)
        self.market_sessions = [
            {"name": "Sydney", "open": (21, 0), "close": (0, 0)},   # 21:00-06:00 UTC
            {"name": "Tokyo", "open": (0, 0), "close": (8, 0)},     # 00:00-08:00 UTC
            {"name": "London", "open": (8, 0), "close": (13, 0)},   # 08:00-17:00 UTC
            {"name": "New York", "open": (13, 0), "close": (21, 0)} # 13:00-22:00 UTC
        ]
        
        self._connect_to_mt5()
        self._verify_symbol()

    def _connect_to_mt5(self):
        """Conexión con MT5 con manejo de errores mejorado"""
        print(f"🔌 Conectando a MT5 - Servidor: {self.server}, Login: {self.login}")
        if not mt5.initialize(server=self.server, login=self.login, password=self.password):
            error = mt5.last_error()
            print(f"❌ Error de conexión MT5: {error}")
            raise Exception(f"Error al conectar a MT5: {error}")
        print(f"✅ Conexión exitosa a {self.server}")

    def _verify_symbol(self):
        """Verificación robusta del símbolo"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            available = mt5.symbols_get()
            print(f"Símbolos disponibles: {[s.name for s in available[:10]]}")
            raise Exception(f"Símbolo {self.symbol} no disponible")
        
        if not symbol_info.visible:
            print(f"Activando símbolo {self.symbol}...")
            if not mt5.symbol_select(self.symbol, True):
                raise Exception(f"No se pudo activar {self.symbol}")
        print(f"✅ Símbolo {self.symbol} listo para operar")

    def _get_mt5_timeframe(self):
        """Mapeo de timeframe a constantes MT5"""
        return {
            1: mt5.TIMEFRAME_M1,
            5: mt5.TIMEFRAME_M5,
            15: mt5.TIMEFRAME_M15,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1
        }.get(self.timeframe_min, mt5.TIMEFRAME_M5)

    def _get_previous_day_data(self):
        """Obtiene datos del día anterior"""
        now = datetime.now(pytz.utc)
        previous_day = now - timedelta(days=self.lookback_days)
        
        start = previous_day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = previous_day.replace(hour=23, minute=59, second=59, microsecond=999)
        
        print(f"\n📅 Obteniendo datos del día anterior {start} a {end}")
        
        rates = mt5.copy_rates_range(
            self.symbol,
            mt5.TIMEFRAME_D1,
            start,
            end
        )
        
        if rates is None or len(rates) == 0:
            raise Exception("No se pudieron obtener datos del día anterior")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        return {
            "date": start.strftime("%Y-%m-%d"),
            "high": df['high'].iloc[0],
            "low": df['low'].iloc[0],
            "open": df['open'].iloc[0],
            "close": df['close'].iloc[0]
        }

    def _get_previous_session_data(self):
        """Obtiene datos de la sesión anterior"""
        now = datetime.now(pytz.utc)
        current_time = now.hour * 60 + now.minute
        
        # Determinar sesión actual
        current_session = None
        for session in self.market_sessions:
            open_time = session["open"][0] * 60 + session["open"][1]
            close_time = session["close"][0] * 60 + session["close"][1]
            
            if open_time < close_time:
                if open_time <= current_time < close_time:
                    current_session = session
                    break
            else:
                if current_time >= open_time or current_time < close_time:
                    current_session = session
                    break
        
        if current_session is None:
            raise Exception("No se pudo determinar la sesión actual")
        
        print(f"\n🏛️ Sesión actual: {current_session['name']}")
        
        # Encontrar sesión anterior
        current_idx = next(i for i, s in enumerate(self.market_sessions) if s["name"] == current_session["name"])
        previous_idx = (current_idx - 1) % len(self.market_sessions)
        previous_session = self.market_sessions[previous_idx]
        
        print(f"🔍 Sesión anterior detectada: {previous_session['name']}")
        
        # Calcular rango de tiempo
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        session_start = today.replace(
            hour=previous_session["open"][0],
            minute=previous_session["open"][1],
            second=0,
            microsecond=0
        )
        session_end = today.replace(
            hour=previous_session["close"][0],
            minute=previous_session["close"][1],
            second=0,
            microsecond=0
        )
        
        # Ajustes por cambios de día
        if session_start > now:
            session_start -= timedelta(days=1)
        if session_end > now:
            session_end -= timedelta(days=1)
        
        if previous_session["open"][0] > previous_session["close"][0]:
            session_start -= timedelta(days=1)
        
        print(f"⏳ Rango de sesión: {session_start} a {session_end}")
        
        # Obtener datos con diferentes timeframes
        for tf in [self.timeframe, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_D1]:
            try:
                rates = mt5.copy_rates_range(
                    self.symbol,
                    tf,
                    session_start,
                    session_end
                )
                
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    
                    if tf != self.timeframe:
                        print(f"⚠️ Usando timeframe alternativo ({tf})")
                    
                    return {
                        "name": previous_session["name"],
                        "high": df['high'].max(),
                        "low": df['low'].min(),
                        "open": df['open'].iloc[0],
                        "close": df['close'].iloc[-1],
                        "start": session_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "end": session_end.strftime("%Y-%m-%d %H:%M:%S"),
                        "data_points": len(df),
                        "timeframe": tf
                    }
            except Exception as e:
                print(f"⚠️ Error con timeframe {tf}: {str(e)}")
                continue
        
        raise Exception(f"No se pudieron obtener datos para la sesión {previous_session['name']}")

    def _get_current_candles(self):
        """Obtiene las velas actuales"""
        print("\n🕯️ Obteniendo velas actuales...")
        
        rates = mt5.copy_rates_from_pos(
            self.symbol,
            self.timeframe,
            0,  # Posición más reciente
            3   # Obtener 3 velas
        )
        
        if rates is None or len(rates) < 2:
            raise Exception("No se pudieron obtener velas actuales")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        print(f"✅ Velas obtenidas: {len(df)} registros")
        
        return {
            "penultimate": df.iloc[-2],
            "last": df.iloc[-1]
        }

    def analyze_signals(self):
        """Análisis completo con manejo de errores mejorado"""
        try:
            print("\n🔎 Iniciando análisis de señales...")
            
            # 1. Obtener datos del día anterior
            previous_day = self._get_previous_day_data()
            print(f"\n📅 DÍA ANTERIOR ({previous_day['date']}):")
            print(f"• Open: {previous_day['open']}")
            print(f"• High: {previous_day['high']}")
            print(f"• Low: {previous_day['low']}")
            print(f"• Close: {previous_day['close']}")
            
            # 2. Obtener datos de la sesión anterior
            previous_session = self._get_previous_session_data()
            print(f"\n🏛️ SESIÓN ANTERIOR ({previous_session['name']}):")
            print(f"• Horario: {previous_session['start']} a {previous_session['end']}")
            print(f"• Velas analizadas: {previous_session['data_points']}")
            if previous_session['timeframe'] != self.timeframe:
                print(f"• ⚠️ Usando timeframe alternativo: {previous_session['timeframe']}")
            print(f"• Open: {previous_session['open']}")
            print(f"• High: {previous_session['high']}")
            print(f"• Low: {previous_session['low']}")
            print(f"• Close: {previous_session['close']}")
            
            # 3. Obtener velas actuales
            candles = self._get_current_candles()
            print(f"\n🕯️ VELAS ACTUALES ({self.timeframe_min} min):")
            print("Penúltima vela:")
            print(f"• Open: {candles['penultimate']['open']}")
            print(f"• High: {candles['penultimate']['high']}")
            print(f"• Low: {candles['penultimate']['low']}")
            print(f"• Close: {candles['penultimate']['close']}")
            print("\nÚltima vela:")
            print(f"• Open: {candles['last']['open']}")
            print(f"• High: {candles['last']['high']}")
            print(f"• Low: {candles['last']['low']}")
            print(f"• Close: {candles['last']['close']}")
            
            # 4. Generar señales
            signals = []
            # Señales basadas en día anterior
            if ((candles['penultimate']['high'] >= previous_day['high'] and 
                candles['penultimate']['low'] < previous_day['high']) or 
                (candles['last']['high'] >= previous_day['high'] and 
                candles['last']['low'] < previous_day['high'])):
                signals.append("RUPTURA PDH (Previous Day High)")
                print("🚨 Señal detectada: RUPTURA PDH")

            if ((candles['penultimate']['high'] > previous_day['low'] and 
                candles['penultimate']['low'] <= previous_day['low']) or 
                (candles['last']['high'] > previous_day['low'] and 
                candles['last']['low'] <= previous_day['low'])):
                signals.append("RUPTURA PDL (Previous Day Low)")
                print("🚨 Señal detectada: RUPTURA PDL")

            # Señales basadas en sesión anterior
            if ((candles['penultimate']['high'] >= previous_session['high'] and 
                candles['penultimate']['low'] < previous_session['high']) or 
                (candles['last']['high'] >= previous_session['high'] and 
                candles['last']['low'] < previous_session['high'])):
                signals.append("RUPTURA PSH (Previous Session High)")
                print("🚨 Señal detectada: RUPTURA PSH")

            if ((candles['penultimate']['high'] > previous_session['low'] and 
                candles['penultimate']['low'] <= previous_session['low']) or 
                (candles['last']['high'] > previous_session['low'] and 
                candles['last']['low'] <= previous_session['low'])):
                signals.append("RUPTURA PSL (Previous Session Low)")
                print("🚨 Señal detectada: RUPTURA PSL")
            if not signals:
                print("🔍 No se detectaron señales de ruptura")
            
            return signals
            
        except Exception as e:
            print(f"❌ Error en análisis: {str(e)}")
            return []

class TradingAlarmModel:
    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread = None
        self.config = {
            'selected_pairs': FOREX_PAIRS.copy(),
            'timeframe': 5,
            'audio_file': None,
            'mt5_server': 'MetaQuotes-Demo',
            'mt5_login': '94099863',  # Guardado como string para la interfaz
            'mt5_password': ''
        }
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'rb') as f:
                    self.config = pickle.load(f)
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            
    def save_config(self):
        try:
            with open(CONFIG_FILE, 'wb') as f:
                pickle.dump(self.config, f)
        except Exception as e:
            print(f"Error guardando configuración: {e}")
            
    def set_audio_file(self, audio_file):
        self.config['audio_file'] = audio_file
        self.save_config()
        
    def set_timeframe(self, timeframe):
        self.config['timeframe'] = timeframe
        self.save_config()
        
    def set_selected_pairs(self, pairs):
        self.config['selected_pairs'] = pairs
        self.save_config()
        
    def set_mt5_credentials(self, login, password, server):
        """Valida y guarda las credenciales MT5"""
        try:
            # Validar que el login sea numérico
            int(login)
            self.config['mt5_login'] = login
            self.config['mt5_password'] = password
            self.config['mt5_server'] = server
            self.save_config()
        except ValueError:
            raise ValueError("El login de MT5 debe ser un número")
            
    def analyze_pair(self, symbol):
        """Usa la clase TradingSignalController para analizar el par"""
        try:
            # Convertir login a entero para la conexión
            login = int(self.config['mt5_login'])
            
            analyzer = TradingSignalController(
                symbol=symbol,
                timeframe_min=self.config['timeframe'],
                server=self.config['mt5_server'],
                login=login,
                password=self.config['mt5_password']
            )
            return analyzer.analyze_signals()
        except Exception as e:
            raise Exception(f"Error analizando {symbol}: {str(e)}")
            
    def play_sound(self):
        """Reproduce el archivo de audio configurado"""
        if not SOUND_AVAILABLE or not self.config['audio_file']:
            return
            
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            
        try:
            sound = pygame.mixer.Sound(self.config['audio_file'])
            sound.play()
        except Exception as e:
            print(f"Error reproduciendo sonido: {e}")

class TradingAlarmView:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.setup_window()
        self.setup_ui()
        
    def setup_window(self):
        self.root.title("Alarma de Trading Profesional")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        try:
            self.root.iconbitmap(default='icono.ico')
        except:
            try:
                img = Image.new('RGB', (32, 32), color='#0078d7')
                draw = ImageDraw.Draw(img)
                draw.ellipse((8, 8, 24, 24), fill='white')
                img.save('temp_icon.ico')
                self.root.iconbitmap(default='temp_icon.ico')
            except:
                pass
                
    def setup_ui(self):
        self.setup_style()
        self.setup_main_frame()
        self.setup_pairs_selection()
        self.setup_timeframe_selection()
        self.setup_audio_selection()
        self.setup_mt5_credentials()
        self.setup_controls()
        
    def setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.root.configure(bg='#2d2d2d')
        self.style.configure('.', background='#2d2d2d', foreground='white')
        self.style.configure('TFrame', background='#2d2d2d')
        self.style.configure('TLabel', background='#2d2d2d', foreground='white')
        self.style.configure('TButton', background='#3d3d3d', foreground='white')
        self.style.configure('Accent.TButton', background='#0078d7', foreground='white')
        self.style.map('Accent.TButton',
                     background=[('active', '#005a9e'), ('pressed', '#004b84')])
        self.style.configure('TEntry', fieldbackground='#3d3d3d', foreground='white')
        self.style.configure('TCombobox', fieldbackground='#3d3d3d', foreground='white')
        
    def setup_main_frame(self):
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
    def setup_pairs_selection(self):
        pairs_frame = ttk.LabelFrame(self.main_frame, text="Pares de Forex", padding=10)
        pairs_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Crear checkboxes para cada par
        self.pair_vars = {}
        for i, pair in enumerate(FOREX_PAIRS):
            var = tk.BooleanVar(value=pair in self.controller.model.config['selected_pairs'])
            self.pair_vars[pair] = var
            
            cb = ttk.Checkbutton(
                pairs_frame, 
                text=pair, 
                variable=var,
                command=self.update_selected_pairs
            )
            cb.grid(row=i//4, column=i%4, sticky="w", padx=5, pady=2)
            
    def setup_timeframe_selection(self):
        timeframe_frame = ttk.Frame(self.main_frame)
        timeframe_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(timeframe_frame, text="Frecuencia de análisis:").pack(side=tk.LEFT)
        
        self.timeframe_combo = ttk.Combobox(
            timeframe_frame, 
            values=list(TIMEFRAMES.keys()),
            state="readonly"
        )
        self.timeframe_combo.pack(side=tk.LEFT, padx=5)
        
        # Establecer el valor actual
        current_tf = next((k for k, v in TIMEFRAMES.items() 
                          if v == self.controller.model.config['timeframe']), "5 minutos")
        self.timeframe_combo.set(current_tf)
        self.timeframe_combo.bind("<<ComboboxSelected>>", self.update_timeframe)
        
    def setup_audio_selection(self):
        audio_frame = ttk.Frame(self.main_frame)
        audio_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(audio_frame, text="Archivo de alarma:").pack(side=tk.LEFT)
        
        self.audio_label = ttk.Label(
            audio_frame, 
            text=os.path.basename(self.controller.model.config['audio_file']) 
            if self.controller.model.config['audio_file'] else "Ningún archivo seleccionado",
            width=30
        )
        self.audio_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            audio_frame, 
            text="Seleccionar", 
            command=self.select_audio_file,
            style='Accent.TButton'
        ).pack(side=tk.LEFT)
        
    def setup_mt5_credentials(self):
        cred_frame = ttk.LabelFrame(self.main_frame, text="Credenciales MT5", padding=10)
        cred_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Servidor
        ttk.Label(cred_frame, text="Servidor:").grid(row=0, column=0, sticky="w")
        self.server_entry = ttk.Entry(cred_frame)
        self.server_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.server_entry.insert(0, self.controller.model.config['mt5_server'])
        
        # Login
        ttk.Label(cred_frame, text="Login:").grid(row=1, column=0, sticky="w")
        self.login_entry = ttk.Entry(cred_frame)
        self.login_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.login_entry.insert(0, self.controller.model.config['mt5_login'])
        
        # Contraseña
        ttk.Label(cred_frame, text="Contraseña:").grid(row=2, column=0, sticky="w")
        self.password_entry = ttk.Entry(cred_frame, show="*")
        self.password_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.password_entry.insert(0, self.controller.model.config['mt5_password'])
        
        # Botón Guardar
        ttk.Button(
            cred_frame, 
            text="Guardar Credenciales", 
            command=self.save_mt5_credentials,
            style='Accent.TButton'
        ).grid(row=3, column=0, columnspan=2, pady=(5, 0))
        
    def setup_controls(self):
        controls_frame = ttk.Frame(self.main_frame)
        controls_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_button = ttk.Button(
            controls_frame, 
            text="Iniciar Monitoreo", 
            command=self.start_monitoring,
            style='Accent.TButton',
            width=20
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            controls_frame, 
            text="Detener Monitoreo", 
            command=self.stop_monitoring,
            style='Accent.TButton',
            width=20
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state='disabled')
        
        self.status_label = ttk.Label(
            controls_frame, 
            text="Configura los parámetros y haz clic en Iniciar",
            font=('Segoe UI', 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
        
    def update_selected_pairs(self):
        selected = [pair for pair, var in self.pair_vars.items() if var.get()]
        self.controller.set_selected_pairs(selected)
        
    def update_timeframe(self, event=None):
        selected = self.timeframe_combo.get()
        self.controller.set_timeframe(TIMEFRAMES[selected])
        
    def select_audio_file(self):
        filetypes = (
            ('Archivos de audio', '*.wav *.mp3 *.ogg'),
            ('Todos los archivos', '*.*')
        )
        
        filename = filedialog.askopenfilename(
            title='Seleccionar archivo de audio',
            filetypes=filetypes
        )
        
        if filename:
            self.controller.set_audio_file(filename)
            self.audio_label.config(text=os.path.basename(filename))
            
    def save_mt5_credentials(self):
        server = self.server_entry.get()
        login = self.login_entry.get()
        password = self.password_entry.get()
        
        if not server or not login:
            messagebox.showwarning("Advertencia", "Servidor y login son obligatorios")
            return
            
        try:
            self.controller.set_mt5_credentials(login, password, server)
            messagebox.showinfo("Éxito", "Credenciales guardadas correctamente")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        
    def start_monitoring(self):
        if not self.controller.model.config['selected_pairs']:
            messagebox.showwarning("Advertencia", "Debes seleccionar al menos un par")
            return
            
        if not self.controller.model.config['audio_file']:
            messagebox.showwarning("Advertencia", "Debes seleccionar un archivo de audio")
            return
            
        if not self.controller.model.config['mt5_server'] or not self.controller.model.config['mt5_login']:
            messagebox.showwarning("Advertencia", "Debes configurar las credenciales MT5")
            return
            
        try:
            # Validar que el login sea numérico
            int(self.controller.model.config['mt5_login'])
        except ValueError:
            messagebox.showerror("Error", "El login de MT5 debe ser un número")
            return
            
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_label.config(text="Monitoreo activo...")
        
        self.controller.start_monitoring()
        
    def stop_monitoring(self):
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_label.config(text="Monitoreo detenido")
        
        self.controller.stop_monitoring()
        
    def show_alarm(self, message):
        """Muestra una ventana de alarma con el mensaje"""
        alarm_window = tk.Toplevel(self.root)
        alarm_window.title("¡Alarma de Trading!")
        alarm_window.geometry("400x150")
        alarm_window.resizable(False, False)
        alarm_window.attributes('-topmost', True)
        alarm_window.configure(bg='#d70000')
        
        tk.Label(
            alarm_window, 
            text="¡SEÑAL DETECTADA!", 
            font=('Arial', 16, 'bold'), 
            fg='white',
            bg='#d70000'
        ).pack(pady=10)
        
        tk.Label(
            alarm_window, 
            text=message, 
            font=('Arial', 12),
            fg='white',
            bg='#d70000'
        ).pack(pady=5)
        
        tk.Button(
            alarm_window, 
            text="Aceptar", 
            command=alarm_window.destroy,
            bg='#0078d7',
            fg='white',
            relief=tk.FLAT,
            activebackground='#005a9e'
        ).pack(pady=10)
        
        # Reproducir sonido
        self.controller.play_sound()
        
        # Hacer parpadear la ventana
        self.flash_window(alarm_window)
        
    def flash_window(self, window):
        current_bg = window.cget('bg')
        new_bg = '#000000' if current_bg == '#d70000' else '#d70000'
        window.configure(bg=new_bg)
        window.after(500, lambda: self.flash_window(window))
        
    def show_error(self, message):
        messagebox.showerror("Error", message)

class TradingAlarmController:
    def __init__(self, root):
        self.model = TradingAlarmModel()
        self.view = TradingAlarmView(root, self)
        self.monitoring_thread = None
        self.monitoring_active = False
        
    def start_monitoring(self):
        """Inicia el monitoreo en un hilo separado"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self.run_monitoring, daemon=True)
        self.monitoring_thread.start()
        
    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.monitoring_active = False
        
    def run_monitoring(self):
        """Ejecuta el monitoreo continuo"""
        while self.monitoring_active:
            try:
                # Convertir login a entero para la conexión
                login = int(self.model.config['mt5_login'])
                
                if not mt5.initialize(
                    server=self.model.config['mt5_server'],
                    login=login,
                    password=self.model.config['mt5_password']
                ):
                    error = mt5.last_error()
                    raise Exception(f"Error de conexión MT5: {error}")
                
                # Analizar cada par seleccionado
                for symbol in self.model.config['selected_pairs']:
                    if not self.monitoring_active:
                        break
                        
                    try:
                        signals = self.model.analyze_pair(symbol)
                        for signal in signals:
                            self.view.root.after(0, lambda msg=f"{symbol}: {signal}": self.view.show_alarm(msg))
                    except Exception as e:
                        self.view.root.after(0, lambda msg=str(e): self.view.show_error(msg))
                
                # Esperar hasta el próximo intervalo
                sleep_time = self.model.config['timeframe'] * 60
                for _ in range(sleep_time):
                    if not self.monitoring_active:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.view.root.after(0, lambda msg=str(e): self.view.show_error(msg))
                time.sleep(5)  # Esperar antes de reintentar
            finally:
                mt5.shutdown()
    
    def set_audio_file(self, audio_file):
        self.model.set_audio_file(audio_file)
        
    def set_timeframe(self, timeframe):
        self.model.set_timeframe(timeframe)
        
    def set_selected_pairs(self, pairs):
        self.model.set_selected_pairs(pairs)
        
    def set_mt5_credentials(self, login, password, server):
        self.model.set_mt5_credentials(login, password, server)
        
    def play_sound(self):
        self.model.play_sound()

def main():
    # Verificar dependencias
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("Advertencia: MetaTrader5 no está instalado. Intentando instalar...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "MetaTrader5"])
            import MetaTrader5 as mt5
        except:
            print("No se pudo instalar MetaTrader5. La aplicación no funcionará correctamente.")
            sys.exit(1)
    
    root = tk.Tk()
    
    if sys.platform == 'win32':
        try:
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID('Trading.Alarm.1')
        except:
            pass
    
    controller = TradingAlarmController(root)
    root.mainloop()

if __name__ == "__main__":
    main()
