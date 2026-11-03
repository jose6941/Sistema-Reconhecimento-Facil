"""Estado em memória do último reconhecimento (mostrado na aba Ao vivo)."""

import threading
from typing import Any


class EstadoReconhecimento:
    """Guarda o último reconhecimento com acesso protegido por lock."""

    def __init__(self, camera_id: str):
        self._camera_id = camera_id
        self._lock = threading.Lock()
        self._atual = self._montar("idle")

    def _montar(
        self,
        status: str,
        user: str | None = None,
        user_id: int | None = None,
        confidence: float = 0.0,
        distance_lbph: float | None = None,
        data_hora: str | None = None,
        foto_url: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "user": user,
            "user_id": user_id,
            "confidence": confidence,
            "distance_lbph": distance_lbph,
            "data_hora": data_hora,
            "foto_url": foto_url,
            "camera_id": self._camera_id,
        }

    def atualizar(self, **campos: Any) -> dict[str, Any]:
        novo = self._montar(**campos)
        with self._lock:
            self._atual = novo
        return dict(novo)

    def obter(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._atual)
