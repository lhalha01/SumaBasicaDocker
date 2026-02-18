async function sumar() {
    // Obtener los valores de los inputs
    const numberA = parseInt(document.getElementById('numeroA').value) || 0;
    const numberB = parseInt(document.getElementById('numeroB').value) || 0;
    
    // Validar que los números estén en sus rangos
    if (numberA < 0 || numberA > 99 || numberB < 0 || numberB > 99) {
        alert('Por favor, ingresa números entre 0 y 99');
        return;
    }
    
    try {
        // Llamar al servicio proxy que coordina ambos contenedores
        const response = await fetch('http://localhost:8080/suma-dos-digitos', {
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
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mostrar el resultado final
        document.getElementById('resultado').textContent = data.Result;
        
        // Mostrar detalles del contenedor de unidades
        document.getElementById('uni-a').textContent = data.Details.Unidades.A;
        document.getElementById('uni-b').textContent = data.Details.Unidades.B;
        document.getElementById('uni-cin').textContent = data.Details.Unidades.CarryIn;
        document.getElementById('uni-result').textContent = data.Details.Unidades.Result;
        document.getElementById('uni-cout').textContent = data.Details.Unidades.CarryOut;
        
        // Mostrar detalles del contenedor de decenas
        document.getElementById('dec-a').textContent = data.Details.Decenas.A;
        document.getElementById('dec-b').textContent = data.Details.Decenas.B;
        document.getElementById('dec-cin').textContent = data.Details.Decenas.CarryIn;
        document.getElementById('dec-result').textContent = data.Details.Decenas.Result;
        document.getElementById('dec-cout').textContent = data.Details.Decenas.CarryOut;
        
        // Resaltar el carry que se transfiere entre contenedores
        const carryElement = document.getElementById('uni-cout');
        const carryInElement = document.getElementById('dec-cin');
        
        if (data.Details.Unidades.CarryOut === 1) {
            carryElement.style.color = '#ff6b6b';
            carryElement.style.fontWeight = 'bold';
            carryInElement.style.color = '#ff6b6b';
            carryInElement.style.fontWeight = 'bold';
        } else {
            carryElement.style.color = '';
            carryElement.style.fontWeight = '';
            carryInElement.style.color = '';
            carryInElement.style.fontWeight = '';
        }
        
    } catch (error) {
        console.error('Error al realizar la suma:', error);
        alert('Error al realizar la suma. Verifica que los contenedores estén corriendo.');
    }
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
