# Calculadora con Cascada de Contenedores

Aplicación web que suma números de 2 dígitos (0-99) usando **2 contenedores enlazados en cascada**, simulando un sumador de circuitos digitales (Ripple-Carry Adder).

## Rama: DosDigitos

Esta rama implementa la suma de números de 2 dígitos mediante la conexión en cascada de dos contenedores:
- **Contenedor 1 (Unidades)**: Puerto 8001
- **Contenedor 2 (Decenas)**: Puerto 8002

El **CarryOut** del primer contenedor se conecta automáticamente al **CarryIn** del segundo.

## Arquitectura del Sistema

```
Frontend (Puerto 8080)
        ↓
    Proxy Flask
        ↓
   ┌────┴─────┐
   ↓          ↓
Container 1   Container 2
(Unidades)    (Decenas)
:8001    →    :8002
         CarryOut → CarryIn
```

### Flujo de Datos

1. Usuario ingresa: `A=47`, `B=38`
2. Proxy separa en dígitos:
   - Unidades: `A=7, B=8`
   - Decenas: `A=4, B=3`
3. Contenedor 1 (Unidades):
   - Input: `7 + 8 + 0(CarryIn)` = 15
   - Output: `Result=5, CarryOut=1`
4. Contenedor 2 (Decenas):
   - Input: `4 + 3 + 1(CarryIn)` ← usa el carry del contenedor 1
   - Output: `Result=8, CarryOut=0`
5. Resultado final: **`[CarryOut][Decenas][Unidades]` = `085` → `85`**

## Requisitos

- **Podman** o **Docker** instalado
- **Python 3.x** con Flask
- **PowerShell** (Windows)

## Instalación de Podman

```powershell
winget install -e --id RedHat.Podman-Desktop
```

### Configuración Inicial

```powershell
podman machine init
podman machine set --rootful
podman machine start
```

## Despliegue

### Paso 1: Instalar Dependencias Python

```powershell
python -m pip install flask flask-cors requests
```

### Paso 2: Iniciar los Contenedores en Cascada

```powershell
# Iniciar ambos contenedores
podman compose up -d

# Verificar que están corriendo
podman ps
```

Deberías ver:
- `sumabasicadocker-suma-unidades-1` en puerto 8001
- `sumabasicadocker-suma-decenas-1` en puerto 8002

### Paso 3: Iniciar el Proxy/Frontend

```powershell
python proxy.py
```

### Paso 4: Abrir la Aplicación

Navega a: **http://localhost:8080**

## Estructura de Archivos

```
SumaBasicaDocker/
├── index.html          # Frontend con visualización de cascada
├── script.js           # Lógica JavaScript (llama a /suma-dos-digitos)
├── styles.css          # Estilos CSS modernos
├── proxy.py            # Proxy que coordina ambos contenedores
├── docker-compose.yml  # Define 2 servicios (unidades + decenas)
└── README.md           # Este documento
```

## Funcionalidades

### Frontend Interactivo

- **Inputs**: Números de 0 a 99
- **Visualización en tiempo real** de:
  - Detalles del Contenedor 1 (Unidades)
  - Detalles del Contenedor 2 (Decenas)
  - CarryOut transferido entre contenedores (resaltado en rojo)
  - Resultado final concatenado

### Endpoint del Proxy

**POST** `/suma-dos-digitos`

**Request:**
```json
{
  "NumberA": 47,
  "NumberB": 38
}
```

**Response:**
```json
{
  "Result": 85,
  "CarryOut": 0,
  "Details": {
    "Unidades": {
      "A": 7, "B": 8, "CarryIn": 0,
      "Result": 5, "CarryOut": 1
    },
    "Decenas": {
      "A": 4, "B": 3, "CarryIn": 1,
      "Result": 8, "CarryOut": 0
    }
  }
}
```

## Gestión de Contenedores

```powershell
# Ver contenedores activos
podman ps

# Ver logs de un contenedor específico
podman logs sumabasicadocker-suma-unidades-1
podman logs sumabasicadocker-suma-decenas-1

# Detener todos los servicios
podman compose down

# Reiniciar servicios
podman compose restart
```

## Ejemplos de Prueba

### Ejemplo 1: Sin carry entre dígitos
```
47 + 32 = 79
- Unidades: 7+2=9 → Result=9, CarryOut=0
- Decenas: 4+3+0=7 → Result=7, CarryOut=0
- Resultado: 79
```

### Ejemplo 2: Con carry entre dígitos
```
47 + 38 = 85
- Unidades: 7+8=15 → Result=5, CarryOut=1
- Decenas: 4+3+1=8 → Result=8, CarryOut=0
- Resultado: 85
```

### Ejemplo 3: Con carry final (overflow)
```
99 + 99 = 198
- Unidades: 9+9=18 → Result=8, CarryOut=1
- Decenas: 9+9+1=19 → Result=9, CarryOut=1
- Resultado: 198 (concatena: 1+9+8)
```

## Pruebas con curl

### Probar contenedor de unidades directamente:
```powershell
curl.exe -X POST http://localhost:8001/suma -H "Content-Type: application/json" -d '{\"NumberA\":7,\"NumberB\":8,\"CarryIn\":0}'
```

### Probar contenedor de decenas directamente:
```powershell
curl.exe -X POST http://localhost:8002/suma -H "Content-Type: application/json" -d '{\"NumberA\":4,\"NumberB\":3,\"CarryIn\":1}'
```

### Probar la cascada completa:
```powershell
curl.exe -X POST http://localhost:8080/suma-dos-digitos -H "Content-Type: application/json" -d '{\"NumberA\":47,\"NumberB\":38}'
```

## Solución de Problemas

### Puertos ocupados

```powershell
# Ver qué está usando los puertos
netstat -ano | Select-String ":8001|:8002|:8080"

# Detener contenedores antiguos
podman compose down
podman ps -a
```

### Reiniciar todo

```powershell
podman compose down
podman compose up -d
python proxy.py
```

## URLs del Sistema

- **Frontend:** http://localhost:8080
- **API Cascada:** http://localhost:8080/suma-dos-digitos
- **Contenedor Unidades:** http://localhost:8001/suma
- **Contenedor Decenas:** http://localhost:8002/suma
- **Docs API Backend:** http://localhost:8001/docs

## Escalabilidad

Esta arquitectura se puede extender fácilmente a más dígitos:

- **3 dígitos (0-999)**: 3 contenedores en cascada
- **4 dígitos (0-9999)**: 4 contenedores en cascada
- **N dígitos**: N contenedores en cascada

Cada contenedor adicional recibe el CarryOut del anterior como su CarryIn.

---

**Rama:** DosDigitos  
**Versión:** 2.0  
**Fecha:** Febrero 2026
