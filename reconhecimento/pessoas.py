"""Normalização de nomes de pessoas <-> nomes de pasta do dataset (fonte única)."""


def slug_pessoa(nome: str) -> str:
    """Nome seguro de pasta: minúsculas, `_` no lugar de espaços, só letras/números/`_`.

    Remove `/`, `.` e demais caracteres, o que impede path traversal (`../..`).
    """
    texto = nome.strip().lower().replace(" ", "_")
    texto = "".join(c for c in texto if c.isalnum() or c == "_")
    return texto or "usuario"


def nome_exibicao(pasta: str) -> str:
    """Nome mostrado no painel a partir do nome da pasta (`maria_jose` -> `Maria Jose`)."""
    return pasta.replace("_", " ").title()
