"""Ponto de entrada do servidor de reconhecimento facial (TCC IFSP Birigui).

Uso:
    python servidor_reconhecimento.py                      # sobe a API em http://0.0.0.0:5000
    python servidor_reconhecimento.py --train              # só treina o modelo LBPH
    python servidor_reconhecimento.py --esp32-url http://192.168.0.55

A lógica está no pacote `reconhecimento/`; as configurações vêm do `.env` (ver `.env.example`).
"""

import argparse
import logging

from reconhecimento import create_app
from reconhecimento.config import Settings

logger = logging.getLogger("servidor_reconhecimento")


def main(argv: list[str] | None = None) -> None:
    settings = Settings.from_env()

    parser = argparse.ArgumentParser(description="Servidor de reconhecimento facial")
    parser.add_argument("--train", action="store_true", help="Treina o modelo LBPH a partir do dataset e sai")
    parser.add_argument("--serve", action="store_true", help="Sobe o servidor Flask (padrão)")
    parser.add_argument(
        "--esp32-url",
        default=settings.esp32_url,
        help="Conecta ao stream do ESP32-CAM ao iniciar (ex.: http://192.168.0.55). Padrão: ESP32_URL do .env",
    )
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", default=settings.port, type=int)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    app = create_app(settings)
    contexto = app.extensions["reconhecimento"]

    if args.train:
        contexto.treino.executar()
        return

    if args.esp32_url:
        logger.info("Iniciando conexão automática com o ESP32-CAM em %s ...", args.esp32_url)
        contexto.worker.conectar(args.esp32_url)

    logger.info("Iniciando Servidor Flask em http://%s:%d ...", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
