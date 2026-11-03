"""Capturas de rostos desconhecidos e vínculo a uma pessoa."""

import shutil
from datetime import datetime

from flask import Blueprint, jsonify, request

from reconhecimento.api.validacao import ErroValidacao, inteiro_json, texto_json
from reconhecimento.contexto import obter_contexto
from reconhecimento.pessoas import slug_pessoa

bp = Blueprint("capturas", __name__)


@bp.get("/api/capturas-desconhecidas")
def listar():
    return jsonify(obter_contexto().banco.listar_capturas_desconhecidas(apenas_pendentes=True))


@bp.post("/api/vincular-captura")
def vincular():
    """Copia a foto da captura para o dataset da pessoa, marca como resolvida e agenda o retreino."""
    ctx = obter_contexto()
    corpo = request.get_json(silent=True)
    corpo = corpo if isinstance(corpo, dict) else {}
    captura_id = inteiro_json(corpo, "captura_id")
    nome_pessoa = texto_json(corpo, "nome_pessoa")

    captura = ctx.banco.obter_captura_desconhecida(captura_id)
    if captura is None:
        return jsonify({"erro": "Captura não encontrada."}), 404

    # A foto precisa estar dentro de static/ (defesa contra caminhos manipulados no banco)
    static = ctx.settings.static_dir.resolve()
    origem = (ctx.settings.base_dir / captura["caminho_foto"].lstrip("/")).resolve()
    if not origem.is_relative_to(static):
        raise ErroValidacao("Caminho da captura inválido.")

    destino = ctx.settings.dataset_dir / slug_pessoa(nome_pessoa)
    destino.mkdir(parents=True, exist_ok=True)
    if origem.is_file():
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(origem, destino / f"vinculado_{captura_id}_{carimbo}.jpg")

    ctx.banco.resolver_captura_desconhecida(captura_id, usuario_id=0)
    ctx.treino.iniciar_async()
    return jsonify(
        {"sucesso": True, "mensagem": f"Captura #{captura_id} vinculada a '{nome_pessoa}'. Retreinamento iniciado!"}
    )
