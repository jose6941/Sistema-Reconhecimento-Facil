"""Worker que consome o stream MJPEG do ESP32-CAM em segundo plano."""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

from reconhecimento.servicos.acesso import AcessoService, Debounce
from reconhecimento.video.mjpeg import ExtratorMJPEG

logger = logging.getLogger(__name__)

TIMEOUT_CONEXAO_S = 8
ESPERA_STATUS_INVALIDO_S = 2.0
ESPERA_ERRO_S = 1.5
JANELA_FPS_S = 2.0


def normalizar_url_stream(url: str) -> str:
    """Completa o esquema e o caminho: `192.168.0.55` -> `http://192.168.0.55/stream`."""
    base = url.strip().rstrip("/")
    if "://" not in base:
        base = "http://" + base
    if base.endswith(("/stream", "/capture")):
        return base
    return base + "/stream"


@dataclass
class _Conexao:
    url: str
    parar: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class ESP32StreamWorker:
    def __init__(self, servico: AcessoService, debounce_seconds: float):
        self._servico = servico
        self._debounce = Debounce(debounce_seconds)
        self._conexao: _Conexao | None = None
        self._lock = threading.Lock()
        self.fps = 0.0
        self.ultimo_frame_ts: str | None = None

    # ----------------------------------------------------------------- controle
    def conectar(self, url: str) -> None:
        self.desconectar()
        conexao = _Conexao(url=normalizar_url_stream(url))
        conexao.thread = threading.Thread(target=self._loop, args=(conexao,), daemon=True, name="esp32-stream")
        with self._lock:
            self._conexao = conexao
        conexao.thread.start()
        logger.info("Worker de Stream ESP32-CAM iniciado para: %s", conexao.url)

    def desconectar(self) -> None:
        with self._lock:
            conexao, self._conexao = self._conexao, None
        if conexao is not None:
            conexao.parar.set()  # cada conexão tem o próprio sinal: a antiga nunca "ressuscita"
            if conexao.thread and conexao.thread.is_alive():
                conexao.thread.join(timeout=1.5)
        self.fps = 0.0
        logger.info("Worker de Stream ESP32-CAM desconectado.")

    def obter_status(self) -> dict:
        with self._lock:
            conexao = self._conexao
        ativo = bool(conexao and conexao.thread and conexao.thread.is_alive() and not conexao.parar.is_set())
        return {
            "conectado": ativo,
            "url": conexao.url if ativo and conexao else None,
            "fps": self.fps,
            "ultimo_frame_ts": self.ultimo_frame_ts,
        }

    # --------------------------------------------------------------------- laço
    def _loop(self, conexao: _Conexao) -> None:
        falhas = 0
        while not conexao.parar.is_set():
            try:
                logger.info("Conectando ao stream do ESP32 em %s ...", conexao.url)
                resposta = requests.get(conexao.url, stream=True, timeout=TIMEOUT_CONEXAO_S)
                if resposta.status_code != 200:
                    resposta.close()
                    falhas += 1
                    conexao.parar.wait(ESPERA_STATUS_INVALIDO_S)
                    continue
                falhas = 0
                try:
                    self._consumir(resposta, conexao)
                finally:
                    resposta.close()
            except Exception as e:  # rede instável não pode matar o worker
                falhas += 1
                if falhas % 10 == 1:
                    logger.warning("Instabilidade na conexão com o stream do ESP32 (%s): %s", conexao.url, e)
                conexao.parar.wait(ESPERA_ERRO_S)

    def _consumir(self, resposta: requests.Response, conexao: _Conexao) -> None:
        extrator = ExtratorMJPEG()
        quadros = 0
        inicio_janela = time.time()

        for pedaco in resposta.iter_content(chunk_size=2048):
            if conexao.parar.is_set():
                return
            for jpeg in extrator.alimentar(pedaco):
                self._processar(jpeg)
                quadros += 1
                agora = time.time()
                if agora - inicio_janela >= JANELA_FPS_S:
                    self.fps = round(quadros / (agora - inicio_janela), 1)
                    quadros, inicio_janela = 0, agora

    def _processar(self, jpeg: bytes) -> None:
        self.ultimo_frame_ts = datetime.now().isoformat(timespec="seconds")
        try:
            self._servico.processar_imagem(jpeg, debounce=self._debounce, registrar_sem_rosto=False)
        except Exception:  # um quadro ruim não derruba o stream
            logger.exception("Erro ao processar quadro do stream.")
