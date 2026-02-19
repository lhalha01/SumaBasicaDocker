# Documento Técnico: script.js

## 1. Propósito
`script.js` implementa toda la lógica cliente de la calculadora:
- captura de entrada y validación,
- llamada al proxy (`/suma-n-digitos`),
- renderizado de resultado y detalle de pods,
- terminal embebido con stream SSE,
- control de auto-scroll y limpieza de terminal.

## 2. Módulos funcionales

### A) Estado UI global
Variables globales:
- `autoScrollEnabled`: controla scroll automático de terminal.
- `terminalEventSource`: instancia activa de `EventSource`.
- `terminalStreamConnected`: bandera de conexión real SSE.
- `terminalStatusState`: estado visual (`connecting`, `connected`, `retrying`).

### B) Terminal embebido
Funciones principales:
- `setTerminalStatus(state, text)`: actualiza badge de estado en cabecera.
- `appendTerminalLine(message, level)`: agrega línea al visor con clase semántica.
- `connectTerminalStream()`: abre SSE contra `/terminal-stream`, procesa mensajes y reconexión.
- `clearTerminal()`: limpia la vista y llama `POST /terminal-clear`.
- `toggleAutoScroll()`: alterna auto-scroll ON/OFF.

### C) Operación de suma
`sumar()`:
1. Lee `numeroA` y `numeroB`.
2. Valida rango 0..9999.
3. Muestra placeholders de carga.
4. Registra trazas en terminal.
5. Ejecuta `fetch('http://localhost:8080/suma-n-digitos', { method: 'POST' ... })`.
6. Si OK:
   - actualiza resultado (`Result`, `ContenedoresUsados`, `CarryOut`),
   - renderiza eventos y pods.
7. Si falla:
   - muestra `alert`,
   - resetea panel de resultados.

## 3. Renderizado de detalle de pods

### `renderPodDetailsProgressively(details, eventos)`
- Limpia contenedor.
- Calcula delays por pod para animación secuencial.
- Renderiza pods con `setTimeout`.

### `calculatePodDelays(eventos, details)`
- Ordena por `Posicion` y asigna delay incremental (400ms).

### `renderSinglePod(detail, index, detailsReversed, container)`
- Dibuja tarjeta de pod con:
  - posición,
  - puerto local de acceso,
  - A/B/CarryIn/Result/CarryOut.
- Marca carry activo.
- Inserta flechas entre pods resaltando continuidad de carry.

## 4. Renderizado de eventos de escalado
`renderScalingEvents(eventos)`:
- Si SSE está conectado, no renderiza eventos estáticos (evita duplicado).
- Si no hay SSE, usa fallback visual local:
  - prompt,
  - separador,
  - líneas temporizadas por tipo (`escalado`, `espera`, `listo`),
  - mensaje final `DONE`.

## 5. Ciclo de vida de página
En `DOMContentLoaded`:
- se inicia conexión SSE (`connectTerminalStream()`),
- se registra Enter en inputs numéricos para ejecutar `sumar()`.

## 6. Contrato esperado del backend

### Request
`POST /suma-n-digitos`
```json
{ "NumberA": 1234, "NumberB": 5678 }
```

### Response (campos usados por frontend)
- `Result`
- `ContenedoresUsados`
- `CarryOut`
- `Details[]`
- `EventosEscalado[]`

### SSE
`GET /terminal-stream` emite JSON por línea con:
- `timestamp`
- `level`
- `message`

## 7. Comportamientos clave UX
- Terminal con estados de conexión y reconexión automática de `EventSource`.
- Auto-scroll configurable por el usuario.
- Degradación elegante: si no hay SSE, se mantiene render local de eventos.
- Animación progresiva de pods para visualizar la cascada.

## 8. Riesgos y límites actuales
- `fetch` apunta explícitamente a `http://localhost:8080`; no usa ruta relativa.
- Uso de `alert()` bloqueante en errores.
- No hay cancelación de operación en curso ni debounce del botón.
- Si hay múltiples sumas rápidas, el terminal puede mezclar líneas de distintas operaciones.

## 9. Mejoras sugeridas
- Usar URL relativa (`/suma-n-digitos`) para mayor portabilidad.
- Añadir correlación por operación (`operationId`) para agrupar logs.
- Sustituir `alert()` por panel de errores no bloqueante.
- Deshabilitar botón durante request en curso para evitar condiciones de carrera.
