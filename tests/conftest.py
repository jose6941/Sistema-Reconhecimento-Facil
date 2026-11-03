"""Fixtures compartilhadas: tudo roda em pastas temporárias, sem câmera e sem modelo treinado."""

from dataclasses import replace

import cv2
import numpy as np
import pytest

from reconhecimento import create_app
from reconhecimento.banco_dados import BancoDados
from reconhecimento.config import Settings
from reconhecimento.visao.pipeline import (
    AUTORIZADO,
    SEM_ROSTO,
    ResultadoReconhecimento,
)


def jpeg_sintetico(largura: int = 160, altura: int = 120, valor: int = 0) -> bytes:
    imagem = np.full((altura, largura, 3), valor, dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", imagem)
    assert ok
    return buffer.tobytes()


def resultado_com_rosto(status: str = AUTORIZADO, user: str | None = "Ana", user_id: int | None = 0, **extra):
    """Resultado de reconhecimento com imagem e recorte sintéticos."""
    base = ResultadoReconhecimento(
        status=status,
        user=user,
        user_id=user_id,
        confidence=0.7 if status == AUTORIZADO else 0.0,
        distance_lbph=30.0 if status == AUTORIZADO else 80.0,
        imagem_bgr=np.full((120, 160, 3), 90, dtype=np.uint8),
        recorte_face=np.full((50, 50, 3), 128, dtype=np.uint8),
        caixa=(10, 10, 50, 50),
    )
    return replace(base, **extra)


class PipelineFalso:
    """Substitui o pipeline real: devolve sempre o resultado configurado."""

    def __init__(self, resultado: ResultadoReconhecimento | None = None):
        self.resultado = resultado or ResultadoReconhecimento(SEM_ROSTO)
        self.labels = {0: "Ana"}
        self.chamadas = 0

    @property
    def modelo_carregado(self) -> bool:
        return bool(self.labels)

    def processar_imagem(self, imagem: bytes) -> ResultadoReconhecimento:
        self.chamadas += 1
        return replace(self.resultado)

    def carregar_modelo(self) -> None:
        pass


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings.com_base(tmp_path, max_upload_bytes=200_000)


@pytest.fixture
def banco(settings) -> BancoDados:
    bd = BancoDados(settings.db_path)
    bd.inicializar()
    return bd


@pytest.fixture
def pipeline_falso() -> PipelineFalso:
    return PipelineFalso()


@pytest.fixture
def app(settings, banco, pipeline_falso):
    return create_app(settings, pipeline=pipeline_falso, banco=banco)


@pytest.fixture
def ctx(app):
    return app.extensions["reconhecimento"]


@pytest.fixture
def client(app):
    return app.test_client()
