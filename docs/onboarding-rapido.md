# Onboarding Rápido (1 página)

## 1) Qué es este proyecto
Aplicación web que suma números de hasta 4 dígitos usando una cascada de pods en Kubernetes (modelo tipo ripple-carry). El backend real está distribuido por posición decimal:
- Pod-0: Unidades
- Pod-1: Decenas
- Pod-2: Centenas
- Pod-3: Millares

El `proxy.py` orquesta escalado dinámico, readiness, port-forward, ejecución en cascada y scale-down a cero.

## 2) Componentes clave
- `index.html` / `styles.css`: UI
- `script.js`: lógica cliente + terminal embebido (SSE)
- `proxy.py`: orquestador Flask
- `k8s/deployment.yaml`: Deployments + Services NodePort
- `k8s/namespace.yaml`: namespace `calculadora-suma`

Documentación técnica ampliada:
- `docs/proxy-tecnico.md`
- `docs/script-tecnico.md`

## 3) Arranque rápido (Windows + Podman + Minikube)
```powershell
# Podman
podman machine start podman-machine-default

# Minikube
minikube start --driver=podman

# Verificar cluster
kubectl get nodes

# Desplegar recursos
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml

# Dependencias Python
pip install flask flask-cors requests

# Ejecutar proxy/frontend
python proxy.py
```
Abrir: `http://localhost:8080`

## 4) Flujo funcional (resumen)
1. Usuario envía `NumberA` y `NumberB` desde frontend.
2. `proxy.py` descompone en dígitos y calcula cuántos pods necesita.
3. Escala deployments requeridos a `1`, espera `Ready`, levanta `port-forward`.
4. Ejecuta suma posición a posición propagando carry.
5. Devuelve `Result`, `Details`, `EventosEscalado`.
6. En segundo plano, escala deployments a `0` y cierra port-forwards.

## 5) Endpoint principal
`POST /suma-n-digitos`

Request:
```json
{ "NumberA": 9876, "NumberB": 5432 }
```

Response (campos importantes):
- `Result`
- `CarryOut`
- `ContenedoresUsados`
- `Details[]`
- `EventosEscalado[]`

## 6) Terminal embebido
- Cliente abre `EventSource('/terminal-stream')`.
- Backend publica líneas con `timestamp`, `level`, `message`.
- Estado visual de stream: conectando/conectado/reintentando.
- Limpieza de buffer: `POST /terminal-clear`.

## 7) Verificación rápida de salud
```powershell
kubectl get deployments -n calculadora-suma
kubectl get pods -n calculadora-suma
kubectl get services -n calculadora-suma
```
Esperado en reposo (rama dinámica): deployments en `0/0` tras completar una operación.

## 8) Problemas comunes
- `Unable to connect to the server`: cluster apagado → iniciar Podman + Minikube.
- Fallo de `port-forward`: revisar puertos ocupados/procesos viejos.
- UI sin logs: verificar que `proxy.py` esté en ejecución y `GET /terminal-stream` responda 200.

## 9) Checklist para contribuir
- Probar una suma simple (`1 + 1`) y una de 4 dígitos (`1 + 9999`).
- Confirmar que el terminal embebido muestra escalado y scale-down.
- Validar que deployments vuelven a `0/0`.
- Mantener cambios en la rama de versión correspondiente (sin PR si así se gestiona el repositorio).
