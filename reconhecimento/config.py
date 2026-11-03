"""Configuração central do backend, lida do ambiente (.env) e imutável depois de criada."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROJETO = Path(__file__).resolve().parent.parent


def _ler_float(env: Mapping[str, str], nome: str, padrao: float) -> float:
    try:
        return float(env.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _ler_int(env: Mapping[str, str], nome: str, padrao: int) -> int:
    try:
        return int(env.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


@dataclass(frozen=True)
class Settings:
    """Parâmetros e caminhos do sistema. Use `Settings.com_base()` ou `Settings.from_env()`."""

    base_dir: Path
    dataset_dir: Path
    model_path: Path
    labels_path: Path
    static_dir: Path
    desconhecidos_dir: Path
    acessos_dir: Path
    db_path: Path

    lbph_threshold: float = 65.0
    debounce_seconds: float = 4.0
    camera_id: str = "CAM-01 · Portaria"
    cors_origins: tuple[str, ...] = ("*",)
    max_upload_bytes: int = 5 * 1024 * 1024
    host: str = "0.0.0.0"
    port: int = 5000
    esp32_url: str | None = None

    @classmethod
    def com_base(cls, base_dir: Path | str, **alteracoes) -> "Settings":
        """Monta os caminhos a partir de uma pasta base; `alteracoes` sobrescreve qualquer campo."""
        base = Path(base_dir)
        static = base / "static"
        padrao = cls(
            base_dir=base,
            dataset_dir=base / "dataset",
            model_path=base / "modelo_lbph.yml",
            labels_path=base / "labels.json",
            static_dir=static,
            desconhecidos_dir=static / "desconhecidos",
            acessos_dir=static / "acessos",
            db_path=base / "acessos.db",
        )
        return replace(padrao, **alteracoes) if alteracoes else padrao

    @classmethod
    def from_env(
        cls,
        base_dir: Path | str = RAIZ_PROJETO,
        env: Mapping[str, str] | None = None,
    ) -> "Settings":
        """Lê o `.env` da pasta base (se `env` não for informado) e as variáveis do sistema."""
        base = Path(base_dir)
        if env is None:
            load_dotenv(base / ".env")
            env = os.environ

        origens = tuple(o.strip() for o in env.get("CORS_ORIGINS", "*").split(",") if o.strip())
        return cls.com_base(
            base,
            lbph_threshold=_ler_float(env, "LBPH_CONFIDENCE_THRESHOLD", 65.0),
            debounce_seconds=_ler_float(env, "DEBOUNCE_SECONDS", 4.0),
            camera_id=env.get("CAMERA_ID") or "CAM-01 · Portaria",
            cors_origins=origens or ("*",),
            max_upload_bytes=max(1, _ler_int(env, "MAX_UPLOAD_MB", 5)) * 1024 * 1024,
            host=env.get("FLASK_HOST") or "0.0.0.0",
            port=_ler_int(env, "FLASK_PORT", 5000),
            esp32_url=env.get("ESP32_URL") or None,
        )

    def garantir_diretorios(self) -> None:
        for pasta in (self.dataset_dir, self.static_dir, self.desconhecidos_dir, self.acessos_dir):
            pasta.mkdir(parents=True, exist_ok=True)
