# Calculadora con Kubernetes y N-Dígitos

Aplicación web que suma números de hasta 4 dígitos (0-9999) usando **Kubernetes** para orquestar múltiples pods en cascada, simulando un sumador de circuitos digitales (Ripple-Carry Adder).

## Rama: NDigitos

Esta rama implementa la suma de números de N dígitos (1-4) mediante la orquestación dinámica de pods en Kubernetes:
- **Pod 0 (Unidades)**: NodePort 30000
- **Pod 1 (Decenas)**: NodePort 30001
- **Pod 2 (Centenas)**: NodePort 30002
- **Pod 3 (Millares)**: NodePort 30003

El **CarryOut** de cada pod se conecta automáticamente al **CarryIn** del siguiente pod en la cascada.

## Rama: DigitosDinamicos (ACTUAL)

Esta rama extiende **NDigitos** implementando **escalado dinámico de pods** (scale-to-zero):

### Características del Escalado Dinámico

- **Estado inicial**: Todos los deployments tienen `replicas: 0` (sin pods corriendo)
- **Escalado bajo demanda**: Los pods se escalan automáticamente según los dígitos necesarios
- **Optimización de recursos**: Solo se activan los pods necesarios para cada operación:
  - `5 + 3` → Solo escala Pod-0 (Unidades)
  - `99 + 88` → Escala Pod-0 y Pod-1 (Unidades + Decenas)
  - `9876 + 5432` → Escala los 4 pods (Unidades + Decenas + Centenas + Millares)
- **Port-forwarding dinámico**: El proxy Flask establece automáticamente los port-forwards necesarios

### Ventajas

- **Ahorro de recursos**: 0 MB de RAM en reposo vs. 256 MB con 4 pods siempre activos
- **Escalado horizontal**: Solo paga por lo que usa
- **Latencia aceptable**: ~10-15 segundos para el primer request (tiempo de arranque del pod), <1 segundo para subsecuentes
- **Ideal para cargas intermitentes**: Calculadora de uso ocasional

### Flujo de Escalado

1. Usuario solicita: `9876 + 5432`
2. Proxy detecta que necesita 4 dígitos
3. Escala dinámicamente: `kubectl scale deployment suma-digito-{0,1,2,3} --replicas=1`
4. Espera a que los pods estén `Ready` (kubectl wait)
5. Establece port-forwards para cada pod
6. Ejecuta la suma en cascada
7. Retorna el resultado

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CAPA DE PRESENTACIÓN                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Frontend Web (HTML/CSS/JavaScript)                                   │  │
│  │  http://localhost:8080                                                │  │
│  │  • Entrada de números (0-9999)                                        │  │
│  │  • Visualización de resultados y carry                                │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │ HTTP POST
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CAPA DE ORQUESTACIÓN                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Proxy Flask (Python)                                                 │  │
│  │  • Descomposición de números en dígitos                              │  │
│  │  • Escalado dinámico de pods (scale-to-zero)                         │  │
│  │  • Gestión de port-forwards (kubectl port-forward)                   │  │
│  │  • Propagación de CarryOut → CarryIn en cascada                      │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │ kubectl scale + port-forward
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER (Minikube)                            │
│                    Namespace: calculadora-suma                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Escalado Dinámico (replicas: 0→1)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Pod-0      │  │   Pod-1      │  │   Pod-2      │  │   Pod-3      │   │
│  │  (Unidades)  │  │  (Decenas)   │  │  (Centenas)  │  │  (Millares)  │   │
│  │              │  │              │  │              │  │              │   │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │   │
│  │ │ Backend  │ │  │ │ Backend  │ │  │ │ Backend  │ │  │ │ Backend  │ │   │
│  │ │ Container│ │  │ │ Container│ │  │ │ Container│ │  │ │ Container│ │   │
│  │ │ :8000    │ │  │ │ :8000    │ │  │ │ :8000    │ │  │ │ :8000    │ │   │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │   │
│  │      ↕       │  │      ↕       │  │      ↕       │  │      ↕       │   │
│  │ Service:     │  │ Service:     │  │ Service:     │  │ Service:     │   │
│  │ NodePort     │  │ NodePort     │  │ NodePort     │  │ NodePort     │   │
│  │ :30000       │  │ :30001       │  │ :30002       │  │ :30003       │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────────┘
          │                 │                 │                 │
          └─────────────────┴─────────────────┴─────────────────┘
                     Port-forward a localhost

         ┌──────────────────────────────────────────────────────────┐
         │           FLUJO DE CARRY EN CASCADA                      │
         │                                                          │
         │  Pod-0 (U)     Pod-1 (D)     Pod-2 (C)     Pod-3 (M)    │
         │  ────────      ────────      ────────      ────────      │
         │   6 + 2    →    7 + 3    →    8 + 4    →    9 + 5       │
         │  + Cin:0       + Cin:0       + Cin:1       + Cin:1       │
         │  ────────      ────────      ────────      ────────      │
         │  = 8           = 10          = 13          = 15          │
         │  Cout: 0  ───→ Cout: 1  ───→ Cout: 1  ───→ Cout: 1      │
         │    │              │              │              │        │
         │    └──────────────┴──────────────┴──────────────┘        │
         │                  Resultado: 15308                        │
         └──────────────────────────────────────────────────────────┘
