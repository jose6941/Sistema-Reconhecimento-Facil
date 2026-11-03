"""Testes de segurança e estabilidade da API: entradas maliciosas ou malformadas nunca causam erro 500."""

import io
import json

import pytest

from reconhecimento import create_app
from reconhecimento.visao.pipeline import AUTORIZADO, IMAGEM_INVALIDA, ResultadoReconhecimento
from tests.conftest import PipelineFalso, jpeg_sintetico, resultado_com_rosto


def enviar(client, dados: bytes, nome="foto.jpg", campo="imagem"):
    return client.post("/reconhecer", data={campo: (io.BytesIO(dados), nome)}, content_type="multipart/form-data")


# ----------------------------------------------------------------- parâmetros
@pytest.mark.parametrize("valor", ["abc", "-1", "0", "501", "1e3", "9999999999999999999", "1.5", "%00", "' OR 1=1"])
def test_limite_invalido_retorna_400(client, valor):
    for rota in ("/api/logs", "/api/logs/recentes", "/api/logs/excecoes"):
        r = client.get(rota, query_string={"limite": valor})
        assert r.status_code == 400, (rota, valor)
        assert "erro" in r.json


@pytest.mark.parametrize("valor", ["abc", "-1", "1000001", "1.5"])
def test_offset_invalido_retorna_400(client, valor):
    assert client.get("/api/logs", query_string={"offset": valor}).status_code == 400


@pytest.mark.parametrize("valor", ["2026-13-45", "ontem", "2026-02-30", "'; DROP TABLE logs_acesso;--", "2026/01/01", "20260101"])
@pytest.mark.parametrize("campo", ["data_inicio", "data_fim"])
def test_data_invalida_retorna_400(client, campo, valor):
    assert client.get("/api/logs", query_string={campo: valor}).status_code == 400


def test_status_de_filtro_desconhecido_retorna_400(client):
    assert client.get("/api/logs", query_string={"status": "admin"}).status_code == 400
    assert client.get("/api/logs", query_string={"status": "authorized' OR '1'='1"}).status_code == 400


def test_texto_de_filtro_muito_longo(client):
    assert client.get("/api/logs", query_string={"usuario": "a" * 101}).status_code == 400


@pytest.mark.parametrize("malicioso", ["'; DROP TABLE logs_acesso; --", "%", "_", "\\", "<script>alert(1)</script>"])
def test_filtro_de_usuario_malicioso_e_inofensivo(client, banco, malicioso):
    banco.registrar_log(None, "Ana", "authorized", 0.9)
    r = client.get("/api/logs", query_string={"usuario": malicioso})
    assert r.status_code == 200
    assert r.json == []
    assert len(client.get("/api/logs").json) == 1


def test_limites_validos_nas_bordas(client):
    assert client.get("/api/logs", query_string={"limite": "1"}).status_code == 200
    assert client.get("/api/logs", query_string={"limite": "500"}).status_code == 200


# ------------------------------------------------------------------- upload
def test_upload_sem_campo(client):
    r = client.post("/reconhecer", data={"outro": (io.BytesIO(b"x"), "x.jpg")}, content_type="multipart/form-data")
    assert r.status_code == 400 and r.json["status"] == "error"


def test_upload_sem_multipart(client):
    assert client.post("/reconhecer", data="texto").status_code == 400
    assert client.post("/reconhecer", json={"imagem": "x"}).status_code == 400


def test_upload_vazio(client):
    assert enviar(client, b"").status_code == 400


def test_upload_corrompido_nao_gera_log_nem_erro_500(client, ctx, pipeline_falso):
    pipeline_falso.resultado = ResultadoReconhecimento(IMAGEM_INVALIDA)
    for lixo in (b"nao e imagem", bytes(range(256)) * 20, b"\xff\xd8\xff\xd9"):
        r = enviar(client, lixo)
        assert r.status_code == 400
    assert ctx.banco.consultar_logs() == []


