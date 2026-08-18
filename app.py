import os
from datetime import datetime
from zoneinfo import ZoneInfo
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

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

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
        .message img { max-width: 100%; border-radius: 8px; margin-top: 8px; display: block; }
        #input-container { background-color: #1e293b; padding: 15px; border-top: 1px solid #334155; display: flex; gap: 10px; align-items: center; }
        input[type="text"] { flex: 1; background-color: #0f172a; border: 1px solid #334155; color: #ffffff; padding: 12px 16px; border-radius: 8px; outline: none; font-size: 0.95rem; }
        input[type="text"]:focus { border-color: #38bdf8; }
        .file-btn { background-color: #334155; color: #38bdf8; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-size: 1.2rem; display: flex; align-items: center; justify-content: center; border: 1px solid #475569; transition: background 0.2s; }
        .file-btn:hover { background-color: #475569; }
        #fileInput { display: none; }
        button.send-btn { background-color: #0284c7; color: #ffffff; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
        button.send-btn:hover { background-color: #0369a1; }
    </style>
</head>
<body>
    <header>
        <h1>AIDA // SYSTEM CONSOLE</h1>
    </header>
    <div id="chat-container">
        <div class="message aida">Hola, señor. Núcleo principal sincronizado al 100%. ¿En qué trabajamos hoy?</div>
    </div>
    <div id="input-container">
        <label for="fileInput" class="file-btn" title="Adjuntar imagen">📎</label>
        <input type="file" id="fileInput" accept="image/*" onchange="previewImage()">
        <input type="text" id="userInput" placeholder="Escribe un mensaje o consulta técnica..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" onclick="sendMessage()">Enviar</button>
    </div>

    <script>
        let selectedImageBase64 = null;

        function previewImage() {
            const file = document.getElementById('fileInput').files[0];
            if (file) {
                const reader = new FileReader();
                reader.onloadend = function() {
                    selectedImageBase64 = reader.result;
                    const chat = document.getElementById('chat-container');
                    chat.innerHTML += `<div class="message user">[Imagen Adjunta]<br><img src="${selectedImageBase64}"></div>`;
                    chat.scrollTop = chat.scrollHeight;
                }
                reader.readAsDataURL(file);
            }
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat-container');
            const text = input.value.trim();
            
            if (!text && !selectedImageBase64) return;

            if (!selectedImageBase64 && text) {
                chat.innerHTML += `<div class="message user">${text}</div>`;
            }
            
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const loadingId = 'load-' + Date.now();
            chat.innerHTML += `<div class="message aida" id="${loadingId}">Procesando flujo de datos...</div>`;
            chat.scrollTop = chat.scrollHeight;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text, image: selectedImageBase64 })
                });
                const data = await response.json();
                document.getElementById(loadingId).innerText = data.response;
            } catch (err) {
                document.getElementById(loadingId).innerText = "Error: Sin conexión con el núcleo de AIDA.";
            }
            
            selectedImageBase64 = null;
            document.getElementById('fileInput').value = '';
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_CHAT)

@app.route('/modelos')
def diagnostico_modelos():
    try:
        modelos_gemini = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods] if GEMINI_KEY else []
        modelos_groq = [m.id for m in groq_client.models.list().data] if groq_client else []
        return jsonify({"estado": "Operativo", "modelos_gemini": modelos_gemini, "modelos_groq": modelos_groq})
    except Exception as e:
        return jsonify({"error_diagnostico": str(e)})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    user_image = data.get('image', None)

    system_prompt = "Eres AIDA, un asistente virtual avanzado y técnico."

    try:
        # Implementación oficial con el modelo verificado en el listado de Groq
        if groq_client and not user_image:
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
        return jsonify({"response": f"Error en AIDA: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
