"""Regras de negócio de um acesso: reconhecer, aplicar revogação, salvar fotos, registrar e notificar.

Este é o único caminho de registro de acessos. É usado tanto pela rota `/reconhecer` (ESP32 enviando
imagens) quanto pelo worker de stream, e também pela simulação de leitura.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime

import cv2
import numpy as np

from reconhecimento.banco_dados import BancoDados
from reconhecimento.config import Settings
from reconhecimento.servicos.estado import EstadoReconhecimento
from reconhecimento.servicos.eventos import BrokerEventos
from reconhecimento.visao.pipeline import (
    AUTORIZADO,
    IMAGEM_INVALIDA,
    NEGADO,
    REVOGADO,
    SEM_ROSTO,
    FaceRecognitionPipeline,
    ResultadoReconhecimento,
)

logger = logging.getLogger(__name__)

COR_AUTORIZADO = (0, 200, 0)
COR_ALERTA = (0, 0, 255)


class Debounce:
    """Impede registros repetidos da mesma chave dentro de um intervalo."""

    def __init__(self, segundos: float, relogio: Callable[[], float] = time.time):
        self._segundos = segundos
        self._relogio = relogio
        self._ultimo: dict[str, float] = {}
        self._lock = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = self._relogio()
        with self._lock:
            if agora - self._ultimo.get(chave, 0.0) >= self._segundos:
                self._ultimo[chave] = agora
                return True
            return False


class AcessoService:
    def __init__(
        self,
        settings: Settings,
        pipeline: FaceRecognitionPipeline,
        banco: BancoDados,
        broker: BrokerEventos,
        estado: EstadoReconhecimento,
    ):
        self._settings = settings
        self._pipeline = pipeline
        self._banco = banco
        self._broker = broker
        self._estado = estado

    # ------------------------------------------------------------- principal
    def processar_imagem(
        self,
        imagem: bytes,
        *,
        debounce: Debounce | None = None,
        registrar_sem_rosto: bool = True,
    ) -> ResultadoReconhecimento | None:
        """Processa uma imagem e registra o acesso.

        Retorna None quando o registro foi suprimido pelo `debounce`. Imagens inválidas retornam
        o resultado (status `invalid_image`) sem gerar log nem evento.
        """
        r = self._pipeline.processar_imagem(imagem)

        if r.status == IMAGEM_INVALIDA:
            return r

        if r.status == AUTORIZADO and self._banco.obter_status_usuario(r.user_id) == "revogado":
            r.status = REVOGADO
            r.mensagem = "Acesso negado: Usuário com permissão revogada!"

        self._salvar_ultimo_frame(r)

        if r.status == SEM_ROSTO and not registrar_sem_rosto:
            return r

        if debounce is not None and not debounce.permitir(r.user or f"status_{r.status}"):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if r.status == NEGADO:
            self._guardar_desconhecido(r, timestamp)
        elif r.status in (AUTORIZADO, REVOGADO):
            r.foto_path = self._guardar_recorte(r, self._settings.acessos_dir, f"acesso_{timestamp}.jpg", "acessos")

        self._registrar_e_publicar(r)
        logger.info("Reconhecimento concluído: %s -> %s", r.user, r.status)
        return r

    def simular_leitura(self, tipo: str, nome: str) -> dict:
        """Gera um acesso fictício (para demonstração). Mantém os IDs fixos históricos da simulação."""
        if tipo == "autorizado":
            r = ResultadoReconhecimento(AUTORIZADO, user=nome, user_id=1, confidence=0.96, distance_lbph=38.4)
        elif tipo == "revogado":
            r = ResultadoReconhecimento(
                REVOGADO,
                user=nome if nome != "Marina Costa" else "Sérgio Baptista",
                user_id=2,
                confidence=0.94,
                distance_lbph=42.1,
            )
        else:  # negado / desconhecido
            captura_id = self._banco.salvar_captura_desconhecida("/static/desconhecidos/simulacao.jpg")
            r = ResultadoReconhecimento(NEGADO, user=f"Desconhecido #{captura_id}", distance_lbph=88.7)
        self._registrar_e_publicar(r)
        return self._estado.obter()

    # --------------------------------------------------------------- internos
    def _registrar_e_publicar(self, r: ResultadoReconhecimento) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        r.data_hora = agora
        r.log_id = self._banco.registrar_log(
            usuario_id=r.user_id,
            usuario_nome=r.user,
            status=r.status,
            confianca=r.confidence,
            distancia_lbph=r.distance_lbph,
            foto_path=r.foto_path,
        )
        self._estado.atualizar(
            status=r.status,
            user=r.user,
            user_id=r.user_id,
            confidence=r.confidence,
            distance_lbph=r.distance_lbph,
            data_hora=agora,
            foto_url=r.foto_path,
        )
        self._broker.publicar(
            {
                "tipo": "novo_acesso",
                "dados": {
                    "id": r.log_id,
                    "data_hora": agora,
                    "usuario_nome": r.user,
                    "status": r.status,
                    "confianca": r.confidence,
                    "distancia_lbph": r.distance_lbph,
                    "foto_path": r.foto_path,
                },
            }
        )

    def _guardar_desconhecido(self, r: ResultadoReconhecimento, timestamp: str) -> None:
        caminho = self._guardar_recorte(r, self._settings.desconhecidos_dir, f"desconhecido_{timestamp}.jpg", "desconhecidos")
        r.foto_path = caminho
        if caminho:
            r.captura_id = self._banco.salvar_captura_desconhecida(caminho)
            r.user = f"Desconhecido #{r.captura_id}"
        else:
            r.user = "Desconhecido"

    @staticmethod
    def _guardar_recorte(r: ResultadoReconhecimento, pasta, nome_arquivo: str, subpasta_url: str) -> str | None:
        recorte = r.recorte_face
        if recorte is None or recorte.size == 0:
            return None
        cv2.imwrite(str(pasta / nome_arquivo), recorte)
        return f"/static/{subpasta_url}/{nome_arquivo}"

    def _salvar_ultimo_frame(self, r: ResultadoReconhecimento) -> None:
        """Salva o último quadro (com caixa e rótulo, se houver rosto) para a aba Ao vivo."""
        if r.imagem_bgr is None:
            return
        quadro: np.ndarray = r.imagem_bgr.copy()
        if r.caixa is not None:
            x, y, w, h = r.caixa
            cor = COR_AUTORIZADO if r.status == AUTORIZADO else COR_ALERTA
            cv2.rectangle(quadro, (x, y), (x + w, y + h), cor, 2)
            rotulo = f"{r.user or 'Desconhecido'} ({r.confidence * 100:.0f}%)"
            cv2.putText(quadro, rotulo, (x, max(25, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
        cv2.imwrite(str(self._settings.static_dir / "ultimo_frame.jpg"), quadro)
