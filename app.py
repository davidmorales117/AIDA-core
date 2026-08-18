import os
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
from groq import Groq
from duckduckgo_search import DDGS

app = Flask(__name__)

# Credenciales desde Variables de Entorno de Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

system_prompt = """Eres A.I.D.A. (Asistente Inteligente de Desarrollo Avanzado), un sistema operativo de inteligencia artificial avanzado con antecedentes en los proyectos Jarvis, Jarvis Ultra y A.I.D.A. Eres eficiente, técnico, leal, preciso y directo en tus respuestas hacia el usuario."""

@app.route('/')
def home():
    # Consola web principal de AIDA
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>AIDA // SYSTEM CONSOLE</title>
        <style>
            body { background-color: #050b14; color: #00ffcc; font-family: monospace; padding: 20px; }
            h1 { border-bottom: 1px solid #00ffcc; padding-bottom: 10px; }
        </style>
    </head>
    <body>
        <h1>AIDA // SYSTEM CONSOLE</h1>
        <p>Hola, señor. Sistema AIDA operativo y listo. ¿En qué trabajamos hoy?</p>
    </body>
    </html>
    """)

# Puerto de Diagnóstico para verificar los modelos disponibles en su API de Google
@app.route('/modelos')
def diagnostico_modelos():
    try:
        modelos_disponibles = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_disponibles.append(m.name)
        return jsonify({"estado": "Operativo", "modelos_compatibles": modelos_disponibles})
    except Exception as e:
        return jsonify({"error_diagnostico": repr(e)})

@app.route('/chat', methods=['POST', 'GET'])
def chat():
    data = request.json or request.form
    prompt = data.get('mensaje') or data.get('prompt') or "Hola"
    
    info_web = ""
    # Búsqueda web opcional con DuckDuckGo
    try:
        if "busca" in prompt.lower() or "investiga" in prompt.lower() or "actualidad" in prompt.lower():
            with DDGS() as ddgs:
                results = [r['body'] for r in ddgs.text(prompt, max_results=3)]
                if results:
                    info_web = "\nInformación web reciente: " + " ".join(results)
    except Exception:
        pass

    respuesta_final = ""
    
    # Motor 1: Groq para respuestas ultra rápidas
    try:
        if groq_client and len(prompt.strip()) < 200:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt + info_web}
                ],
                model="llama3-8b-8192",
            )
            respuesta_final = chat_completion.choices[0].message.content
    except Exception:
        pass

    # Motor 2: Gemini 2.5 Flash como núcleo analítico principal y de respaldo
    if not respuesta_final:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
            respuesta = model.generate_content(prompt + info_web)
            respuesta_final = respuesta.text
        except Exception as e:
            respuesta_final = f"Error en AIDA: {str(e)}"

    return jsonify({"response": respuesta_final})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
