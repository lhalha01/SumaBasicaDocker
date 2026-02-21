"""
Tests unitarios para k8s_orchestrator.py.

Cobertura:
    - service_url()                      : modo in-cluster vs local
    - escalar_pod()                      : éxito, error de kubectl, timeout
    - esperar_pod_ready()                : éxito, fallo, timeout
    - obtener_puerto_local_disponible()  : puerto libre, puerto ocupado
    - detener_port_forward()             : proceso activo, proceso inexistente
"""
import subprocess
import pytest
from unittest.mock import MagicMock, patch, call


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def logger():
    return MagicMock()


@pytest.fixture()
def orch(logger, RealOrchClass):
    """Instancia real de K8sOrchestrator (modo local, sin in_cluster)."""
    return RealOrchClass(
        logger=logger,
        namespace="calculadora-suma",
        max_digitos=4,
        base_port=31000,
        in_cluster=False,
        service_port=8000,
    )


@pytest.fixture()
def orch_in_cluster(logger, RealOrchClass):
    """Instancia real de K8sOrchestrator configurada en modo in-cluster."""
    return RealOrchClass(
        logger=logger,
        namespace="calculadora-suma",
        max_digitos=4,
        base_port=31000,
        in_cluster=True,
        service_port=8000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# service_url
# ─────────────────────────────────────────────────────────────────────────────

class TestServiceUrl:
    def test_modo_local_sin_portforward_registrado(self, orch):
        url, port = orch.service_url(0)
        assert url == "http://localhost:31000"
        assert port == 31000

    def test_modo_local_con_portforward_registrado(self, orch):
        orch.port_forward_ports[2] = 31099
        url, port = orch.service_url(2)
        assert url == "http://localhost:31099"
        assert port == 31099

    def test_modo_in_cluster_digito_0(self, orch_in_cluster):
        url, port = orch_in_cluster.service_url(0)
        assert url == "http://suma-digito-0.calculadora-suma.svc.cluster.local:8000"
        assert port == 8000

    def test_modo_in_cluster_digito_3(self, orch_in_cluster):
        url, port = orch_in_cluster.service_url(3)
        assert url == "http://suma-digito-3.calculadora-suma.svc.cluster.local:8000"


# ─────────────────────────────────────────────────────────────────────────────
# escalar_pod
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalarPod:
    def _make_result(self, returncode=0, stderr=""):
        r = MagicMock()
        r.returncode = returncode
        r.stderr = stderr
        return r

    def test_escala_exitosamente(self, orch, logger):
        with patch("k8s_orchestrator.subprocess.run", return_value=self._make_result(0)):
            assert orch.escalar_pod(0, 1) is True
        logger.assert_called()

    def test_escala_a_cero(self, orch):
        with patch("k8s_orchestrator.subprocess.run", return_value=self._make_result(0)):
            assert orch.escalar_pod(0, 0) is True

    def test_retorna_false_si_kubectl_falla(self, orch):
        with patch("k8s_orchestrator.subprocess.run",
                   return_value=self._make_result(1, "deployment not found")):
            assert orch.escalar_pod(0, 1) is False

    def test_retorna_false_si_timeout(self, orch):
        with patch("k8s_orchestrator.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="kubectl", timeout=10)):
            assert orch.escalar_pod(0, 1) is False

    def test_retorna_false_si_excepcion(self, orch):
        with patch("k8s_orchestrator.subprocess.run",
                   side_effect=OSError("kubectl not found")):
            assert orch.escalar_pod(0, 1) is False

    def test_nombre_deployment_correcto(self, orch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            r = MagicMock()
            r.returncode = 0
            return r

        with patch("k8s_orchestrator.subprocess.run", side_effect=fake_run):
            orch.escalar_pod(2, 1)

        assert "suma-digito-2" in captured["cmd"]
        assert "--replicas=1" in captured["cmd"]
        assert "-n" in captured["cmd"]
        assert "calculadora-suma" in captured["cmd"]


# ─────────────────────────────────────────────────────────────────────────────
# esperar_pod_ready
# ─────────────────────────────────────────────────────────────────────────────

class TestEsperarPodReady:
    def _make_result(self, returncode=0):
        r = MagicMock()
        r.returncode = returncode
        r.stderr = ""
        return r

    def test_pod_listo(self, orch):
        with patch("k8s_orchestrator.subprocess.run", return_value=self._make_result(0)):
            assert orch.esperar_pod_ready(0, timeout=60) is True

    def test_pod_no_listo(self, orch):
        with patch("k8s_orchestrator.subprocess.run", return_value=self._make_result(1)):
            assert orch.esperar_pod_ready(0, timeout=60) is False

    def test_timeout_subprocess(self, orch):
        with patch("k8s_orchestrator.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="kubectl", timeout=60)):
            assert orch.esperar_pod_ready(0, timeout=60) is False

    def test_excepcion_genérica(self, orch):
        with patch("k8s_orchestrator.subprocess.run",
                   side_effect=RuntimeError("unexpected")):
            assert orch.esperar_pod_ready(1) is False

    def test_label_digito_en_comando(self, orch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            r = MagicMock()
            r.returncode = 0
            return r

        with patch("k8s_orchestrator.subprocess.run", side_effect=fake_run):
            orch.esperar_pod_ready(3)

        assert any("digito=3" in arg for arg in captured["cmd"])


# ─────────────────────────────────────────────────────────────────────────────
# obtener_puerto_local_disponible
# ─────────────────────────────────────────────────────────────────────────────

class TestObtenerPuertoLocalDisponible:
    def test_puerto_preferido_libre(self, orch):
        # Parcheamos socket para que el bind del puerto preferido tenga éxito
        mock_socket = MagicMock()
        mock_socket.__enter__ = lambda s: s
        mock_socket.__exit__ = MagicMock(return_value=False)
        mock_socket.bind = MagicMock()  # no lanza OSError → puerto libre

        with patch("k8s_orchestrator.socket.socket", return_value=mock_socket):
            port = orch.obtener_puerto_local_disponible(31000)
        assert port == 31000

    def test_puerto_preferido_ocupado_devuelve_alternativo(self, orch):
        call_count = {"n": 0}

        class FakeSocket:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def setsockopt(self, *a): pass
            def bind(self, addr):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise OSError("Address in use")
                # segunda vez: socket libre en puerto dinámico
            def getsockname(self):
                return ("127.0.0.1", 49999)

        with patch("k8s_orchestrator.socket.socket", return_value=FakeSocket()):
            port = orch.obtener_puerto_local_disponible(31000)
        assert port == 49999


# ─────────────────────────────────────────────────────────────────────────────
# detener_port_forward
# ─────────────────────────────────────────────────────────────────────────────

class TestDetenerPortForward:
    def test_sin_proceso_registrado_no_falla(self, orch):
        orch.detener_port_forward(0)   # no debe lanzar excepción

    def test_termina_proceso_activo(self, orch, logger):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None   # proceso vivo
        orch.port_forward_processes[0] = mock_proc
        orch.port_forward_ports[0] = 31000

        orch.detener_port_forward(0)

        mock_proc.terminate.assert_called_once()
        assert 0 not in orch.port_forward_processes
        assert 0 not in orch.port_forward_ports

    def test_limpia_proceso_ya_terminado(self, orch):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0   # ya terminó
        orch.port_forward_processes[1] = mock_proc
        orch.port_forward_ports[1] = 31001

        orch.detener_port_forward(1)

        assert 1 not in orch.port_forward_processes
        assert 1 not in orch.port_forward_ports


# ─────────────────────────────────────────────────────────────────────────────
# establecer_port_forward — modo in-cluster
# ─────────────────────────────────────────────────────────────────────────────

class TestEstablecerPortForwardInCluster:
    def test_retorna_true_sin_ejecutar_kubectl(self, orch_in_cluster):
        with patch("k8s_orchestrator.subprocess.Popen") as mock_popen:
            result = orch_in_cluster.establecer_port_forward(0)
        assert result is True
        mock_popen.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# escalar_a_cero
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalarACero:
    def test_escala_todos_los_pods(self, orch, logger):
        with patch.object(orch, "escalar_pod", return_value=True) as mock_scale:
            with patch("k8s_orchestrator.time.sleep"):
                orch.escalar_a_cero(delay_seconds=0)
        assert mock_scale.call_count == 4
        for i in range(4):
            mock_scale.assert_any_call(i, 0)

    def test_respeta_delay(self, orch):
        sleep_calls = []
        with patch.object(orch, "escalar_pod", return_value=True):
            with patch("k8s_orchestrator.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                orch.escalar_a_cero(delay_seconds=2)
        assert 2 in sleep_calls
