async function sumar() {
    // Obtener los valores de los inputs
    const carryIn = parseInt(document.getElementById('numero0').value) || 0;
    const numberA = parseInt(document.getElementById('numero1').value) || 0;
    const numberB = parseInt(document.getElementById('numero2').value) || 0;
    
    // Validar que los números estén en sus rangos
    if (carryIn < 0 || carryIn > 1) {
        alert('Por favor, ingresa un número entre 0 y 1 en el primer campo');
        return;
    }
    if (numberA < 0 || numberA > 9 || numberB < 0 || numberB > 9) {
        alert('Por favor, ingresa números entre 0 y 9');
        return;
    }
    
    try {
        // Llamar al servicio FastAPI a través del proxy CORS
        const response = await fetch('http://localhost:8080/suma', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                NumberA: numberA,
                NumberB: numberB,
                CarryIn: carryIn
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al conectar con el servicio');
        }
        
        const data = await response.json();
        
        // Mostrar los resultados desde la API
        document.getElementById('decenas').textContent = data.CarryOut;
        document.getElementById('unidades').textContent = data.Result;
        
        // Agregar animación
        animarResultado();
        
    } catch (error) {
        alert('Error: ' + error.message + '\n\nAsegúrate de que el servidor FastAPI esté ejecutándose en http://localhost:8000');
        console.error('Error:', error);
    }
}

function animarResultado() {
    const displays = document.querySelectorAll('.output-display');
    displays.forEach(display => {
        display.style.transform = 'scale(1.2)';
        setTimeout(() => {
            display.style.transform = 'scale(1)';
        }, 200);
    });
}

// Permitir sumar con la tecla Enter
document.addEventListener('DOMContentLoaded', () => {
    const selects = document.querySelectorAll('select');
    selects.forEach(select => {
        // Permitir sumar con Enter
        select.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sumar();
            }
        });
    });
});
