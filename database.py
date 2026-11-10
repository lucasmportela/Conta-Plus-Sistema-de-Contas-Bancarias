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

            CREATE TABLE IF NOT EXISTS tentativas_login (
                chave_hash TEXT PRIMARY KEY,
                tentativas INTEGER NOT NULL,
                inicio_janela INTEGER NOT NULL,
                bloqueado_ate INTEGER NOT NULL DEFAULT 0,
                atualizado_em INTEGER NOT NULL
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tentativas_login_atualizado_em ON tentativas_login(atualizado_em)"
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



def obter_bloqueio_login(
    conn, chave_hash, agora, janela_segundos, retencao_segundos
):
    """Consulta o bloqueio e remove registros expirados de tentativas."""
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "DELETE FROM tentativas_login WHERE atualizado_em < ?",
        (agora - retencao_segundos,),
    )
    registro = conn.execute(
        """
        SELECT inicio_janela, bloqueado_ate
        FROM tentativas_login
        WHERE chave_hash = ?
        """,
        (chave_hash,),
    ).fetchone()

    if registro is None:
        return 0

    bloqueado_ate = registro["bloqueado_ate"]
    if bloqueado_ate > agora:
        return bloqueado_ate - agora

    janela_expirada = agora - registro["inicio_janela"] >= janela_segundos
    if bloqueado_ate or janela_expirada:
        conn.execute(
            "DELETE FROM tentativas_login WHERE chave_hash = ?",
            (chave_hash,),
        )
    return 0


def registrar_falha_login(
    conn, chave_hash, agora, limite, janela_segundos,
    bloqueio_segundos, retencao_segundos
):
    """Registra falha de forma atômica e retorna os segundos de bloqueio."""
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "DELETE FROM tentativas_login WHERE atualizado_em < ?",
        (agora - retencao_segundos,),
    )
    registro = conn.execute(
        """
        SELECT tentativas, inicio_janela, bloqueado_ate
        FROM tentativas_login
        WHERE chave_hash = ?
        """,
        (chave_hash,),
    ).fetchone()

    reiniciar = (
        registro is None
        or agora - registro["inicio_janela"] >= janela_segundos
        or registro["bloqueado_ate"] > 0
    )
    if reiniciar:
        tentativas = 1
        inicio_janela = agora
    else:
        tentativas = registro["tentativas"] + 1
        inicio_janela = registro["inicio_janela"]

    bloqueado_ate = agora + bloqueio_segundos if tentativas >= limite else 0
    conn.execute(
        """
        INSERT INTO tentativas_login
            (chave_hash, tentativas, inicio_janela, bloqueado_ate, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chave_hash) DO UPDATE SET
            tentativas = excluded.tentativas,
            inicio_janela = excluded.inicio_janela,
            bloqueado_ate = excluded.bloqueado_ate,
            atualizado_em = excluded.atualizado_em
        """,
        (chave_hash, tentativas, inicio_janela, bloqueado_ate, agora),
    )
    return max(0, bloqueado_ate - agora)


def limpar_tentativas_login(conn, chave_hash):
    """Remove o contador após autenticação bem-sucedida."""
    conn.execute(
        "DELETE FROM tentativas_login WHERE chave_hash = ?",
        (chave_hash,),
    )
