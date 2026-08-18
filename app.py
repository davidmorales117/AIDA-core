import os
from datetime import datetime
import zoneinfo
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
from groq import Groq
from duckduckgo_search import DDGS

app = Flask(__name__)

# Credenciales desde Variables de Entorno
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

client_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# --- PLANTILLA HTML/CSS/JS PARA LA INTERFAZ WEB ---
HTML_CHAT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIDA System // Console</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: #0f172a; color: #f8fafc; display: flex; flex-direction: column; height: 100vh; }
        header { background-color: #1e293b; padding: 15px 20px; border-bottom: 1px solid #334155; text-align: center; }
        header h1 { font-size: 1.1rem; color: #38bdf8; letter-spacing: 2px; font-weight: 600; }
        #chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 85%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 0.95rem; white-space: pre-wrap; word-break: break-word; }
        .user { background-color: #0284c7; color: #ffffff; align-self: flex-end; border-bottom-right-radius: 2px; }
        .aida { background-color: #1e293b; color: #e2e8f0; align-self: flex-start; border-bottom-left-radius: 2px; border: 1px solid #334155; }
        #input-container { background-color: #1e293b; padding: 15px; border-top: 1px solid #334155; display: flex; gap: 10px; }
        input { flex: 1; background-color: #0f172a; border: 1px solid #334155; color: #ffffff; padding: 12px 16px; border-radius: 8px; outline: none; font-size: 0.95rem; }
        input:focus { border-color: #38bdf8; }
        button { background-color: #0284c7; color: #ffffff; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
        button:hover { background-color: #0369a1; }
    </style>
</head>
<body>
    <header>
        <h1>AIDA // SYSTEM CONSOLE</h1>
    </header>
    <div id="chat-container">
        <div class="message aida">Hola, señor. Sistema AIDA operativo y listo. ¿En qué trabajamos hoy?</div>
    </div>
    <div id="input-container">
        <input type="text" id="userInput" placeholder="Escribe un mensaje o consulta técnica..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">Enviar</button>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat-container');
            const text = input.value.trim();
            if (!text) return;

            chat.innerHTML += `<div class="message user">${text}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const loadingId = 'load-' + Date.now();
            chat.innerHTML += `<div class="message aida" id="${loadingId}">Procesando...</div>`;
            chat.scrollTop = chat.scrollHeight;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                });
                const data = await response.json();
                document.getElementById(loadingId).innerText = data.response;
            } catch (err) {
                document.getElementById(loadingId).innerText = "Error: Sin conexión con el servidor central de AIDA.";
            }
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""

def obtener_prompt_sistema():
    ahora = datetime.now(zoneinfo.ZoneInfo("America/Bogota"))
    hora_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
    
    return (
        f"Eres AIDA, una asistente técnica, analítica, directa y sincera. "
        f"Tu objetivo es dar opiniones honestas, razonar soluciones y detectar fallos lógicos. "
        f"La fecha y hora actual exacta es: {hora_str}."
    )

def buscar_web(consulta):
    try:
        results = list(DDGS().text(consulta, max_results=3))
        if not results:
            return ""
        texto = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return f"\n\n[Información encontrada en la Web]:\n{texto}"
    except Exception:
        return ""

def enrutador_ia(prompt):
    prompt_lower = prompt.lower()
    system_prompt = obtener_prompt_sistema()
    
    info_web = ""
    palabras_clave = ["busca", "noticias", "precio", "hoy", "quien gano", "resultado"]
    if any(p in prompt_lower for p in palabras_clave):
        info_web = buscar_web(prompt)

    # Motor 1: Groq (Respuestas cortas/rápidas)
    if len(prompt) < 70 and not info_web and client_groq:
        try:
            completion = client_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return completion.choices[0].message.content
        except Exception:
            pass

    # Motor 2: Gemini 1.5 Flash (Razonamiento denso/Código con sufijo actualizado)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest", system_instruction=system_prompt)
        respuesta = model.generate_content(prompt + info_web)
        return respuesta.text
    except Exception as e:
        return f"Error en AIDA: {str(e)}"

@app.route('/')
def home():
    return render_template_string(HTML_CHAT)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_text = data.get('text', '')
    
    if not user_text:
        return jsonify({"response": "No se recibió texto."}), 400

    respuesta_final = enrutador_ia(user_text)
    return jsonify({"response": respuesta_final})
