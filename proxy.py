from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

BACKEND_UNIDADES_URL = "http://localhost:8001"
BACKEND_DECENAS_URL = "http://localhost:8002"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "Not Found", 404

@app.route('/suma-dos-digitos', methods=['POST', 'OPTIONS'])
def suma_dos_digitos():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        data = request.json
        # Extraer los dígitos
        numberA = int(data.get('NumberA', 0))  # 0-99
        numberB = int(data.get('NumberB', 0))  # 0-99
        
        # Separar en unidades y decenas
        a_unidades = numberA % 10
        a_decenas = numberA // 10
        b_unidades = numberB % 10
        b_decenas = numberB // 10
        
        # Paso 1: Sumar unidades (puerto 8001)
        unidades_response = requests.post(
            f"{BACKEND_UNIDADES_URL}/suma",
            json={
                'NumberA': a_unidades,
                'NumberB': b_unidades,
                'CarryIn': 0
            },
            headers={'Content-Type': 'application/json'}
        )
        unidades_data = unidades_response.json()
        result_unidades = unidades_data['Result']
        carry_out_unidades = unidades_data['CarryOut']
        
        # Paso 2: Sumar decenas usando el carry de unidades (puerto 8002)
        decenas_response = requests.post(
            f"{BACKEND_DECENAS_URL}/suma",
            json={
                'NumberA': a_decenas,
                'NumberB': b_decenas,
                'CarryIn': carry_out_unidades
            },
            headers={'Content-Type': 'application/json'}
        )
        decenas_data = decenas_response.json()
        result_decenas = decenas_data['Result']
        carry_out_decenas = decenas_data['CarryOut']
        
        # Construir el resultado final concatenando: CarryOut(decenas) + Result(decenas) + Result(unidades)
        if carry_out_decenas == 0:
            # Si no hay carry final, solo mostrar decenas+unidades
            resultado_final = str(result_decenas) + str(result_unidades)
        else:
            # Si hay carry final, incluirlo al principio
            resultado_final = str(carry_out_decenas) + str(result_decenas) + str(result_unidades)
        
        resultado_final = int(resultado_final)
        
        response_data = {
            'Result': resultado_final,
            'CarryOut': carry_out_decenas,
            'Details': {
                'Unidades': {
                    'A': a_unidades,
                    'B': b_unidades,
                    'CarryIn': 0,
                    'Result': result_unidades,
                    'CarryOut': carry_out_unidades
                },
                'Decenas': {
                    'A': a_decenas,
                    'B': b_decenas,
                    'CarryIn': carry_out_unidades,
                    'Result': result_decenas,
                    'CarryOut': carry_out_decenas
                }
            }
        }
        
        response = make_response(jsonify(response_data), 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        print(f"Error: {e}")
        response = make_response(jsonify({"error": str(e)}), 500)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