def test_upload_acima_do_limite_retorna_413(client, ctx):
    r = enviar(client, b"\x00" * (ctx.settings.max_upload_bytes + 1024))
    assert r.status_code == 413
    assert r.is_json and "erro" in r.json


def test_upload_valido(client, ctx, pipeline_falso):
    ctx.banco.salvar_usuarios({0: "Ana"})
    pipeline_falso.resultado = resultado_com_rosto(AUTORIZADO)
    r = enviar(client, jpeg_sintetico())
    assert r.status_code == 200
    assert r.json["status"] == "authorized" and r.json["user"] == "Ana" and r.json["log_id"]
    assert "imagem_bgr" not in r.json  # nada de matrizes do OpenCV na resposta


# --------------------------------------------------------------- status/usuários
@pytest.mark.parametrize("corpo", [None, {}, {"status": "admin"}, {"status": ""}, {"status": None}, {"status": 1}, [], "revogado"])
def test_patch_status_invalido(client, ctx, corpo):
    ctx.banco.salvar_usuarios({0: "Ana"})
    r = client.patch("/api/usuarios/0/status", json=corpo)
    assert r.status_code == 400
    assert ctx.banco.obter_status_usuario(0) == "ativo"


def test_patch_status_sem_json(client):
    assert client.patch("/api/usuarios/0/status", data="status=revogado").status_code == 400


def test_patch_status_usuario_inexistente(client):
    assert client.patch("/api/usuarios/999/status", json={"status": "revogado"}).status_code == 404


@pytest.mark.parametrize("caminho", ["/api/usuarios/abc/status", "/api/usuarios/-1/status", "/api/usuarios/1.5/status"])
def test_id_de_usuario_invalido(client, caminho):
    assert client.patch(caminho, json={"status": "ativo"}).status_code == 404


def test_patch_status_valido(client, ctx):
    ctx.banco.salvar_usuarios({0: "Ana"})
    assert client.patch("/api/usuarios/0/status", json={"status": "revogado"}).status_code == 200
    assert ctx.banco.obter_status_usuario(0) == "revogado"


# ---------------------------------------------------------------- vincular captura
def criar_captura(ctx, settings, caminho="/static/desconhecidos/c.jpg", escrever=True):
    ctx.banco.salvar_usuarios({0: "Fulano"})  # o vínculo grava usuario_id=0 (ver teste xfail abaixo)
    if escrever:
        arquivo = settings.base_dir / caminho.lstrip("/")
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(jpeg_sintetico())
    return ctx.banco.salvar_captura_desconhecida(caminho)


@pytest.mark.parametrize("captura_id", ["abc", None, True, -1, 0, 1.5, [], {}, "1; DROP TABLE x"])
def test_vincular_captura_id_invalido(client, captura_id):
    r = client.post("/api/vincular-captura", json={"captura_id": captura_id, "nome_pessoa": "Ana"})
    assert r.status_code == 400


@pytest.mark.parametrize("nome", [None, "", "   ", 123, [], "a" * 101])
def test_vincular_captura_nome_invalido(client, ctx, settings, nome):
    cid = criar_captura(ctx, settings)
    assert client.post("/api/vincular-captura", json={"captura_id": cid, "nome_pessoa": nome}).status_code == 400


@pytest.mark.parametrize("corpo", [None, [], "x"])
def test_vincular_captura_corpo_invalido(client, corpo):
    assert client.post("/api/vincular-captura", json=corpo).status_code == 400


def test_vincular_captura_inexistente(client):
    assert client.post("/api/vincular-captura", json={"captura_id": 999, "nome_pessoa": "Ana"}).status_code == 404