```

### Componentes

- **Frontend**: HTML/CSS/JavaScript (Puerto 8080)
- **Proxy Flask**: Orquesta las llamadas a los servicios K8s y gestiona el escalado dinámico
- **Pods Kubernetes**: 4 pods idénticos del backend (ghcr.io/lhalha01/contenedores-backend:latest)
  - **Escalado dinámico**: Los pods inician en `replicas: 0` y se escalan bajo demanda
  - **Port-forwarding automático**: El proxy establece los port-forwards cuando se necesitan
- **Servicios NodePort**: Exponen cada pod en puertos 30000-30003

### Flujo de Datos (Ejemplo: 9876 + 5432)

1. Usuario ingresa: `A=9876`, `B=5432`
2. Proxy descompone en dígitos (derecha a izquierda):
   ```
   Posición  | A | B |
   ---------|---|---|
   0 (Unid) | 6 | 2 |
   1 (Dec)  | 7 | 3 |
   2 (Cent) | 8 | 4 |
   3 (Mill) | 9 | 5 |
   ```
3. **Pod-0 (Unidades)**:
   - Input: `6 + 2 + 0(CarryIn)` = 8
   - Output: `Result=8, CarryOut=0` ✓
   
4. **Pod-1 (Decenas)**:
   - Input: `7 + 3 + 0(CarryIn previo)` = 10
   - Output: `Result=0, CarryOut=1` ✓
   
5. **Pod-2 (Centenas)**:
   - Input: `8 + 4 + 1(CarryIn previo)` = 13
   - Output: `Result=3, CarryOut=1` ✓
   
6. **Pod-3 (Millares)**:
   - Input: `9 + 5 + 1(CarryIn previo)` = 15
   - Output: `Result=5, CarryOut=1` ✓

7. **Resultado final**: `[CarryOut][M][C][D][U]` = `15308` ✓

## Requisitos

- **Kubernetes**: Minikube, Podman Desktop, o cualquier cluster local
- **kubectl**: Para gestionar recursos de K8s
- **Python 3.x**: Con Flask, Flask-CORS y Requests
- **Podman Desktop** (recomendado para Windows): Incluye Kubernetes integrado

## Instalación

### Paso 1: Instalar Podman Desktop (Windows)

```powershell
winget install RedHat.Podman-Desktop
```

### Paso 2: Habilitar Kubernetes en Podman Desktop

1. Abrir **Podman Desktop**
2. Ir a **Settings** → **Kubernetes**
3. Activar **Enable Kubernetes**
4. Esperar a que el cluster esté **Running** ✓

### Paso 3: Verificar Kubernetes

```powershell
kubectl cluster-info
kubectl get nodes
```

Deberías ver un nodo en estado **Ready**.

### Paso 4: Instalar Dependencias Python

```powershell
pip install flask flask-cors requests
```

## Despliegue en Kubernetes

### 1. Crear Secret para GitHub Container Registry

Para descargar la imagen privada del backend, necesitas autenticarte:

```powershell
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=lhalha01 \
  --docker-password=<TU_GITHUB_PAT> \
  -n calculadora-suma
```

**Nota**: Reemplaza `<TU_GITHUB_PAT>` con tu Personal Access Token de GitHub con permisos `read:packages`.

### 2. Aplicar Manifiestos de Kubernetes

```powershell
# Crear namespace
kubectl apply -f k8s/namespace.yaml

# Desplegar pods y servicios
kubectl apply -f k8s/deployment.yaml

# Verificar que los pods estén Running
kubectl get pods -n calculadora-suma
```

### 3. Port-Forward de Servicios (Automático)

**Rama DigitosDinamicos**: El proxy Flask establece automáticamente los port-forwards necesarios cuando escala los pods. No es necesario ejecutar comandos de port-forward manualmente.

**Nota**: Si deseas verificar manualmente los servicios o usar la rama NDigitos (sin escalado dinámico), puedes establecer port-forwards manualmente:

```powershell
# Terminal 1
kubectl port-forward -n calculadora-suma service/suma-digito-0 30000:8000

# Terminal 2
kubectl port-forward -n calculadora-suma service/suma-digito-1 30001:8000

