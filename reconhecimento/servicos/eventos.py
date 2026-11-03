"""Broker de eventos em memória para o Server-Sent Events (SSE)."""

import queue
import threading
from typing import Any


class BrokerEventos:
    """Distribui eventos para os clientes conectados. Publicar nunca bloqueia."""

    def __init__(self, tamanho_fila: int = 30):
        self._tamanho_fila = tamanho_fila
        self._assinantes: list[queue.Queue[dict[str, Any]]] = []
        self._lock = threading.Lock()

    def assinar(self) -> "queue.Queue[dict[str, Any]]":
        fila: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=self._tamanho_fila)
        with self._lock:
            self._assinantes.append(fila)
        return fila

    def cancelar(self, fila: "queue.Queue[dict[str, Any]]") -> None:
        with self._lock:
            if fila in self._assinantes:
                self._assinantes.remove(fila)

    def publicar(self, evento: dict[str, Any]) -> int:
        """Envia o evento a todos os assinantes; descarta para quem estiver com a fila cheia."""
        with self._lock:
            assinantes = list(self._assinantes)
        entregues = 0
        for fila in assinantes:
            try:
                fila.put_nowait(evento)
                entregues += 1
            except queue.Full:
                pass
        return entregues

    @property
    def total_assinantes(self) -> int:
        with self._lock:
            return len(self._assinantes)
