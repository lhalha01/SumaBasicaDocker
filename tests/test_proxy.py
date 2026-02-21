"""
Tests unitarios e de integración para proxy.py.

Cobertura:
    - get_digitos()           : descomposición de número en dígitos
    - normalizar_digitos()    : padding de listas de dígitos
    - get_nombre_posicion()   : mapeo posición → nombre
    - POST /suma-n-digitos    : validaciones, happy-path, opciones CORS
    - GET  /terminal-stream   : cabeceras SSE
    - POST /terminal-clear    : limpia buffer
    - GET  /docs-url          : respuestas ok / pending / error
    - GET  /grafana-url       : respuestas ok / pending / error
    - GET  /                  : sirve index.html
"""
import json
import pytest
from unittest.mock import patch, MagicMock

import proxy as proxy_module
from proxy import get_digitos, normalizar_digitos, get_nombre_posicion


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES PURAS
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDigitos:
    def test_cero(self):
        assert get_digitos(0) == [0]

    def test_un_digito(self):
        assert get_digitos(7) == [7]

    def test_dos_digitos(self):
        assert get_digitos(56) == [6, 5]

    def test_cuatro_digitos(self):
        assert get_digitos(1234) == [4, 3, 2, 1]

    def test_numero_con_cero_intermedio(self):
        # 1007 → [7, 0, 0, 1]
        assert get_digitos(1007) == [7, 0, 0, 1]

    def test_maximo_soportado(self):
        assert get_digitos(9999) == [9, 9, 9, 9]

    def test_potencia_de_10(self):
        assert get_digitos(100) == [0, 0, 1]


class TestNormalizarDigitos:
    def test_misma_longitud(self):
        a, b = normalizar_digitos([1, 2], [3, 4])
        assert a == [1, 2]
        assert b == [3, 4]

    def test_a_mas_corto(self):
        a, b = normalizar_digitos([5], [3, 4])
        assert a == [5, 0]
        assert b == [3, 4]

    def test_b_mas_corto(self):
        a, b = normalizar_digitos([1, 2, 3], [9])
        assert a == [1, 2, 3]
        assert b == [9, 0, 0]

    def test_ambos_vacios(self):
        a, b = normalizar_digitos([], [])
        assert a == []
        assert b == []


class TestGetNombrePosicion:
    @pytest.mark.parametrize("pos,nombre", [
        (0, "Unidades"),
        (1, "Decenas"),
        (2, "Centenas"),
        (3, "Millares"),
    ])
    def test_posiciones_validas(self, pos, nombre):
        assert get_nombre_posicion(pos) == nombre

    def test_posicion_fuera_de_rango(self):
        assert get_nombre_posicion(5) == "Posicion-5"


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: POST /suma-n-digitos
# ─────────────────────────────────────────────────────────────────────────────

class TestSumaNDigitosValidaciones:
    def test_numero_negativo_a(self, client):
        rv = client.post("/suma-n-digitos", json={"NumberA": -1, "NumberB": 0})
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_numero_negativo_b(self, client):
        rv = client.post("/suma-n-digitos", json={"NumberA": 0, "NumberB": -5})
        assert rv.status_code == 400

    def test_numero_mayor_que_maximo(self, client):
        rv = client.post("/suma-n-digitos", json={"NumberA": 10000, "NumberB": 0})
        assert rv.status_code == 400

    def test_ambos_en_limite_superior(self, client):
        rv = client.post("/suma-n-digitos", json={"NumberA": 9999, "NumberB": 9999})
        # Puede ser 200 (si el mock funciona) o 500 (error de red), nunca 400
        assert rv.status_code != 400

    def test_options_cors(self, client):
        rv = client.options("/suma-n-digitos")
        assert rv.status_code == 200
        assert "Access-Control-Allow-Origin" in rv.headers


