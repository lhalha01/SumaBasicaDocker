# Guía de Publicación: Frontal + API dentro de AKS

## 1. Objetivo
Publicar la aplicación completa en Azure Kubernetes Service (AKS), incluyendo:
- **Frontal** (HTML/CSS/JS)
- **API Proxy** (Flask)
- **Servicios de suma por dígito** (backend)

La exposición pública se realiza con **un único endpoint** (dominio o IP pública), de forma que el frontal y la API compartan origen.

---

## 2. Arquitectura recomendada en AKS

- Namespace: `calculadora-suma`
- Deployments backend:
  - `suma-digito-0`
  - `suma-digito-1`
  - `suma-digito-2`
  - `suma-digito-3`
- Service backend por dígito (ClusterIP o NodePort según estrategia)
- Deployment proxy/frontal: `suma-basica-proxy`
- Service proxy: `suma-basica-proxy` (ClusterIP)
- Exposición externa:
  - **Opción A (recomendada):** Ingress Controller + Ingress
  - **Opción B (simple):** Service `LoadBalancer`

> Recomendación: usar Ingress para tener HTTPS y un único host estable.

---

## 3. Prerrequisitos

- Azure CLI autenticado (`az login`)
- `kubectl` instalado
- `helm` instalado (si despliegas con Helm)
- AKS existente (ejemplo):
  - Resource Group: `AHL_resources`
  - Cluster: `KSuma`
- Contexto kubectl apuntando al clúster:

```powershell
az aks get-credentials -g AHL_resources -n KSuma --overwrite-existing
kubectl config current-context
```

---

## 4. Preparar namespace y secreto de imágenes

```powershell
kubectl create namespace calculadora-suma --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret docker-registry ghcr-secret `
  --namespace calculadora-suma `
  --docker-server=ghcr.io `
  --docker-username=<GITHUB_USER> `
  --docker-password=<GITHUB_PAT> `
  --dry-run=client -o yaml | kubectl apply -f -
```

Si usas solo imágenes públicas, este secreto no es obligatorio.

---

## 5. Despliegue con Helm (flujo recomendado)

Si la rama incluye chart Helm (por ejemplo `ConHelm`):

```powershell
helm lint .\helm\suma-basica

helm upgrade --install suma-basica .\helm\suma-basica `
  --namespace calculadora-suma `
  --create-namespace `
  -f .\helm\suma-basica\values-local.yaml `
  --set namespace.create=false `
  --wait --timeout 15m
```

Verificación:

```powershell
helm status suma-basica -n calculadora-suma
kubectl get deployments,services,pods -n calculadora-suma
```

---

## 6. Exposición pública

### Opción A: Ingress (recomendada)
1. Instala NGINX Ingress Controller (si no existe).
2. Crea un Ingress que apunte a `suma-basica-proxy` puerto `8080`.
3. Asocia DNS al `EXTERNAL-IP` del Ingress.
4. Configura TLS (cert-manager o certificado manual).

Ejemplo de Ingress mínimo:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: suma-basica-ingress
  namespace: calculadora-suma
spec:
  ingressClassName: nginx
  rules:
    - host: suma.midominio.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: suma-basica-proxy
                port:
                  number: 8080
```

### Opción B: LoadBalancer
Configura el service del proxy como `LoadBalancer` y consume la IP pública asignada.

---

## 7. Validación funcional

### 7.1 Health frontal
```powershell
python -c "import requests; r=requests.get('https://suma.midominio.com', timeout=20); print(r.status_code)"
```

### 7.2 Operación de suma
```powershell
python -c "import requests; r=requests.post('https://suma.midominio.com/suma-n-digitos', json={'NumberA':123,'NumberB':456}, timeout=120); print(r.status_code); print(r.json().get('Result'))"
```

Resultado esperado: `200` y `579`.

---

## 8. Operación y troubleshooting

### Ver estado general
```powershell
kubectl get deployments,services,pods -n calculadora-suma
kubectl get events -n calculadora-suma --sort-by=.lastTimestamp
```

### Logs del proxy
```powershell
kubectl logs -n calculadora-suma deploy/suma-basica-proxy --tail=200
```

### Problemas comunes
- `ImagePullBackOff`: imagen no existe o secret inválido.
- `CrashLoopBackOff`: revisar variables de entorno y logs.
- `No se pudo escalar el pod`: permisos RBAC insuficientes del proxy.
- `Timeout en ingress`: service/targetPort incorrecto o health probe fallando.

---

## 9. Recomendaciones de costo mínimo

- Reutilizar el AKS existente (`KSuma`) para frontal + API.
- Exponer solo el proxy (un endpoint), no cada servicio interno.
- Mantener backend en scale-to-zero cuando aplique.
- Usar un solo Ingress público para simplificar operación.

---

## 10. Checklist final

- [ ] AKS en estado `Running`
- [ ] Namespace `calculadora-suma` creado
- [ ] Secret de imágenes validado (si aplica)
- [ ] Release Helm en estado `deployed`
- [ ] `suma-basica-proxy` en `Running`
- [ ] Endpoint público accesible
- [ ] `POST /suma-n-digitos` retorna `200`
