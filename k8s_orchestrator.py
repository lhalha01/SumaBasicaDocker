import os
import socket
import subprocess
import time


class K8sOrchestrator:
    def __init__(
        self,
        logger,
        namespace="calculadora-suma",
        max_digitos=4,
        base_port=31000,
        in_cluster=False,
        service_port=8000
    ):
        self.logger = logger
        self.namespace = namespace
        self.max_digitos = max_digitos
        self.base_port = base_port
        self.in_cluster = in_cluster
        self.service_port = service_port
        self.port_forward_processes = {}
        self.port_forward_ports = {}

    def obtener_puerto_local_disponible(self, puerto_preferido):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_local:
            socket_local.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                socket_local.bind(("127.0.0.1", puerto_preferido))
                return puerto_preferido
            except OSError:
                pass

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_local:
            socket_local.bind(("127.0.0.1", 0))
            return socket_local.getsockname()[1]

    def escalar_pod(self, digito, replicas):
        deployment_name = f"suma-digito-{digito}"
        cmd = ["kubectl", "scale", "deployment", deployment_name, f"--replicas={replicas}", "-n", self.namespace]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger(f"✓ Deployment {deployment_name} escalado a {replicas} réplica(s)", "success")
                return True

            self.logger(f"✗ Error escalando {deployment_name}: {result.stderr}", "error")
            return False
        except subprocess.TimeoutExpired:
            self.logger(f"✗ Timeout escalando {deployment_name}", "error")
            return False
        except Exception as error:
            self.logger(f"✗ Excepción escalando {deployment_name}: {error}", "error")
            return False

    def esperar_pod_ready(self, digito, timeout=60):
        cmd = [
            "kubectl", "wait", "--for=condition=ready",
            "pod",
            "-l", f"app=suma-backend,digito={digito}",
            "-n", self.namespace,
            f"--timeout={timeout}s"
        ]

        try:
            self.logger(f"⏳ Esperando a que el pod suma-digito-{digito} esté listo...", "info")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            if result.returncode == 0:
                self.logger(f"✓ Pod suma-digito-{digito} está listo", "success")
                return True

            self.logger(f"✗ Pod suma-digito-{digito} no está listo: {result.stderr}", "error")
            return False
        except subprocess.TimeoutExpired:
            self.logger(f"✗ Timeout esperando pod suma-digito-{digito}", "error")
            return False
        except Exception as error:
            self.logger(f"✗ Excepción esperando pod suma-digito-{digito}: {error}", "error")
            return False

    def esperar_endpoints_servicio(self, digito, timeout=30):
        service_name = f"suma-digito-{digito}"
        deadline = time.time() + timeout

        self.logger(
            f"⏳ Esperando endpoints para servicio {service_name}...",
            "info"
        )

        while time.time() < deadline:
            cmd_endpoints = [
                "kubectl", "get", "endpoints", service_name,
                "-n", self.namespace,
                "-o", "jsonpath={.subsets[*].addresses[*].ip}"
            ]

            cmd_endpoint_slices = [
                "kubectl", "get", "endpointslices",
                "-n", self.namespace,
                "-l", f"kubernetes.io/service-name={service_name}",
                "-o", "jsonpath={.items[*].endpoints[*].addresses[*]}"
            ]

            try:
                result_endpoints = subprocess.run(
                    cmd_endpoints,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                result_endpoint_slices = subprocess.run(
                    cmd_endpoint_slices,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                has_endpoints = result_endpoints.returncode == 0 and result_endpoints.stdout.strip()
                has_endpoint_slices = (
                    result_endpoint_slices.returncode == 0
                    and result_endpoint_slices.stdout.strip()
                )

                if has_endpoints or has_endpoint_slices:
                    self.logger(
                        f"✓ Servicio {service_name} tiene endpoints activos",
                        "success"
                    )
                    return True
            except Exception:
                pass

            time.sleep(1)

        self.logger(
            f"✗ Timeout esperando endpoints para servicio {service_name}",
            "error"
        )
        return False

    def establecer_port_forward(self, digito):
        try:
            if self.in_cluster:
                self.logger(
                    f"✓ Modo in-cluster activo para digito-{digito}: usando servicio interno",
                    "info"
                )
                return True

            if digito in self.port_forward_processes:
                proceso = self.port_forward_processes[digito]
                if proceso.poll() is None:
                    puerto_actual = self.port_forward_ports.get(digito, self.base_port + digito)
                    self.logger(
                        f"✓ Port-forward para digito-{digito} ya está activo (puerto {puerto_actual})",
                        "success"
                    )
                    return True

                self.port_forward_processes.pop(digito, None)
                self.port_forward_ports.pop(digito, None)

            service_name = f"suma-digito-{digito}"
            puerto_preferido = self.base_port + digito
            local_port = self.obtener_puerto_local_disponible(puerto_preferido)

            if local_port != puerto_preferido:
                self.logger(
                    f"⚠ Puerto {puerto_preferido} ocupado para digito-{digito}; usando {local_port}",
                    "warning"
                )

            cmd = ["kubectl", "port-forward", f"svc/{service_name}", f"{local_port}:8000", "-n", self.namespace]

            proceso = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )

            time.sleep(1.5)

            if proceso.poll() is not None:
                try:
                    _, stderr_data = proceso.communicate(timeout=1)
                except Exception:
                    stderr_data = ""

                detalle = f" Detalle: {stderr_data.strip()}" if stderr_data else ""
                self.logger(f"✗ Port-forward terminó inmediatamente para {service_name}.{detalle}", "error")
                return False

            self.port_forward_processes[digito] = proceso
            self.port_forward_ports[digito] = local_port
            self.logger(f"✓ Port-forward establecido para {service_name} en puerto {local_port}", "success")
            return True
        except Exception as error:
            self.logger(f"✗ Excepción estableciendo port-forward para digito-{digito}: {error}", "error")
            return False

    def detener_port_forward(self, digito):
        proceso = self.port_forward_processes.get(digito)
        if not proceso:
            return

        try:
            if proceso.poll() is None:
                proceso.terminate()
                try:
                    proceso.wait(timeout=2)
                except Exception:
                    proceso.kill()
            self.logger(f"✓ Port-forward detenido para suma-digito-{digito}", "info")
        except Exception as error:
            self.logger(f"⚠ No se pudo detener port-forward de suma-digito-{digito}: {error}", "warning")
        finally:
            self.port_forward_processes.pop(digito, None)
            self.port_forward_ports.pop(digito, None)

    def service_url(self, digito):
        if self.in_cluster:
            service_name = f"suma-digito-{digito}"
            return f"http://{service_name}.{self.namespace}.svc.cluster.local:{self.service_port}", self.service_port

        local_port = self.port_forward_ports.get(digito, self.base_port + digito)
        return f"http://localhost:{local_port}", local_port

    def escalar_a_cero(self, delay_seconds=2):
        if delay_seconds > 0:
            time.sleep(delay_seconds)

        self.logger(f"\n{'-' * 60}", "info")
        self.logger("Iniciando scale-down automático a 0 réplicas", "info")

        for i in range(self.max_digitos):
            self.logger(f"⏬ Escalando suma-digito-{i} -> 0", "info")
            if self.escalar_pod(i, 0):
                self.logger(f"✓ suma-digito-{i} en 0 réplicas", "success")
            else:
                self.logger(f"✗ No se pudo escalar suma-digito-{i} a 0", "error")

            if not self.in_cluster:
                self.detener_port_forward(i)

        self.logger("✓ Scale-down completado: pods en zero", "success")
        self.logger(f"{'-' * 60}\n", "info")
