#!/usr/bin/env python3
"""
Gera o arquivo secrets.h do firmware a partir do .env desta pasta.

Uso (dentro de CameraWebServer/):
    python3 gerar_secrets.py

Variáveis lidas: WIFI_SSID, WIFI_PASSWORD.
O secrets.h é ignorado pelo Git (.gitignore) para não vazar credenciais.
"""
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(PASTA, ".env")
SAIDA = os.path.join(PASTA, "secrets.h")
OBRIGATORIAS = ("WIFI_SSID", "WIFI_PASSWORD")


def ler_env(caminho):
    valores = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            valores[chave.strip()] = valor
    return valores


def literal_c(texto):
    """Escapa o texto para uso dentro de uma string C."""
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def main():
    if not os.path.isfile(ENTRADA):
        sys.exit("Arquivo .env não encontrado. Rode: cp .env.example .env  e preencha os valores.")

    env = ler_env(ENTRADA)
    faltando = [k for k in OBRIGATORIAS if not env.get(k)]
    if faltando:
        sys.exit("Preencha no .env: " + ", ".join(faltando))

    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("// Arquivo GERADO por gerar_secrets.py a partir do .env. NÃO edite nem versione.\n")
        f.write("#pragma once\n")
        for chave in OBRIGATORIAS:
            f.write(f'#define {chave} "{literal_c(env[chave])}"\n')

    print(f"secrets.h gerado em {SAIDA}")


if __name__ == "__main__":
    main()
