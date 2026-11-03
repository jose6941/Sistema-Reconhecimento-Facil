import cv2
import pytest

from reconhecimento.servicos.acesso import Debounce
from reconhecimento.visao.pipeline import (
    AUTORIZADO,
    ERRO,
    IMAGEM_INVALIDA,
    NEGADO,
    REVOGADO,
    SEM_ROSTO,
    ResultadoReconhecimento,
)
from tests.conftest import jpeg_sintetico, resultado_com_rosto


@pytest.fixture
def servico(ctx):
    return ctx.acesso


def fila_de_eventos(ctx):
    return ctx.broker.assinar()


def test_autorizado_registra_salva_foto_e_notifica(ctx, servico, pipeline_falso, settings, banco):
    banco.salvar_usuarios({0: "Ana"})
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO)
    fila = fila_de_eventos(ctx)

    r = servico.processar_imagem(jpeg_sintetico())

    assert r.status == AUTORIZADO and r.log_id is not None
    assert r.foto_path.startswith("/static/acessos/acesso_")
    assert (settings.acessos_dir / r.foto_path.rsplit("/", 1)[1]).is_file()
    log = banco.consultar_logs()[0]
    assert (log["usuario_nome"], log["status"], log["foto_path"]) == ("Ana", "authorized", r.foto_path)
    evento = fila.get_nowait()
    assert evento["tipo"] == "novo_acesso" and evento["dados"]["id"] == r.log_id
    assert ctx.estado.obter()["status"] == "authorized"
    assert (settings.static_dir / "ultimo_frame.jpg").is_file()


def test_usuario_revogado_e_bloqueado(servico, pipeline_falso, banco):
    banco.salvar_usuarios({0: "Ana"})
    banco.atualizar_status_usuario(0, "revogado")
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO)

    r = servico.processar_imagem(jpeg_sintetico())

    assert r.status == REVOGADO
    assert "revogada" in r.mensagem
    assert banco.consultar_logs()[0]["status"] == "revoked"


def test_desconhecido_vira_captura_pendente(servico, pipeline_falso, settings, banco):
    pipeline_falso.resultado = resultado_com_rosto(NEGADO, user=None, user_id=None)

    r = servico.processar_imagem(jpeg_sintetico())

    assert r.status == NEGADO
    assert r.captura_id == 1 and r.user == "Desconhecido #1"
    assert (settings.desconhecidos_dir / r.foto_path.rsplit("/", 1)[1]).is_file()
    assert banco.listar_capturas_desconhecidas()[0]["caminho_foto"] == r.foto_path


def test_desconhecido_sem_recorte(servico, pipeline_falso, banco):
    pipeline_falso.resultado = resultado_com_rosto(NEGADO, user=None, user_id=None, recorte_face=None)

    r = servico.processar_imagem(jpeg_sintetico())

    assert r.user == "Desconhecido" and r.foto_path is None
    assert banco.listar_capturas_desconhecidas() == []


def test_sem_rosto_registra_so_quando_pedido(servico, pipeline_falso, banco, settings):
    pipeline_falso.resultado = ResultadoReconhecimento(SEM_ROSTO, imagem_bgr=resultado_com_rosto().imagem_bgr)

    servico.processar_imagem(jpeg_sintetico(), registrar_sem_rosto=False)
    assert banco.consultar_logs() == []
    assert (settings.static_dir / "ultimo_frame.jpg").is_file()  # o feed ao vivo continua atualizando

    servico.processar_imagem(jpeg_sintetico(), registrar_sem_rosto=True)
    assert [x["status"] for x in banco.consultar_logs()] == ["no_face_detected"]


def test_imagem_invalida_nao_gera_log_nem_evento(ctx, servico, pipeline_falso, banco):
    pipeline_falso.resultado = ResultadoReconhecimento(IMAGEM_INVALIDA)
    fila = fila_de_eventos(ctx)

    r = servico.processar_imagem(b"lixo")

    assert r.status == IMAGEM_INVALIDA
    assert banco.consultar_logs() == []
    assert fila.empty()


def test_modelo_nao_treinado_registra_erro(servico, pipeline_falso, banco):
    pipeline_falso.resultado = resultado_com_rosto(ERRO, user=None, user_id=None, message="Modelo não treinado.")
    assert servico.processar_imagem(jpeg_sintetico()).status == ERRO
    assert banco.consultar_logs()[0]["status"] == "error"


def test_debounce_suprime_repeticoes_da_mesma_pessoa(servico, pipeline_falso, banco):
    banco.salvar_usuarios({0: "Ana", 1: "Bia"})
    agora = [1000.0]
    debounce = Debounce(4.0, relogio=lambda: agora[0])
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO, user="Ana", user_id=0)

    assert servico.processar_imagem(jpeg_sintetico(), debounce=debounce) is not None
    agora[0] += 3.9
    assert servico.processar_imagem(jpeg_sintetico(), debounce=debounce) is None  # dentro da janela

    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO, user="Bia", user_id=1)
    assert servico.processar_imagem(jpeg_sintetico(), debounce=debounce) is not None  # outra pessoa

    agora[0] += 0.2
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO, user="Ana", user_id=0)
    assert servico.processar_imagem(jpeg_sintetico(), debounce=debounce) is not None  # janela vencida
    assert len(banco.consultar_logs()) == 3


def test_debounce_de_desconhecidos_usa_chave_unica(servico, pipeline_falso, banco):
    debounce = Debounce(4.0, relogio=lambda: 50.0)
    pipeline_falso.resultado = resultado_com_rosto(NEGADO, user=None, user_id=None)
    servico.processar_imagem(jpeg_sintetico(), debounce=debounce)
    assert servico.processar_imagem(jpeg_sintetico(), debounce=debounce) is None
    assert len(banco.listar_capturas_desconhecidas()) == 1  # sem inundar a lista de capturas


def test_frame_ao_vivo_tem_caixa_desenhada(servico, pipeline_falso, settings, banco):
    banco.salvar_usuarios({0: "Ana"})
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO)
    servico.processar_imagem(jpeg_sintetico())
    quadro = cv2.imread(str(settings.static_dir / "ultimo_frame.jpg"))
    assert quadro.shape == (120, 160, 3)
    assert quadro[10, 30].tolist() != [90, 90, 90]  # borda verde sobre o fundo cinza


@pytest.mark.xfail(
    strict=True,
    reason="Bug conhecido (resumo.md 6.1): a simulação usa IDs fixos 1 e 2; em banco vazio viola a chave estrangeira.",
)
def test_simulacao_em_banco_vazio(servico):
    servico.simular_leitura("autorizado", "Marina Costa")


@pytest.mark.parametrize(("tipo", "status"), [("autorizado", "authorized"), ("revogado", "revoked"), ("negado", "denied")])
def test_simulacao_com_usuarios_existentes(servico, banco, tipo, status):
    banco.salvar_usuarios({1: "Marina Costa", 2: "Sérgio Baptista"})
    estado = servico.simular_leitura(tipo, "Marina Costa")
    assert estado["status"] == status
    assert banco.consultar_logs()[0]["status"] == status
