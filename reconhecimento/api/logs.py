"""Consulta ao histórico de acessos."""

from flask import Blueprint, jsonify, request

from reconhecimento.api.validacao import bool_param, data_param, int_param, status_log_param, texto_param
from reconhecimento.contexto import obter_contexto

bp = Blueprint("logs", __name__, url_prefix="/api/logs")

LIMITE_MAXIMO = 500
OFFSET_MAXIMO = 1_000_000


@bp.get("")
def listar():
    """Histórico com filtros: usuario, status, data_inicio, data_fim, excecoes, limite e offset."""
    args = request.args
    logs = obter_contexto().banco.consultar_logs(
        usuario_nome=texto_param(args, "usuario"),
        status=status_log_param(args),
        data_inicio=data_param(args, "data_inicio"),
        data_fim=data_param(args, "data_fim"),
        limite=int_param(args, "limite", 100, 1, LIMITE_MAXIMO),
        offset=int_param(args, "offset", 0, 0, OFFSET_MAXIMO),
        apenas_excecoes=bool_param(args, "excecoes"),
    )
    return jsonify(logs)


@bp.get("/recentes")
def recentes():
    limite = int_param(request.args, "limite", 15, 1, LIMITE_MAXIMO)
    return jsonify(obter_contexto().banco.consultar_logs(limite=limite))


@bp.get("/excecoes")
def excecoes():
    limite = int_param(request.args, "limite", 15, 1, LIMITE_MAXIMO)
    return jsonify(obter_contexto().banco.listar_excecoes(limite=limite))
