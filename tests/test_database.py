"""Testes de integração da camada SQLite do Conta+."""
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database


class TestDatabaseIntegration(unittest.TestCase):
    def setUp(self):
        self._previous_db_path = database.DB_PATH
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="conta_plus_database_tests_"
        )
        database.DB_PATH = Path(self._temporary_directory.name) / "test.db"
        database.inicializar_banco()

    def tearDown(self):
        database.DB_PATH = self._previous_db_path
        self._temporary_directory.cleanup()

    def criar_usuario(self, email="lucas@example.com"):
        with database.conectar() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                ("Lucas Martins", email, "hash-de-teste"),
            )
            return cursor.lastrowid

    def criar_conta(
        self, owner_id=None, nome="Lucas Martins", numero="12345", saldo="100.00"
    ):
        with database.conectar() as conn:
            cursor = conn.execute(
                """
                INSERT INTO contas (owner_id, nome, numero, saldo)
                VALUES (?, ?, ?, ?)
                """,
                (owner_id, nome, numero, saldo),
            )
            return cursor.lastrowid

    def test_inicializacao_cria_tabelas_indices_e_chaves_estrangeiras(self):
        with database.conectar() as conn:
            tabelas = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            colunas = {
                row["name"] for row in conn.execute("PRAGMA table_info(contas)")
            }
            indices = {
                row["name"] for row in conn.execute("PRAGMA index_list(contas)")
            }

        self.assertIn("usuarios", tabelas)
        self.assertIn("contas", tabelas)
        self.assertIn("transacoes", tabelas)
        self.assertIn("owner_id", colunas)
        self.assertIn("idx_contas_owner_id", indices)
        self.assertEqual(foreign_keys, 1)

    def test_conexao_confirma_dados_ao_finalizar(self):
        usuario_id = self.criar_usuario()
        conta_id = self.criar_conta(owner_id=usuario_id)
        with database.conectar() as conn:
            conta = database.obter_conta(conn, conta_id, usuario_id)
        self.assertIsNotNone(conta)
        self.assertEqual(conta["numero"], "12345")

    def test_conexao_faz_rollback_quando_ocorre_excecao(self):
        with self.assertRaisesRegex(RuntimeError, "forçar rollback"):
            with database.conectar() as conn:
                conn.execute(
                    "INSERT INTO contas (nome, numero, saldo) VALUES (?, ?, ?)",
                    ("Conta Temporária", "ROLLBACK", "50.00"),
                )
                raise RuntimeError("forçar rollback")

        with database.conectar() as conn:
            conta = conn.execute(
                "SELECT id FROM contas WHERE numero = ?", ("ROLLBACK",)
            ).fetchone()
        self.assertIsNone(conta)

    def test_numero_da_conta_deve_ser_unico(self):
        self.criar_conta(numero="UNICO")
        with self.assertRaises(sqlite3.IntegrityError):
            self.criar_conta(nome="Outra Pessoa", numero="UNICO", saldo="10.00")
        with database.conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM contas WHERE numero = ?", ("UNICO",)
            ).fetchone()[0]
        self.assertEqual(total, 1)

    def test_chave_estrangeira_impede_transacao_sem_conta(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with database.conectar() as conn:
                conn.execute(
                    """
                    INSERT INTO transacoes
                    (conta_id, tipo, descricao, valor, saldo_anterior, saldo_atual)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (99999, "DEPOSITO", "Conta inexistente", "10.00", "0.00", "10.00"),
                )

    def test_listar_obter_e_salvar_transacao_respeitam_proprietario(self):
        usuario_a = self.criar_usuario("a@example.com")
        usuario_b = self.criar_usuario("b@example.com")
        conta_a = self.criar_conta(owner_id=usuario_a, numero="CONTA-A")
        self.criar_conta(owner_id=usuario_b, numero="CONTA-B")

        with database.conectar() as conn:
            contas_a = database.listar_contas(conn, usuario_a)
            conta = database.obter_conta(conn, conta_a, usuario_a)
            conta_de_b = database.obter_conta(conn, conta_a, usuario_b)
            database.salvar_transacao(
                conn, conta_a, "DEPOSITO", "Depósito de teste",
                Decimal("25.50"), Decimal("100.00"), Decimal("125.50"),
            )

        self.assertEqual(len(contas_a), 1)
        self.assertIsNotNone(conta)
        self.assertIsNone(conta_de_b)
        with database.conectar() as conn:
            transacao = conn.execute(
                "SELECT * FROM transacoes WHERE conta_id = ?", (conta_a,)
            ).fetchone()
        self.assertEqual(transacao["tipo"], "DEPOSITO")
        self.assertEqual(transacao["valor"], "25.50")

    def test_obter_conta_inexistente_retorna_none(self):
        with database.conectar() as conn:
            conta = database.obter_conta(conn, 99999, 1)
        self.assertIsNone(conta)

    def test_migracao_mantem_contas_antigas_sem_proprietario(self):
        self.tearDown()
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="conta_plus_legacy_tests_"
        )
        database.DB_PATH = Path(self._temporary_directory.name) / "legacy.db"
        with database.conectar() as conn:
            conn.execute(
                """
                CREATE TABLE contas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    numero TEXT NOT NULL UNIQUE,
                    saldo TEXT NOT NULL DEFAULT '0.00',
                    criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "INSERT INTO contas (nome, numero, saldo) VALUES (?, ?, ?)",
                ("Conta antiga", "LEGADO", "75.00"),
            )

        database.inicializar_banco()
        with database.conectar() as conn:
            colunas = {
                row["name"] for row in conn.execute("PRAGMA table_info(contas)")
            }
            total_sem_dono = conn.execute(
                "SELECT COUNT(*) FROM contas WHERE owner_id IS NULL"
            ).fetchone()[0]
            usuario_id = conn.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                ("Novo usuário", "novo@example.com", "hash"),
            ).lastrowid
            contas_usuario = database.listar_contas(conn, usuario_id)

        self.assertIn("owner_id", colunas)
        self.assertEqual(total_sem_dono, 1)
        self.assertEqual(contas_usuario, [])


if __name__ == "__main__":
    unittest.main()
