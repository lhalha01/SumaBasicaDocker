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
        
        // Llamar al servicio proxy que coordina los pods de Kubernetes
        const response = await fetch('http://localhost:8080/suma-n-digitos', {
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
        
        // Renderizar los detalles de los pods
        renderPodDetails(data.Details);
        
    } catch (error) {
        console.error('Error al realizar la suma:', error);
        alert('Error: ' + error.message + '\\n\\nVerifica que los pods de Kubernetes estén corriendo.');
        
        // Resetear display
        document.getElementById('resultado').textContent = '?';
        document.getElementById('pods-usados').textContent = '?';
        document.getElementById('carry-final').textContent = '?';
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

// Permitir usar Enter para ejecutar la suma
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input[type="number"]');
    inputs.forEach(input => {
        input.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                sumar();
            }
        });
    });
});
