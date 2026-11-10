"""Testes de backup e restauração do banco SQLite do Conta+."""
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from scripts.backup_restore import (
    backup_database,
    restore_database,
    verify_database,
)


class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.previous_db_path = database.DB_PATH
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="conta_plus_backup_tests_"
        )
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source.db"
        self.backup = self.root / "backup.sqlite3"
        self.restored = self.root / "restored.db"
        database.DB_PATH = self.source
        database.inicializar_banco()
        with database.conectar() as conn:
            self.user_id = conn.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                ("Usuário de Teste", "backup@example.invalid", "hash-falso"),
            ).lastrowid
            self.account_id = conn.execute(
                "INSERT INTO contas (owner_id, nome, numero, saldo) VALUES (?, ?, ?, ?)",
                (self.user_id, "Conta de Teste", "BACKUP-TEST-001", "100.00"),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO transacoes
                (conta_id, tipo, descricao, valor, saldo_anterior, saldo_atual)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.account_id, "DEPOSITO", "Depósito sintético", "100.00", "0.00", "100.00"),
            )

    def tearDown(self):
        database.DB_PATH = self.previous_db_path
        self.temporary_directory.cleanup()

    def test_backup_e_restauracao_preservam_snapshot_consistente(self):
        backup_database(self.source, self.backup)
        with database.conectar() as conn:
            conn.execute(
                "UPDATE contas SET saldo = ? WHERE id = ?",
                ("999.99", self.account_id),
            )

        restore_database(self.backup, self.restored)
        verify_database(self.backup)
        verify_database(self.restored)

        with closing(sqlite3.connect(self.restored)) as conn:
            saldo = conn.execute(
                "SELECT saldo FROM contas WHERE id = ?", (self.account_id,)
            ).fetchone()[0]
            transacoes = conn.execute(
                "SELECT COUNT(*) FROM transacoes WHERE conta_id = ?",
                (self.account_id,),
            ).fetchone()[0]
        self.assertEqual(saldo, "100.00")
        self.assertEqual(transacoes, 1)

    def test_backup_nao_sobrescreve_destino_existente(self):
        self.backup.write_text("não sobrescrever", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            backup_database(self.source, self.backup)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "não sobrescrever")

    def test_restauracao_nao_sobrescreve_destino_existente(self):
        backup_database(self.source, self.backup)
        self.restored.write_text("preservar", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            restore_database(self.backup, self.restored)
        self.assertEqual(self.restored.read_text(encoding="utf-8"), "preservar")

    def test_origem_e_destino_nao_podem_ser_o_mesmo_arquivo(self):
        with self.assertRaises(ValueError):
            backup_database(self.source, self.source)

    def test_verificacao_rejeita_arquivo_corrompido(self):
        corrupt = self.root / "corrupt.db"
        corrupt.write_bytes(b"isto nao e um banco sqlite")
        with self.assertRaises((sqlite3.DatabaseError, ValueError)):
            verify_database(corrupt)


if __name__ == "__main__":
    unittest.main()
