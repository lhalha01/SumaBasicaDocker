# Calculadora Básica con Docker/Podman

Aplicación web de calculadora que suma dos números (0-9) con un bit de acarreo de entrada (CarryIn: 0-1).

## Arquitectura del Sistema

```
Frontend + Proxy (Puerto 8080) → Backend Container (Puerto 8000)
```

## Requisitos

- **Podman** o **Docker** instalado
- **Python 3.x** con Flask
- **PowerShell** (Windows)

## Instalación de Podman

```powershell
winget install -e --id RedHat.Podman-Desktop
```

### Configuración Inicial de Podman

```powershell
# Inicializar y configurar la máquina virtual
podman machine init
podman machine set --rootful
podman machine start
```

## Despliegue con Docker Compose / Podman Compose

### Paso 1: Instalar Dependencias Python

```powershell
python -m pip install flask flask-cors requests
```

### Paso 2: Iniciar los Servicios

```powershell
# Iniciar el backend con Podman Compose
podman compose up -d

# En otra terminal, iniciar el proxy/frontend
python proxy.py
```

El proxy servirá:
- **Frontend**: http://localhost:8080 (HTML, CSS, JS)
- **API Proxy**: http://localhost:8080/suma → http://localhost:8000/suma

### Paso 3: Acceder a la Aplicación

Abre tu navegador en: **http://localhost:8080**

## Estructura de Archivos

```
SumaBasicaDocker/
├── index.html          # Frontend de la calculadora
├── script.js           # Lógica JavaScript
├── styles.css          # Estilos CSS
├── proxy.py            # Proxy Flask (sirve frontend y API)
├── docker-compose.yml  # Configuración del contenedor backend
└── README.md           # Este documento
```

## Gestión del Contenedor

```powershell
# Ver contenedores en ejecución
podman ps

# Ver logs del backend
podman logs sumabasicadocker-suma-api-1

# Detener servicios
podman compose down

# Reiniciar backend
podman compose restart
```

## Solución de Problemas

### Puerto 8000 ya en uso

```powershell
# Ver qué está usando el puerto
netstat -ano | Select-String ":8000"

# Detener contenedores antiguos
podman stop suma-api
podman rm suma-api
```

### Caché del navegador

Presiona **Ctrl + Shift + R** para recargar sin caché.

### Error: Connection refused

```powershell
# Verificar que Podman machine está corriendo
podman machine start

# Reiniciar el contenedor
podman compose up -d
```

## Verificación de la API

### Probar el Backend directamente:
```powershell
curl.exe -X POST http://localhost:8000/suma -H "Content-Type: application/json" -d '{\"NumberA\":5,\"NumberB\":3,\"CarryIn\":1}'
```

Respuesta esperada: `{"Result":9,"CarryOut":0}`

### Probar a través del Proxy:
```powershell
curl.exe -X POST http://localhost:8080/suma -H "Content-Type: application/json" -d '{\"NumberA\":5,\"NumberB\":3,\"CarryIn\":1}'
```

## Comandos Rápidos

```powershell
# Iniciar todo
podman machine start
podman compose up -d
python proxy.py

# Detener todo
# Ctrl+C para detener proxy.py
podman compose down
```

## URLs

- **Aplicación Web:** http://localhost:8080
- **API Backend:** http://localhost:8000
- **Documentación API:** http://localhost:8000/docs

## Especificaciones

- **NumberA:** Entero de 0 a 9
- **NumberB:** Entero de 0 a 9
- **CarryIn:** Bit (0 o 1)
- **Result:** Suma módulo 10
- **CarryOut:** Bit de acarreo de salida

---

**Versión:** 2.0  
**Fecha:** Febrero 2026