@pytest.mark.parametrize("nome", ["../../etc", "..\\..\\x", "/abs/olute", "a/../../b", "C:\\Windows"])
def test_vincular_captura_nao_escapa_do_dataset(client, ctx, settings, monkeypatch, nome):
    monkeypatch.setattr(ctx.treino, "iniciar_async", lambda: True)
    cid = criar_captura(ctx, settings)

    r = client.post("/api/vincular-captura", json={"captura_id": cid, "nome_pessoa": nome})

    assert r.status_code == 200
    copiados = list(settings.base_dir.rglob("vinculado_*"))
    assert len(copiados) == 1
    assert copiados[0].resolve().is_relative_to(settings.dataset_dir.resolve())


@pytest.mark.parametrize("caminho", ["/static/../segredo.jpg", "/static/../../segredo.jpg", "/etc/passwd", "/dataset/x.jpg", "../segredo.jpg"])
def test_vincular_captura_com_caminho_fora_de_static(client, ctx, settings, monkeypatch, caminho):
    monkeypatch.setattr(ctx.treino, "iniciar_async", lambda: True)
    (settings.base_dir / "segredo.jpg").write_bytes(b"segredo")
    (settings.base_dir.parent / "segredo.jpg").write_bytes(b"segredo")
    cid = criar_captura(ctx, settings, caminho=caminho, escrever=False)

    r = client.post("/api/vincular-captura", json={"captura_id": cid, "nome_pessoa": "Ana"})

    assert r.status_code == 400
    assert not list(settings.base_dir.rglob("vinculado_*"))
    assert ctx.banco.listar_capturas_desconhecidas()[0]["resolvida"] == 0


@pytest.mark.xfail(
    strict=True,
    reason="Bug conhecido (resumo.md 6.1): o vínculo grava usuario_id=0; sem o usuário 0 a chave estrangeira falha (500).",
)
def test_vincular_captura_sem_usuario_zero(client, ctx, settings, monkeypatch):
    monkeypatch.setattr(ctx.treino, "iniciar_async", lambda: True)
    arquivo = settings.static_dir / "desconhecidos" / "c.jpg"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(jpeg_sintetico())
    cid = ctx.banco.salvar_captura_desconhecida("/static/desconhecidos/c.jpg")
    assert client.post("/api/vincular-captura", json={"captura_id": cid, "nome_pessoa": "Ana"}).status_code == 200


def test_vincular_captura_valida(client, ctx, settings, monkeypatch):
    chamadas = []
    monkeypatch.setattr(ctx.treino, "iniciar_async", lambda: chamadas.append(1) or True)
    cid = criar_captura(ctx, settings)

    r = client.post("/api/vincular-captura", json={"captura_id": str(cid), "nome_pessoa": "Maria José"})

    assert r.status_code == 200 and chamadas == [1]
    assert len(list((settings.dataset_dir / "maria_josé").glob("vinculado_*.jpg"))) == 1
    assert ctx.banco.listar_capturas_desconhecidas() == []


# ---------------------------------------------------------------------- câmera
URLS_PROIBIDAS = [
    "file:///etc/passwd",
    "javascript:alert(1)",
    "ftp://servidor/stream",
    "gopher://x",
    "http://",
    "http://:80",
    "http://usuario:senha@192.168.0.55",
    "http://169.254.169.254/latest/meta-data",
    "http://0.0.0.0",
    "http://[fe80::1]/",
    "http://host:99999/stream",
    "http://host:abc",
    "",
    "   ",
    "a" * 400,
]


@pytest.mark.parametrize("url", URLS_PROIBIDAS)
def test_conectar_camera_recusa_urls_perigosas(client, ctx, monkeypatch, url):
    chamadas = []
    monkeypatch.setattr(ctx.worker, "conectar", lambda u: chamadas.append(u))
    r = client.post("/api/camera/conectar", json={"url": url})
    assert r.status_code == 400
    assert chamadas == []


@pytest.mark.parametrize("corpo", [None, {}, {"url": None}, {"url": 123}, {"url": ["http://x"]}, [], "http://x"])
def test_conectar_camera_corpo_invalido(client, corpo):
    assert client.post("/api/camera/conectar", json=corpo).status_code == 400


