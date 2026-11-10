import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "instance" / "contas.db"


@contextmanager
def conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_banco():
    with conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                senha_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                numero TEXT NOT NULL UNIQUE,
                saldo TEXT NOT NULL DEFAULT '0.00',
                criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conta_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor TEXT NOT NULL,
                saldo_anterior TEXT NOT NULL,
                saldo_atual TEXT NOT NULL,
                conta_relacionada_id INTEGER,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conta_id) REFERENCES contas(id),
                FOREIGN KEY (conta_relacionada_id) REFERENCES contas(id)
            );
            """
        )

        colunas_contas = {
            coluna["name"]
            for coluna in conn.execute("PRAGMA table_info(contas)").fetchall()
        }
        if "owner_id" not in colunas_contas:
            # Registros antigos permanecem sem proprietário e não são expostos
            # a nenhum usuário até uma atribuição administrativa explícita.
            conn.execute(
                "ALTER TABLE contas ADD COLUMN owner_id INTEGER REFERENCES usuarios(id)"
            )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contas_owner_id ON contas(owner_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transacoes_conta_id ON transacoes(conta_id)"
        )


def obter_conta(conn, conta_id, usuario_id):
    return conn.execute(
        """
        SELECT id, nome, numero, saldo, criada_em
        FROM contas
        WHERE id = ? AND owner_id = ?
        """,
        (conta_id, usuario_id),
    ).fetchone()


def listar_contas(conn, usuario_id):
    return conn.execute(
        """
        SELECT id, nome, numero, saldo, criada_em
        FROM contas
        WHERE owner_id = ?
        ORDER BY id DESC
        """,
        (usuario_id,),
    ).fetchall()


def salvar_transacao(
    conn, conta_id, tipo, descricao, valor,
    saldo_anterior, saldo_atual, conta_relacionada_id=None
):
    conn.execute(
        """
        INSERT INTO transacoes
        (conta_id, tipo, descricao, valor, saldo_anterior, saldo_atual, conta_relacionada_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conta_id, tipo, descricao, f"{valor:.2f}",
            f"{saldo_anterior:.2f}", f"{saldo_atual:.2f}",
            conta_relacionada_id,
        ),
    )