class TestSumaNDigitosHappyPath:
    """Tests que requieren simular la llamada HTTP al backend."""

    def _mock_backend(self, responses):
        """
        responses: lista de dicts {Result, CarryOut} a devolver en orden.
        """
        call_count = {"n": 0}

        def fake_post(url, json, headers, timeout):
            resp = MagicMock()
            resp.ok = True
            idx = min(call_count["n"], len(responses) - 1)
            resp.json.return_value = responses[idx]
            call_count["n"] += 1
            return resp

        return fake_post

    def test_suma_un_digito(self, client, mock_orch):
        mock_orch.service_url.return_value = ("http://localhost:31000", 31000)
        backend = self._mock_backend([{"Result": 9, "CarryOut": 0}])
        with patch("proxy.requests.post", side_effect=backend):
            rv = client.post("/suma-n-digitos", json={"NumberA": 4, "NumberB": 5})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["Result"] == 9
        assert data["NumDigitos"] == 1
        assert data["ContenedoresUsados"] == 1

    def test_suma_dos_digitos_sin_carry(self, client, mock_orch):
        mock_orch.service_url.side_effect = [
            ("http://localhost:31000", 31000),
            ("http://localhost:31001", 31001),
        ]
        backend = self._mock_backend([
            {"Result": 1, "CarryOut": 0},   # 3 + 8 = 11 → Result=1, carry=1  ← forzamos respuesta mock
            {"Result": 4, "CarryOut": 0},   # 1 + 3 + carry = 4
        ])
        with patch("proxy.requests.post", side_effect=backend):
            rv = client.post("/suma-n-digitos", json={"NumberA": 13, "NumberB": 38})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["NumDigitos"] == 2

    def test_suma_cuatro_digitos(self, client, mock_orch):
        mock_orch.service_url.side_effect = [
            ("http://localhost:3100{}".format(i), 31000 + i) for i in range(4)
        ]
        backend = self._mock_backend([
            {"Result": 2, "CarryOut": 1},
            {"Result": 1, "CarryOut": 1},
            {"Result": 9, "CarryOut": 0},
            {"Result": 6, "CarryOut": 0},
        ])
        with patch("proxy.requests.post", side_effect=backend):
            rv = client.post("/suma-n-digitos", json={"NumberA": 1234, "NumberB": 5678})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["Result"] == 6912
        assert data["NumDigitos"] == 4
        assert len(data["Details"]) == 4

    def test_suma_cero_mas_cero(self, client, mock_orch):
        mock_orch.service_url.return_value = ("http://localhost:31000", 31000)
        backend = self._mock_backend([{"Result": 0, "CarryOut": 0}])
        with patch("proxy.requests.post", side_effect=backend):
            rv = client.post("/suma-n-digitos", json={"NumberA": 0, "NumberB": 0})
        assert rv.status_code == 200
        assert rv.get_json()["Result"] == 0

    def test_response_contiene_details(self, client, mock_orch):
        mock_orch.service_url.return_value = ("http://localhost:31000", 31000)
        backend = self._mock_backend([{"Result": 5, "CarryOut": 0}])
        with patch("proxy.requests.post", side_effect=backend):
            rv = client.post("/suma-n-digitos", json={"NumberA": 2, "NumberB": 3})
        data = rv.get_json()
        assert "Details" in data
        assert data["Details"][0]["NombrePosicion"] == "Unidades"
        assert "EventosEscalado" in data

    def test_error_backend_devuelve_500(self, client, mock_orch):
        mock_orch.service_url.return_value = ("http://localhost:31000", 31000)
        with patch("proxy.requests.post", side_effect=Exception("Connection refused")):
            rv = client.post("/suma-n-digitos", json={"NumberA": 1, "NumberB": 2})
        assert rv.status_code == 500

    def test_fallo_escalar_pod_devuelve_500(self, client, mock_orch):
        mock_orch.escalar_pod.return_value = False
        rv = client.post("/suma-n-digitos", json={"NumberA": 1, "NumberB": 2})
        assert rv.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /terminal-stream
# ─────────────────────────────────────────────────────────────────────────────

class TestTerminalStream:
    def test_content_type_sse(self, client):
        # Abrimos la stream y comprobamos cabeceras sin consumir el cuerpo completo
        with client.get("/terminal-stream", buffered=False) as rv:
            assert rv.status_code == 200
            assert "text/event-stream" in rv.content_type
            assert rv.headers.get("Cache-Control") == "no-cache"


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: POST /terminal-clear
# ─────────────────────────────────────────────────────────────────────────────

