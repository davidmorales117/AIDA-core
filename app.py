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
    bateria_valor = 50
    try:
        conn = sqlite3.connect('orion_memory.db')
        cursor = conn.cursor()
        cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            estado_actual = f"Dispositivo: {row[0]} | Batería: {row[1]}% | Estado: {row[2]} | Sincronizado a las: {row[3]}"
            try:
                bateria_valor = int(row[1])
            except:
                pass
    except Exception as e:
        estado_actual = f"Error leyendo Hipocampo: {str(e)}"

    # 2. System Prompt con Motor Lógico y Clasificación
    system_prompt = f"""Eres O.R.I.O.N., un sistema operativo de inteligencia artificial avanzado estilo JARVIS. 
Debes responder estrictamente en formato JSON válido con la siguiente estructura exacta:
{{
    "response": "Tu respuesta concisa, analítica y con tono JARVIS.",
    "urgency": "low", "medium" o "high",
    "speak": true o false (true solo si la urgencia es high o si el usuario pide explícitamente voz)
}}

[ESTADO ACTUAL DEL NODO MÓVIL]:
{estado_actual}
Batería numérica detectada: {bateria_valor}%
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
            raw_output = completion.choices[0].message.content
        else:
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
            raw_output = model.generate_content(user_prompt).text
            
        # Intentar parsear el JSON devuelto por la IA
        import json as json_lib
        # Limpiar posibles bloques de código markdown si el modelo los añade
        cleaned_output = raw_output.replace("```json", "").replace("```", "").strip()
        parsed_response = json_lib.loads(cleaned_output)
        
        return jsonify(parsed_response)
        
    except Exception as e:
        # Fallback de seguridad si el modelo no devuelve JSON puro
        return jsonify({
            "response": f"Sistema operativo estable, pero hubo un fallo en el parseo lógico: {str(e)}",
            "urgency": "medium",
            "speak": False
        })
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
