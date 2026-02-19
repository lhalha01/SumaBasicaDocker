# Documento Técnico: proxy.py

## 1. Propósito
`proxy.py` es el orquestador de la aplicación. Expone una API HTTP para sumar números de hasta 4 dígitos y coordina en tiempo real:
- escalado de deployments en Kubernetes,
- espera de pods en estado Ready,
- establecimiento de `kubectl port-forward`,
- ejecución de suma en cascada (Ripple-Carry),
- streaming de logs al frontend (SSE),
- scale-down automático a 0.

## 2. Responsabilidades principales

### API y estáticos
- Sirve frontend y archivos estáticos.
- Endpoint principal de negocio: `POST /suma-n-digitos`.
- Endpoints de terminal embebido:
  - `GET /terminal-stream` (SSE)
  - `POST /terminal-clear`

### Orquestación de Kubernetes
- Escala deployments `suma-digito-{0..3}` con `kubectl scale`.
- Espera readiness con `kubectl wait` por label `app=suma-backend,digito={n}`.
- Crea `port-forward` por pod/servicio.
- Gestiona colisiones de puertos locales con asignación dinámica.

### Cálculo distribuido
- Descompone números en dígitos (de derecha a izquierda).
- Propaga `CarryIn`/`CarryOut` entre pods.
- Recompone resultado final incluyendo carry global.

### Observabilidad
- `registrar_terminal()` publica cada línea en:
  - consola del servidor,
  - buffer en memoria (`deque`) para SSE.

## 3. Configuración clave
- `MAX_DIGITOS = 4`: límite funcional (0-9999).
- `AUTO_SCALE_DOWN = True`: habilita scale-down post-operación.
- `SCALE_DOWN_DELAY_SECONDS = 2`: retardo antes de bajar a 0.
- `K8S_SERVICES`: base histórica de puertos preferidos locales 31000-31003.

## 4. Estructuras de estado en memoria
- `port_forward_processes`: diccionario `digito -> subprocess`.
- `port_forward_ports`: diccionario `digito -> puerto local real`.
- `terminal_log_buffer`: buffer circular (máx. 1000 líneas).
- `terminal_log_lock`: sincronización entre hilos (request thread + scale-down thread + SSE readers).

## 5. Flujo completo de `POST /suma-n-digitos`
1. Validación de entrada (`NumberA`, `NumberB`, rango permitido).
2. Conversión a dígitos y normalización de longitud.
3. Para cada posición necesaria:
   - escala deployment a 1,
   - espera pod Ready,
   - establece port-forward (con fallback de puerto local),
   - registra evento para UI.
4. Para cada pod activo:
   - invoca `POST /suma` del backend por localhost+puerto forward,
   - aplica reintentos (`llamar_servicio_con_reintento`),
   - captura `Result` + `CarryOut`.
5. Reconstruye resultado final.
6. Responde JSON con `Result`, `Details`, `EventosEscalado`.
7. Lanza hilo daemon para scale-down a 0 (si está habilitado).

## 6. Gestión de puertos y port-forward
`establecer_port_forward(digito)`:
- Reutiliza proceso activo si sigue vivo.
- Si no, intenta puerto preferido `31000+n`.
- Si está ocupado, solicita puerto libre del SO (`bind(0)`).
- Arranca `kubectl port-forward svc/suma-digito-n <local>:8000 -n calculadora-suma`.
- Verifica que no muera en arranque; en caso de fallo intenta devolver detalle de stderr.

`detener_port_forward(digito)`:
- `terminate()` y fallback a `kill()`.
- Limpia diccionarios de estado.

## 7. Streaming de terminal (SSE)
`GET /terminal-stream`:
- Envía eventos `data: {...}` en formato JSON con:
  - `timestamp`
  - `level` (`info|success|warning|error`)
  - `message`
- Reajusta cursor si el buffer se vacía o rota.
- Mantiene conexión con polling corto (`sleep(0.4)`).

## 8. Escalado a cero
`escalar_a_cero_en_background()`:
- Espera `SCALE_DOWN_DELAY_SECONDS`.
- Recorre `MAX_DIGITOS` completo (0..3), no solo pods usados.
- Escala cada deployment a 0 y detiene sus port-forwards.
- Registra trazas para que el frontend muestre claramente la transición a zero.

## 9. Manejo de errores
- Errores de validación → HTTP 400.
- Errores de orquestación/comunicación → HTTP 500.
- Fallos transitorios en llamadas backend mitigados con reintentos.
- Fallos de port-forward quedan reflejados en logs SSE y respuesta de error.

## 10. Consideraciones de concurrencia
- Flask corre con `threaded=True`; múltiples requests pueden solaparse.
- El buffer de logs está protegido con lock.
- Estado de port-forwards es global de proceso; dos operaciones simultáneas pueden competir por escalado/puertos.

## 11. Puntos de extensión recomendados
- Añadir request-id por operación para agrupar logs en frontend.
- Añadir endpoint de health (`/healthz`) para Kubernetes/liveness.
- Migrar shelling-out de `kubectl` a cliente Python de Kubernetes para mayor control.
- Parametrizar namespace y límites vía variables de entorno.

## 12. Dependencias externas
- Flask, Flask-CORS
- requests
- kubectl disponible en PATH
- Cluster Kubernetes activo y namespace `calculadora-suma`
