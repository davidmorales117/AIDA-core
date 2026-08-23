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

  # 3. El Enrutador Lógico Avanzado
    prompt_clasificador = f"""
    Eres el Enrutador Lógico de AIDA. Decide qué acción ejecutar según el usuario.
    Modos disponibles: {catalogo_modos}
    REGLAS ESTRICTAS DE RESPUESTA (Solo devuelve la palabra exacta):
    1. Si pide crear un modo nuevo: CREAR_MODO
    2. Si pide ELIMINAR un modo: ELIMINAR_MODO_[Nombre] (ej. ELIMINAR_MODO_Consultor)
    3. Si pide MODIFICAR/EDITAR un modo: EDITAR_MODO_[Nombre]
    4. Si es una consulta normal que encaja en un modo existente: [NOMBRE_DEL_MODO]
    5. Si no encaja en nada: Base
    """
    
    try:
        decision = llamar_ia(prompt_clasificador, user_prompt).strip().replace('"', '').replace("'", "")
    except:
        decision = "Base"

    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()

    # 4. Auto-Gestión de la Red Neuronal (CRUD)
    if decision.startswith("CREAR_MODO"):
        # (Usa la misma lógica de creación que ya teníamos, es perfecta)
        prompt_creador = """Redacta el perfil de este nuevo modo en JSON válido: {"nombre_modo": "X", "descripcion": "Y", "system_prompt": "Z"}"""
        nuevo_modo_crudo = llamar_ia(prompt_creador, user_prompt)
        nuevo_modo_json = json_lib.loads(nuevo_modo_crudo.replace("```json", "").replace("```", "").strip())
        cursor.execute("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)", (nuevo_modo_json['nombre_modo'], nuevo_modo_json['descripcion'], nuevo_modo_json['system_prompt']))
        conn.commit()
        conn.close()
        return jsonify({"response": f"Modo '{nuevo_modo_json['nombre_modo']}' acoplado a mi red neuronal.", "urgency": "low", "speak": True})

    elif decision.startswith("ELIMINAR_MODO_"):
        modo_a_borrar = decision.split("_")[2]
        cursor.execute("DELETE FROM modos_operativos WHERE nombre_modo = ?", (modo_a_borrar,))
        conn.commit()
        conn.close()
        return jsonify({"response": f"Protocolo '{modo_a_borrar}' purgado de la memoria, señor.", "urgency": "medium", "speak": True})

    # (Nota: La lógica de EDITAR_MODO se procesaría extrayendo el modo y haciendo un UPDATE en SQL con un nuevo prompt generado por la IA)

    # 5. Extraer Historial de Charla (Memoria a Corto Plazo)
    cursor.execute("SELECT rol, contenido FROM historial_chat ORDER BY id DESC LIMIT 4")
    historial_reciente = cursor.fetchall()
    memoria_texto = "\n".join([f"{h[0]}: {h[1]}" for h in reversed(historial_reciente)])

    # 6. Cargar Modo Activo
    modo_system_prompt = "Opera de manera general y analítica."
    if decision != "Base" and not decision.startswith("EDITAR"):
        cursor.execute("SELECT system_prompt FROM modos_operativos WHERE nombre_modo = ?", (decision,))
        resultado_modo = cursor.fetchone()
        if resultado_modo:
            modo_system_prompt = resultado_modo[0]

    # 7. System Prompt Final con Memoria Inyectada
    system_prompt_final = f"""
    Eres AIDA, un sistema operativo de inteligencia artificial avanzado.
    [MODO ACTIVO: {decision}] -> {modo_system_prompt}

    [MEMORIA RECIENTE DE LA CONVERSACIÓN]:
    {memoria_texto}

    DIRECTIVA OBLIGATORIA: Responde EXCLUSIVAMENTE en español. Devuelve JSON válido con "response", "urgency", "speak".
    [ESTADO ACTUAL DEL NODO MÓVIL]: {estado_actual}
    Batería: {bateria_valor}%
    """
    
    # 8. Ejecución y Guardado
    try:
        raw_output = llamar_ia(system_prompt_final, user_prompt)
        parsed_response = json_lib.loads(raw_output.replace("```json", "").replace("```", "").strip())
        
        # Guardar en historial
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("Usuario", user_prompt))
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("AIDA", parsed_response["response"]))
        conn.commit()
        
    except Exception as e:
        parsed_response = {"response": f"Fallo lógico en el enrutamiento final: {str(e)}", "urgency": "medium", "speak": False}
        
    conn.close()
    return jsonify(parsed_response)
   
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
