import sqlite3

import pytest

from reconhecimento.banco_dados import BancoDados


def inserir_log(banco, data_hora, nome="Ana", status="authorized"):
    with banco._conexao() as con:
        con.execute(
            "INSERT INTO logs_acesso (data_hora, usuario_nome, status, confianca) VALUES (?, ?, ?, 0.5)",
            (data_hora, nome, status),
        )


def test_inicializar_e_idempotente(banco):
    banco.inicializar()
    banco.inicializar()
    assert banco.listar_usuarios() == []


def test_migra_esquema_antigo(tmp_path):
    caminho = tmp_path / "antigo.db"
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, data_cadastro TEXT NOT NULL)")
    con.execute("CREATE TABLE logs_acesso (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, usuario TEXT, status TEXT)")
    con.execute("INSERT INTO logs_acesso (data_hora, usuario, status) VALUES ('2026-01-01T10:00:00', 'Velho', 'authorized')")
    con.commit()
    con.close()

    banco = BancoDados(caminho)
    banco.inicializar()

    log = banco.consultar_logs()[0]
    assert log["usuario_nome"] == "Velho"
    assert "distancia_lbph" in log and "foto_path" in log
    banco.salvar_usuarios({0: "Ana"})
    assert banco.listar_usuarios()[0]["status"] == "ativo"


def test_salvar_usuarios_preserva_status(banco):
    banco.salvar_usuarios({0: "Ana", 1: "Bia"})
    assert banco.atualizar_status_usuario(1, "revogado") is True
    banco.salvar_usuarios({0: "Ana Maria", 1: "Bia"})
    por_id = {u["id"]: u for u in banco.listar_usuarios()}
    assert por_id[0]["nome"] == "Ana Maria"
    assert por_id[1]["status"] == "revogado"


def test_status_usuario(banco):
    banco.salvar_usuarios({0: "Ana"})
    assert banco.obter_status_usuario(0) == "ativo"
    assert banco.obter_status_usuario(None) == "desconhecido"
    assert banco.obter_status_usuario(999) == "ativo"
    banco.atualizar_status_usuario(0, "revogado")
    assert banco.obter_status_usuario(0) == "revogado"


def test_atualizar_status_invalido_e_inexistente(banco):
    with pytest.raises(ValueError):
        banco.atualizar_status_usuario(0, "admin")
    assert banco.atualizar_status_usuario(123, "ativo") is False


def test_filtros_combinados(banco):
    banco.salvar_usuarios({0: "Ana"})
    banco.registrar_log(0, "Ana", "authorized", 0.9)
    banco.registrar_log(None, "Desconhecido #1", "denied", 0.0)
    banco.registrar_log(0, "Ana", "revoked", 0.8)

    assert len(banco.consultar_logs()) == 3
    assert [x["status"] for x in banco.consultar_logs(status="denied")] == ["denied"]
    assert len(banco.consultar_logs(usuario_nome="ana")) == 2
    assert {x["status"] for x in banco.consultar_logs(apenas_excecoes=True)} == {"denied", "revoked"}
    assert [x["status"] for x in banco.consultar_logs(usuario_nome="Ana", apenas_excecoes=True)] == ["revoked"]
    assert len(banco.listar_excecoes()) == 2


def test_filtro_por_data_inclui_o_dia_final(banco):
    inserir_log(banco, "2026-03-01T08:00:00")
    inserir_log(banco, "2026-03-02T23:59:00")
    inserir_log(banco, "2026-03-03T00:00:01")

    assert len(banco.consultar_logs(data_inicio="2026-03-02")) == 2
    assert len(banco.consultar_logs(data_fim="2026-03-02")) == 2
    assert len(banco.consultar_logs(data_inicio="2026-03-02", data_fim="2026-03-02")) == 1


def test_paginacao_e_ordenacao_estavel(banco):
    for i in range(5):
        inserir_log(banco, "2026-03-01T08:00:00", nome=f"P{i}")  # mesma data: desempate por id

    pagina1 = banco.consultar_logs(limite=2, offset=0)
    pagina2 = banco.consultar_logs(limite=2, offset=2)
    pagina3 = banco.consultar_logs(limite=2, offset=4)

    nomes = [x["usuario_nome"] for x in pagina1 + pagina2 + pagina3]
    assert nomes == ["P4", "P3", "P2", "P1", "P0"]
    assert banco.consultar_logs(limite=2, offset=10) == []


@pytest.mark.parametrize(
    "malicioso",
    ["'; DROP TABLE logs_acesso; --", "' OR '1'='1", '" OR 1=1 --', "Ana'); DELETE FROM usuarios;--"],
)
def test_sql_injection_nos_filtros(banco, malicioso):
    banco.registrar_log(None, "Ana", "authorized", 0.9)

    assert banco.consultar_logs(usuario_nome=malicioso) == []
    assert banco.consultar_logs(status=malicioso) == []
    assert len(banco.consultar_logs()) == 1  # tabela intacta


def test_like_trata_curingas_como_texto(banco):
    banco.registrar_log(None, "Ana", "authorized", 0.9)
    banco.registrar_log(None, "100% Real", "authorized", 0.9)
    banco.registrar_log(None, "a_b", "authorized", 0.9)
    banco.registrar_log(None, "axb", "authorized", 0.9)

    assert [x["usuario_nome"] for x in banco.consultar_logs(usuario_nome="%")] == ["100% Real"]
    assert [x["usuario_nome"] for x in banco.consultar_logs(usuario_nome="a_b")] == ["a_b"]


def test_capturas_desconhecidas(banco):
    cid = banco.salvar_captura_desconhecida("/static/desconhecidos/x.jpg")
    assert banco.obter_captura_desconhecida(cid)["caminho_foto"] == "/static/desconhecidos/x.jpg"
    assert banco.obter_captura_desconhecida(999) is None
    assert len(banco.listar_capturas_desconhecidas()) == 1

    banco.salvar_usuarios({0: "Ana"})
    banco.resolver_captura_desconhecida(cid, usuario_id=0)
    assert banco.listar_capturas_desconhecidas() == []
    assert len(banco.listar_capturas_desconhecidas(apenas_pendentes=False)) == 1


def test_estatisticas(banco):
    banco.salvar_usuarios({0: "Ana", 1: "Bia"})
    banco.atualizar_status_usuario(1, "revogado")
    banco.registrar_log(0, "Ana", "authorized", 0.9)
    banco.registrar_log(None, "Desconhecido #1", "denied", 0.0)
    banco.salvar_captura_desconhecida("/static/desconhecidos/x.jpg")

    e = banco.obter_estatisticas_historico()
    assert e["entradas_hoje"] == 1
    assert e["total_tentativas_hoje"] == 2
    assert e["excecoes_hoje"] == 1
    assert (e["total_usuarios"], e["usuarios_ativos"], e["usuarios_revogados"]) == (2, 1, 1)
    assert e["capturas_pendentes"] == 1


def test_chave_estrangeira_ativa(banco):
    with pytest.raises(sqlite3.IntegrityError):
        banco.registrar_log(999, "Fantasma", "authorized", 0.9)
