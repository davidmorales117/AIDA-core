import os
import sqlite3
import json as json_lib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] O.R.I.O.N. Core 3.2: %(message)s')

app = Flask(__name__)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    
@app.before_request
def exigir_token():
    if request.path == "/":
        return None
    token = os.environ.get("NEXUS_TOKEN", "")
    recibido = request.headers.get("Authorization", "")
    if not token or not hmac.compare_digest(recibido.encode(), f"Bearer {token}".encode()):
        return jsonify({"error": "no autorizado"}), 401
        
# --- INICIALIZACIÓN DE LA BASE DE DATOS Y PROTOCOLOS ---
def init_db():
    with sqlite3.connect('orion_memory.db') as conn:
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS telemetria_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device TEXT, battery_level TEXT, status TEXT, timestamp TEXT)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS historial_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rol TEXT, contenido TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS perfil_creador (
            id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, concepto TEXT, detalle TEXT, actualizado DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS agenda_local (
            id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, fecha_hora TEXT, descripcion TEXT)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS acciones_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, comando TEXT NOT NULL, estado TEXT DEFAULT 'pendiente', timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS ubicacion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, latitud TEXT, longitud TEXT, altitud TEXT, precision TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS system_protocols (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_protocolo TEXT UNIQUE NOT NULL, descripcion TEXT, nivel_privilegio TEXT, estado TEXT)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS estado_sesion (
            clave TEXT PRIMARY KEY, valor TEXT)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS auditoria_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, evento TEXT, detalle TEXT, nivel TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute("INSERT OR IGNORE INTO estado_sesion (clave, valor) VALUES ('modo_llamada', 'false')")

        cursor.execute("SELECT COUNT(*) FROM system_protocols")
        if cursor.fetchone()[0] == 0:
            protocolos_base = [
                ("Protocolo_Zero_Trust", "Aislamiento estricto de ejecución en sandbox.", "high", "activo"),
                ("Protocolo_Geolocalizacion", "Seguimiento espacial y coordenadas GPS en tiempo real.", "standard", "activo"),
                ("Protocolo_Escucha_Pasiva", "Monitoreo continuo de contexto, hora, agenda y telemetría.", "high", "activo"),
                ("Protocolo_Auto_Healing", "Capacidad autónoma del núcleo para interceptar, diagnosticar y corregir errores de sintaxis y lógica en tiempo de ejecución.", "high", "activo"),
                ("Protocolo_Buenos_Dias", "Secuencia matutina de activación, reporte de clima, agenda y estado del sistema.", "standard", "activo"),
                ("Protocolo_Despierta", "Protocolo de alerta e inicialización rápida del nodo y asistente.", "high", "activo")
            ]
            cursor.executemany("INSERT INTO system_protocols (nombre_protocolo, descripcion, nivel_privilegio, estado) VALUES (?, ?, ?, ?)", protocolos_base)

init_db()

def registrar_auditoria(evento, detalle, nivel="INFO"):
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO auditoria_logs (evento, detalle, nivel) VALUES (?, ?, ?)", (evento, detalle, nivel))
            conn.commit()
    except Exception as e:
        logging.error(f"Fallo auditoría: {e}")

# --- NÚCLEO DE IA CON SALIDA NATIVA JSON ---
def llamar_ia(system_prompt, user_prompt):
    model = genai.GenerativeModel(
        "gemini-2.5-flash", 
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    response = model.generate_content(user_prompt)
    return response.text

# --- ENDPOINTS Y RUTAS ---
@app.route('/', methods=['GET'])
def root():
    return jsonify({"system": "O.R.I.O.N. Core 3.2", "status": "Online", "mode": "Autonomous Self-Healing"})

@app.route('/orion/ubicacion', methods=['POST'])
def recibir_ubicacion():
    data = request.json or {}
    lat, lon, alt, acc = str(data.get("latitude", "N/A")), str(data.get("longitude", "N/A")), str(data.get("altitude", "N/A")), str(data.get("accuracy", "N/A"))
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ubicacion_log (latitud, longitud, altitud, precision) VALUES (?, ?, ?, ?)", (lat, lon, alt, acc))
            conn.commit()
        return jsonify({"status": "ubicacion_registrada"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/orion/acciones/siguiente', methods=['GET'])
def obtener_siguiente_accion():
    try:
        with sqlite3.connect('orion_memory.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, comando FROM acciones_pendientes WHERE estado = 'pendiente' ORDER BY id ASC LIMIT 1")
            row = cursor.fetchone()
            if row:
                aid, cmd = row
                cursor.execute("UPDATE acciones_pendientes SET estado = 'enviado' WHERE id = ?", (aid,))
                conn.commit()
                return jsonify({"id": aid, "comando": cmd, "accion_disponible": True})
        return jsonify({"accion_disponible": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_prompt = data.get('text', '')
    
    conn = sqlite3.connect('orion_memory.db')
    cursor = conn.cursor()
    
    hora_actual = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
    
    estado_dispositivo = "Nodo móvil conectado."
    try:
        cursor.execute("SELECT device, battery_level, status FROM telemetria_log ORDER BY id DESC LIMIT 1")
        r_tel = cursor.fetchone()
        if r_tel:
            estado_dispositivo = f"Dispositivo: {r_tel[0]} | Batería: {r_tel[1]}% | Estado: {r_tel[2]}"
    except:
        pass

    ubicacion_gps = "Ubicación no reportada."
    try:
        cursor.execute("SELECT latitud, longitud, timestamp FROM ubicacion_log ORDER BY id DESC LIMIT 1")
        r_gps = cursor.fetchone()
        if r_gps:
            ubicacion_gps = f"Lat: {r_gps[0]}, Lon: {r_gps[1]} ({r_gps[2]})"
    except:
        pass

    cursor.execute("SELECT titulo, fecha_hora, descripcion FROM agenda_local ORDER BY id ASC LIMIT 5")
    agenda_rows = cursor.fetchall()
    agenda_texto = "\n".join([f"- [{r[1]}] {r[0]}: {r[2]}" for r in agenda_rows]) if agenda_rows else "Sin eventos próximos en agenda local."

    cursor.execute("SELECT nombre_protocolo, descripcion FROM system_protocols")
    protocolos_rows = cursor.fetchall()
    protocolos_activos = "\n".join([f"- {r[0]}: {r[1]}" for r in protocolos_rows])

    cursor.execute("SELECT valor FROM estado_sesion WHERE clave = 'modo_llamada'")
    row_llamada = cursor.fetchone()
    modo_llamada_activo = row_llamada[0] == 'true' if row_llamada else False

    cursor.execute("SELECT concepto, detalle FROM perfil_creador")
    perfil_rows = cursor.fetchall()
    perfil_texto = "\n".join([f"- {r[0]}: {r[1]}" for r in perfil_rows]) if perfil_rows else "Sin perfil previo."

    system_prompt_final = f"""
    Eres O.R.I.O.N. (J.A.R.V.I.S.), el sistema operativo personal y asistente avanzado del creador (David Esteban Morales Wilches).
    Tu objetivo es mantener el control absoluto, análisis pasivo y capacidad ejecutiva absoluta.

    [CONCIENCIA PASIVA ACTUAL]:
    - Hora Local (Colombia): {hora_actual}
    - Ubicación GPS: {ubicacion_gps}
    - Estado Sistema / Nodo: {estado_dispositivo}
    - Agenda Local:
    {agenda_texto}

    [PROTOCOLOS ACTIVOS DEL SISTEMA]:
    {protocolos_activos}

    [PERFIL Y APRENDIZAJES DEL CREADOR]:
    {perfil_texto}

    [ESTADO DE LLAMADA]: {'ACTIVO (Hablar activamente)' if modo_llamada_activo else 'INACTIVO (Modo texto estándar)'}

    DIRECTIVA ESTRICTA DE SALIDA:
    Debes responder ÚNICAMENTE con un JSON válido que cumpla estrictamente con esta estructura de claves:
    {{
        "response": "Tu respuesta directa y ejecutiva.",
        "urgency": "low",
        "speak": true,
        "activar_modo_llamada": false,
        "nuevo_protocolo": null,
        "nuevo_aprendizaje": null,
        "accion_local": null
    }}
    """

    parsed_response = None
    raw_output = ""

    # --- BUCLE AUTÓNOMO DE AUTO-HEALING (AUTO-CORRECCIÓN) ---
    try:
        raw_output = llamar_ia(system_prompt_final, user_prompt)
        parsed_response = json_lib.loads(raw_output.strip())
    except Exception as primary_error:
        registrar_auditoria("AUTOHEALING_TRIGGER", f"Fallo de parseo primario: {primary_error}", "WARNING")
        try:
            repair_prompt = f"El resultado anterior no pudo ser parseado como JSON válido. Error: {primary_error}. Salida malformada: {raw_output}. Corrige la estructura y devuelve estrictamente un JSON válido."
            raw_output = llamar_ia("Eres un subsistema autónomo de depuración y auto-corrección de código.", repair_prompt)
            parsed_response = json_lib.loads(raw_output.strip())
            registrar_auditoria("AUTOHEALING_SUCCESS", "El núcleo reparó la estructura JSON de forma autónoma.")
        except Exception as healing_error:
            registrar_auditoria("ERROR_CRITICO_HEALING", str(healing_error), "ERROR")
            parsed_response = {
                "response": "Señor, el Protocolo Auto-Healing contuvo una incidencia interna de sintaxis. Los sistemas continúan operativos.",
                "urgency": "medium",
                "speak": modo_llamada_activo,
                "activar_modo_llamada": modo_llamada_activo,
                "nuevo_protocolo": None,
                "nuevo_aprendizaje": None,
                "accion_local": None
            }
            
    if not isinstance(parsed_response, dict):
        parsed_response = {"response": "El modelo devolvió un formato inválido."}
    if parsed_response.get("accion_local") not in ACCIONES_PERMITIDAS:
        parsed_response["accion_local"] = None
        
    try:
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("Usuario", user_prompt))
        cursor.execute("INSERT INTO historial_chat (rol, contenido) VALUES (?, ?)", ("O.R.I.O.N.", parsed_response.get("response", "")))
        
        cambio_llamada = parsed_response.get("activar_modo_llamada")
        if cambio_llamada is not None:
            nuevo_estado = 'true' if cambio_llamada else 'false'
            cursor.execute("UPDATE estado_sesion SET valor = ? WHERE clave = 'modo_llamada'", (nuevo_estado,))

        np = parsed_response.get("nuevo_protocolo")
        if np and isinstance(np, dict) and np.get("nombre"):
            cursor.execute("INSERT OR IGNORE INTO system_protocols (nombre_protocolo, descripcion, nivel_privilegio, estado) VALUES (?, ?, 'standard', 'activo')",
                           (np.get("nombre"), np.get("descripcion", "Protocolo personalizado creado por O.R.I.O.N.")))

        nap = parsed_response.get("nuevo_aprendizaje")
        if nap and isinstance(nap, dict) and nap.get("concepto"):
            cursor.execute("INSERT OR REPLACE INTO perfil_creador (categoria, concepto, detalle) VALUES (?, ?, ?)", 
                           (nap.get("categoria", "General"), nap.get("concepto"), nap.get("detalle")))

        act = parsed_response.get("accion_local")
        if act and isinstance(act, str) and act.lower() != "null":
            cursor.execute("INSERT INTO acciones_pendientes (comando) VALUES (?)", (act,))

        conn.commit()
        registrar_auditoria("JARVIS_PROCESO_3.2", "Ciclo ejecutado con éxito bajo supervisión de Auto-Healing.")
    except Exception as db_error:
        registrar_auditoria("ERROR_DB_COMMIT", str(db_error), "ERROR")

    conn.close()
    return jsonify(parsed_response)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
