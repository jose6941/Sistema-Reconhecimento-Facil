import json

import cv2
import numpy as np
import pytest

from reconhecimento.servicos.eventos import BrokerEventos
from reconhecimento.visao.pipeline import FaceRecognitionPipeline
from reconhecimento.visao.treino import ServicoTreino


def padrao_base(semente: int) -> np.ndarray:
    """Padrões visuais bem diferentes por pessoa (o LBPH compara texturas, não ruído)."""
    y, x = np.mgrid[0:200, 0:200]
    if semente == 1:
        return (127 + 120 * np.sin(x / 3.0)).astype(np.uint8)  # listras verticais
    return (((x // 10 + y // 10) % 2) * 220 + 15).astype(np.uint8)  # xadrez


def salvar_imagens(pasta, semente, quantidade=4):
    pasta.mkdir(parents=True)
    base = padrao_base(semente)
    for i in range(quantidade):
        ruido = np.random.default_rng(semente * 100 + i).integers(-6, 6, (200, 200))
        imagem = np.clip(base.astype(int) + ruido, 0, 255).astype(np.uint8)
        cv2.imwrite(str(pasta / f"foto_{i:03d}.png"), imagem)
    return base


@pytest.fixture
def servico(settings, banco):
    settings.garantir_diretorios()
    pipeline = FaceRecognitionPipeline(settings)
    pipeline.detectar_faces = lambda cinza: [(0, 0, 200, 200)]  # considera a imagem inteira como rosto
    broker = BrokerEventos()
    return ServicoTreino(settings, pipeline, banco, broker), pipeline, broker


def test_dataset_vazio(servico):
    treino, _, _ = servico
    assert treino.executar() is False


def test_pastas_sem_rosto_valido(servico, settings):
    treino, pipeline, _ = servico
    pipeline.detectar_faces = lambda cinza: []
    salvar_imagens(settings.dataset_dir / "ana", 1)
    assert treino.executar() is False
    assert not settings.model_path.exists()


def test_arquivos_corrompidos_sao_ignorados(servico, settings):
    treino, _, _ = servico
    salvar_imagens(settings.dataset_dir / "ana", 1)
    (settings.dataset_dir / "ana" / "quebrada.jpg").write_bytes(b"nao e imagem")
    (settings.dataset_dir / "ana" / "notas.txt").write_text("ignorar")
    assert treino.executar() is True


def test_treino_completo_reconhece_quem_foi_treinado(servico, settings, banco):
    treino, pipeline, broker = servico
    salvar_imagens(settings.dataset_dir / "ana_souza", 1)
    salvar_imagens(settings.dataset_dir / "bia", 2)
    (settings.dataset_dir / "arquivo_solto.txt").write_text("nao e pessoa")
    fila = broker.assinar()

    assert treino.executar() is True

    labels = json.loads(settings.labels_path.read_text(encoding="utf-8"))
    assert labels == {"0": "Ana Souza", "1": "Bia"}
    assert settings.model_path.exists()
    assert {u["nome"] for u in banco.listar_usuarios()} == {"Ana Souza", "Bia"}
    assert pipeline.labels == {0: "Ana Souza", 1: "Bia"}

    def roi(pasta):
        imagem = cv2.imread(str(settings.dataset_dir / pasta / "foto_000.png"))  # imagem usada no treino
        return pipeline.recortar_normalizar(pipeline.pre_processar(imagem), (0, 0, 200, 200))

    rotulo_ana, dist_ana = pipeline.reconhecer(roi("ana_souza"))
    rotulo_bia, dist_bia = pipeline.reconhecer(roi("bia"))
    assert (rotulo_ana, rotulo_bia) == (0, 1)
    assert dist_ana < 65.0 and dist_bia < 65.0

    evento = fila.get_nowait()
    assert evento["tipo"] == "treinamento_concluido"
    assert evento["dados"]["total_identidades"] == 2


def test_retreino_preserva_status_revogado(servico, settings, banco):
    treino, _, _ = servico
    salvar_imagens(settings.dataset_dir / "ana", 1)
    treino.executar()
    banco.atualizar_status_usuario(0, "revogado")

    treino.executar()

    assert banco.obter_status_usuario(0) == "revogado"


def test_nao_roda_dois_treinos_ao_mesmo_tempo(servico, settings):
    treino, _, _ = servico
    salvar_imagens(settings.dataset_dir / "ana", 1)
    assert treino._em_execucao.acquire(blocking=False)
    try:
        assert treino.em_andamento
        assert treino.iniciar_async() is False
        assert treino.executar() is False
    finally:
        treino._em_execucao.release()


def test_falha_inesperada_nao_propaga(servico, settings, monkeypatch):
    treino, _, _ = servico
    salvar_imagens(settings.dataset_dir / "ana", 1)
    monkeypatch.setattr(treino, "_treinar", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert treino.executar() is False
    assert not treino.em_andamento  # o lock foi liberado
