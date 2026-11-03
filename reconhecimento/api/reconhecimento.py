"""Rotas de reconhecimento (entrada de imagens) e de saúde do serviço."""

from flask import Blueprint, jsonify, request

from reconhecimento.contexto import obter_contexto
from reconhecimento.visao.pipeline import IMAGEM_INVALIDA

bp = Blueprint("reconhecimento", __name__)


def _erro(mensagem: str, codigo: int = 400):
    return jsonify({"status": "error", "message": mensagem}), codigo


@bp.post("/reconhecer")
def reconhecer():
    """Recebe uma imagem (multipart, campo `imagem`), reconhece, registra e notifica o painel."""
    arquivo = request.files.get("imagem")
    if arquivo is None:
        return _erro("Campo 'imagem' ausente.")

    conteudo = arquivo.read()
    if not conteudo:
        return _erro("Arquivo de imagem vazio.")

    resultado = obter_contexto().acesso.processar_imagem(conteudo)
    if resultado is None or resultado.status == IMAGEM_INVALIDA:
        return _erro("Imagem inválida ou corrompida.")
    return jsonify(resultado.para_json()), 200


@bp.get("/saude")
def saude():
    return jsonify({"status": "ok", "modelo_carregado": obter_contexto().pipeline.modelo_carregado}), 200
