from flask import Flask, request, jsonify, make_response, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import requests
import os
import subprocess
import time
import json
import threading
import socket
from collections import deque

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

# Configuración de servicios Kubernetes (NodePort)
# El proxy usa puertos locales dedicados para port-forward (31000-31003)
# y evita conflicto con NodePort (30000-30003).
# digito-0 (unidades) -> localhost:31000
# digito-1 (decenas) -> localhost:31001
# digito-2 (centenas) -> localhost:31002
# digito-3 (millares) -> localhost:31003
K8S_SERVICES = {
    0: "http://localhost:31000",
    1: "http://localhost:31001",
    2: "http://localhost:31002",
    3: "http://localhost:31003"
}

MAX_DIGITOS = 4  # Soporta hasta 9999
AUTO_SCALE_DOWN = True
SCALE_DOWN_DELAY_SECONDS = 2

# Funciones de escalado dinámico
# Diccionario para almacenar los procesos de port-forward activos
port_forward_processes = {}
port_forward_ports = {}

# Buffer de logs para terminal embebido en frontend
terminal_log_buffer = deque(maxlen=1000)
terminal_log_lock = threading.Lock()

def registrar_terminal(mensaje, nivel='info'):
    """Registra un mensaje en consola y en el stream de terminal del frontend."""
    texto = str(mensaje)
    lineas = texto.splitlines() if texto else [""]

    for linea in lineas:
        entry = {
            'timestamp': time.strftime('%H:%M:%S'),
            'level': nivel,
            'message': linea
        }
        with terminal_log_lock:
            terminal_log_buffer.append(entry)
        print(linea, flush=True)

def llamar_servicio_con_reintento(service_url, payload, digito, intentos=3):
    """
    Llama al servicio de suma de un dígito con reintentos para manejar
    fallos transitorios durante el arranque del pod.
    """
    ultimo_error = None

    for intento in range(1, intentos + 1):
        try:
            response = requests.post(
                f"{service_url}/suma",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=8
            )

            if not response.ok:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            return response.json()

        except requests.exceptions.RequestException as e:
            ultimo_error = e
            registrar_terminal(f"⚠ Intento {intento}/{intentos} falló en digito-{digito}: {e}", 'warning')
            if intento < intentos:
                time.sleep(1)
        except Exception as e:
            ultimo_error = e
            registrar_terminal(f"⚠ Intento {intento}/{intentos} falló en digito-{digito}: {e}", 'warning')
            if intento < intentos:
                time.sleep(1)

    raise Exception(f"Fallo comunicando con digito-{digito} tras {intentos} intentos: {ultimo_error}")