# Terminal 3
kubectl port-forward -n calculadora-suma service/suma-digito-2 30002:8000

# Terminal 4
kubectl port-forward -n calculadora-suma service/suma-digito-3 30003:8000
```

En la rama **DigitosDinamicos**, el proxy gestiona esto automáticamente.

**Tip para rama NDigitos**: Puedes usar un script PowerShell para iniciar todos los port-forwards en background:

```powershell
Start-Job -ScriptBlock { kubectl port-forward -n calculadora-suma service/suma-digito-0 30000:8000 }
Start-Job -ScriptBlock { kubectl port-forward -n calculadora-suma service/suma-digito-1 30001:8000 }
Start-Job -ScriptBlock { kubectl port-forward -n calculadora-suma service/suma-digito-2 30002:8000 }
Start-Job -ScriptBlock { kubectl port-forward -n calculadora-suma service/suma-digito-3 30003:8000 }
```

### 4. Iniciar el Proxy Flask

```powershell
python proxy.py
```

### 5. Abrir la Aplicación

Navega a: **http://localhost:8080**

## Estructura de Archivos

```
SumaBasicaDocker/
├── k8s/
│   ├── namespace.yaml      # Definición del namespace
│   └── deployment.yaml     # 4 Deployments + Services (NodePort)
├── index.html              # Frontend con visualización dinámica de pods
├── script.js               # Lógica JavaScript (llama a /suma-n-digitos)
├── styles.css              # Estilos CSS con tema Kubernetes
├── proxy.py                # Servidor Flask que orquesta los pods
└── README.md               # Este archivo

## Comandos Útiles de Kubernetes

### Ver Recursos

```powershell
# Ver todos los recursos en el namespace
kubectl get all -n calculadora-suma

# Ver logs de un pod específico
kubectl logs -n calculadora-suma <nombre-pod>

# Describir un pod (útil para debugging)
kubectl describe pod -n calculadora-suma <nombre-pod>

# Ver servicios y sus puertos
kubectl get services -n calculadora-suma
```

### Escalar Pods

**Rama DigitosDinamicos**: El escalado se realiza automáticamente. Los deployments inician en `replicas: 0` y el proxy los escala bajo demanda.

Para escalar manualmente (rama NDigitos o debugging):

```powershell
# Aumentar réplicas de un deployment
kubectl scale deployment suma-digito-0 --replicas=3 -n calculadora-suma

# Verificar réplicas
kubectl get deployments -n calculadora-suma

# Escalar todos los deployments a 0 (rama DigitosDinamicos por defecto)
kubectl scale deployment suma-digito-0 suma-digito-1 suma-digito-2 suma-digito-3 --replicas=0 -n calculadora-suma

# Escalar todos los deployments a 1 (rama NDigitos comportamiento original)
kubectl scale deployment suma-digito-0 suma-digito-1 suma-digito-2 suma-digito-3 --replicas=1 -n calculadora-suma
```

### Limpiar Recursos

```powershell
# Eliminar todo el namespace (y sus recursos)
kubectl delete namespace calculadora-suma

# O eliminar recursos individuales
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/namespace.yaml
```

### Reiniciar Pods

```powershell
# Reiniciar todos los pods de un deployment
kubectl rollout restart deployment suma-digito-0 -n calculadora-suma

# Verificar el estado del rollout
kubectl rollout status deployment suma-digito-0 -n calculadora-suma
```

## API del Proxy

### Endpoint Principal

**POST** `/suma-n-digitos`

**Request:**
```json
{
  "NumberA": 9876,
  "NumberB": 5432
}
```

**Response:**
```json
{
  "Result": 15308,
  "CarryOut": 1,
  "NumDigitos": 4,
  "ContenedoresUsados": 4,
  "Details": [
    {
      "Posicion": 0,
      "NombrePosicion": "Unidades",
      "Pod": "suma-digito-0",
      "Port": 30000,
      "A": 6, "B": 2, "CarryIn": 0,
      "Result": 8, "CarryOut": 0
    },
    {
      "Posicion": 1,
      "NombrePosicion": "Decenas",
      "Pod": "suma-digito-1",
      "Port": 30001,
      "A": 7, "B": 3, "CarryIn": 0,
      "Result": 0, "CarryOut": 1
    },
    {
      "Posicion": 2,
      "NombrePosicion": "Centenas",
      "Pod": "suma-digito-2",
      "Port": 30002,
      "A": 8, "B": 4, "CarryIn": 1,
      "Result": 3, "CarryOut": 1
    },
    {
      "Posicion": 3,
      "NombrePosicion": "Millares",
      "Pod": "suma-digito-3",
      "Port": 30003,
      "A": 9, "B": 5, "CarryIn": 1,
      "Result": 5, "CarryOut": 1
    }
  ]
}
```