@pytest.mark.parametrize("url", ["192.168.0.55", "http://192.168.0.55", "https://esp32cam.local:81/stream", "http://localhost:8080"])
def test_conectar_camera_aceita_enderecos_validos(client, ctx, monkeypatch, url):
    chamadas = []
    monkeypatch.setattr(ctx.worker, "conectar", lambda u: chamadas.append(u))
    assert client.post("/api/camera/conectar", json={"url": url}).status_code == 200
    assert len(chamadas) == 1


# ------------------------------------------------------------------------ simular
def test_simular_leitura_valida_entrada(client):
    assert client.post("/api/simular-leitura", json={"tipo": "root"}).status_code == 400
    assert client.post("/api/simular-leitura", json={"tipo": ["autorizado"]}).status_code == 400
    assert client.post("/api/simular-leitura", json={"tipo": "negado", "nome": "a" * 101}).status_code == 400
    assert client.post("/api/simular-leitura", json={"tipo": "negado", "nome": 5}).status_code == 400


def test_nomes_com_html_voltam_como_texto_json(client, ctx):
    xss = "<script>alert(1)</script>"
    ctx.banco.salvar_usuarios({1: xss, 2: "Outro"})

    r = client.post("/api/simular-leitura", json={"tipo": "autorizado", "nome": xss})

    assert r.status_code == 200
    logs = client.get("/api/logs")
    assert logs.mimetype == "application/json"
    assert logs.json[0]["usuario_nome"] == xss  # armazenado e devolvido como texto puro


# ------------------------------------------------------------------ erros gerais
def test_rotas_inexistentes_e_metodos_errados_retornam_json(client):
    r = client.get("/api/nao-existe")
    assert r.status_code == 404 and r.is_json
    r = client.delete("/api/logs")
    assert r.status_code == 405 and r.is_json


def test_erro_interno_nao_vaza_detalhes(client, ctx, monkeypatch):
    def quebrar():
        raise RuntimeError("senha-do-banco=123 /home/usuario/segredo")

    monkeypatch.setattr(ctx.banco, "listar_usuarios", quebrar)

    r = client.get("/api/usuarios")

    assert r.status_code == 500
    assert "senha" not in r.get_data(as_text=True) and "/home" not in r.get_data(as_text=True)


def test_nao_serve_arquivos_fora_de_static(client, settings):
    (settings.base_dir / "acessos.db").write_bytes(b"SQLite format 3\x00 segredo")
    (settings.base_dir / "labels.json").write_text('{"0": "segredo"}')
    for caminho in (
        "/static/../acessos.db",
        "/static/%2e%2e/acessos.db",
        "/static/..%2facessos.db",
        "/static/../labels.json",
        "/acessos.db",
        "/labels.json",
        "/modelo_lbph.yml",
    ):
        r = client.get(caminho)
        assert r.status_code in (400, 404), caminho
        assert b"segredo" not in r.data and b"SQLite" not in r.data


# ----------------------------------------------------------------------- CORS
def test_cors_so_libera_origens_configuradas(settings, banco):
    from dataclasses import replace

    restrito = replace(settings, cors_origins=("http://painel.exemplo.com",))
    client = create_app(restrito, pipeline=PipelineFalso(), banco=banco).test_client()

    permitido = client.get("/saude", headers={"Origin": "http://painel.exemplo.com"})
    negado = client.get("/saude", headers={"Origin": "http://malicioso.com"})

    assert permitido.headers.get("Access-Control-Allow-Origin") == "http://painel.exemplo.com"
    assert negado.headers.get("Access-Control-Allow-Origin") is None


def test_cors_padrao_libera_todas(client):
    r = client.get("/saude", headers={"Origin": "http://qualquer.com"})
    assert r.headers.get("Access-Control-Allow-Origin") in ("*", "http://qualquer.com")


def test_respostas_de_erro_sao_json_valido(client):
    r = client.get("/api/logs", query_string={"limite": "x"})
    assert json.loads(r.get_data(as_text=True))["erro"]
