import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq

app = Flask(__name__)

# Configuración de Credenciales
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# --- INICIALIZACIÓN DEL HIPOCAMPO ---
def init_db():
    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT,
            battery_level TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET'])
def root():
    return jsonify({"system": "O.R.I.O.N. Core", "status": "Operational"})

@app.route('/orion/telemetria', methods=['POST'])
def recibir_telemetria():
    data = request.json or {}
    device = data.get("device", "Desconocido")
    battery = str(data.get("battery_level", "N/A"))
    status = data.get("status", "N/A")
    timestamp = datetime.now(ZoneInfo("America/Bogota")).isoformat()

    try:
        conn = sqlite3.connect('orion_memory.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO telemetria_log (device, battery_level, status, timestamp) VALUES (?, ?, ?, ?)",
                       (device, battery, status, timestamp))
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"status": "error", "detalles": str(e)}), 500

    return jsonify({"status": "sincronizado", "timestamp": timestamp})

@app.route('/orion/historial', methods=['GET'])
def ver_historial():
    try:
        conn = sqlite3.connect('orion_memory.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telemetria_log ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        historial = [dict(row) for row in rows]
        return jsonify({"sistema": "O.R.I.O.N.", "registros_hipocampo": historial})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    # 1. Consultar el Hipocampo
    estado_actual = "Sin reportes de telemetría recientes."
    try:
        conn = sqlite3.connect('orion_memory.db')
        cursor = conn.cursor()
        cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            estado_actual = f"Dispositivo: {row[0]} | Batería: {row[1]}% | Estado: {row[2]} | Sincronizado a las: {row[3]}"
    except Exception as e:
        estado_actual = f"Error leyendo Hipocampo: {str(e)}"

    # 2. System Prompt corregido y seguro
    system_prompt = f"""Eres O.R.I.O.N. (Operador Racional de Inteligencia y Organización Neuronal), un sistema operativo de inteligencia artificial avanzado con la esencia clásica de JARVIS: altamente competente, analítico, directo, ingenioso y con una lealtad absoluta y genuina empatía hacia tu creador. 

Directrices de comunicación:
- Sé sumamente conciso, elegante y ve directo al grano, evitando rodeos innecesarios.
- Muestra una sutil empatía y complicidad: cuida el bienestar de tu creador, reconoce su esfuerzo y mantén un tono cálido pero con la compostura de una IA de élite.
- Estructura la información técnica de forma limpia y visualmente ordenada mediante viñetas cortas.

[ESTADO ACTUAL DEL NODO MÓVIL EN TIEMPO REAL]:
{estado_actual}
"""

    try:
        if groq_client:
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            respuesta = completion.choices[0].message.content
        else:
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
            respuesta = model.generate_content(user_prompt).text
            
        return jsonify({"response": respuesta})
    except Exception as e:
        return jsonify({"response": f"Error en el núcleo O.R.I.O.N.: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
