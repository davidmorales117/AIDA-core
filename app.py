from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['POST'])
def aida_logic():
    # Recibe el mensaje desde MacroDroid
    data = request.json
    mensaje = data.get("text", "").lower()
    
    # Lógica básica de AIDA
    if "hola" in mensaje:
        respuesta = "Sistemas en línea, Señor. AIDA a tu servicio."
    elif "hora" in mensaje:
        from datetime import datetime
        respuesta = f"La hora es {datetime.now().strftime('%H:%M')}"
    else:
        respuesta = f"Entendido, procesando: {mensaje}"
        
    return jsonify({"response": respuesta})

if __name__ == '__main__':
    app.run(debug=True)