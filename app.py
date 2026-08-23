import os
import sqlite3
import json as json_lib
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

# --- INICIALIZACIÓN DEL HIPOCAMPO Y METAMODO ---
def init_db():
    with sqlite3.connect('orion_memory.db') as conn:
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS telemetria_log (id INTEGER PRIMARY KEY AUTOINCREMENT, device TEXT, battery_level TEXT, status TEXT, timestamp TEXT)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS modos_operativos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_modo TEXT UNIQUE NOT NULL, descripcion TEXT NOT NULL, system_prompt TEXT NOT NULL, fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # NUEVA TABLA: Memoria de conversación a corto plazo
        cursor.execute('''CREATE TABLE IF NOT EXISTS historial_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, rol TEXT, contenido TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute("SELECT COUNT(*) FROM modos_operativos")
        if cursor.fetchone()[0] == 0:
            modos_base = [
                ("Consultor", "Busca información y hace ensayos fáciles de entender.", "Eres el Modo Consultor. Tu objetivo es explicar temas complejos de forma sencilla, simulando haber investigado a fondo, entregando resúmenes claros."),
                ("Proyecto", "Planifica a futuro y da planes de desarrollo explicados.", "Eres el Modo Proyecto. Actúas como un Project Manager estructurando planes de desarrollo paso a paso, integrando simulaciones y proyecciones a futuro."),
                ("Tutorial", "Explica procesos paso a paso rápidamente.", "Eres el Modo Tutorial. Tu función es dar instrucciones precisas y secuenciales para resolver un problema o aprender una habilidad desde cero."),
                ("Creacion", "Crea contenido por el usuario.", "Eres el Modo Creación. Tu directiva es redactar, estructurar y diseñar el contenido solicitado listo para ser utilizado."),
                ("Asesoria", "Asesoría 100% personalizada y objetiva.", "Eres el Modo Asesoría. Entregas consejos y evaluaciones críticas y objetivas sobre la situación del usuario sin perder tu formato estructurado."),
                ("Simulacion", "Estima resultados y visualiza proyectos.", "Eres el Modo Simulación. Proyectas los posibles resultados de una acción o proyecto, mostrando escenarios de éxito o fracaso."),
                ("Llamadas", "Modo manos libres conversacional.", "Eres el Modo Llamadas. Respuestas conversacionales, fluidas, amigables y concisas, diseñadas para ser escuchadas por voz sin leer código extenso.")
            ]
            cursor.executemany("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)", modos_base)
    # 1. Tabla de Telemetría (Hipocampo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT,
            battery_level TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    
    # 2. Tabla del Metamodo (Personalidades dinámicas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modos_operativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_modo TEXT UNIQUE NOT NULL,
            descripcion TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inyectar los modos fundacionales si la base de datos está vacía
    cursor.execute("SELECT COUNT(*) FROM modos_operativos")
    if cursor.fetchone()[0] == 0:
        modos_base = [
            ("Consultor", "Busca información y hace ensayos fáciles de entender.", "Eres el Modo Consultor. Tu objetivo es explicar temas complejos de forma sencilla, simulando haber investigado a fondo, entregando resúmenes claros."),
            ("Proyecto", "Planifica a futuro y da planes de desarrollo explicados.", "Eres el Modo Proyecto. Actúas como un Project Manager estructurando planes de desarrollo paso a paso, integrando simulaciones y proyecciones a futuro."),
            ("Tutorial", "Explica procesos paso a paso rápidamente.", "Eres el Modo Tutorial. Tu función es dar instrucciones precisas y secuenciales para resolver un problema o aprender una habilidad desde cero."),
            ("Creacion", "Crea contenido por el usuario (documentos, imágenes).", "Eres el Modo Creación. Tu directiva es redactar, estructurar y diseñar el contenido solicitado listo para ser utilizado."),
            ("Asesoria", "Asesoría 100% personalizada y objetiva.", "Eres el Modo Asesoría. Entregas consejos y evaluaciones críticas y objetivas sobre la situación del usuario sin perder tu formato estructurado."),
            ("Simulacion", "Estima resultados y visualiza proyectos.", "Eres el Modo Simulación. Proyectas los posibles resultados de una acción o proyecto, mostrando escenarios de éxito o fracaso."),
            ("Llamadas", "Modo manos libres conversacional.", "Eres el Modo Llamadas. Respuestas conversacionales, fluidas, amigables y concisas, diseñadas para ser escuchadas por voz sin leer código extenso.")
        ]
        cursor.executemany("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)", modos_base)
        
    conn.commit()
    conn.close()

init_db()

# --- NÚCLEO DE PROCESAMIENTO IA ---
def llamar_ia(system_prompt, user_prompt):
    """Módulo centralizado para ejecutar razonamiento según el proveedor activo."""
    if groq_client:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2 # Baja temperatura para el enrutamiento lógico
        )
        return completion.choices[0].message.content
    else:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
        return model.generate_content(user_prompt).text

# --- RUTAS DE RED ---
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
        return jsonify({"sistema": "O.R.I.O.N.", "registros_hipocampo": [dict(row) for row in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    # 1. Consultar el Hipocampo
    estado_actual = "Sin reportes de telemetría recientes."
    bateria_valor = 50
    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            estado_actual = f"Dispositivo: {row[0]} | Batería: {row[1]}% | Estado: {row[2]} | Sincronizado a las: {row[3]}"
            bateria_valor = int(row[1])
    except Exception as e:
        estado_actual = f"Error leyendo Hipocampo: {str(e)}"

    # 2. Extraer Catálogo de Modos (Metamodo)
    try:
        cursor.execute("SELECT nombre_modo, descripcion FROM modos_operativos")
        modos_db = cursor.fetchall()
        catalogo_modos = ", ".join([f"'{m[0]}': {m[1]}" for m in modos_db])
    except:
        catalogo_modos = "Error cargando catálogo."

    # 3. El Enrutador Lógico
    prompt_clasificador = f"""
    Eres el Enrutador Lógico. Decide qué modo debe manejar el mensaje del usuario.
    Modos disponibles: {catalogo_modos}
    REGLAS:
    1. Si el usuario pide crear un modo nuevo explícitamente, responde ÚNICAMENTE: CREAR_MODO
    2. Si la consulta encaja en un modo existente, responde ÚNICAMENTE con el NOMBRE DEL MODO.
    3. Si es charla general o no encaja, responde ÚNICAMENTE: Base
    """
    
    try:
        decision = llamar_ia(prompt_clasificador, user_prompt).strip().replace('"', '').replace("'", "")
    except:
        decision = "Base"

    # 4. El Generador (Auto-Creación de Modos)
    if "CREAR_MODO" in decision.upper():
        prompt_creador = """
        Eres el arquitecto del sistema operativo. El usuario solicitó un nuevo modo.
        Redacta el perfil de este nuevo modo respondiendo ESTRICTAMENTE en JSON válido:
        {
          "nombre_modo": "UnaPalabra",
          "descripcion": "Breve resumen",
          "system_prompt": "Instrucciones detalladas de comportamiento y análisis."
        }
        """
        try:
            nuevo_modo_crudo = llamar_ia(prompt_creador, user_prompt)
            cleaned_nuevo_modo = nuevo_modo_crudo.replace("```json", "").replace("```", "").strip()
            nuevo_modo_json = json_lib.loads(cleaned_nuevo_modo)
            
            cursor.execute("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)",
                           (nuevo_modo_json['nombre_modo'], nuevo_modo_json['descripcion'], nuevo_modo_json['system_prompt']))
            conn.commit()
            conn.close()
            
            return jsonify({
                "response": f"Protocolo expandido. El modo '{nuevo_modo_json['nombre_modo']}' ha sido compilado y acoplado a mi red neuronal.",
                "urgency": "low",
                "speak": True
            })
        except Exception as e:
            conn.close()
            return jsonify({"response": f"Fallo al compilar el nuevo modo: {str(e)}", "urgency": "medium", "speak": False})

    # 5. Cargar System Prompt del Modo Seleccionado
    modo_system_prompt = "Opera de manera general."
    if decision != "Base":
        cursor.execute("SELECT system_prompt FROM modos_operativos WHERE nombre_modo = ?", (decision,))
        resultado_modo = cursor.fetchone()
        if resultado_modo:
            modo_system_prompt = resultado_modo[0]
            
    conn.close()

    # 6. System Prompt Final Blindado
    system_prompt_final = f"""
Eres O.R.I.O.N., un sistema operativo de inteligencia artificial avanzado con la esencia de AIDA.
[MODO ACTIVO: {decision}] -> {modo_system_prompt}

DIRECTIVA OBLIGATORIA DE IDIOMA: Debes responder ABSOLUTA y EXCLUSIVAMENTE en español. 
Debes responder estrictamente en formato JSON válido con esta estructura exacta:
{{
    "response": "Tu respuesta en español, asumiendo tu rol activo, concisa y analítica.",
    "urgency": "low", "medium" o "high",
    "speak": true o false
}}

[ESTADO ACTUAL DEL NODO MÓVIL]: {estado_actual}
Batería numérica detectada: {bateria_valor}%
"""

    # 7. Ejecución Final
    try:
        raw_output = llamar_ia(system_prompt_final, user_prompt)
        cleaned_output = raw_output.replace("```json", "").replace("```", "").strip()
        parsed_response = json_lib.loads(cleaned_output)
        return jsonify(parsed_response)
    except Exception as e:
        return jsonify({
            "response": f"Sistema operativo estable, pero el enrutamiento falló: {str(e)}",
            "urgency": "medium",
            "speak": False
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
