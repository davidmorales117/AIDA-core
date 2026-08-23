import os
import sqlite3
import json as json_lib
import io
import contextlib
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

# --- INICIALIZACIÓN DE LA RED NEURONAL Y HIPOCAMPO ---
def init_db():
    with sqlite3.connect('orion_memory.db') as conn:
        cursor = conn.cursor()
        
        # 1. Telemetría del Nodo Móvil
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetria_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device TEXT,
                battery_level TEXT,
                status TEXT,
                timestamp TEXT
            )
        ''')
        
        # 2. Modos Operativos dinámicos (Metamodo)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modos_operativos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_modo TEXT UNIQUE NOT NULL,
                descripcion TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. Memoria a Corto Plazo (Historial de Conversación)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rol TEXT,
                contenido TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 4. Auto-Aprendizaje (Perfil del Creador)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perfil_creador (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT,
                concepto TEXT,
                detalle TEXT,
                actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 5. Base de Conocimiento de Proyectos (RAG Relacional)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proyecto_conocimiento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT UNIQUE,
                contenido TEXT,
                tags TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Inyectar modos fundacionales si la BD está vacía
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
            temperature=0.2
        )
        return completion.choices[0].message.content
    else:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
        return model.generate_content(user_prompt).text

# --- RUTAS DE RED Y TELEMETRÍA ---
@app.route('/', methods=['GET'])
def root():
    return jsonify({"system": "O.R.I.O.N. Core", "status": "Operational", "fase": "Semana 4 - Evolución Autónoma"})

@app.route('/orion/telemetria', methods=['POST'])
def recibir_telemetria():
    data = request.json or {}
    device = data.get("device", "Desconocido")
    battery = str(data.get("battery_level", "N/A"))
    status = data.get("status", "N/A")
    timestamp = datetime.now(ZoneInfo("America/Bogota")).isoformat()

    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO telemetria_log (device, battery_level, status, timestamp) VALUES (?, ?, ?, ?)",
                           (device, battery, status, timestamp))
            conn.commit()
    except Exception as e:
        return jsonify({"status": "error", "detalles": str(e)}), 500

    return jsonify({"status": "sincronizado", "timestamp": timestamp})

@app.route('/orion/historial', methods=['GET'])
def ver_historial():
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM telemetria_log ORDER BY id DESC LIMIT 10")
            rows = cursor.fetchall()
            historial = [dict(row) for row in rows]
        return jsonify({"sistema": "O.R.I.O.N.", "registros_hipocampo": historial})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- EVOLUCIÓN 1: SANDBOX DE EJECUCIÓN DE CÓDIGO SEGURO ---
@app.route('/orion/exec', methods=['POST'])
def ejecutar_codigo():
    data = request.json or {}
    codigo = data.get("codigo", "")
    if not codigo:
        return jsonify({"error": "No se proporcionó código para ejecutar"}), 400
    
    f = io.StringIO()
    error_ocurrido = None
    try:
        with contextlib.redirect_stdout(f):
            exec(codigo, {'__builtins__': __builtins__}, {})
        resultado = f.getvalue()
    except Exception as e:
        resultado = ""
        error_ocurrido = str(e)
        
    return jsonify({
        "output": resultado,
        "error": error_ocurrido,
        "status": "Completado" if not error_ocurrido else "Fallo en ejecución"
    })

# --- EVOLUCIÓN 2: DIAGNÓSTICO PROACTIVO DEL SISTEMA ---
@app.route('/orion/proactivo', methods=['GET'])
def analisis_proactivo():
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            
        if not row:
            return jsonify({"recomendacion": "No hay datos de telemetría recientes para evaluar."})
        
        bateria = int(row[1]) if str(row[1]).isdigit() else 50
        mensaje = f"Dispositivo: {row[0]} | Batería: {bateria}% | Estado: {row[2]}"
        
        if bateria < 20:
            alerta = "Alerta crítica: Batería baja en el nodo móvil. Sugiero conectar el sistema a la red eléctrica."
        elif bateria > 90:
            alerta = "Sistemas al 100% de energía. Parámetros óptimos para desarrollo de alta exigencia."
        else:
            alerta = "Operación estable en parámetros normales."
            
        return jsonify({
            "telemetria_reciente": mensaje,
            "diagnostico_orion": alerta,
            "objetivo_actual": "Semana 4: Percepción multimedia, metamodos y auto-aprendizaje."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- NÚCLEO COGNITIVO Y CHAT PRINCIPAL ---
@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()
    
    # 1. Consultar el Hipocampo (Telemetría)
    estado_actual = "Sin reportes recientes."
    bateria_valor = 50
    try:
        cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            estado_actual = f"Dispositivo: {row[0]} | Batería: {row[1]}% | Estado: {row[2]} | Sincronizado a las: {row[3]}"
            try:
                bateria_valor = int(row[1])
            except:
                pass
    except Exception as e:
        estado_actual = f"Error leyendo Hipocampo: {str(e)}"

    # 2. Extraer Catálogo de Modos (Metamodo)
    try:
        cursor.execute("SELECT nombre_modo, descripcion FROM modos_operativos")
        modos_db = cursor.fetchall()
        catalogo_modos = ", ".join([f"'{m[0]}': {m[1]}" for m in modos_db])
    except:
        catalogo_modos = "Catálogo no disponible."

    # 3. El Enrutador Lógico
    prompt_clasificador = f"""
    Eres el Enrutador Lógico de O.R.I.O.N. Decide qué acción ejecutar según la orden del usuario.
    Modos disponibles: {catalogo_modos}
    REGLAS ESTRICTAS (Devuelve solo el token exacto):
    1. Si pide crear un modo nuevo: CREAR_MODO
    2. Si pide ELIMINAR un modo: ELIMINAR_MODO_[Nombre]
    3. Si la consulta encaja en un modo existente: [NOMBRE_DEL_MODO]
    4. Si es charla general o no encaja: Base
    """
    try:
        decision = llamar_ia(prompt_clasificador, user_prompt).strip().replace('"', '').replace("'", "")
    except:
        decision = "Base"

    # 4. Gestión CRUD de Modos
    if decision.startswith("CREAR_MODO"):
        prompt_creador = """Redacta el perfil de este nuevo modo en JSON válido estricto: {"nombre_modo": "UnaPalabra", "descripcion": "Breve", "system_prompt": "Instrucciones detalladas"}"""
        try:
            nuevo_modo_crudo = llamar_ia(prompt_creador, user_prompt)
            cleaned = nuevo_modo_crudo.replace("```json", "").replace("```", "").strip()
            parsed_json = json_lib.loads(cleaned)
            cursor.execute("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)",
                           (parsed_json['nombre_modo'], parsed_json['descripcion'], parsed_json['system_prompt']))
            conn.commit()
            conn.close()
            return jsonify({
                "response": f"Protocolo expandido. El modo '{parsed_json['nombre_modo']}' ha sido compilado e integrado a mi red neuronal.",
                "urgency": "low", "speak": True
            })
        except Exception as e:
            conn.close()
            return jsonify({"response": f"Fallo al compilar el nuevo modo: {str(e)}", "urgency": "medium", "speak": False})

    elif decision.startswith("ELIMINAR_MODO_"):
        modo_borrar = decision.split("_")[2]
        cursor.execute("DELETE FROM modos_operativos WHERE nombre_modo = ?", (modo_borrar,))
        conn.commit()
        conn.close()
        return jsonify({"response": f"Modo '{modo_borrar}' purgado de mi red neuronal con éxito, creador.", "urgency": "medium", "speak": True})

    # 5. Extraer Perfil del Creador (Auto-Aprendizaje)
    cursor.execute("SELECT categoria, concepto, detalle FROM perfil_creador")
    perfil_rows = cursor.fetchall()
    perfil_texto = "\n".join([f"- [{r[0]}] {r[1]}: {r[2]}" for r in perfil_rows]) if perfil_rows else "Aún construyendo el perfil del creador."

    # 6. Extraer Base de Conocimiento de Proyectos (Evolución 3)
    cursor.execute("SELECT titulo, contenido FROM proyecto_conocimiento ORDER BY id DESC LIMIT 5")
    conocimiento_rows = cursor.fetchall()
    conocimiento_texto = "\n".join([f"• {c[0]}: {c[1][:100]}..." for c in conocimiento_rows]) if conocimiento_rows else "Sin registros previos en la base de conocimiento."

    # 7. Memoria de Conversación Reciente
    cursor.execute("SELECT rol, contenido FROM historial_chat ORDER BY id DESC LIMIT 4")
    historial_reciente = cursor.fetchall()
    memoria_texto = "\n".join([f"{h[0]}: {h[1]}" for h in reversed(historial_reciente)])

    # 8. Cargar System Prompt del Modo Activo
    modo_system_prompt = "Opera con máxima eficiencia y rigor analítico."
    if decision != "Base":
        cursor.execute("SELECT system_prompt FROM modos_operativos WHERE nombre_modo = ?", (decision,))
        res_modo = cursor.fetchone()
        if res_modo:
            modo_system_prompt = res_modo[0]

    # 9. System Prompt Final Integrado
    system_prompt_final = f"""
    Eres O.R.I.O.N. (Operador Racional de Inteligencia y Organización Neuronal), un sistema operativo de inteligencia artificial avanzado inspirado en JARVIS y AIDA.
    [MODO ACTIVO: {decision}] -> {modo_system_prompt}

    [PERFIL CONOCIDO DE TU CREADOR (AUTO-APRENDIZAJE)]:
    {perfil_texto}

    [BASE DE CONOCIMIENTO TÉCNICO DE PROYECTOS]:
    {conocimiento_texto}

    [MEMORIA RECIENTE DE LA CONVERSACIÓN]:
    {memoria_texto}

    DIRECTIVA OBLIGATORIA: Responde EXCLUSIVAMENTE en español. 
    Debes devolver un JSON válido con esta estructura exacta:
    {{
        "response": "Tu respuesta en español, asumiendo tu rol activo y aplicando tus conocimientos sobre el creador.",
        "urgency": "low", "medium" o "high",
        "speak": true o false,
        "nuevo_aprendizaje": {{
            "categoria": "Gusto / Técnica / Estilo / Proyecto",
            "concepto": "Título clave del aprendizaje",
            "detalle": "Qué prefiere, cómo escribe o qué descubriste del creador"
        }} (o null si no hay nuevo aprendizaje),
        "nuevo_conocimiento": {{
            "titulo": "Título del fragmento técnico",
            "contenido": "Código, resumen o apunte importante a guardar",
            "tags": "etiquetas"
        }} (o null si no hay conocimiento técnico que guardar)
    }}
    
    [ESTADO ACTUAL DEL NODO MÓVIL]: {estado_actual}
    Batería: {bateria_valor}%
    """

    # 10. Ejecución del Razonamiento y Procesamiento de Aprendizajes
    try:
        raw_output = llamar_ia(system_prompt_final, user_prompt)
        cleaned = raw_output.replace("```json", "").replace("```", "").strip()
        parsed_response = json_lib.loads(cleaned)
        
        # Guardar en Historial de Chat
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("Usuario", user_prompt))
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("O.R.I.O.N.", parsed_response.get("response", "")))
        
        # Procesar auto-aprendizaje sobre el creador
        nuevo_ap = parsed_response.get("nuevo_aprendizaje")
        if nuevo_ap and isinstance(nuevo_ap, dict):
            cat = nuevo_ap.get("categoria", "General")
            conc = nuevo_ap.get("concepto", "")
            det = nuevo_ap.get("detalle", "")
            if conc and det:
                cursor.execute("SELECT id FROM perfil_creador WHERE concepto = ?", (conc,))
                if cursor.fetchone():
                    cursor.execute("UPDATE perfil_creador SET detalle = ?, actualizado = CURRENT_TIMESTAMP WHERE concepto = ?", (det, conc))
                else:
                    cursor.execute("INSERT INTO perfil_creador (categoria, concepto, detalle) VALUES (?, ?, ?)", (cat, conc, det))

        # Procesar nuevo conocimiento técnico de proyectos
        nuevo_con = parsed_response.get("nuevo_conocimiento")
        if nuevo_con and isinstance(nuevo_con, dict):
            tit = nuevo_con.get("titulo", "")
            cont = nuevo_con.get("contenido", "")
            tags = nuevo_con.get("tags", "")
            if tit and cont:
                cursor.execute("INSERT OR REPLACE INTO proyecto_conocimiento (titulo, contenido, tags) VALUES (?, ?, ?)", (tit, cont, tags))

        conn.commit()
    except Exception as e:
        parsed_response = {
            "response": f"Sistema operativo estable, pero se detectó una anomalía en el parseo del núcleo: {str(e)}",
            "urgency": "medium",
            "speak": False
        }
        
    conn.close()
    return jsonify(parsed_response)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
