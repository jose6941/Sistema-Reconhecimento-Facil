"""Contêiner dos serviços da aplicação, acessível pelas rotas via `current_app`."""

from dataclasses import dataclass

from flask import current_app

from reconhecimento.banco_dados import BancoDados
from reconhecimento.config import Settings
from reconhecimento.servicos.acesso import AcessoService
from reconhecimento.servicos.estado import EstadoReconhecimento
from reconhecimento.servicos.eventos import BrokerEventos
from reconhecimento.video.stream_worker import ESP32StreamWorker
from reconhecimento.visao.pipeline import FaceRecognitionPipeline
from reconhecimento.visao.treino import ServicoTreino


@dataclass
class Contexto:
    settings: Settings
    banco: BancoDados
    pipeline: FaceRecognitionPipeline
    broker: BrokerEventos
    estado: EstadoReconhecimento
    acesso: AcessoService
    treino: ServicoTreino
    worker: ESP32StreamWorker


def obter_contexto() -> Contexto:
    return current_app.extensions["reconhecimento"]
