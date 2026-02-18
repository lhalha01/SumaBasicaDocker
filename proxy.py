from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import requests
import os
import subprocess
import time

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

# Funciones de escalado dinámico
# Diccionario para almacenar los procesos de port-forward activos
port_forward_processes = {}

def establecer_port_forward(digito):
    """
    Establece un port-forward para el servicio de un dígito específico.
    
    Args:
        digito: Número de dígito (0-3) correspondiente al servicio
    
    Returns:
        True si el port-forward fue exitoso, False en caso contrario
    """
    global port_forward_processes
    
    try:
        # Si ya existe un port-forward activo, no hacer nada
        if digito in port_forward_processes:
            proceso = port_forward_processes[digito]
            if proceso.poll() is None:  # El proceso aún está corriendo
                print(f"✓ Port-forward para digito-{digito} ya está activo")
                return True
        
        service_name = f"suma-digito-{digito}"
        namespace = "calculadora-suma"
        local_port = 30000 + digito
        
        cmd = [
            "kubectl", "port-forward",
            f"svc/{service_name}",
            f"{local_port}:8000",
            "-n", namespace
        ]
        
        # Iniciar el proceso de port-forward en background
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        port_forward_processes[digito] = proceso
        
        # Esperar un momento para que el port-forward se establezca
        time.sleep(2)
        
        print(f"✓ Port-forward establecido para {service_name} en puerto {local_port}")
        return True
        
    except Exception as e:
        print(f"✗ Excepción estableciendo port-forward para digito-{digito}: {e}")
        return False

def escalar_pod(digito, replicas):
    """
    Escala el deployment de un dígito específico al número de réplicas indicado.
    
    Args:
        digito: Número de dígito (0-3) correspondiente al deployment
        replicas: Número de réplicas deseadas (0 para apagar, 1 para encender)
    
    Returns:
        True si el escalado fue exitoso, False en caso contrario
    """
    try:
        deployment_name = f"suma-digito-{digito}"
        namespace = "calculadora-suma"
        
        cmd = [
            "kubectl", "scale", "deployment", deployment_name,
            f"--replicas={replicas}",
            "-n", namespace
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"✓ Deployment {deployment_name} escalado a {replicas} réplica(s)")
            return True
        else:
            print(f"✗ Error escalando {deployment_name}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout escalando deployment suma-digito-{digito}")
        return False
    except Exception as e:
        print(f"✗ Excepción escalando suma-digito-{digito}: {e}")
        return False

def esperar_pod_ready(digito, timeout=60):
    """
    Espera a que el pod de un dígito específico esté en estado Ready.
    
    Args:
        digito: Número de dígito (0-3) correspondiente al pod
        timeout: Tiempo máximo de espera en segundos (default: 60)
    
    Returns:
        True si el pod está listo, False si se agotó el tiempo
    """
    try:
        deployment_name = f"suma-digito-{digito}"
        namespace = "calculadora-suma"
        
        # Usar kubectl wait para esperar a que el pod esté ready
        cmd = [
            "kubectl", "wait", f"--for=condition=ready",
            "pod",
            "-l", f"app=suma-backend,digito={digito}",
            "-n", namespace,
            f"--timeout={timeout}s"
        ]
        
        print(f"⏳ Esperando a que el pod suma-digito-{digito} esté listo...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        
        if result.returncode == 0:
            print(f"✓ Pod suma-digito-{digito} está listo")
            return True
        else:
            print(f"✗ Pod suma-digito-{digito} no está listo: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout esperando pod suma-digito-{digito}")
        return False
    except Exception as e:
        print(f"✗ Excepción esperando pod suma-digito-{digito}: {e}")
        return False

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
        
        # Escalar dinámicamente los pods necesarios (escalado horizontal)
        print(f"\n{'='*60}")
        print(f"Escalando pods para operación: {numberA} + {numberB}")
        print(f"Se necesitan {num_digitos} pod(s)")
        print(f"{'='*60}")
        
        # Array para registrar eventos de escalado
        eventos_escalado = []
        
        # Escalar cada pod necesario
        for i in range(num_digitos):
            inicio_escalado = time.time()
            
            # Registrar inicio de escalado
            eventos_escalado.append({
                'Tipo': 'escalado',
                'Pod': f'suma-digito-{i}',
                'Posicion': get_nombre_posicion(i),
                'Estado': f'Pod {i+1} de {num_digitos}',
                'Timestamp': time.strftime('%H:%M:%S')
            })
            
            # Escalar a 1 réplica
            if not escalar_pod(i, 1):
                raise Exception(f"No se pudo escalar el pod suma-digito-{i}")
            
            # Registrar espera
            eventos_escalado.append({
                'Tipo': 'espera',
                'Pod': f'suma-digito-{i}',
                'Posicion': get_nombre_posicion(i),
                'Estado': 'Esperando pod Ready...',
                'Timestamp': time.strftime('%H:%M:%S')
            })
            
            # Esperar a que el pod esté listo
            if not esperar_pod_ready(i, timeout=60):
                raise Exception(f"El pod suma-digito-{i} no está listo después de 60 segundos")
            
            # Establecer port-forward para este pod
            if not establecer_port_forward(i):
                raise Exception(f"No se pudo establecer port-forward para suma-digito-{i}")
            
            # Registrar completado
            tiempo_escalado = round(time.time() - inicio_escalado, 2)
            eventos_escalado.append({
                'Tipo': 'listo',
                'Pod': f'suma-digito-{i}',
                'Posicion': get_nombre_posicion(i),
                'Estado': f'✓ Listo ({tiempo_escalado}s)',
                'Timestamp': time.strftime('%H:%M:%S')
            })
        
        print(f"✓ Todos los pods necesarios están listos y accesibles\n")
        
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
            'Details': detalles,
            'EventosEscalado': eventos_escalado
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
    print("MODO: Escalado Dinámico (Scale-to-Zero)")
    print("=" * 60)
    print(f"Soporta números de 0 a {10**MAX_DIGITOS - 1} ({MAX_DIGITOS} dígitos)")
    print(f"Los pods se escalan automáticamente según la demanda")
    print(f"Servicios Kubernetes configurados:")
    for pos, url in K8S_SERVICES.items():
        print(f"  - Dígito {pos} ({get_nombre_posicion(pos)}): {url}")
    print("=" * 60)
    print("Servidor corriendo en http://localhost:8080")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8080, debug=True)
