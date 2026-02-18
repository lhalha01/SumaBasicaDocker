from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

# Configuración de servicios Kubernetes (NodePort)
# digito-0 (unidades) -> localhost:30000
# digito-1 (decenas) -> localhost:30001
# digito-2 (centenas) -> localhost:30002
# digito-3 (millares) -> localhost:30003
K8S_SERVICES = {
    0: "http://localhost:30000",
    1: "http://localhost:30001",
    2: "http://localhost:30002",
    3: "http://localhost:30003"
}

MAX_DIGITOS = 4  # Soporta hasta 9999

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "Not Found", 404

def get_digitos(numero):
    """Convierte un número en una lista de sus dígitos (de derecha a izquierda)"""
    if numero == 0:
        return [0]
    
    digitos = []
    while numero > 0:
        digitos.append(numero % 10)
        numero //= 10
    return digitos

def normalizar_digitos(digitos_a, digitos_b):
    """Normaliza ambas listas de dígitos al mismo tamaño, rellenando con ceros"""
    max_len = max(len(digitos_a), len(digitos_b))
    
    # Rellenar con ceros a la izquierda (final de la lista)
    while len(digitos_a) < max_len:
        digitos_a.append(0)
    while len(digitos_b) < max_len:
        digitos_b.append(0)
    
    return digitos_a, digitos_b

@app.route('/suma-n-digitos', methods=['POST', 'OPTIONS'])
def suma_n_digitos():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        data = request.json
        numberA = int(data.get('NumberA', 0))
        numberB = int(data.get('NumberB', 0))
        
        # Validar que los números no excedan el límite
        max_numero = 10 ** MAX_DIGITOS - 1  # 9999 para 4 dígitos
        if numberA < 0 or numberA > max_numero or numberB < 0 or numberB > max_numero:
            raise ValueError(f"Los números deben estar entre 0 y {max_numero}")
        
        # Obtener dígitos de ambos números (de derecha a izquierda)
        digitos_a = get_digitos(numberA)
        digitos_b = get_digitos(numberB)
        
        # Normalizar para que tengan el mismo tamaño
        digitos_a, digitos_b = normalizar_digitos(digitos_a, digitos_b)
        num_digitos = len(digitos_a)
        
        # Validar que no excedamos el límite de contenedores
        if num_digitos > MAX_DIGITOS:
            raise ValueError(f"Solo soportamos hasta {MAX_DIGITOS} dígitos (0-{max_numero})")
        
        # Realizar la cascada de sumas
        resultados = []
        detalles = []
        carry_in = 0
        
        for i in range(num_digitos):
            # Llamar al servicio de Kubernetes correspondiente
            service_url = K8S_SERVICES[i]
            
            response = requests.post(
                f"{service_url}/suma",
                json={
                    'NumberA': digitos_a[i],
                    'NumberB': digitos_b[i],
                    'CarryIn': carry_in
                },
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if not response.ok:
                raise Exception(f"Error en servicio digito-{i}: {response.status_code}")
            
            data_response = response.json()
            result = data_response['Result']
            carry_out = data_response['CarryOut']
            
            resultados.append(result)
            detalles.append({
                'Posicion': i,
                'NombrePosicion': get_nombre_posicion(i),
                'A': digitos_a[i],
                'B': digitos_b[i],
                'CarryIn': carry_in,
                'Result': result,
                'CarryOut': carry_out,
                'Pod': f'suma-digito-{i}',
                'Port': 30000 + i
            })
            
            carry_in = carry_out
        
        # Construir el resultado final
        # Concatenar: [CarryOut_final] + [Result_n-1] + ... + [Result_1] + [Result_0]
        resultado_str = ""
        
        # Si hay carry final, agregarlo
        if carry_in > 0:
            resultado_str += str(carry_in)
        
        # Agregar los resultados de cada posición (de mayor a menor)
        for i in range(num_digitos - 1, -1, -1):
            resultado_str += str(resultados[i])
        
        resultado_final = int(resultado_str)
        
        response_data = {
            'Result': resultado_final,
            'CarryOut': carry_in,
            'NumDigitos': num_digitos,
            'ContenedoresUsados': num_digitos,
            'Details': detalles
        }
        
        response = make_response(jsonify(response_data), 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except ValueError as e:
        print(f"Validation Error: {e}")
        response = make_response(jsonify({"error": str(e)}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        print(f"Error: {e}")
        response = make_response(jsonify({"error": str(e)}), 500)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

def get_nombre_posicion(pos):
    """Retorna el nombre de la posición del dígito"""
    nombres = {
        0: "Unidades",
        1: "Decenas",
        2: "Centenas",
        3: "Millares"
    }
    return nombres.get(pos, f"Posicion-{pos}")

if __name__ == '__main__':
    print("=" * 60)
    print("Proxy de Calculadora con N Dígitos - Kubernetes")
    print("=" * 60)
    print(f"Soporta números de 0 a {10**MAX_DIGITOS - 1} ({MAX_DIGITOS} dígitos)")
    print(f"Servicios Kubernetes configurados:")
    for pos, url in K8S_SERVICES.items():
        print(f"  - Dígito {pos} ({get_nombre_posicion(pos)}): {url}")
    print("=" * 60)
    print("Servidor corriendo en http://localhost:8080")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8080, debug=True)
