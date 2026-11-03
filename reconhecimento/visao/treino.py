"""Treinamento do classificador LBPH a partir de dataset/<pessoa>/*.jpg."""

import json
import logging
import threading

import cv2
import numpy as np

from reconhecimento.banco_dados import BancoDados
from reconhecimento.config import Settings
from reconhecimento.pessoas import nome_exibicao
from reconhecimento.servicos.eventos import BrokerEventos
from reconhecimento.visao.pipeline import FaceRecognitionPipeline

logger = logging.getLogger(__name__)

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png")


class ServicoTreino:
    """Treina o modelo e recarrega o pipeline. Só um treino roda por vez."""

    def __init__(
        self,
        settings: Settings,
        pipeline: FaceRecognitionPipeline,
        banco: BancoDados,
        broker: BrokerEventos,
    ):
        self._settings = settings
        self._pipeline = pipeline
        self._banco = banco
        self._broker = broker
        self._em_execucao = threading.Lock()

    @property
    def em_andamento(self) -> bool:
        return self._em_execucao.locked()

    def iniciar_async(self) -> bool:
        """Dispara o treino em segundo plano. Retorna False se já houver um em andamento."""
        if self._em_execucao.locked():
            return False
        threading.Thread(target=self.executar, daemon=True, name="treino-lbph").start()
        return True

    def executar(self) -> bool:
        """Treina de forma síncrona. Retorna True se o modelo foi gerado."""
        if not self._em_execucao.acquire(blocking=False):
            logger.warning("Treinamento já em andamento; nova solicitação ignorada.")
            return False
        try:
            return self._treinar()
        except Exception:  # um treino com falha não pode derrubar o servidor
            logger.exception("Falha inesperada durante o treinamento.")
            return False
        finally:
            self._em_execucao.release()

    def _treinar(self) -> bool:
        s = self._settings
        if not s.dataset_dir.is_dir():
            logger.error("Diretório de dataset não encontrado: %s", s.dataset_dir)
            return False

        pastas = sorted(p for p in s.dataset_dir.iterdir() if p.is_dir())
        if not pastas:
            logger.warning("Nenhuma pasta de usuário encontrada em %s", s.dataset_dir)
            return False

        faces_treino: list[np.ndarray] = []
        ids_treino: list[int] = []
        labels: dict[int, str] = {}
        resumo: list[tuple[str, int, int]] = []

        for identificador, pasta in enumerate(pastas):
            nome = nome_exibicao(pasta.name)
            labels[identificador] = nome
            arquivos = sorted(f for f in pasta.iterdir() if f.suffix.lower() in EXTENSOES_IMAGEM)
            aproveitadas = 0

            for arquivo in arquivos:
                imagem = cv2.imread(str(arquivo))
                if imagem is None:
                    continue
                cinza = self._pipeline.pre_processar(imagem)
                faces = self._pipeline.detectar_faces(cinza)
                if not faces:
                    continue
                faces_treino.append(self._pipeline.recortar_normalizar(cinza, faces[0]))
                ids_treino.append(identificador)
                aproveitadas += 1

            resumo.append((nome, len(arquivos), aproveitadas))

        if not faces_treino:
            logger.warning("Nenhuma face válida encontrada no dataset para treinamento.")
            return False

        reconhecedor = cv2.face.LBPHFaceRecognizer_create()
        reconhecedor.train(faces_treino, np.array(ids_treino))
        reconhecedor.write(str(s.model_path))
        s.labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

        self._banco.salvar_usuarios(labels)
        self._pipeline.carregar_modelo()  # sem reiniciar o servidor

        logger.info("--- Treinamento concluído com sucesso ---")
        for nome, total, aproveitadas in resumo:
            logger.info("  %-25s %3d/%3d fotos aproveitadas", nome, aproveitadas, total)

        self._broker.publicar(
            {
                "tipo": "treinamento_concluido",
                "dados": {"total_identidades": len(labels), "total_amostras": len(faces_treino)},
            }
        )
        return True
