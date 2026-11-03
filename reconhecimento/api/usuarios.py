"""Pessoas cadastradas e treinamento do modelo."""

from flask import Blueprint, jsonify, request

from reconhecimento.api.validacao import ErroValidacao
from reconhecimento.banco_dados import STATUS_VALIDOS_USUARIO
from reconhecimento.contexto import obter_contexto
from reconhecimento.pessoas import slug_pessoa
from reconhecimento.visao.treino import EXTENSOES_IMAGEM

bp = Blueprint("usuarios", __name__)


@bp.get("/api/usuarios")
def listar():
    ctx = obter_contexto()
    usuarios = ctx.banco.listar_usuarios()
    for usuario in usuarios:
        pasta = ctx.settings.dataset_dir / slug_pessoa(usuario["nome"])
        usuario["total_fotos"] = (
            sum(1 for f in pasta.iterdir() if f.suffix.lower() in EXTENSOES_IMAGEM) if pasta.is_dir() else 0
        )
    return jsonify(usuarios)


@bp.patch("/api/usuarios/<int:usuario_id>/status")
def atualizar_status(usuario_id: int):
    corpo = request.get_json(silent=True)
    novo_status = corpo.get("status") if isinstance(corpo, dict) else None
    if novo_status not in STATUS_VALIDOS_USUARIO:
        raise ErroValidacao("Status inválido. Use 'ativo' ou 'revogado'.")

    if not obter_contexto().banco.atualizar_status_usuario(usuario_id, novo_status):
        return jsonify({"erro": "Usuário não encontrado."}), 404
    return jsonify({"sucesso": True, "usuario_id": usuario_id, "novo_status": novo_status})


@bp.post("/api/treinar")
def treinar():
    """Dispara o treinamento em segundo plano (ignora se já houver um em andamento)."""
    if obter_contexto().treino.iniciar_async():
        return jsonify({"sucesso": True, "mensagem": "Treinamento do modelo LBPH iniciado."})
    return jsonify({"sucesso": True, "mensagem": "Já existe um treinamento em andamento."})