class TestTerminalClear:
    def test_limpia_buffer(self, client):
        # Añadir algo al buffer
        proxy_module.registrar_terminal("test message")
        rv = client.post("/terminal-clear")
        assert rv.status_code == 200
        assert rv.get_json() == {"ok": True}
        with proxy_module.terminal_log_lock:
            assert len(proxy_module.terminal_log_buffer) == 0


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /docs-url
# ─────────────────────────────────────────────────────────────────────────────

class TestDocsUrl:
    def test_devuelve_ip_cuando_disponible(self, client):
        mock_result = MagicMock()
        mock_result.stdout = "10.0.0.5"
        with patch("proxy.subprocess.run", return_value=mock_result):
            rv = client.get("/docs-url")
        data = rv.get_json()
        assert data["status"] == "ok"
        assert data["url"] == "http://10.0.0.5"

    def test_devuelve_pending_cuando_sin_ip(self, client):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("proxy.subprocess.run", return_value=mock_result):
            rv = client.get("/docs-url")
        data = rv.get_json()
        assert data["status"] == "pending"
        assert data["url"] is None

    def test_devuelve_error_si_subprocess_falla(self, client):
        with patch("proxy.subprocess.run", side_effect=Exception("kubectl not found")):
            rv = client.get("/docs-url")
        data = rv.get_json()
        assert data["status"] == "error"
        assert data["url"] is None


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /grafana-url
# ─────────────────────────────────────────────────────────────────────────────

class TestGrafanaUrl:
    def test_devuelve_ip_cuando_disponible(self, client):
        mock_result = MagicMock()
        mock_result.stdout = "20.30.40.50"
        with patch("proxy.subprocess.run", return_value=mock_result):
            rv = client.get("/grafana-url")
        data = rv.get_json()
        assert data["status"] == "ok"
        assert data["url"] == "http://20.30.40.50"

    def test_devuelve_pending_cuando_sin_ip(self, client):
        mock_result = MagicMock()
        mock_result.stdout = "  "  # solo espacios
        with patch("proxy.subprocess.run", return_value=mock_result):
            rv = client.get("/grafana-url")
        data = rv.get_json()
        assert data["status"] == "pending"

    def test_devuelve_error_si_exception(self, client):
        with patch("proxy.subprocess.run", side_effect=TimeoutError()):
            rv = client.get("/grafana-url")
        assert rv.get_json()["status"] == "error"


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN: llamar_servicio_con_reintento
# ─────────────────────────────────────────────────────────────────────────────

class TestLlamarServicioConReintento:
    def test_exito_primer_intento(self):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"Result": 3, "CarryOut": 0}
        with patch("proxy.requests.post", return_value=mock_resp):
            result = proxy_module.llamar_servicio_con_reintento(
                "http://localhost:31000", {"NumberA": 1, "NumberB": 2, "CarryIn": 0}, 0, intentos=3
            )
        assert result == {"Result": 3, "CarryOut": 0}

    def test_reintenta_y_falla_lanza_excepcion(self):
        with patch("proxy.requests.post", side_effect=Exception("timeout")):
            with patch("proxy.time.sleep"):  # acelerar test
                with pytest.raises(Exception, match="Fallo comunicando"):
                    proxy_module.llamar_servicio_con_reintento(
                        "http://localhost:31000", {}, 0, intentos=2
                    )

    def test_exito_en_segundo_intento(self):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"Result": 7, "CarryOut": 0}
        call_count = {"n": 0}

        def flaky_post(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise ConnectionError("transient")
            return mock_resp

        with patch("proxy.requests.post", side_effect=flaky_post):
            with patch("proxy.time.sleep"):
                result = proxy_module.llamar_servicio_con_reintento(
                    "http://localhost:31000", {}, 0, intentos=3
                )
        assert result["Result"] == 7
        assert call_count["n"] == 2

    def test_respuesta_http_error_lanza_excepcion(self):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        with patch("proxy.requests.post", return_value=mock_resp):
            with patch("proxy.time.sleep"):
                with pytest.raises(Exception):
                    proxy_module.llamar_servicio_con_reintento(
                        "http://localhost:31000", {}, 0, intentos=1
                    )
