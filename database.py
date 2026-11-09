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
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def obter_conta(conn, conta_id):
    return conn.execute(
        "SELECT id, nome, numero, saldo, criada_em FROM contas WHERE id = ?",
        (conta_id,),
    ).fetchone()


def listar_contas(conn):
    return conn.execute(
        """
        SELECT id, nome, numero, saldo, criada_em
        FROM contas
        ORDER BY id DESC
        """
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
