import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq

app = Flask(__name__)

# Configuración de Credenciales IA
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# --- INICIALIZACIÓN DEL HIPOCAMPO (BASE DE DATOS) ---
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
# ---------------------------------------------------

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "system": "O.R.I.O.N. Core",
        "status": "Operational",
        "hipocampo": "Active (SQLite)"
    })

@app.route('/orion/telemetria', methods=['POST'])
def recibir_telemetria():
    data = request.json or {}
    device = data.get("device", "Desconocido")
    battery = str(data.get("battery_level", "N/A"))
    status = data.get("status", "N/A")
    timestamp = datetime.now(ZoneInfo("America/Bogota")).isoformat()

    # Guardar en el Hipocampo (Base de Datos)
    try:
        conn = sqlite3.connect('orion_memory.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO telemetria_log (device, battery_level, status, timestamp) VALUES (?, ?, ?, ?)",
                       (device, battery, status, timestamp))
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"status": "error", "detalles": str(e)}), 500

    print(f"[HIPOCAMPO - GUARDADO]: {data} a las {timestamp}")
    return jsonify({"status": "sincronizado y guardado", "timestamp": timestamp})

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
    
    system_prompt = "Eres O.R.I.O.N. (Operador Racional de Inteligencia y Organización Neuronal), un sistema operativo de inteligencia artificial avanzado, técnico, hiper-rápido y con mentalidad de ingeniería pura estilo Jarvis. Responde con precisión quirúrgica."

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
