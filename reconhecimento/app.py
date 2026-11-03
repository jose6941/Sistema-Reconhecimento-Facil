"""Fábrica da aplicação Flask."""

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from reconhecimento.api import camera, capturas, logs, reconhecimento, sistema, usuarios
from reconhecimento.api.validacao import ErroValidacao
from reconhecimento.banco_dados import BancoDados
from reconhecimento.config import Settings
from reconhecimento.contexto import Contexto
from reconhecimento.servicos.acesso import AcessoService
from reconhecimento.servicos.estado import EstadoReconhecimento
from reconhecimento.servicos.eventos import BrokerEventos
from reconhecimento.video.stream_worker import ESP32StreamWorker
from reconhecimento.visao.pipeline import FaceRecognitionPipeline
from reconhecimento.visao.treino import ServicoTreino

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    pipeline: FaceRecognitionPipeline | None = None,
    banco: BancoDados | None = None,
) -> Flask:
    """Monta a aplicação. `pipeline` e `banco` podem ser injetados (testes)."""
    settings = settings or Settings.from_env()
    settings.garantir_diretorios()

    banco = banco or BancoDados(settings.db_path)
    banco.inicializar()
    pipeline = pipeline or FaceRecognitionPipeline(settings)

    broker = BrokerEventos()
    estado = EstadoReconhecimento(settings.camera_id)
    acesso = AcessoService(settings, pipeline, banco, broker, estado)

    app = Flask(__name__, static_folder=str(settings.static_dir), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes
    origens = "*" if settings.cors_origins == ("*",) else list(settings.cors_origins)
    CORS(app, origins=origens)

    app.extensions["reconhecimento"] = Contexto(
        settings=settings,
        banco=banco,
        pipeline=pipeline,
        broker=broker,
        estado=estado,
        acesso=acesso,
        treino=ServicoTreino(settings, pipeline, banco, broker),
        worker=ESP32StreamWorker(acesso, settings.debounce_seconds),
    )

    for modulo in (reconhecimento, sistema, logs, usuarios, capturas, camera):
        app.register_blueprint(modulo.bp)

    _registrar_erros(app)
    return app


def _registrar_erros(app: Flask) -> None:
    @app.errorhandler(ErroValidacao)
    def _validacao(e: ErroValidacao):
        return jsonify({"erro": e.mensagem}), e.status_code

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        return jsonify({"erro": e.description}), e.code

    @app.errorhandler(Exception)
    def _inesperado(e: Exception):
        logger.exception("Erro não tratado")
        return jsonify({"erro": "Erro interno do servidor."}), 500
