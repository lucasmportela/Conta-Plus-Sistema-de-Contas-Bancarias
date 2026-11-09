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

    def criar_conta(self, nome="Lucas Martins", numero="12345", saldo="100.00"):
        with database.conectar() as conn:
            cursor = conn.execute(
                "INSERT INTO contas (nome, numero, saldo) VALUES (?, ?, ?)",
                (nome, numero, saldo),
            )
            return cursor.lastrowid

    def test_inicializacao_cria_tabelas_e_chaves_estrangeiras(self):
        with database.conectar() as conn:
            tabelas = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

        self.assertIn("contas", tabelas)
        self.assertIn("transacoes", tabelas)
        self.assertEqual(foreign_keys, 1)

    def test_conexao_confirma_dados_ao_finalizar(self):
        conta_id = self.criar_conta()

        with database.conectar() as conn:
            conta = database.obter_conta(conn, conta_id)

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
                "SELECT id FROM contas WHERE numero = ?",
                ("ROLLBACK",),
            ).fetchone()

        self.assertIsNone(conta)

    def test_numero_da_conta_deve_ser_unico(self):
        self.criar_conta(numero="UNICO")

        with self.assertRaises(sqlite3.IntegrityError):
            with database.conectar() as conn:
                conn.execute(
                    "INSERT INTO contas (nome, numero, saldo) VALUES (?, ?, ?)",
                    ("Outra Pessoa", "UNICO", "10.00"),
                )

        with database.conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM contas WHERE numero = ?",
                ("UNICO",),
            ).fetchone()[0]

        self.assertEqual(total, 1)

    def test_chave_estrangeira_impede_transacao_sem_conta(self):
        with self.assertRaises(Exception):
            with database.conectar() as conn:
                conn.execute(
                    """
                    INSERT INTO transacoes
                    (conta_id, tipo, descricao, valor, saldo_anterior, saldo_atual)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (99999, "DEPOSITO", "Conta inexistente", "10.00", "0.00", "10.00"),
                )

    def test_listar_obter_e_salvar_transacao(self):
        conta_id = self.criar_conta(saldo="150.00")

        with database.conectar() as conn:
            contas = database.listar_contas(conn)
            conta = database.obter_conta(conn, conta_id)
            database.salvar_transacao(
                conn,
                conta_id,
                "DEPOSITO",
                "Depósito de teste",
                Decimal("25.50"),
                Decimal("150.00"),
                Decimal("175.50"),
            )

        self.assertEqual(len(contas), 1)
        self.assertEqual(conta["saldo"], "150.00")

        with database.conectar() as conn:
            transacao = conn.execute(
                "SELECT * FROM transacoes WHERE conta_id = ?",
                (conta_id,),
            ).fetchone()

        self.assertEqual(transacao["tipo"], "DEPOSITO")
        self.assertEqual(transacao["valor"], "25.50")
        self.assertEqual(transacao["saldo_anterior"], "150.00")
        self.assertEqual(transacao["saldo_atual"], "175.50")

    def test_obter_conta_inexistente_retorna_none(self):
        with database.conectar() as conn:
            conta = database.obter_conta(conn, 99999)

        self.assertIsNone(conta)


if __name__ == "__main__":
    unittest.main()
