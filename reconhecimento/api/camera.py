"""Câmera: último frame processado e conexão com o stream do ESP32-CAM."""

from flask import Blueprint, jsonify, request, send_from_directory

from reconhecimento.api.validacao import url_camera
from reconhecimento.contexto import obter_contexto

bp = Blueprint("camera", __name__, url_prefix="/api/camera")


@bp.get("/ultimo-frame")
def ultimo_frame():
    static = obter_contexto().settings.static_dir
    for nome in ("ultimo_frame.jpg", "placeholder.jpg"):
        if (static / nome).is_file():
            resposta = send_from_directory(static, nome, max_age=0)
            resposta.headers["Cache-Control"] = "no-store"
            return resposta
    return "", 204


@bp.post("/conectar")
def conectar():
    corpo = request.get_json(silent=True)
    url = url_camera(corpo.get("url") if isinstance(corpo, dict) else None)
    worker = obter_contexto().worker
    worker.conectar(url)
    return jsonify({"sucesso": True, "status": worker.obter_status()})


@bp.post("/desconectar")
def desconectar():
    worker = obter_contexto().worker
    worker.desconectar()
    return jsonify({"sucesso": True, "status": worker.obter_status()})


@bp.get("/info")
def info():
    return jsonify(obter_contexto().worker.obter_status())
