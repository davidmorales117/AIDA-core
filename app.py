# app.py - Núcleo Backend O.R.I.O.N. (Headless API)
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq

app = Flask(__name__)

# Credenciales de IA
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# Memoria de estado del nodo móvil
ULTIMA_TELEMETRIA = {"estado": "Sin reportes"}

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "system": "O.R.I.O.N. Core",
        "status": "Operational",
        "architecture": "Decentralized Cloud Backend"
    })

@app.route('/orion/telemetria', methods=['POST'])
def recibir_telemetria():
    global ULTIMA_TELEMETRIA
    data = request.json or {}
    ULTIMA_TELEMETRIA = data
    print(f"[TELEMETRÍA RECIBIDA]: {data}")
    return jsonify({"status": "sincronizado", "timestamp": datetime.now(ZoneInfo("America/Bogota")).isoformat()})

@app.route('/orion/estado', methods=['GET'])
def ver_estado():
    return jsonify({"sistema": "O.R.I.O.N.", "nodo_movil": ULTIMA_TELEMETRIA})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    system_prompt = "Eres O.R.I.O.N. (Operador Racional de Inteligencia y Organización Neuronal), un sistema operativo de inteligencia artificial avanzado, técnico, hiper-rápido y con mentalidad de ingeniería pura estilo Jarvis. Responde con precisión quirúrgica y sin rodeos."

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
