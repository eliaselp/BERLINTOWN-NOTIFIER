# BERLINTOWN-NOTIFIER
 Sistema de Monitoreo de Señales Forex

📈 Trading Alarm - Sistema de Monitoreo de Señales Forex
 
*(Imagen ilustrativa de la interfaz)*

🔍 Descripción

Trading Alarm es una aplicación profesional para traders que monitorea pares de Forex en tiempo real, detectando rupturas de niveles clave (Previous Day High/Low y Previous Session High/Low) y alertando al usuario con notificaciones visuales y sonoras.

🚀 Características Principales

- **Monitoreo en tiempo real** de múltiples pares de Forex
- **Detección automática** de rupturas de niveles clave
- **Alertas visuales y sonoras** configurables
- **Interfaz intuitiva** con diseño moderno
- **Configuración personalizable** de pares, timeframes y credenciales
- **Soporte para MetaTrader 5** (demo y cuentas reales)

⚙️ Requisitos del Sistema

- **Windows** (compatible con MetaTrader 5)
- **MetaTrader 5** instalado con una cuenta configurada
- **Conexión a Internet** estable
- **Python 3.7+** con los siguientes paquetes:
  - `MetaTrader5`
  - `pandas`
  - `pytz`
  - `Pillow`
  - `pygame` (opcional para sonido)

📦 Instalación

1. Clona el repositorio o descarga los archivos:
   ```bash
   git clone https://github.com/tu-usuario/trading-alarm.git
   cd trading-alarm
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Ejecuta la aplicación:
   ```bash
   python trading_alarm.py
   ```

🖥️ Guía de Uso de la Interfaz

1. Configuración Inicial
- **Pares de Forex**: Selecciona los pares que deseas monitorear (múltiple selección disponible)
- **Frecuencia de análisis**: Elige entre 1 minuto o 5 minutos
- **Archivo de alarma**: Selecciona un archivo de audio para las alertas (formato WAV, MP3 u OGG)

2. Credenciales MT5
- **Servidor**: Ingresa el servidor de tu broker (ej: `MetaQuotes-Demo`)
- **Login**: Número de cuenta MT5
- **Contraseña**: Contraseña de la cuenta (opcional para cuentas demo)

3. Monitoreo
- **Iniciar Monitoreo**: Comienza el análisis en tiempo real
- **Detener Monitoreo**: Pausa el sistema de alertas

4. Alertas
Cuando se detecte una señal, la aplicación:
1. Mostrará una ventana emergente con los detalles
2. Reproducirá el sonido configurado (si está disponible)
3. La ventana parpadeará para mayor visibilidad

🛠️ Funcionamiento Técnico

El sistema analiza:
1. **Datos del día anterior** (PDH/PDL - Previous Day High/Low)
2. **Datos de la sesión anterior** (PSH/PSL - Previous Session High/Low)
3. **Velas actuales** en el timeframe seleccionado

Detecta las siguientes señales:
- Ruptura del máximo del día anterior (PDH)
- Ruptura del mínimo del día anterior (PDL)
- Ruptura del máximo de la sesión anterior (PSH)
- Ruptura del mínimo de la sesión anterior (PSL)

📄 Licencia

Este proyecto está bajo la licencia. No se permite el uso ni distribución sin permisos del autor.


**Nota**: Esta aplicación requiere conexión constante a internet y MetaTrader 5 en ejecución con una cuenta válida configurada. Las señales generadas son herramientas informativas y no constituyen asesoramiento financiero.
