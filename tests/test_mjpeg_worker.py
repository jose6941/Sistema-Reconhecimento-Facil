import threading
import time

import pytest

from reconhecimento.video import stream_worker
from reconhecimento.video.mjpeg import EOI, SOI, ExtratorMJPEG
from reconhecimento.video.stream_worker import ESP32StreamWorker, normalizar_url_stream


def jpeg(conteudo: bytes = b"dados") -> bytes:
    return SOI + conteudo + EOI


def test_frame_unico():
    assert ExtratorMJPEG().alimentar(jpeg()) == [jpeg()]


def test_frame_em_varios_pedacos():
    ext = ExtratorMJPEG()
    quadro = jpeg(b"x" * 100)
    assert ext.alimentar(quadro[:10]) == []
    assert ext.alimentar(quadro[10:50]) == []
    assert ext.alimentar(quadro[50:]) == [quadro]


def test_marcador_partido_entre_pedacos():
    ext = ExtratorMJPEG()
    assert ext.alimentar(b"\xff") == []
    assert ext.alimentar(b"\xd8abc\xff") == []
    assert ext.alimentar(b"\xd9") == [jpeg(b"abc")]


def test_varios_frames_em_um_pedaco():
    assert ExtratorMJPEG().alimentar(jpeg(b"1") + jpeg(b"2") + jpeg(b"3")) == [jpeg(b"1"), jpeg(b"2"), jpeg(b"3")]


def test_lixo_antes_do_frame_e_descartado():
    assert ExtratorMJPEG().alimentar(b"--boundary\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg()) == [jpeg()]


def test_eoi_solto_antes_do_soi_nao_trava_o_stream():
    """Regressão: um EOI órfão antes do SOI impedia a extração de todos os frames seguintes."""
    assert ExtratorMJPEG().alimentar(b"lixo" + EOI + b"mais lixo" + jpeg(b"ok")) == [jpeg(b"ok")]


def test_buffer_nao_cresce_sem_limite():
    ext = ExtratorMJPEG(limite_buffer=1000, manter_ao_podar=100)
    ext.alimentar(SOI + b"a" * 5000)  # frame que nunca termina
    assert ext.tamanho_buffer <= 1000
    for _ in range(50):
        ext.alimentar(b"\x00" * 4096)  # sem nenhum marcador
    assert ext.tamanho_buffer <= 1000


def test_recupera_apos_lixo():
    ext = ExtratorMJPEG(limite_buffer=1000, manter_ao_podar=100)
    ext.alimentar(b"\x00" * 5000)
    assert ext.alimentar(jpeg(b"novo")) == [jpeg(b"novo")]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("192.168.0.55", "http://192.168.0.55/stream"),
        ("http://192.168.0.55/", "http://192.168.0.55/stream"),
        (" http://192.168.0.55/stream ", "http://192.168.0.55/stream"),
        ("http://192.168.0.55/capture", "http://192.168.0.55/capture"),
        ("https://cam.local:81", "https://cam.local:81/stream"),
    ],
)
def test_normalizar_url(entrada, esperado):
    assert normalizar_url_stream(entrada) == esperado


# ----------------------------------------------------------------------- worker
class RespostaFalsa:
    status_code = 200

    def __init__(self, pedacos):
        self._pedacos = pedacos
        self.fechada = False

    def iter_content(self, chunk_size=0):
        yield from self._pedacos
        while True:  # mantém o stream "aberto" para o worker poder ser parado
            time.sleep(0.005)
            yield b""

    def close(self):
        self.fechada = True


class ServicoFalso:
    def __init__(self):
        self.chamadas = []
        self.evento = threading.Event()

    def processar_imagem(self, imagem, **kwargs):
        self.chamadas.append((imagem, kwargs))
        self.evento.set()


@pytest.fixture
def worker_rapido(monkeypatch):
    monkeypatch.setattr(stream_worker, "ESPERA_ERRO_S", 0.01)
    monkeypatch.setattr(stream_worker, "ESPERA_STATUS_INVALIDO_S", 0.01)
    servico = ServicoFalso()
    worker = ESP32StreamWorker(servico, debounce_seconds=4.0)
    yield worker, servico
    worker.desconectar()


def test_worker_processa_quadros_do_stream(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    monkeypatch.setattr(stream_worker.requests, "get", lambda *a, **k: RespostaFalsa([jpeg(b"1") + jpeg(b"2")]))

    worker.conectar("192.168.0.55")

    assert servico.evento.wait(2)
    time.sleep(0.05)
    imagem, kwargs = servico.chamadas[0]
    assert imagem == jpeg(b"1")
    assert kwargs["registrar_sem_rosto"] is False and kwargs["debounce"] is not None
    status = worker.obter_status()
    assert status["conectado"] is True and status["url"] == "http://192.168.0.55/stream"
    assert status["ultimo_frame_ts"] is not None


def test_worker_reconecta_apos_erro_de_rede(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    tentativas = []

    def get(*args, **kwargs):
        tentativas.append(1)
        if len(tentativas) < 3:
            raise ConnectionError("rede caiu")
        return RespostaFalsa([jpeg()])

    monkeypatch.setattr(stream_worker.requests, "get", get)
    worker.conectar("http://cam")

    assert servico.evento.wait(2)
    assert len(tentativas) == 3


def test_worker_trata_status_http_invalido(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    respostas = [type("R", (), {"status_code": 503, "close": lambda self: None})(), RespostaFalsa([jpeg()])]
    monkeypatch.setattr(stream_worker.requests, "get", lambda *a, **k: respostas.pop(0))

    worker.conectar("http://cam")

    assert servico.evento.wait(2)


def test_erro_no_processamento_nao_derruba_o_worker(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    chamadas = []

    def processar(imagem, **kwargs):
        chamadas.append(imagem)
        if len(chamadas) == 1:
            raise RuntimeError("quadro ruim")
        servico.evento.set()

    servico.processar_imagem = processar
    monkeypatch.setattr(stream_worker.requests, "get", lambda *a, **k: RespostaFalsa([jpeg(b"1") + jpeg(b"2")]))

    worker.conectar("http://cam")

    assert servico.evento.wait(2)
    assert len(chamadas) >= 2


def test_desconectar_para_a_thread(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    monkeypatch.setattr(stream_worker.requests, "get", lambda *a, **k: RespostaFalsa([jpeg()]))
    worker.conectar("http://cam")
    assert servico.evento.wait(2)

    worker.desconectar()

    assert worker.obter_status()["conectado"] is False
    assert worker.obter_status()["url"] is None
    time.sleep(0.1)
    assert not [t for t in threading.enumerate() if t.name == "esp32-stream"]


def test_reconectar_nao_deixa_threads_antigas_vivas(monkeypatch, worker_rapido):
    worker, servico = worker_rapido
    monkeypatch.setattr(stream_worker.requests, "get", lambda *a, **k: RespostaFalsa([jpeg()]))

    for endereco in ("http://a", "http://b", "http://c"):
        worker.conectar(endereco)

    time.sleep(0.2)
    vivas = [t for t in threading.enumerate() if t.name == "esp32-stream"]
    assert len(vivas) == 1
    assert worker.obter_status()["url"] == "http://c/stream"
