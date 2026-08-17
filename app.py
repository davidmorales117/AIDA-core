import os
from datetime import datetime
import zoneinfo
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq
from duckduckgo_search import DDGS

app = Flask(__name__)

# Configuración de Claves desde Variables de Entorno
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

client_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

def obtener_prompt_sistema():
    # Obtener hora actual en zona horaria local
    ahora = datetime.now(zoneinfo.ZoneInfo("America/Bogota"))
    hora_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
    
    return (
        f"Eres AIDA, una asistente técnica, analítica, directa y sincera. "
        f"Tu objetivo es dar opiniones honestas y razonar soluciones. "
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
    
    # 1. Búsqueda Web si se requiere
    info_web = ""
    palabras_clave = ["busca", "noticias", "precio", "hoy", "quien gano", "resultado"]
    if any(p in prompt_lower for p in palabras_clave):
        info_web = buscar_web(prompt)

    # 2. Motor ultrarrápido con Groq (Mensajes cortos)
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

    # 3. Razonamiento profundo con Gemini
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_prompt)
        respuesta = model.generate_content(prompt + info_web)
        return respuesta.text
    except Exception as e:
        return f"Error en AIDA: {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_text = data.get('text', '')
    
    if not user_text:
        return jsonify({"response": "No se recibió texto."}), 400

    respuesta_final = enrutador_ia(user_text)
    return jsonify({"response": respuesta_final})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
