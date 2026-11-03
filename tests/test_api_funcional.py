import cv2

from tests.conftest import jpeg_sintetico


def preparar_usuarios(ctx):
    ctx.banco.salvar_usuarios({1: "Marina Costa", 2: "Sérgio Baptista"})


def test_saude_e_status(client):
    assert client.get("/saude").json == {"status": "ok", "modelo_carregado": True}
    status = client.get("/api/status").json
    assert status["status"] == "online" and status["limiar_lbph"] == 65.0
    assert status["camera_id"] == "CAM-01 · Portaria"
    assert status["ultimo_reconhecimento"]["status"] == "idle"


def test_fluxo_simular_logs_estatisticas(client, ctx):
    preparar_usuarios(ctx)
    for tipo in ("autorizado", "revogado", "negado"):
        assert client.post("/api/simular-leitura", json={"tipo": tipo}).status_code == 200

    logs = client.get("/api/logs").json
    assert [x["status"] for x in logs] == ["denied", "revoked", "authorized"]
    assert client.get("/api/logs/recentes").json == logs
    assert [x["status"] for x in client.get("/api/logs/excecoes").json] == ["denied", "revoked"]

    estatisticas = client.get("/api/estatisticas").json
    assert estatisticas["entradas_hoje"] == 1 and estatisticas["excecoes_hoje"] == 2
    assert client.get("/api/status").json["ultimo_reconhecimento"]["status"] == "denied"


def test_filtros_do_historico(client, ctx):
    preparar_usuarios(ctx)
    client.post("/api/simular-leitura", json={"tipo": "autorizado", "nome": "Marina Costa"})
    client.post("/api/simular-leitura", json={"tipo": "revogado", "nome": "Sérgio Baptista"})
    client.post("/api/simular-leitura", json={"tipo": "negado"})

    def consultar(**params):
        r = client.get("/api/logs", query_string=params)
        assert r.status_code == 200
        return [x["usuario_nome"] for x in r.json]

    assert consultar(usuario="marina") == ["Marina Costa"]
    assert consultar(status="revoked") == ["Sérgio Baptista"]
    assert len(consultar(excecoes="true")) == 2
    assert consultar(excecoes="true", status="denied") == ["Desconhecido #1"]
    assert consultar(data_inicio="2999-01-01") == []
    assert len(consultar(data_inicio="2000-01-01", data_fim="2999-12-31")) == 3
    assert len(consultar(limite=2)) == 2
    assert len(consultar(limite=2, offset=2)) == 1
    assert consultar(usuario="nao-existe") == []


def test_usuarios_com_total_de_fotos(client, ctx, settings):
    ctx.banco.salvar_usuarios({0: "Ana Souza"})
    pasta = settings.dataset_dir / "ana_souza"
    pasta.mkdir(parents=True)
    for nome in ("1.jpg", "2.PNG", "3.jpeg", "notas.txt"):
        (pasta / nome).write_bytes(b"x")

    usuarios = client.get("/api/usuarios").json

    assert usuarios[0]["nome"] == "Ana Souza" and usuarios[0]["total_fotos"] == 3


def test_treinar_dispara_uma_vez(client, ctx, monkeypatch):
    estados = iter([True, False])
    monkeypatch.setattr(ctx.treino, "iniciar_async", lambda: next(estados))

    primeira = client.post("/api/treinar").json
    segunda = client.post("/api/treinar").json

    assert primeira["sucesso"] and "iniciado" in primeira["mensagem"]
    assert segunda["sucesso"] and "andamento" in segunda["mensagem"]


def test_ultimo_frame(client, settings, ctx, pipeline_falso):
    assert client.get("/api/camera/ultimo-frame").status_code == 204

    (settings.static_dir / "ultimo_frame.jpg").write_bytes(jpeg_sintetico())
    r = client.get("/api/camera/ultimo-frame")

    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    assert r.headers["Cache-Control"] == "no-store"
    assert cv2.imdecode(__import__("numpy").frombuffer(r.data, "uint8"), 1) is not None


def test_camera_info_e_desconectar(client):
    info = client.get("/api/camera/info").json
    assert info["conectado"] is False and info["url"] is None
    r = client.post("/api/camera/desconectar")
    assert r.status_code == 200 and r.json["status"]["conectado"] is False


def test_sse_entrega_init_e_novos_eventos(client, ctx):
    preparar_usuarios(ctx)
    resposta = client.get("/api/eventos")
    assert resposta.mimetype == "text/event-stream"
    fluxo = iter(resposta.response)

    primeiro = next(fluxo)
    assert b'"tipo": "init"' in primeiro and ctx.broker.total_assinantes == 1

    client.post("/api/simular-leitura", json={"tipo": "autorizado"})
    segundo = next(fluxo)
    assert b'"tipo": "novo_acesso"' in segundo and b"Marina Costa" in segundo

    resposta.close()
    assert ctx.broker.total_assinantes == 0  # sem vazamento de assinantes


def test_sse_fechado_antes_de_ler_nao_vaza_assinante(client, ctx):
    resposta = client.get("/api/eventos")
    resposta.close()
    assert ctx.broker.total_assinantes == 0
