let autoScrollEnabled = true;
let terminalEventSource = null;

// ── Docs link auto-resolve ───────────────────────────────────
async function resolveDocsLink() {
    const link = document.getElementById('docs-link');
    if (!link) return;

    try {
        const res = await fetch('/docs-url');
        if (!res.ok) throw new Error('fetch failed');
        const data = await res.json();
        if (data.url) {
            link.href = data.url;
            link.classList.remove('docs-pending');
        } else {
            link.classList.add('docs-pending');
            link.title = 'Documentación no disponible aún (LoadBalancer pendiente)';
        }
    } catch (_) {
        link.classList.add('docs-pending');
        link.title = 'No se pudo resolver la URL de documentación';
    }
}

// ── Grafana link auto-resolve ──────────────────────────────────
async function resolveGrafanaLink() {
    const link = document.getElementById('grafana-link');
    if (!link) return;

    try {
        const res = await fetch('/grafana-url');
        if (!res.ok) throw new Error('fetch failed');
        const data = await res.json();
        if (data.url) {
            link.href = data.url;
            link.classList.remove('grafana-pending');
        } else {
            link.classList.add('grafana-pending');
            link.title = 'Grafana no disponible aún (LoadBalancer pendiente)';
        }
    } catch (_) {
        link.classList.add('grafana-pending');
        link.title = 'No se pudo resolver la URL de Grafana';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    resolveDocsLink();
    resolveGrafanaLink();
});
// ────────────────────────────────────────────────────────────
let terminalStreamConnected = false;
let terminalStatusState = 'connecting';

function setTerminalStatus(state, text) {
    const status = document.getElementById('terminal-status');
    if (!status || terminalStatusState === state) {
        return;
    }

    terminalStatusState = state;
    status.classList.remove('terminal-status-connected', 'terminal-status-connecting', 'terminal-status-retrying');

    if (state === 'connected') {
        status.classList.add('terminal-status-connected');
    } else if (state === 'retrying') {
        status.classList.add('terminal-status-retrying');
    } else {
        status.classList.add('terminal-status-connecting');
    }

    status.textContent = `● ${text}`;
}

function appendTerminalLine(message, level = 'info') {
    const container = document.getElementById('scaling-log');
    if (!container) return;

    const emptyMessage = container.querySelector('.empty-message');
    if (emptyMessage) {
        emptyMessage.remove();
    }

    const line = document.createElement('div');
    line.className = `terminal-line terminal-${level}`;
    line.textContent = message;
    container.appendChild(line);

    if (autoScrollEnabled) {
        container.scrollTop = container.scrollHeight;
    }
}

function connectTerminalStream() {
    if (terminalEventSource) {
        terminalEventSource.close();
    }

    setTerminalStatus('connecting', 'Conectando...');

    terminalEventSource = new EventSource('/terminal-stream');

    terminalEventSource.onopen = () => {
        terminalStreamConnected = true;
        setTerminalStatus('connected', 'Conectado');
        appendTerminalLine('[STREAM] Conectado a logs en vivo del proxy', 'success');
    };

    terminalEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            const timestamp = data.timestamp ? `[${data.timestamp}] ` : '';
            appendTerminalLine(`${timestamp}${data.message}`, data.level || 'info');
        } catch {
            appendTerminalLine(event.data, 'info');
        }
    };

    terminalEventSource.onerror = () => {
        setTerminalStatus('retrying', 'Reintentando...');
        if (terminalStreamConnected) {
            appendTerminalLine('[STREAM] Desconectado. Reintentando...', 'warning');
        }
        terminalStreamConnected = false;
    };
}

