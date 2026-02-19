# Especificación SDD del Proyecto SumaBasicaDocker

## 1. Propósito del documento

Definir todas las especificaciones funcionales, técnicas y operativas necesarias para reconstruir este proyecto desde cero bajo un enfoque SDD (Desarrollo Dirigido por Especificaciones), sin depender del código existente.

## 2. Visión del producto

Aplicación web educativa que implementa la suma de dos números enteros no negativos de hasta 4 dígitos, modelando un sumador en cascada (Ripple-Carry) distribuido en varios servicios backend orquestados por Kubernetes.

## 3. Objetivos

- Simular arquitectura distribuida por posición decimal (unidades, decenas, centenas, millares).
- Escalar pods de forma dinámica según la cantidad de dígitos requeridos.
- Reducir consumo en reposo con estrategia scale-to-zero.
- Exponer trazabilidad operacional en una terminal embebida en frontend.

## 4. Alcance

### 4.1 En alcance

- Frontend web para entrada de datos y visualización de resultados.
- Proxy backend en Python/Flask que orquesta Kubernetes.
- 4 servicios backend homogéneos para cálculo por dígito.
- Manifiestos Kubernetes para namespace, deployments y services.
- Chart Helm para empaquetar y desplegar workloads por dígito.
- Mecanismo de logs en tiempo real por SSE.
- Scripts operativos PowerShell para despliegue, diagnóstico y limpieza Helm en local.
- Pipeline CI/CD con prácticas IaC, CI, CD, CaC y DaC.

### 4.2 Fuera de alcance

- Soporte de números negativos.
- Soporte de más de 4 dígitos.
- Persistencia de datos histórica (base de datos).
- Multi-tenant o autenticación de usuario final.

## 5. Stakeholders y perfiles

- Estudiante/desarrollador: usa la app para aprender orquestación y carry en cascada.
- Docente/mentor: evalúa arquitectura, observabilidad y calidad.
- DevOps: despliega y opera solución en clúster local o AKS.

## 6. Requisitos funcionales

### RF-01 Entrada de operación

El sistema debe permitir capturar NumberA y NumberB entre 0 y 9999.

### RF-02 Validación

El sistema debe rechazar entradas fuera de rango con mensaje claro.

### RF-03 Orquestación por dígitos

El proxy debe calcular cuántos dígitos son necesarios y activar únicamente los pods requeridos para la operación.

### RF-04 Escalado dinámico

El proxy debe escalar a 1 réplica los deployments necesarios antes de calcular.

### RF-05 Readiness

El proxy debe esperar condición Ready de cada pod antes de invocarlo.

### RF-06 Comunicación en cascada

Cada pod debe recibir NumberA, NumberB y CarryIn, y devolver Result y CarryOut.

### RF-07 Reconstrucción de resultado

El proxy debe construir el resultado final concatenando carry final y resultados parciales en orden correcto.

### RF-08 Eventos de escalado

El sistema debe registrar eventos de escalado y estado por pod para la UI.

### RF-09 Terminal embebida

La UI debe mostrar logs operativos en tiempo real vía SSE.

### RF-10 Limpieza de terminal

La UI debe poder limpiar el buffer de terminal.

### RF-11 Auto scale-down

Tras completar una operación, el sistema debe escalar deployments a 0 y cerrar port-forwards.

### RF-12 Estado de stream

La UI debe mostrar estado de conexión del stream: conectando, conectado, reintentando.

## 7. Requisitos no funcionales

### RNF-01 Disponibilidad local

El sistema debe funcionar en entorno local con Kubernetes activo.

### RNF-02 Latencia

- Primera operación con pods apagados: latencia aceptable de arranque (segundos).
- Operaciones subsecuentes: latencia reducida.

### RNF-03 Observabilidad

Todo evento crítico de orquestación debe quedar visible en terminal embebida y consola backend.

### RNF-04 Seguridad mínima

- CORS controlado para uso local.
- Secret para registro de imágenes privadas.

### RNF-05 Portabilidad

El diseño debe poder migrarse a AKS con ajustes de red y permisos.

### RNF-06 Mantenibilidad

Separación clara de responsabilidades: frontend, proxy, manifiestos, docs, pipeline.

