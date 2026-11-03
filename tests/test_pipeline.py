import cv2
import numpy as np
import pytest

from reconhecimento.visao.pipeline import (
    AUTORIZADO,
    ERRO,
    IMAGEM_INVALIDA,
    NEGADO,
    SEM_ROSTO,
    FaceRecognitionPipeline,
)
from tests.conftest import jpeg_sintetico


@pytest.fixture
def pipeline(settings):
    settings.garantir_diretorios()
    return FaceRecognitionPipeline(settings)


def com_rosto_falso(pipeline, distancia, rotulo=0):
    """Simula uma detecção e uma predição (o Haar real não acha rostos em imagens sintéticas)."""
    pipeline.labels = {0: "Ana", 1: "Bia"}
    pipeline.detectar_faces = lambda cinza: [(20, 20, 100, 100)]
    pipeline.reconhecer = lambda roi: (rotulo, distancia)
    return jpeg_sintetico(200, 200, 100)


def test_bytes_invalidos(pipeline):
    for lixo in (b"", b"nao e uma imagem", b"\xff\xd8\xff\xd9", bytes(range(256)) * 10):
        assert pipeline.processar_imagem(lixo).status == IMAGEM_INVALIDA


def test_sem_rosto(pipeline):
    r = pipeline.processar_imagem(jpeg_sintetico())
    assert r.status == SEM_ROSTO
    assert r.imagem_bgr is not None


def test_modelo_nao_treinado(pipeline):
    pipeline.detectar_faces = lambda cinza: [(20, 20, 100, 100)]
    r = pipeline.processar_imagem(jpeg_sintetico(200, 200))
    assert r.status == ERRO
    assert r.message == "Modelo não treinado."


@pytest.mark.parametrize(
    ("distancia", "esperado"),
    [(0.0, AUTORIZADO), (40.0, AUTORIZADO), (65.0, AUTORIZADO), (65.01, NEGADO), (120.0, NEGADO)],
)
def test_limiar_de_autorizacao(pipeline, distancia, esperado):
    r = pipeline.processar_imagem(com_rosto_falso(pipeline, distancia))
    assert r.status == esperado
    if esperado == AUTORIZADO:
        assert r.user == "Ana" and r.user_id == 0
        assert r.confidence == round(max(0.0, 1 - distancia / 100), 2)
    else:
        assert r.user is None and r.user_id is None and r.confidence == 0.0
        assert r.recorte_face is not None


def test_rotulo_desconhecido_no_modelo(pipeline):
    r = pipeline.processar_imagem(com_rosto_falso(pipeline, 30.0, rotulo=7))
    assert r.status == AUTORIZADO
    assert r.user == "desconhecido"


def test_limiar_vem_da_configuracao(settings):
    from dataclasses import replace

    pipeline = FaceRecognitionPipeline(replace(settings, lbph_threshold=50.0))
    assert pipeline.processar_imagem(com_rosto_falso(pipeline, 55.0)).status == NEGADO


def test_maior_rosto_vence(pipeline):
    class Cascata:
        def detectMultiScale(self, *args, **kwargs):  # noqa: N802 - nome da API do OpenCV
            return np.array([[0, 0, 80, 80], [10, 10, 150, 150], [5, 5, 90, 90]])

    pipeline._cascade = Cascata()
    assert pipeline.detectar_faces(np.zeros((200, 200), np.uint8))[0] == (10, 10, 150, 150)


def test_roi_normalizada_200x200(pipeline):
    cinza = np.random.default_rng(0).integers(0, 255, (300, 300), dtype=np.uint8)
    roi = pipeline.recortar_normalizar(cinza, (50, 60, 120, 90))
    assert roi.shape == (200, 200)


def test_carregar_modelo_corrompido_nao_derruba(settings):
    settings.garantir_diretorios()
    settings.model_path.write_text("lixo")
    settings.labels_path.write_text("{nao e json")
    pipeline = FaceRecognitionPipeline(settings)
    assert pipeline.labels == {}
    assert not pipeline.modelo_carregado


def test_pre_processamento_gera_cinza():
    imagem = np.random.default_rng(1).integers(0, 255, (50, 60, 3), dtype=np.uint8)
    saida = FaceRecognitionPipeline.pre_processar(imagem)
    assert saida.shape == (50, 60) and saida.dtype == np.uint8


def test_cascata_real_carregada(pipeline):
    assert not pipeline._cascade.empty()
    assert cv2.face.LBPHFaceRecognizer_create() is not None
