FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && KVER=v1.25.7 \
    && curl -L -o /usr/local/bin/kubectl https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY proxy.py k8s_orchestrator.py index.html script.js styles.css ./

ENV K8S_NAMESPACE=calculadora-suma
ENV ORCHESTRATOR_IN_CLUSTER=true
ENV BACKEND_SERVICE_PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "proxy.py"]