## 8. Arquitectura lógica

### 8.1 Componentes

- Frontend (HTML/CSS/JS): interacción y visualización.
- Proxy Flask: API de suma, coordinación de operación y SSE.
- Módulo `k8s_orchestrator.py`: orquestación `kubectl` (scale, wait, port-forward, scale-down).
- Servicios backend por dígito (4): cálculo atómico por posición.
- Kubernetes: deployments y services NodePort.
- Helm: chart `helm/suma-basica` para instalación/upgrade parametrizable.

### 8.2 Flujo de alto nivel

1. Frontend envía operación al proxy.
2. Proxy descompone números y escala pods necesarios.
3. Proxy espera readiness y establece rutas de acceso.
4. Proxy ejecuta suma en cascada propagando carry.
5. Proxy devuelve resultado y detalle.
6. Proxy inicia scale-down a zero.

## 9. Contratos de API

### 9.1 Endpoint principal

Método: POST  
Ruta: /suma-n-digitos

Request JSON:

- NumberA: integer
- NumberB: integer

Response JSON:

- Result: integer
- CarryOut: integer (0 o 1)
- NumDigitos: integer
- ContenedoresUsados: integer
- Details: array
- EventosEscalado: array

### 9.2 Contrato de Details

Cada elemento debe incluir:

- Posicion
- NombrePosicion
- Pod
- Port
- A
- B
- CarryIn
- Result
- CarryOut

### 9.3 Contrato de EventosEscalado

Cada evento debe incluir:

- Tipo (escalado, espera, listo)
- Pod
- Posicion
- Estado
- Timestamp

### 9.4 Stream de terminal

Método: GET  
Ruta: /terminal-stream  
Tipo: text/event-stream (SSE)

Evento JSON:

- timestamp
- level (info, success, warning, error)
- message

### 9.5 Limpieza de buffer

Método: POST  
Ruta: /terminal-clear

## 10. Reglas de negocio

- RB-01: Solo se permiten números de 0 a 9999.
- RB-02: Máximo 4 pods lógicos por operación.
- RB-03: El carry debe propagarse de posición menor a mayor.
- RB-04: Si falla escalado/readiness de un pod, la operación completa falla.
- RB-05: Si un pod no responde, se permiten reintentos limitados.
- RB-06: Después de la operación, el sistema debe intentar volver a 0 réplicas.

## 11. Especificación de frontend

### 11.1 Pantalla principal

Debe incluir:

- Inputs NumberA y NumberB.
- Botón Calcular.
- Resultado, pods usados y carry final.
- Panel de detalle de pods en cascada.
- Terminal embebida con controles de limpiar y auto-scroll.

### 11.2 Comportamientos UI

- Enter en input ejecuta cálculo.
- Indicadores de carga durante operación.
- Render progresivo de pods para visualizar secuencia.
- Render de flechas y resaltado de carry.

## 12. Especificación de backend proxy y orquestador

### 12.1 Tecnologías

- Python 3.x
- Flask + Flask-CORS
- requests
- subprocess para comandos kubectl

### 12.2 Separación de responsabilidades

- `proxy.py`: validación de entrada, secuencia de cálculo, exposición de endpoints y SSE.
- `k8s_orchestrator.py`: ejecución de comandos `kubectl`, manejo de port-forwards y scale-down.

### 12.3 Comandos orquestados

- kubectl scale
- kubectl wait
- kubectl port-forward

### 12.4 Gestión de puertos

- Definir puertos preferidos por dígito.
- Si hay colisión, seleccionar puerto libre dinámico.

### 12.5 Concurrencia

- Proteger buffer de logs con lock.
- Evitar desincronización del stream en reinicios o limpieza de buffer.

## 13. Especificación Kubernetes

### 13.1 Namespace

- Nombre: calculadora-suma

### 13.2 Deployments

- 4 deployments (suma-digito-0..3)
- Imagen backend común
- Label app=suma-backend y digito={0..3}
- Configuración inicial esperada en rama dinámica: replicas 0

### 13.3 Services

- 4 services tipo NodePort (uno por dígito)
- Puerto target del contenedor: 8000

### 13.4 Secret de registro

