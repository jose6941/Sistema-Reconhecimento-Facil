"""Validação de entrada da API. Qualquer valor inválido vira `ErroValidacao` (HTTP 400), nunca 500."""

import ipaddress
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from reconhecimento.banco_dados import STATUS_VALIDOS_LOG

TAMANHO_MAX_TEXTO = 100


class ErroValidacao(Exception):
    """Entrada inválida enviada pelo cliente."""

    status_code = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def int_param(valores: Mapping[str, Any], nome: str, padrao: int, minimo: int, maximo: int) -> int:
    bruto = valores.get(nome)
    if bruto is None or bruto == "":
        return padrao
    try:
        numero = int(bruto)
    except (TypeError, ValueError):
        raise ErroValidacao(f"O parâmetro '{nome}' deve ser um número inteiro.") from None
    if not minimo <= numero <= maximo:
        raise ErroValidacao(f"O parâmetro '{nome}' deve estar entre {minimo} e {maximo}.")
    return numero


def inteiro_json(corpo: Mapping[str, Any], nome: str) -> int:
    """Inteiro positivo vindo de JSON (aceita 12 ou "12"; recusa bool, float e texto)."""
    valor = corpo.get(nome)
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ErroValidacao(f"O campo '{nome}' é obrigatório e deve ser um número inteiro.")
    try:
        numero = int(valor)
    except ValueError:
        raise ErroValidacao(f"O campo '{nome}' deve ser um número inteiro.") from None
    if numero < 1:
        raise ErroValidacao(f"O campo '{nome}' deve ser positivo.")
    return numero


def data_param(valores: Mapping[str, Any], nome: str) -> str | None:
    bruto = valores.get(nome)
    if not bruto:
        return None
    try:
        return datetime.strptime(bruto, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        raise ErroValidacao(f"O parâmetro '{nome}' deve estar no formato AAAA-MM-DD.") from None


def texto_param(valores: Mapping[str, Any], nome: str) -> str | None:
    bruto = valores.get(nome)
    if bruto is None or bruto == "":
        return None
    texto = str(bruto).strip()
    if len(texto) > TAMANHO_MAX_TEXTO:
        raise ErroValidacao(f"O parâmetro '{nome}' excede {TAMANHO_MAX_TEXTO} caracteres.")
    return texto or None


def status_log_param(valores: Mapping[str, Any]) -> str | None:
    status = texto_param(valores, "status")
    if status is not None and status not in STATUS_VALIDOS_LOG:
        raise ErroValidacao("Status inválido. Use: " + ", ".join(STATUS_VALIDOS_LOG) + ".")
    return status


def bool_param(valores: Mapping[str, Any], nome: str) -> bool:
    return str(valores.get(nome, "")).strip().lower() in ("1", "true", "sim", "yes")


def texto_json(corpo: Mapping[str, Any], nome: str, padrao: str | None = None) -> str:
    valor = corpo.get(nome, padrao)
    if not isinstance(valor, str) or not valor.strip():
        raise ErroValidacao(f"O campo '{nome}' é obrigatório.")
    valor = valor.strip()
    if len(valor) > TAMANHO_MAX_TEXTO:
        raise ErroValidacao(f"O campo '{nome}' excede {TAMANHO_MAX_TEXTO} caracteres.")
    return valor


def url_camera(valor: Any) -> str:
    """Valida o endereço do ESP32-CAM: só http/https, com host, e fora de faixas perigosas."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErroValidacao("O campo 'url' é obrigatório (ex.: http://192.168.0.55).")
    texto = valor.strip()
    if len(texto) > 300:
        raise ErroValidacao("O campo 'url' é longo demais.")
    if "://" not in texto:
        texto = "http://" + texto
    try:
        partes = urlparse(texto)
        _ = partes.port  # levanta ValueError se a porta for inválida
    except ValueError:
        raise ErroValidacao("URL inválida.") from None
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ErroValidacao("A URL da câmera deve usar http:// ou https:// e informar o endereço.")
    if partes.username or partes.password:
        raise ErroValidacao("A URL da câmera não pode conter usuário ou senha.")
    try:
        ip = ipaddress.ip_address(partes.hostname)
    except ValueError:
        return texto  # nome de host (ex.: esp32cam.local)
    if ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        raise ErroValidacao("Endereço de câmera não permitido.")
    return texto