async function sumar() {
    const numberA = parseInt(document.getElementById('numeroA').value) || 0;
    const numberB = parseInt(document.getElementById('numeroB').value) || 0;
    
    // Validar rangos
    if (numberA < 0 || numberA > 9999 || numberB < 0 || numberB > 9999) {
        alert('Por favor, ingresa números entre 0 y 9999');
        return;
    }
    
    try {
        // Mostrar loading
        document.getElementById('resultado').textContent = '...';
        document.getElementById('pods-usados').textContent = '...';
        document.getElementById('carry-final').textContent = '...';
        
        appendTerminalLine(`$ sumar ${numberA} ${numberB}`, 'info');
        appendTerminalLine('⏳ Ejecutando operación...', 'info');
        
        // Limpiar sección de pods antes de la nueva operación
        const containersSection = document.getElementById('containers-list');
        containersSection.innerHTML = '<p class="loading-message">⏳ Preparando pods...</p>';
        
        // Llamar al servicio proxy que coordina los pods de Kubernetes
        const response = await fetch('/suma-n-digitos', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                NumberA: numberA,
                NumberB: numberB
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mostrar resultado final
        document.getElementById('resultado').textContent = data.Result;
        document.getElementById('pods-usados').textContent = data.ContenedoresUsados;
        document.getElementById('carry-final').textContent = data.CarryOut;
        
        // Renderizar eventos de escalado primero
        renderScalingEvents(data.EventosEscalado || []);
        
        // Renderizar los detalles de los pods progresivamente
        renderPodDetailsProgressively(data.Details, data.EventosEscalado || []);
        
    } catch (error) {
        console.error('Error al realizar la suma:', error);
        alert('Error: ' + error.message + '\\n\\nVerifica que los pods de Kubernetes estén corriendo.');
        
        // Resetear display
        document.getElementById('resultado').textContent = '?';
        document.getElementById('pods-usados').textContent = '?';
        document.getElementById('carry-final').textContent = '?';
    }
}

function renderPodDetailsProgressively(details, eventos) {
    const container = document.getElementById('containers-list');
    
    if (!details || details.length === 0) {
        container.innerHTML = '<p class="empty-message">No hay detalles disponibles</p>';
        return;
    }
    
    // Limpiar contenedor
    container.innerHTML = '';
    
    // Calcular delays basados en eventos de escalado
    const delays = calculatePodDelays(eventos, details);
    
    // Invertir el orden para mostrar de mayor a menor (millares -> unidades)
    const detailsReversed = [...details].reverse();
    
    // Renderizar cada pod con delay progresivo
    detailsReversed.forEach((detail, index) => {
        const delay = delays[detail.Posicion] || 0;
        
        setTimeout(() => {
            renderSinglePod(detail, index, detailsReversed, container);
        }, delay);
    });
}

function calculatePodDelays(eventos, details) {
    const delays = {};
    
    // Los pods deben aparecer de derecha a izquierda (Unidades -> Millares)
    // Calcular el número de pods y asignar delays inversos
    const numPods = details.length;
    
    // Ordenar details por posición para asegurar el orden correcto
    const sortedDetails = [...details].sort((a, b) => a.Posicion - b.Posicion);
    
    // Asignar delays: pos 0 (Unidades/derecha) primero, pos 3 (Millares/izquierda) último
    sortedDetails.forEach((detail, index) => {
        delays[detail.Posicion] = index * 400; // 400ms entre cada pod
    });
    
    return delays;
}

function renderSinglePod(detail, index, detailsReversed, container) {
    const isLast = index === detailsReversed.length - 1;
    
    // Crear el box del contenedor
    const box = document.createElement('div');
    box.className = 'container-box pod-appear';
    
    const carryOutClass = detail.CarryOut === 1 ? 'carry-active' : '';
    const carryInClass = detail.CarryIn === 1 ? 'carry-active' : '';
    
    box.innerHTML = `
        <h3>📦 Pod: ${detail.Pod}</h3>
        <div class="pod-info">
            <span class="badge">Posición: ${detail.NombrePosicion}</span>
            <span class="badge">Puerto: ${detail.Port}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">NumberA:</span>
            <span class="detail-value">${detail.A}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">NumberB:</span>
            <span class="detail-value">${detail.B}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">CarryIn:</span>
            <span class="detail-value ${carryInClass}">${detail.CarryIn}</span>
        </div>
        <div class="detail-row highlight">
            <span class="detail-label">Result:</span>
            <span class="detail-value">${detail.Result}</span>
        </div>
        <div class="detail-row highlight">
            <span class="detail-label">CarryOut:</span>
            <span class="detail-value ${carryOutClass}">${detail.CarryOut}</span>
        </div>
    `;
    
    // Insertar al principio para mantener el orden visual correcto (Millares a la izquierda)
    // Como Unidades aparece primero (delay menor), se inserta primero y queda a la derecha
    container.insertBefore(box, container.firstChild);
    
    // Agregar flecha si no es el último
    if (!isLast) {
        const arrow = document.createElement('div');
        arrow.className = 'arrow pod-appear';
        arrow.textContent = '←';
        
        // Resaltar la flecha si hay carry (el carry fluye de derecha a izquierda)
        // Verificar el CarryOut del pod a la derecha (siguiente en el array invertido)
        if (detailsReversed[index + 1] && detailsReversed[index + 1].CarryOut === 1) {
            arrow.classList.add('arrow-active');
        }
        
        // Insertar flecha también al principio, después del box
        container.insertBefore(arrow, box.nextSibling);
    }
}

function renderPodDetails(details) {
    const container = document.getElementById('containers-list');
    
    if (!details || details.length === 0) {
        container.innerHTML = '<p class="empty-message">No hay detalles disponibles</p>';
        return;
    }
    
    // Limpiar contenedor
    container.innerHTML = '';
    
    // Invertir el orden para mostrar de mayor a menor (millares -> unidades)
    const detailsReversed = [...details].reverse();
    
    detailsReversed.forEach((detail, index) => {
        const isLast = index === detailsReversed.length - 1;
        
        // Crear el box del contenedor
        const box = document.createElement('div');
        box.className = 'container-box';
        
        const carryOutClass = detail.CarryOut === 1 ? 'carry-active' : '';
        const carryInClass = detail.CarryIn === 1 ? 'carry-active' : '';
        
        box.innerHTML = `
            <h3>📦 Pod: ${detail.Pod}</h3>
            <div class="pod-info">
                <span class="badge">Posición: ${detail.NombrePosicion}</span>
                <span class="badge">Puerto: ${detail.Port}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">NumberA:</span>
                <span class="detail-value">${detail.A}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">NumberB:</span>
                <span class="detail-value">${detail.B}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">CarryIn:</span>
                <span class="detail-value ${carryInClass}">${detail.CarryIn}</span>
            </div>
            <div class="detail-row highlight">
                <span class="detail-label">Result:</span>
                <span class="detail-value">${detail.Result}</span>
            </div>
            <div class="detail-row highlight">
                <span class="detail-label">CarryOut:</span>
                <span class="detail-value ${carryOutClass}">${detail.CarryOut}</span>
            </div>
        `;
        
        container.appendChild(box);
        
        // Agregar flecha si no es el último
        if (!isLast) {
            const arrow = document.createElement('div');
            arrow.className = 'arrow';
            arrow.textContent = '←';
            
            // Resaltar la flecha si hay carry (el carry fluye de derecha a izquierda)
            // Verificar el CarryOut del pod a la derecha (siguiente en el array invertido)
            if (detailsReversed[index + 1] && detailsReversed[index + 1].CarryOut === 1) {
                arrow.classList.add('arrow-active');
            }
            
            container.appendChild(arrow);
        }
    });
}

function renderScalingEvents(eventos) {
    if (terminalStreamConnected) {
        return;
    }

    const container = document.getElementById('scaling-log');
    
    if (!eventos || eventos.length === 0) {
        container.innerHTML = `
            <div class="terminal-prompt">root@k8s-proxy:~# <span class="blinking-cursor">_</span></div>
            <p class="empty-message">No hay eventos de escalado disponibles</p>
        `;
        return;
    }
    
    // Limpiar contenedor
    container.innerHTML = `
        <div class="terminal-prompt">root@k8s-proxy:~# kubectl scale --namespace calculadora-suma</div>
    `;

    const separator = document.createElement('div');
    separator.className = 'terminal-separator';
    separator.textContent = '═'.repeat(70);
    container.appendChild(separator);
    
    eventos.forEach((evento, index) => {
        setTimeout(() => {
            const eventItem = document.createElement('div');
            eventItem.className = `scaling-trace scaling-trace-${evento.Tipo}`;
            
            let prefix = '[INFO]';
            let message = `${evento.Posicion} - ${evento.Estado}`;

            if (evento.Tipo === 'escalado') {
                prefix = '[SCALE]';
                message = `Escalando ${evento.Pod} (${evento.Posicion})...`;
            } else if (evento.Tipo === 'espera') {
                prefix = '[WAIT]';
                message = `Esperando ${evento.Pod} en estado Ready...`;
            } else if (evento.Tipo === 'listo') {
                prefix = '[OK]';
                message = `${evento.Pod} listo ${evento.Estado}`;
            }

            eventItem.textContent = `[${evento.Timestamp}] ${prefix} ${message}`;
            container.appendChild(eventItem);

            if (autoScrollEnabled) {
                container.scrollTop = container.scrollHeight;
            }
        }, index * 90);
    });

    setTimeout(() => {
        const doneItem = document.createElement('div');
        doneItem.className = 'terminal-success';
        doneItem.textContent = '[DONE] Operación de escalado completada';
        container.appendChild(doneItem);

        if (autoScrollEnabled) {
            container.scrollTop = container.scrollHeight;
        }
    }, eventos.length * 90 + 120);
}

function clearTerminal() {
    const container = document.getElementById('scaling-log');
    container.innerHTML = `
        <div class="terminal-prompt">root@k8s-proxy:~# <span class="blinking-cursor">_</span></div>
        <p class="empty-message">Terminal limpiado. Esperando operaciones...</p>
    `;

    fetch('/terminal-clear', { method: 'POST' }).catch(() => {});
}

function toggleAutoScroll() {
    autoScrollEnabled = !autoScrollEnabled;
    const button = document.getElementById('btnAutoScroll');

    if (autoScrollEnabled) {
        button.textContent = '🔽 Auto-scroll: ON';
        button.classList.add('active');
    } else {
        button.textContent = '⏸️ Auto-scroll: OFF';
        button.classList.remove('active');
    }
}

// Permitir usar Enter para ejecutar la suma
document.addEventListener('DOMContentLoaded', function() {
    connectTerminalStream();

    const inputs = document.querySelectorAll('input[type="number"]');
    inputs.forEach(input => {
        input.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                sumar();
            }
        });
    });
});
