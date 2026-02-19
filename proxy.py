from flask import Flask, request, jsonify, make_response, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import requests
import os
import time
import json
import threading
from collections import deque
from k8s_orchestrator import K8sOrchestrator

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

MAX_DIGITOS = 4  # Soporta hasta 9999
AUTO_SCALE_DOWN = True
SCALE_DOWN_DELAY_SECONDS = 2

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

orchestrator = K8sOrchestrator(
    logger=registrar_terminal,
    namespace="calculadora-suma",
    max_digitos=MAX_DIGITOS,
    base_port=31000
)

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

def escalar_a_cero_en_background(num_digitos):
    """Escala a cero los pods al terminar la operación usando el módulo de orquestación."""
    if not AUTO_SCALE_DOWN:
        return

    try:
        orchestrator.escalar_a_cero(delay_seconds=SCALE_DOWN_DELAY_SECONDS)
    except Exception as e:
        registrar_terminal(f"✗ Error durante scale-down automático: {e}", 'error')

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
            if not orchestrator.escalar_pod(i, 1):
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
            if not orchestrator.esperar_pod_ready(i, timeout=60):
                raise Exception(f"El pod suma-digito-{i} no está listo después de 60 segundos")
            
            # Establecer port-forward para este pod
            if not orchestrator.establecer_port_forward(i):
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
            service_url, local_port = orchestrator.service_url(i)

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
    registrar_terminal("Servicios Kubernetes configurados (port-forward local):", 'info')
    for pos in range(MAX_DIGITOS):
        registrar_terminal(
            f"  - Dígito {pos} ({get_nombre_posicion(pos)}): http://localhost:{31000 + pos}",
            'info'
        )
    registrar_terminal("=" * 60, 'info')
    registrar_terminal("Servidor corriendo en http://localhost:8080", 'success')
    registrar_terminal("=" * 60, 'info')
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False, threaded=True)
