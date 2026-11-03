import threading

from reconhecimento.servicos.estado import EstadoReconhecimento
from reconhecimento.servicos.eventos import BrokerEventos


def test_publica_para_todos_os_assinantes():
    broker = BrokerEventos()
    a, b = broker.assinar(), broker.assinar()
    assert broker.publicar({"tipo": "x"}) == 2
    assert a.get_nowait() == b.get_nowait() == {"tipo": "x"}


def test_cancelar_remove_assinante():
    broker = BrokerEventos()
    fila = broker.assinar()
    broker.cancelar(fila)
    broker.cancelar(fila)  # idempotente
    assert broker.total_assinantes == 0
    assert broker.publicar({"tipo": "x"}) == 0


def test_fila_cheia_nao_bloqueia_nem_afeta_outros():
    broker = BrokerEventos(tamanho_fila=2)
    lenta, rapida = broker.assinar(), broker.assinar()
    for i in range(5):
        broker.publicar({"n": i})
        rapida.get_nowait()  # a rápida consome tudo
    assert lenta.qsize() == 2  # excedentes descartados, sem exceção
    assert rapida.empty()


def test_publicacao_concorrente():
    broker = BrokerEventos(tamanho_fila=1000)
    fila = broker.assinar()

    def produzir():
        for i in range(100):
            broker.publicar({"n": i})

    threads = [threading.Thread(target=produzir) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert fila.qsize() == 800


def test_estado_inicial_e_atualizacao():
    estado = EstadoReconhecimento("CAM-X")
    inicial = estado.obter()
    assert inicial["status"] == "idle" and inicial["camera_id"] == "CAM-X" and inicial["data_hora"] is None

    estado.atualizar(status="authorized", user="Ana", user_id=0, confidence=0.9)
    copia = estado.obter()
    copia["status"] = "alterado"  # não deve afetar o estado interno
    assert estado.obter()["status"] == "authorized"
