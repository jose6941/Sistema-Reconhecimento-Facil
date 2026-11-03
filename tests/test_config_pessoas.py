import pytest

from reconhecimento.config import Settings
from reconhecimento.pessoas import nome_exibicao, slug_pessoa


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Maria José", "maria_josé"),
        ("  João  Silva ", "joão__silva"),
        ("../../etc/passwd", "etcpasswd"),
        ("..\\..\\windows", "windows"),
        ("a/b\\c.d", "abcd"),
        ("", "usuario"),
        ("   ", "usuario"),
        ("!!!", "usuario"),
    ],
)
def test_slug_pessoa_remove_caracteres_perigosos(entrada, esperado):
    assert slug_pessoa(entrada) == esperado


def test_slug_nunca_contem_separador_de_caminho():
    for texto in ("../x", "a/../b", "/abs", "C:\\x", "x\x00y"):
        resultado = slug_pessoa(texto)
        assert "/" not in resultado and "\\" not in resultado and "." not in resultado and "\x00" not in resultado


def test_nome_exibicao():
    assert nome_exibicao("maria_jose") == "Maria Jose"


def test_settings_padrao():
    s = Settings.from_env("/tmp/x", env={})
    assert s.lbph_threshold == 65.0
    assert s.debounce_seconds == 4.0
    assert s.cors_origins == ("*",)
    assert s.port == 5000
    assert s.esp32_url is None
    assert s.max_upload_bytes == 5 * 1024 * 1024


def test_settings_le_ambiente():
    env = {
        "LBPH_CONFIDENCE_THRESHOLD": "58.5",
        "DEBOUNCE_SECONDS": "2",
        "CORS_ORIGINS": "http://a.com, http://b.com ,",
        "FLASK_PORT": "8080",
        "ESP32_URL": "http://192.168.0.55",
        "CAMERA_ID": "CAM-02",
        "MAX_UPLOAD_MB": "1",
    }
    s = Settings.from_env("/tmp/x", env=env)
    assert s.lbph_threshold == 58.5
    assert s.debounce_seconds == 2.0
    assert s.cors_origins == ("http://a.com", "http://b.com")
    assert s.port == 8080
    assert s.esp32_url == "http://192.168.0.55"
    assert s.camera_id == "CAM-02"
    assert s.max_upload_bytes == 1024 * 1024


def test_settings_valores_invalidos_usam_padrao():
    s = Settings.from_env("/tmp/x", env={"LBPH_CONFIDENCE_THRESHOLD": "abc", "FLASK_PORT": "x", "MAX_UPLOAD_MB": "-5"})
    assert s.lbph_threshold == 65.0
    assert s.port == 5000
    assert s.max_upload_bytes >= 1024 * 1024


def test_settings_imutavel():
    s = Settings.com_base("/tmp/x")
    with pytest.raises(AttributeError):
        s.lbph_threshold = 1.0  # type: ignore[misc]
