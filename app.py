import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq
from duckduckgo_search import DDGS

app = Flask(__name__)

# 1. Obtener claves desde Render (Variables de Entorno)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

# Conectar servicios si existen las claves
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

client_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# 2. Definir la personalidad y actitud de AIDA
SYSTEM_PROMPT = (
    "Eres AIDA, una asistente técnica, analítica, directa y sincera. "
    "Tu objetivo es dar opiniones honestas, identificar fallos en ideas, "
    "razonar soluciones y responder de forma concisa pero profunda."
)

# 3. Función para buscar en la web en tiempo real
def buscar_web(consulta):
    try:
        results = list(DDGS().text(consulta, max_results=3))
        if not results:
            return ""
        texto = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return f"\n\n[Información encontrada en la Web]:\n{texto}"
    except Exception:
        return ""

# 4. Enrutador Multi-Agente (Decide qué IA responde)
def enrutador_ia(prompt):
    prompt_lower = prompt.lower()
    
    # A) Búsqueda Web si incluye palabras clave
    info_web = ""
    palabras_clave = ["busca", "noticias", "precio", "hoy", "quien gano", "resultado"]
    if any(p in prompt_lower for p in palabras_clave):
        info_web = buscar_web(prompt)

    # B) Respuesta ultrarrápida con Groq (Mensajes cortos sin búsqueda web)
    if len(prompt) < 70 and not info_web and client_groq:
        try:
            completion = client_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return completion.choices[0].message.content
        except Exception:
            pass # Si Groq falla, pasa automáticamente a Gemini

    # C) Razonamiento profundo o análisis con Gemini
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)
        respuesta = model.generate_content(prompt + info_web)
        return respuesta.text
    except Exception as e:
        return f"Error al procesar la solicitud con AIDA: {str(e)}"

# 5. Endpoint de la API que recibe las llamadas de MacroDroid o la Web
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
