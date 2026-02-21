"""
Fixtures compartidos para el conjunto de tests de SumaBasicaDocker.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Guardar la clase REAL antes de parchear, para que test_orchestrator.py
# pueda crear instancias reales sin depender del mock.
# ---------------------------------------------------------------------------
import k8s_orchestrator as _orch_module  # noqa: E402  (antes del parche)
_RealK8sOrchestrator = _orch_module.K8sOrchestrator

# ---------------------------------------------------------------------------
# Parchear K8sOrchestrator ANTES de importar proxy para evitar que intente
# conectarse a un clúster real durante los tests.
# ---------------------------------------------------------------------------
mock_orchestrator_instance = MagicMock()
mock_orchestrator_instance.escalar_pod.return_value = True
mock_orchestrator_instance.esperar_pod_ready.return_value = True
mock_orchestrator_instance.esperar_endpoints_servicio.return_value = True
mock_orchestrator_instance.establecer_port_forward.return_value = True
mock_orchestrator_instance.service_url.return_value = ("http://localhost:31000", 31000)
mock_orchestrator_instance.escalar_a_cero.return_value = None

_orch_patcher = patch("k8s_orchestrator.K8sOrchestrator", return_value=mock_orchestrator_instance)
_orch_patcher.start()

# Importar proxy DESPUÉS del parche
import proxy as proxy_module  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Flask app configurada para tests (sin reloader, sin debug)."""
    proxy_module.app.config["TESTING"] = True
    proxy_module.AUTO_SCALE_DOWN = False   # evitar threads de background en tests
    yield proxy_module.app


@pytest.fixture()
def client(app):
    """Flask test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture()
def mock_orch():
    """Devuelve el mock del orquestador para configurarlo en tests específicos."""
    mock_orchestrator_instance.reset_mock()
    mock_orchestrator_instance.escalar_pod.return_value = True
    mock_orchestrator_instance.esperar_pod_ready.return_value = True
    mock_orchestrator_instance.esperar_endpoints_servicio.return_value = True
    mock_orchestrator_instance.establecer_port_forward.return_value = True
    # Limpiar side_effect para que return_value sea efectivo en todos los tests
    mock_orchestrator_instance.service_url.side_effect = None
    mock_orchestrator_instance.service_url.return_value = ("http://localhost:31000", 31000)
    return mock_orchestrator_instance


@pytest.fixture()
def RealOrchClass():
    """Devuelve la clase K8sOrchestrator real (sin parchear) para tests de orquestador."""
    return _RealK8sOrchestrator
