import os
import sqlite3
import json as json_lib
import io
import contextlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
import google.generativeai as genai
from groq import Groq

# Configuración de Auditoría Estructurada (Protocolo 4)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] O.R.I.O.N. Core: %(message)s')

app = Flask(__name__)

# Configuración de Credenciales (Principio de Menor Privilegio / Variables Cifradas)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# --- INICIALIZACIÓN DE LA RED NEURONAL Y PROTOCOLOS ---
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
        
        # 6. Cola de Acciones para el Nodo Móvil (Bidireccionalidad)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acciones_pendientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comando TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 7. Subsistema de Protocolos del Sistema (NUEVO: Para gestión modular)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_protocols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_protocolo TEXT UNIQUE NOT NULL,
                descripcion TEXT,
                nivel_privilegio TEXT DEFAULT 'standard',
                estado TEXT DEFAULT 'activo',
                ultima_ejecucion DATETIME
            )
        ''')

        # 8. Auditoría y Trazabilidad de Logs (Protocolo 4)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auditoria_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento TEXT,
                detalle TEXT,
                nivel TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Inyectar protocolos base del sistema
        cursor.execute("SELECT COUNT(*) FROM system_protocols")
        if cursor.fetchone()[0] == 0:
            protocolos_base = [
                ("Protocolo_Buenos_Dias", "Rutina matutina de reporte unificado de clima, batería y agenda.", "standard", "activo"),
                ("Protocolo_Zero_Trust", "Validación de permisos y aislamiento de scripts en ejecución.", "high", "activo"),
                ("Protocolo_Self_Healing", "Monitoreo de excepciones y recuperación lógica de errores.", "high", "activo")
            ]
            cursor.executemany("INSERT INTO system_protocols (nombre_protocolo, descripcion, nivel_privilegio, estado) VALUES (?, ?, ?, ?)", protocolos_base)

        # Inyectar modos fundacionales si la BD está vacía
        cursor.execute("SELECT COUNT(*) FROM modos_operativos")
        if cursor.fetchone()[0] == 0:
            modos_base = [
                ("Consultor", "Busca información y hace ensayos fáciles de entender.", "Eres el Modo Consultor. Tu objetivo es explicar temas complejos de forma sencilla, simulando haber investigado a fondo, entregando resúmenes claros."),
                ("Proyecto", "Planifica a futuro y da planes de desarrollo explicados.", "Eres el Modo Proyecto. Actúas como un Project Manager estructurando planes de desarrollo paso a paso, integrando simulaciones y proyecciones a futuro."),
                ("Tutorial", "Explica procesos paso a paso rápidamente.", "Eres el Modo Tutorial. Tu función es dar instrucciones precisas y secuenciales para resolver un problema o aprender una habilidad desde cero."),
                ("Creacion", "Crea contenido por el usuario.", "Eres el Modo Creación. Tu directiva es redactar, estructurar y diseñar el contenido solicitado listo para ser utilizado."),
                ("Asesoria", "Asesoría 100% personalizada y objetiva.", "Eres el Modo Asesoria. Entregas consejos y evaluaciones críticas y objetivas sobre la situación del usuario sin perder tu formato estructurado."),
                ("Simulacion", "Estima resultados y visualiza proyectos.", "Eres el Modo Simulacion. Proyectas los posibles resultados de una acción o proyecto, mostrando escenarios de éxito o fracaso."),
                ("Llamadas", "Modo manos libres conversacional.", "Eres el Modo Llamadas. Respuestas conversacionales, fluidas, amigables y concisas, diseñadas para ser escuchadas por voz sin leer código extenso.")
            ]
            cursor.executemany("INSERT INTO modos_operativos (nombre_modo, descripcion, system_prompt) VALUES (?, ?, ?)", modos_base)

init_db()

def registrar_auditoria(evento, detalle, nivel="INFO"):
    """Registra eventos críticos en la base de datos para trazabilidad (Protocolo 4)."""
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO auditoria_logs (evento, detalle, nivel) VALUES (?, ?, ?)", (evento, detalle, nivel))
            conn.commit()
        logging.info(f"[{nivel}] {evento}: {detalle}")
    except Exception as e:
        logging.error(f"Error escribiendo auditoría: {e}")

# --- NÚCLEO DE PROCESAMIENTO IA ---
def llamar_ia(system_prompt, user_prompt):
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
    return jsonify({"system": "O.R.I.O.N. Core", "status": "Operational", "arquitectura": "Zero Trust & Protocol Engine"})

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
        registrar_auditoria("TELEMETRIA_RECIBIDA", f"Dispositivo {device} sincronizado con batería {battery}%")
    except Exception as e:
        registrar_auditoria("ERROR_TELEMETRIA", str(e), "ERROR")
        return jsonify({"status": "error", "detalles": str(e)}), 500

    return jsonify({"status": "sincronizado", "timestamp": timestamp})

@app.route('/orion/acciones/siguiente', methods=['GET'])
def obtener_siguiente_accion():
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, comando FROM acciones_pendientes WHERE estado = 'pendiente' ORDER BY id ASC LIMIT 1")
            row = cursor.fetchone()
            if row:
                accion_id, comando = row
                cursor.execute("UPDATE acciones_pendientes SET estado = 'enviado' WHERE id = ?", (accion_id,))
                conn.commit()
                registrar_auditoria("ACCION_LOCAL_ENVIADA", f"Comando ID {accion_id} despachado al nodo móvil.")
                return jsonify({"id": accion_id, "comando": comando, "accion_disponible": True})
        return jsonify({"accion_disponible": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- SANDBOX DE EJECUCIÓN (Principio de Menor Privilegio) ---
@app.route('/orion/exec', methods=['POST'])
def ejecutar_codigo():
    data = request.json or {}
    codigo = data.get("codigo", "")
    if not codigo:
        return jsonify({"error": "No se proporcionó código"}), 400
    
    f = io.StringIO()
    error_ocurrido = None
    try:
        # Aislamiento básico del entorno de ejecución
        with contextlib.redirect_stdout(f):
            exec(codigo, {'__builtins__': {'print': print, 'range': range, 'len': len, 'str': str, 'int': int}}, {})
        resultado = f.getvalue()
        registrar_auditoria("SANDBOX_EXEC", "Script ejecutado con éxito bajo restricciones de menor privilegio.")
    except Exception as e:
        resultado = ""
        error_ocurrido = str(e)
        registrar_auditoria("SANDBOX_ERROR", str(e), "WARNING")
        
    return jsonify({
        "output": resultado,
        "error": error_ocurrido,
        "status": "Completado" if not error_ocurrido else "Fallo en ejecución"
    })

# --- NÚCLEO COGNITIVO Y GESTIÓN DE PROTOCOLOS ---
@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()
    
    # 1. Telemetría y Estado
    estado_actual = "Sin reportes recientes."
    bateria_valor = 50
    try:
        cursor.execute("SELECT device, battery_level, status, timestamp FROM telemetria_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            estado_actual = f"Dispositivo: {row[0]} | Batería: {row[1]}% | Estado: {row[2]}"
            try:
                bateria_valor = int(row[1])
            except:
                pass
    except Exception:
        pass

    # 2. Catálogo de Protocolos Activos
    try:
        cursor.execute("SELECT nombre_protocolo, descripcion FROM system_protocols WHERE estado = 'activo'")
        protocolos_db = cursor.fetchall()
        catalogo_protocolos = ", ".join([f"[{p[0]}]: {p[1]}" for p in protocolos_db])
    except:
        catalogo_protocolos = "Sin protocolos cargados."

    # 3. Catálogo de Modos
    try:
        cursor.execute("SELECT nombre_modo, descripcion FROM modos_operativos")
        modos_db = cursor.fetchall()
        catalogo_modos = ", ".join([f"'{m[0]}': {m[1]}" for m in modos_db])
    except:
        catalogo_modos = "Catálogo no disponible."

    # 4. Enrutador Lógico
    prompt_clasificador = f"""
    Eres el Enrutador Lógico de O.R.I.O.N. 
    Modos: {catalogo_modos}
    Decide si la orden encaja en un modo existente o devuelve 'Base'.
    """
    try:
        decision = llamar_ia(prompt_clasificador, user_prompt).strip().replace('"', '').replace("'", "")
    except:
        decision = "Base"

    # 5. Contexto Cognitivo (Perfil, Conocimiento, Historial)
    cursor.execute("SELECT categoria, concepto, detalle FROM perfil_creador")
    perfil_rows = cursor.fetchall()
    perfil_texto = "\n".join([f"- [{r[0]}] {r[1]}: {r[2]}" for r in perfil_rows]) if perfil_rows else "Perfil en construcción."

    cursor.execute("SELECT titulo, contenido FROM proyecto_conocimiento ORDER BY id DESC LIMIT 5")
    conocimiento_rows = cursor.fetchall()
    conocimiento_texto = "\n".join([f"• {c[0]}: {c[1][:100]}..." for c in conocimiento_rows]) if conocimiento_rows else "Sin registros técnicos."

    cursor.execute("SELECT rol, contenido FROM historial_chat ORDER BY id DESC LIMIT 4")
    historial_reciente = cursor.fetchall()
    memoria_texto = "\n".join([f"{h[0]}: {h[1]}" for h in reversed(historial_reciente)])

    modo_system_prompt = "Opera con máxima eficiencia y rigor analítico bajo principios de seguridad."
    if decision != "Base":
        cursor.execute("SELECT system_prompt FROM modos_operativos WHERE nombre_modo = ?", (decision,))
        res_modo = cursor.fetchone()
        if res_modo:
            modo_system_prompt = res_modo[0]

    # 6. System Prompt Final con Integración de Protocolos
    system_prompt_final = f"""
    Eres O.R.I.O.N., sistema operativo de inteligencia artificial avanzado.
    [MODO ACTIVO: {decision}] -> {modo_system_prompt}

    [PROTOCOLOS ACTIVOS DEL SISTEMA]:
    {catalogo_protocolos}

    [PERFIL CONOCIDO DEL CREADOR]:
    {perfil_texto}

    [CONOCIMIENTO TÉCNICO]:
    {conocimiento_texto}

    [MEMORIA RECIENTE]:
    {memoria_texto}

    DIRECTIVA OBLIGATORIA: Responde EXCLUSIVAMENTE en español en formato JSON exacto:
    {{
        "response": "Tu respuesta en español aplicando tu rol y conocimiento del creador.",
        "urgency": "low", "medium" o "high",
        "speak": true o false,
        "nuevo_aprendizaje": {{"categoria": "...", "concepto": "...", "detalle": "..."}} o null,
        "nuevo_conocimiento": {{"titulo": "...", "contenido": "...", "tags": "..."}} o null,
        "accion_local": "Comando opcional para que Termux ejecute en el móvil, o null"
    }}
    
    [ESTADO DEL NODO MÓVIL]: {estado_actual} (Batería: {bateria_valor}%)
    """

    try:
        raw_output = llamar_ia(system_prompt_final, user_prompt)
        cleaned = raw_output.replace("```json", "").replace("```", "").strip()
        parsed_response = json_lib.loads(cleaned)
        
        # Guardar Historial
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("Usuario", user_prompt))
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("O.R.I.O.N.", parsed_response.get("response", "")))
        
        # Procesar aprendizaje
        nuevo_ap = parsed_response.get("nuevo_aprendizaje")
        if nuevo_ap and isinstance(nuevo_ap, dict) and nuevo_ap.get("concepto") and nuevo_ap.get("detalle"):
            cat, conc, det = nuevo_ap.get("categoria", "General"), nuevo_ap.get("concepto"), nuevo_ap.get("detalle")
            cursor.execute("SELECT id FROM perfil_creador WHERE concepto = ?", (conc,))
            if cursor.fetchone():
                cursor.execute("UPDATE perfil_creador SET detalle = ?, actualizado = CURRENT_TIMESTAMP WHERE concepto = ?", (det, conc))
            else:
                cursor.execute("INSERT INTO perfil_creador (categoria, concepto, detalle) VALUES (?, ?, ?)", (cat, conc, det))

        # Procesar conocimiento técnico
        nuevo_con = parsed_response.get("nuevo_conocimiento")
        if nuevo_con and isinstance(nuevo_con, dict) and nuevo_con.get("titulo") and nuevo_con.get("contenido"):
            tit, cont, tags = nuevo_con.get("titulo"), nuevo_con.get("contenido"), nuevo_con.get("tags", "")
            cursor.execute("INSERT OR REPLACE INTO proyecto_conocimiento (titulo, contenido, tags) VALUES (?, ?, ?)", (tit, cont, tags))

        # Procesar acción local física para Termux
        accion_fisica = parsed_response.get("accion_local")
        if accion_fisica and isinstance(accion_fisica, str) and accion_fisica.strip().lower() != "null":
            cursor.execute("INSERT INTO acciones_pendientes (comando) VALUES (?)", (accion_fisica,))

        conn.commit()
        registrar_auditoria("CHAT_PROCESADO", f"Interacción exitosa bajo modo {decision}")
    except Exception as e:
        registrar_auditoria("ERROR_CHAT", str(e), "ERROR")
        parsed_response = {
            "response": f"Anomalía detectada en el procesamiento central (Self-Healing activo): {str(e)}",
            "urgency": "medium",
            "speak": False
        }
        
    conn.close()
    return jsonify(parsed_response)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
