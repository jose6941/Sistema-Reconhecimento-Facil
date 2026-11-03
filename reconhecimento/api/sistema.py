"""Status geral, eventos em tempo real (SSE), estatísticas e simulação de leitura."""

import json
import queue
from collections.abc import Iterator

from flask import Blueprint, Response, jsonify, request

from reconhecimento.api.validacao import ErroValidacao, texto_json
from reconhecimento.contexto import obter_contexto

bp = Blueprint("sistema", __name__)

TIPOS_SIMULACAO = ("autorizado", "revogado", "negado", "desconhecido")
INTERVALO_PING_S = 25


@bp.get("/api/status")
def status():
    ctx = obter_contexto()
    return jsonify(
        {
            "status": "online",
            "modelo_carregado": ctx.pipeline.modelo_carregado,
            "total_identidades": len(ctx.pipeline.labels),
            "limiar_lbph": ctx.settings.lbph_threshold,
            "camera_id": ctx.settings.camera_id,
            "ultimo_reconhecimento": ctx.estado.obter(),
        }
    )


@bp.get("/api/eventos")
def eventos():
    """Server-Sent Events: avisa o painel a cada novo acesso e ao fim de cada treinamento."""
    ctx = obter_contexto()

    def gerador() -> Iterator[str]:
        fila = ctx.broker.assinar()  # dentro do gerador: o finally abaixo sempre cancela a inscrição
        try:
            yield f"data: {json.dumps({'tipo': 'init', 'dados': ctx.estado.obter()})}\n\n"
            while True:
                try:
                    yield f"data: {json.dumps(fila.get(timeout=INTERVALO_PING_S))}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"  # mantém a conexão HTTP ativa
        finally:
            ctx.broker.cancelar(fila)

    resposta = Response(gerador(), mimetype="text/event-stream")
    resposta.headers["Cache-Control"] = "no-cache"
    resposta.headers["X-Accel-Buffering"] = "no"
    return resposta


@bp.get("/api/estatisticas")
def estatisticas():
    return jsonify(obter_contexto().banco.obter_estatisticas_historico())


@bp.post("/api/simular-leitura")
def simular_leitura():
    """Simula uma tentativa de acesso, para demonstrar o sistema sem câmera."""
    corpo = request.get_json(silent=True)
    corpo = corpo if isinstance(corpo, dict) else {}
    tipo = corpo.get("tipo", "autorizado")
    if tipo not in TIPOS_SIMULACAO:
        raise ErroValidacao("Tipo inválido. Use: " + ", ".join(TIPOS_SIMULACAO) + ".")
    nome = texto_json(corpo, "nome", "Marina Costa")

    simulacao = obter_contexto().acesso.simular_leitura(tipo, nome)
    return jsonify({"sucesso": True, "simulacao": simulacao})