def obtener_puerto_local_disponible(puerto_preferido):
    """Retorna un puerto local disponible. Intenta primero el preferido."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', puerto_preferido))
            return puerto_preferido
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

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
                puerto_actual = port_forward_ports.get(digito, 31000 + digito)
                registrar_terminal(f"✓ Port-forward para digito-{digito} ya está activo (puerto {puerto_actual})", 'success')
                return True
            else:
                # Limpiar referencias de procesos caídos
                port_forward_processes.pop(digito, None)
                port_forward_ports.pop(digito, None)
        
        service_name = f"suma-digito-{digito}"
        namespace = "calculadora-suma"
        puerto_preferido = 31000 + digito
        local_port = obtener_puerto_local_disponible(puerto_preferido)

        if local_port != puerto_preferido:
            registrar_terminal(
                f"⚠ Puerto {puerto_preferido} ocupado para digito-{digito}; usando {local_port}",
                'warning'
            )
        
        cmd = [
            "kubectl", "port-forward",
            f"svc/{service_name}",
            f"{local_port}:8000",
            "-n", namespace
        ]
        
        # Iniciar el proceso de port-forward en background
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        # Esperar un momento para que el port-forward se establezca
        time.sleep(1.5)

        # Verificar que el proceso sigue vivo después del arranque
        if proceso.poll() is not None:
            try:
                _, stderr_data = proceso.communicate(timeout=1)
            except Exception:
                stderr_data = ""
            detalle = f" Detalle: {stderr_data.strip()}" if stderr_data else ""
            registrar_terminal(f"✗ Port-forward terminó inmediatamente para {service_name}.{detalle}", 'error')
            return False

        port_forward_processes[digito] = proceso
        port_forward_ports[digito] = local_port
        
        registrar_terminal(f"✓ Port-forward establecido para {service_name} en puerto {local_port}", 'success')
        return True
        
    except Exception as e:
        registrar_terminal(f"✗ Excepción estableciendo port-forward para digito-{digito}: {e}", 'error')
        return False

def detener_port_forward(digito):
    """Detiene el proceso de port-forward de un dígito si existe."""
    proceso = port_forward_processes.get(digito)
    if not proceso:
        return

    try:
        if proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=2)
            except Exception:
                proceso.kill()
        registrar_terminal(f"✓ Port-forward detenido para suma-digito-{digito}", 'info')
    except Exception as e:
        registrar_terminal(f"⚠ No se pudo detener port-forward de suma-digito-{digito}: {e}", 'warning')
    finally:
        port_forward_processes.pop(digito, None)
        port_forward_ports.pop(digito, None)

def escalar_a_cero_en_background(num_digitos):
    """Escala a cero los pods usados en la operación y registra trazas para el terminal embebido."""
    if not AUTO_SCALE_DOWN:
        return

    try:
        if SCALE_DOWN_DELAY_SECONDS > 0:
            time.sleep(SCALE_DOWN_DELAY_SECONDS)

        registrar_terminal(f"\n{'-'*60}", 'info')
        registrar_terminal("Iniciando scale-down automático a 0 réplicas", 'info')

        for i in range(MAX_DIGITOS):
            registrar_terminal(f"⏬ Escalando suma-digito-{i} -> 0", 'info')
            if escalar_pod(i, 0):
                registrar_terminal(f"✓ suma-digito-{i} en 0 réplicas", 'success')
            else:
                registrar_terminal(f"✗ No se pudo escalar suma-digito-{i} a 0", 'error')

            detener_port_forward(i)

        registrar_terminal("✓ Scale-down completado: pods en zero", 'success')
        registrar_terminal(f"{'-'*60}\n", 'info')

    except Exception as e:
        registrar_terminal(f"✗ Error durante scale-down automático: {e}", 'error')

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
            registrar_terminal(f"✓ Deployment {deployment_name} escalado a {replicas} réplica(s)", 'success')
            return True
        else:
            registrar_terminal(f"✗ Error escalando {deployment_name}: {result.stderr}", 'error')
            return False
            
    except subprocess.TimeoutExpired:
        registrar_terminal(f"✗ Timeout escalando deployment suma-digito-{digito}", 'error')
        return False
    except Exception as e:
        registrar_terminal(f"✗ Excepción escalando suma-digito-{digito}: {e}", 'error')
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
        
        registrar_terminal(f"⏳ Esperando a que el pod suma-digito-{digito} esté listo...", 'info')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        
        if result.returncode == 0:
            registrar_terminal(f"✓ Pod suma-digito-{digito} está listo", 'success')
            return True
        else:
            registrar_terminal(f"✗ Pod suma-digito-{digito} no está listo: {result.stderr}", 'error')
            return False
            
    except subprocess.TimeoutExpired:
        registrar_terminal(f"✗ Timeout esperando pod suma-digito-{digito}", 'error')
        return False
    except Exception as e:
        registrar_terminal(f"✗ Excepción esperando pod suma-digito-{digito}: {e}", 'error')
        return False

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/terminal-stream')
def terminal_stream():
    def event_stream():
        last_index = 0
        while True:
            try:
                with terminal_log_lock:
                    logs_snapshot = list(terminal_log_buffer)

                # Si el buffer se limpió o rotó (deque maxlen), reajustar cursor
                if last_index > len(logs_snapshot):
                    last_index = 0

                if last_index < len(logs_snapshot):
                    for entry in logs_snapshot[last_index:]:
                        yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                    last_index = len(logs_snapshot)

                time.sleep(0.4)
            except GeneratorExit:
                break
            except Exception:
                break

    response = Response(stream_with_context(event_stream()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/terminal-clear', methods=['POST'])
def terminal_clear():
    with terminal_log_lock:
        terminal_log_buffer.clear()
    return jsonify({'ok': True})

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
        registrar_terminal(f"\n{'='*60}", 'info')
        registrar_terminal(f"Escalando pods para operación: {numberA} + {numberB}", 'info')
        registrar_terminal(f"Se necesitan {num_digitos} pod(s)", 'info')
        registrar_terminal(f"{'='*60}", 'info')
        
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
        
        registrar_terminal(f"✓ Todos los pods necesarios están listos y accesibles\n", 'success')
        
        # Realizar la cascada de sumas
        resultados = []
        detalles = []
        carry_in = 0
        
        for i in range(num_digitos):
            # Llamar al servicio de Kubernetes correspondiente
            local_port = port_forward_ports.get(i, 31000 + i)
            service_url = f"http://localhost:{local_port}"

            payload = {
                'NumberA': digitos_a[i],
                'NumberB': digitos_b[i],
                'CarryIn': carry_in
            }

            data_response = llamar_servicio_con_reintento(service_url, payload, i, intentos=3)
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
                'Port': local_port
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

        # Ejecutar scale-down en background para visualizar transición a zero
        if AUTO_SCALE_DOWN:
            threading.Thread(
                target=escalar_a_cero_en_background,
                args=(num_digitos,),
                daemon=True
            ).start()
        
        response = make_response(jsonify(response_data), 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except ValueError as e:
        registrar_terminal(f"Validation Error: {e}", 'error')
        response = make_response(jsonify({"error": str(e)}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        registrar_terminal(f"Error: {e}", 'error')
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
    registrar_terminal("=" * 60, 'info')
    registrar_terminal("Proxy de Calculadora con N Dígitos - Kubernetes", 'info')
    registrar_terminal("MODO: Escalado Dinámico (Scale-to-Zero)", 'info')
    registrar_terminal("=" * 60, 'info')
    registrar_terminal(f"Soporta números de 0 a {10**MAX_DIGITOS - 1} ({MAX_DIGITOS} dígitos)", 'info')
    registrar_terminal("Los pods se escalan automáticamente según la demanda", 'info')
    registrar_terminal("Servicios Kubernetes configurados:", 'info')
    for pos, url in K8S_SERVICES.items():
        registrar_terminal(f"  - Dígito {pos} ({get_nombre_posicion(pos)}): {url}", 'info')
    registrar_terminal("=" * 60, 'info')
    registrar_terminal("Servidor corriendo en http://localhost:8080", 'success')
    registrar_terminal("=" * 60, 'info')
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False, threaded=True)
