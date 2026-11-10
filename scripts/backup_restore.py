"""Backup e restauração consistentes do SQLite do Conta+.

Os arquivos gerados contêm dados pessoais. Mantenha-os fora do repositório,
restrinja permissões e criptografe-os antes de enviá-los a armazenamento externo.
"""
import argparse
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_TABLES = {"usuarios", "contas", "transacoes"}


def _readonly_connection(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def verify_database(path):
    """Valida integridade SQLite, tabelas essenciais e chaves estrangeiras."""
    database_path = Path(path).expanduser().resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {database_path}")

    with closing(_readonly_connection(database_path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            detail = integrity[0] if integrity else "sem resultado"
            raise ValueError(f"Falha em PRAGMA integrity_check: {detail}")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise ValueError(
                "O arquivo não contém tabelas essenciais do Conta+: "
                + ", ".join(sorted(missing))
            )

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(
                f"Banco contém {len(violations)} violação(ões) de chave estrangeira."
            )

    return True


def _copy_database_consistently(source, destination, operation):
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()

    if source_path == destination_path:
        raise ValueError("Origem e destino precisam ser arquivos diferentes.")
    if not source_path.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {source_path}")
    if destination_path.exists():
        raise FileExistsError(
            f"O destino já existe e não será sobrescrito: {destination_path}"
        )

    if operation == "restore":
        verify_database(source_path)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        with closing(_readonly_connection(source_path)) as source_conn:
            with closing(sqlite3.connect(temporary_path)) as destination_conn:
                source_conn.backup(destination_conn, pages=256, sleep=0.05)
                destination_conn.commit()

        verify_database(temporary_path)
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass

        if destination_path.exists():
            raise FileExistsError(
                f"O destino já existe e não será sobrescrito: {destination_path}"
            )
        os.replace(temporary_path, destination_path)
        return destination_path
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def backup_database(source, destination):
    """Cria backup consistente usando a API SQLite, inclusive com WAL ativo."""
    return _copy_database_consistently(source, destination, "backup")


def restore_database(backup, destination):
    """Restaura para um novo caminho; nunca sobrescreve o banco existente."""
    return _copy_database_consistently(backup, destination, "restore")


def self_test():
    """Exercita backup e restauração com registros sintéticos, sem dados reais."""
    import database

    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="conta_plus_backup_test_") as directory:
        root = Path(directory)
        source = root / "conta_plus.db"
        backup = root / "backup.sqlite3"
        restored = root / "restored.sqlite3"
        try:
            database.DB_PATH = source
            database.inicializar_banco()
            with database.conectar() as conn:
                user_id = conn.execute(
                    "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                    ("Usuário Sintético", "backup-test@example.invalid", "hash-falso"),
                ).lastrowid
                account_id = conn.execute(
                    "INSERT INTO contas (owner_id, nome, numero, saldo) VALUES (?, ?, ?, ?)",
                    (user_id, "Conta Sintética", "BACKUP-TEST-001", "125.50"),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO transacoes
                    (conta_id, tipo, descricao, valor, saldo_anterior, saldo_atual)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, "DEPOSITO", "Registro sintético", "25.50", "100.00", "125.50"),
                )

            backup_database(source, backup)
            with database.conectar() as conn:
                conn.execute(
                    "UPDATE contas SET saldo = ? WHERE id = ?",
                    ("999.99", account_id),
                )
            restore_database(backup, restored)

            with closing(_readonly_connection(restored)) as conn:
                account = conn.execute(
                    "SELECT saldo FROM contas WHERE id = ?", (account_id,)
                ).fetchone()
                transaction_count = conn.execute(
                    "SELECT COUNT(*) FROM transacoes WHERE conta_id = ?", (account_id,)
                ).fetchone()[0]
                user_count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]

            if account is None or account[0] != "125.50":
                raise AssertionError("A restauração não preservou o saldo do snapshot.")
            if transaction_count != 1 or user_count != 1:
                raise AssertionError("A restauração não preservou os registros esperados.")
            verify_database(backup)
            verify_database(restored)
        finally:
            database.DB_PATH = original_db_path

    print("Backup e restauração SQLite aprovados com dados sintéticos.")
    print("Integridade SQLite e chaves estrangeiras verificadas.")
    print("Nenhum dado pessoal ou financeiro real foi utilizado.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Backup, validação e restauração segura do banco SQLite do Conta+."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup_parser = commands.add_parser("backup", help="Cria um backup consistente.")
    backup_parser.add_argument("--source", required=True, help="Caminho do banco ativo.")
    backup_parser.add_argument("--destination", required=True, help="Novo arquivo de backup.")

    restore_parser = commands.add_parser("restore", help="Restaura para um novo caminho.")
    restore_parser.add_argument("--backup", required=True, help="Arquivo de backup validado.")
    restore_parser.add_argument("--destination", required=True, help="Novo caminho de restauração.")

    verify_parser = commands.add_parser("verify", help="Verifica integridade do banco.")
    verify_parser.add_argument("--database", required=True, help="Banco ou backup a verificar.")

    commands.add_parser("self-test", help="Executa teste completo com dados sintéticos.")

    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            result = backup_database(args.source, args.destination)
            print(f"Backup criado e validado: {result}")
        elif args.command == "restore":
            result = restore_database(args.backup, args.destination)
            print(f"Restauração concluída e validada: {result}")
        elif args.command == "verify":
            verify_database(args.database)
            print(f"Integridade e chaves estrangeiras aprovadas: {Path(args.database).resolve()}")
        else:
            self_test()
    except (OSError, sqlite3.Error, ValueError, AssertionError) as error:
        print(f"Falha: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
