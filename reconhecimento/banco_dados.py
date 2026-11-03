"""Camada de persistência SQLite (usuários, logs de acesso e capturas desconhecidas)."""

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

STATUS_VALIDOS_USUARIO = ("ativo", "revogado")
STATUS_VALIDOS_LOG = ("authorized", "denied", "revoked", "no_face_detected", "error")

# Valores estimados exibidos na aba Histórico (não são medições em tempo real).
FAR_ESTIMADO_PCT = 1.8
FRR_ESTIMADO_PCT = 4.3


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _escapar_like(texto: str) -> str:
    """Faz `%`, `_` e `\\` serem tratados como texto literal em um LIKE ... ESCAPE '\\'."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class BancoDados:
    """Acesso ao arquivo SQLite. Cada operação abre e fecha a própria conexão (thread-safe)."""

    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        try:
            yield conexao
            conexao.commit()
        finally:
            conexao.close()

    # ------------------------------------------------------------------ esquema
    def inicializar(self) -> None:
        """Cria as tabelas e migra esquemas antigos."""
        with self._conexao() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL,
                    data_cadastro TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ativo'
                )
                """
            )
            colunas_usuarios = {c["name"] for c in con.execute("PRAGMA table_info(usuarios)")}
            if "status" not in colunas_usuarios:
                con.execute("ALTER TABLE usuarios ADD COLUMN status TEXT NOT NULL DEFAULT 'ativo'")

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS logs_acesso (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT NOT NULL,
                    usuario_id INTEGER,
                    usuario_nome TEXT,
                    status TEXT NOT NULL,
                    confianca REAL,
                    distancia_lbph REAL,
                    foto_path TEXT,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
                """
            )
            colunas_logs = {c["name"] for c in con.execute("PRAGMA table_info(logs_acesso)")}
            if "usuario_id" not in colunas_logs:
                con.execute("ALTER TABLE logs_acesso ADD COLUMN usuario_id INTEGER")
            if "usuario_nome" not in colunas_logs:
                con.execute("ALTER TABLE logs_acesso ADD COLUMN usuario_nome TEXT")
                if "usuario" in colunas_logs:
                    con.execute("UPDATE logs_acesso SET usuario_nome = usuario WHERE usuario_nome IS NULL")
            if "distancia_lbph" not in colunas_logs:
                con.execute("ALTER TABLE logs_acesso ADD COLUMN distancia_lbph REAL")
            if "foto_path" not in colunas_logs:
                con.execute("ALTER TABLE logs_acesso ADD COLUMN foto_path TEXT")

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS capturas_desconhecidas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT NOT NULL,
                    caminho_foto TEXT NOT NULL,
                    resolvida INTEGER NOT NULL DEFAULT 0,
                    usuario_id INTEGER,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
                """
            )

    # ----------------------------------------------------------------- usuários
    def salvar_usuarios(self, labels: Mapping[int | str, str]) -> None:
        """Sincroniza `usuarios` com o mapeamento {id: nome} do treino, preservando o status."""
        agora = _agora()
        with self._conexao() as con:
            for identificador, nome in labels.items():
                con.execute(
                    """
                    INSERT INTO usuarios (id, nome, data_cadastro, status)
                    VALUES (?, ?, ?, 'ativo')
                    ON CONFLICT(id) DO UPDATE SET nome = excluded.nome
                    """,
                    (int(identificador), nome, agora),
                )

    def obter_status_usuario(self, usuario_id: int | None) -> str:
        """'ativo' / 'revogado'; 'desconhecido' se o ID for None; 'ativo' se não houver registro."""
        if usuario_id is None:
            return "desconhecido"
        with self._conexao() as con:
            linha = con.execute("SELECT status FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
        return linha["status"] if linha and linha["status"] else "ativo"

    def atualizar_status_usuario(self, usuario_id: int, novo_status: str) -> bool:
        """Altera o status. Retorna False se o usuário não existir."""
        novo_status = novo_status.lower().strip()
        if novo_status not in STATUS_VALIDOS_USUARIO:
            raise ValueError("Status deve ser 'ativo' ou 'revogado'")
        with self._conexao() as con:
            cursor = con.execute("UPDATE usuarios SET status = ? WHERE id = ?", (novo_status, int(usuario_id)))
            return cursor.rowcount > 0

    def listar_usuarios(self) -> list[dict[str, Any]]:
        with self._conexao() as con:
            cursor = con.execute(
                """
                SELECT
                    u.id, u.nome, u.data_cadastro, u.status,
                    (SELECT MAX(l.data_hora) FROM logs_acesso l
                      WHERE l.usuario_id = u.id AND l.status = 'authorized') AS ultima_entrada,
                    (SELECT COUNT(l.id) FROM logs_acesso l WHERE l.usuario_id = u.id) AS total_acessos
                FROM usuarios u
                ORDER BY u.nome ASC
                """
            )
            return [dict(linha) for linha in cursor.fetchall()]

    # --------------------------------------------------------------------- logs
    def registrar_log(
        self,
        usuario_id: int | None,
        usuario_nome: str | None,
        status: str,
        confianca: float,
        distancia_lbph: float | None = None,
        foto_path: str | None = None,
    ) -> int:
        with self._conexao() as con:
            cursor = con.execute(
                """
                INSERT INTO logs_acesso
                    (data_hora, usuario_id, usuario_nome, status, confianca, distancia_lbph, foto_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (_agora(), usuario_id, usuario_nome, status, confianca, distancia_lbph, foto_path),
            )
            return int(cursor.lastrowid)

    def consultar_logs(
        self,
        usuario_nome: str | None = None,
        status: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        limite: int = 100,
        offset: int = 0,
        apenas_excecoes: bool = False,
    ) -> list[dict[str, Any]]:
        """Histórico filtrado. Datas no formato 'AAAA-MM-DD'; `apenas_excecoes` exclui 'authorized'."""
        condicoes: list[str] = []
        parametros: list[Any] = []

        if usuario_nome:
            condicoes.append("usuario_nome LIKE ? ESCAPE '\\'")
            parametros.append(f"%{_escapar_like(usuario_nome)}%")
        if status:
            condicoes.append("status = ?")
            parametros.append(status)
        if apenas_excecoes:
            condicoes.append("status != 'authorized'")
        if data_inicio:
            condicoes.append("data_hora >= ?")
            parametros.append(data_inicio)
        if data_fim:
            condicoes.append("data_hora <= ?")
            parametros.append(data_fim + "T23:59:59")

        where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
        consulta = f"SELECT * FROM logs_acesso {where} ORDER BY data_hora DESC, id DESC LIMIT ? OFFSET ?"
        parametros.extend([int(limite), int(offset)])

        with self._conexao() as con:
            return [dict(linha) for linha in con.execute(consulta, parametros).fetchall()]

    def listar_excecoes(self, limite: int = 20) -> list[dict[str, Any]]:
        return self.consultar_logs(apenas_excecoes=True, limite=limite)

    # ------------------------------------------------------ capturas desconhecidas
    def salvar_captura_desconhecida(self, caminho_foto: str) -> int:
        with self._conexao() as con:
            cursor = con.execute(
                "INSERT INTO capturas_desconhecidas (data_hora, caminho_foto, resolvida) VALUES (?, ?, 0)",
                (_agora(), caminho_foto),
            )
            return int(cursor.lastrowid)

    def listar_capturas_desconhecidas(self, apenas_pendentes: bool = True, limite: int = 20) -> list[dict[str, Any]]:
        where = "WHERE resolvida = 0" if apenas_pendentes else ""
        consulta = f"SELECT * FROM capturas_desconhecidas {where} ORDER BY data_hora DESC, id DESC LIMIT ?"
        with self._conexao() as con:
            return [dict(linha) for linha in con.execute(consulta, (int(limite),)).fetchall()]

    def obter_captura_desconhecida(self, captura_id: int) -> dict[str, Any] | None:
        with self._conexao() as con:
            linha = con.execute("SELECT * FROM capturas_desconhecidas WHERE id = ?", (int(captura_id),)).fetchone()
        return dict(linha) if linha else None

    def resolver_captura_desconhecida(self, captura_id: int, usuario_id: int) -> None:
        with self._conexao() as con:
            con.execute(
                "UPDATE capturas_desconhecidas SET resolvida = 1, usuario_id = ? WHERE id = ?",
                (int(usuario_id), int(captura_id)),
            )

    # ------------------------------------------------------------- estatísticas
    def obter_estatisticas_historico(self) -> dict[str, Any]:
        """Indicadores (KPIs) exibidos na aba Histórico."""
        hoje = datetime.now().strftime("%Y-%m-%d")

        def contar(con: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
            return int(con.execute(sql, params).fetchone()["c"])

        with self._conexao() as con:
            return {
                "entradas_hoje": contar(
                    con, "SELECT COUNT(*) AS c FROM logs_acesso WHERE data_hora >= ? AND status = 'authorized'", (hoje,)
                ),
                "total_tentativas_hoje": contar(con, "SELECT COUNT(*) AS c FROM logs_acesso WHERE data_hora >= ?", (hoje,)),
                "excecoes_hoje": contar(
                    con, "SELECT COUNT(*) AS c FROM logs_acesso WHERE data_hora >= ? AND status != 'authorized'", (hoje,)
                ),
                "falsos_aceitos_pct": FAR_ESTIMADO_PCT,
                "falsos_rejeitados_pct": FRR_ESTIMADO_PCT,
                "total_usuarios": contar(con, "SELECT COUNT(*) AS c FROM usuarios"),
                "usuarios_ativos": contar(con, "SELECT COUNT(*) AS c FROM usuarios WHERE status = 'ativo'"),
                "usuarios_revogados": contar(con, "SELECT COUNT(*) AS c FROM usuarios WHERE status = 'revogado'"),
                "capturas_pendentes": contar(con, "SELECT COUNT(*) AS c FROM capturas_desconhecidas WHERE resolvida = 0"),
            }