## Ejemplos de Prueba

### Ejemplo 1: Números de 1 dígito (usa solo Pod-0)
```
5 + 3 = 8
- Pod-0 (Unidades): 5+3+0=8 → Result=8, CarryOut=0
- Resultado: 8
- Pods usados: 1
```

### Ejemplo 2: Números de 2 dígitos con carry
```
99 + 88 = 187
- Pod-0 (Unidades): 9+8+0=17 → Result=7, CarryOut=1
- Pod-1 (Decenas): 9+8+1=18 → Result=8, CarryOut=1
- Resultado: 187 (concatena: 1+8+7)
- Pods usados: 2
```

### Ejemplo 3: Números de 4 dígitos
```
9876 + 5432 = 15308
- Pod-0: 6+2+0=8 → Result=8, CarryOut=0
- Pod-1: 7+3+0=10 → Result=0, CarryOut=1
- Pod-2: 8+4+1=13 → Result=3, CarryOut=1
- Pod-3: 9+5+1=15 → Result=5, CarryOut=1
- Resultado: 15308 (concatena: 1+5+3+0+8)
- Pods usados: 4
```

### Ejemplo 4: Máximo valor soportado
```
9999 + 9999 = 19998
- Pod-0: 9+9+0=18 → Result=8, CarryOut=1
- Pod-1: 9+9+1=19 → Result=9, CarryOut=1
- Pod-2: 9+9+1=19 → Result=9, CarryOut=1
- Pod-3: 9+9+1=19 → Result=9, CarryOut=1
- Resultado: 19998
- Pods usados: 4
```

## Pruebas con API

### Probar un pod individual (con port-forward activo):
```powershell
$body = @{NumberA=5; NumberB=3; CarryIn=0} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:30000/suma" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
```

### Probar la cascada completa:
```powershell
$body = @{NumberA=9876; NumberB=5432} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8080/suma-n-digitos" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
```

## Características del Frontend

- **Entradas**: Números de 0 a 9999
- **Visualización dinámica**:
  - Solo muestra los pods realmente usados (1-4)
  - Resalta el CarryOut cuando está activo (rojo con animación)
  - Muestra el flujo de carry entre pods
  - Iconos de Kubernetes (pods, servicios)
- **Responsive**: Se adapta a móviles y tablets
- **Tema**: Colores azul/morado estilo Kubernetes

## Ramas del Proyecto

Este proyecto tiene 3 ramas con diferentes niveles de complejidad:

### `master` - Un Dígito (0-9)
- 1 contenedor Podman
- Puerto: 8000
- Ideal para aprender lo básico

### `DosDigitos` - Dos Dígitos (0-99)
- 2 contenedores Podman en cascada
- Puertos: 8001, 8002
- Introduce el concepto de carry entre contenedores

### `NDigitos` (actual) - N Dígitos (0-9999)
- 4 pods Kubernetes con NodePort
- Puertos: 30000-30003
- Orquestación dinámica según dígitos necesarios
- Arquitectura cloud-native escalable

## URLs del Sistema

- **Frontend**: http://localhost:8080
- **API Proxy**: http://localhost:8080/suma-n-digitos
- **Pod-0 (Unidades)**: http://localhost:30000/suma
- **Pod-1 (Decenas)**: http://localhost:30001/suma
- **Pod-2 (Centenas)**: http://localhost:30002/suma
- **Pod-3 (Millares)**: http://localhost:30003/suma
- **Docs API Backend**: http://localhost:30000/docs

## Solución de Problemas

### Pods en ImagePullBackOff

```powershell
# Verificar el secret
kubectl get secret ghcr-secret -n calculadora-suma

# Si no existe, créalo como se indica en la sección de despliegue
kubectl create secret docker-registry ghcr-secret ...
```

### Port-forward no funciona

```powershell
# Verificar que los pods estén Running
kubectl get pods -n calculadora-suma

# Reiniciar los port-forwards
Get-Job | Remove-Job -Force
kubectl port-forward -n calculadora-suma service/suma-digito-0 30000:8000
# ... repetir para los otros 3 servicios
```

### Proxy no se conecta a los servicios

```powershell
# Verificar que los servicios existan
kubectl get services -n calculadora-suma

# Probar un servicio individualmente
Invoke-WebRequest -Uri "http://localhost:30000/suma" -Method POST ...
```

---

**Rama:** NDigitos  
**Tecnologías**: Kubernetes, Podman Desktop, Flask, Python  
**Versión:** 3.0  
**Fecha:** Febrero 2026  
**Repositorio**: https://github.com/lhalha01/SumaBasicaDocker