- Secret docker-registry para acceso a imagen privada (GHCR)

### 13.5 Helm

- Chart: `helm/suma-basica`
- Values base: `helm/suma-basica/values.yaml`
- Values local: `helm/suma-basica/values-local.yaml`
- Scripts operativos:
  - `scripts/helm-local.ps1`
  - `scripts/helm-status.ps1`
  - `scripts/helm-clean.ps1`
  - `scripts/helm-all.ps1`

## 14. Estrategia SDD por fases

### Fase 1: Especificación

- Cerrar este documento y validarlo con stakeholders.

### Fase 2: Diseño

- Diagramas de componentes, secuencia y despliegue.
- Definición de contratos JSON exactos.

### Fase 3: Implementación guiada por requisitos

- Implementar RF-01..RF-12 con trazabilidad requisito-código.

### Fase 4: Verificación

- Pruebas unitarias, integración y e2e.
- Evidencia por requisito.

### Fase 5: Operación

- Métricas mínimas y runbooks.

## 15. Matriz de trazabilidad (resumen)

- RF-01/02: validaciones frontend/proxy.
- RF-03..07: endpoint /suma-n-digitos y funciones de orquestación.
- RF-08..10: eventos + SSE + terminal UI.
- RF-11: hilo de scale-down.
- RF-12: estado visual del stream.

## 16. Estrategia de pruebas

### 16.1 Casos funcionales

- T01: 5 + 3 = 8 (1 pod).
- T02: 99 + 88 = 187 (2 pods).
- T03: 9876 + 5432 = 15308 (4 pods).
- T04: 9999 + 9999 = 19998.
- T05: Entrada fuera de rango (error).

### 16.2 Casos operativos

- T06: Cluster apagado (error controlado).
- T07: Puerto ocupado (fallback dinámico).
- T08: Pod no Ready en timeout.
- T09: Stream con reconexión automática.
- T10: Scale-down final a 0.

## 17. Criterios de aceptación

- CA-01: Todos los casos T01-T05 pasan.
- CA-02: Logs SSE reflejan eventos críticos.
- CA-03: Tras operación, deployments vuelven a 0/0 en modo dinámico.
- CA-04: Documentación técnica y onboarding disponibles.
- CA-05: Pipeline CI/CD ejecuta validaciones mínimas.

## 18. Especificación DevSecOps

### 18.1 IaC

- Terraform para infraestructura AKS base.

### 18.2 CI

- Lint y validación de Python.
- Validación sintáctica de manifiestos K8s.
- Validación de chart Helm (`helm lint` + render de plantillas).

### 18.3 CD

- Despliegue automatizado de namespace y workloads en AKS.

### 18.4 CaC (Compliance as Code)

- Escaneo de políticas (por ejemplo, Checkov) en repositorio y manifiestos.

### 18.5 DaC (Documentation as Code)

- Lint de markdown.
- Validación de secciones críticas de documentación.

## 19. Parámetros de configuración

- Namespace.
- Imagen backend y tag.
- Límites de recursos por deployment.
- Tipo de servicio/NodePorts por dígito.
- Límite de dígitos.
- Flags de scale-down y retardo.
- Release Helm, ruta de chart y archivo de values por entorno.

## 20. Riesgos y mitigaciones

- Riesgo: Dependencia de kubectl local.
  - Mitigación: migrar a cliente oficial K8s Python.
- Riesgo: colisiones de puertos.
  - Mitigación: detección de puerto libre.
- Riesgo: latencia de cold start.
  - Mitigación: comunicación clara en UI y readiness robusto.

## 21. Definición de listo (DoD)

- Requisitos funcionales implementados y trazables.
- Casos de prueba críticos aprobados.
- Documentación técnica y operativa completa.
- Pipeline CI/CD sin fallos críticos.

## 22. Anexos

- Documento técnico de proxy: docs/proxy-tecnico.md
- Documento técnico de frontend JS: docs/script-tecnico.md
- Onboarding rápido: docs/onboarding-rapido.md
- Scripts operativos Helm: scripts/helm-local.ps1, scripts/helm-status.ps1, scripts/helm-clean.ps1, scripts/helm-all.ps1
