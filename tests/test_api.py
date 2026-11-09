"""Testes de integração das rotas Flask com o banco SQLite.

A aplicação inicializa o banco ao importar app.py. Por isso, este módulo
redireciona database.DB_PATH para um arquivo temporário antes da importação,
evitando qualquer alteração no banco usado pela aplicação local.
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database

_ORIGINAL_DB_PATH = database.DB_PATH
_TEST_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(
    prefix="conta_plus_api_tests_"
)
database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "conta_plus_test.db"

import app as app_module


class TestApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_module.app.config.update(TESTING=True)

    def test_debug_desativado_por_padrao(self):
        self.assertFalse(app_module.app.debug)

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = _ORIGINAL_DB_PATH
        _TEST_DATABASE_DIRECTORY.cleanup()

    def setUp(self):
        # Cada teste começa com um banco limpo e isolado.
        database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "conta_plus_test.db"
        with database.conectar() as conn:
            conn.execute("DROP TABLE IF EXISTS transacoes")
            conn.execute("DROP TABLE IF EXISTS contas")
        database.inicializar_banco()
        self.client = app_module.app.test_client()

    def criar_conta(
        self,
        nome="Lucas Martins",
        numero="00001",
        saldo_inicial="0.00",
    ):
        response = self.client.post(
            "/api/contas",
            json={
                "nome": nome,
                "numero": numero,
                "saldo_inicial": saldo_inicial,
            },
        )
        self.assertEqual(
            response.status_code,
            201,
            msg=f"Não foi possível criar a conta: {response.get_json()}",
        )
        return response.get_json()["conta"]

    def test_pagina_inicial_e_health(self):
        pagina = self.client.get("/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("Conta+", pagina.get_data(as_text=True))

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")

    def test_criar_conta_persiste_e_registra_saldo_inicial(self):
        conta = self.criar_conta(saldo_inicial="125.50")

        lista = self.client.get("/api/contas")
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(len(lista.get_json()), 1)
        self.assertEqual(lista.get_json()[0]["id"], conta["id"])
        self.assertEqual(lista.get_json()[0]["saldo"], "125.50")

        extrato = self.client.get(f"/api/contas/{conta['id']}/extrato")
        self.assertEqual(extrato.status_code, 200)
        self.assertEqual(len(extrato.get_json()["transacoes"]), 1)
        transacao = extrato.get_json()["transacoes"][0]
        self.assertEqual(transacao["tipo"], "DEPOSITO INICIAL")
        self.assertEqual(transacao["valor"], "125.50")

    def test_criar_conta_rejeita_dados_invalidos(self):
        casos_invalidos = [
            {"nome": "Lu", "numero": "10001", "saldo_inicial": "0"},
            {"nome": "Lucas", "numero": "", "saldo_inicial": "0"},
            {"nome": "Lucas", "numero": "10003", "saldo_inicial": "-1"},
            {"nome": "Lucas", "numero": "10004", "saldo_inicial": "abc"},
        ]

        for dados in casos_invalidos:
            with self.subTest(dados=dados):
                response = self.client.post("/api/contas", json=dados)
                self.assertEqual(response.status_code, 400)
                self.assertIn("erro", response.get_json())

        self.assertEqual(self.client.get("/api/contas").get_json(), [])

    def test_numero_de_conta_duplicado_e_rejeitado(self):
        self.criar_conta(numero="00010")

        response = self.client.post(
            "/api/contas",
            json={
                "nome": "Marina Souza",
                "numero": "00010",
                "saldo_inicial": "50.00",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Já existe", response.get_json()["erro"])
        self.assertEqual(len(self.client.get("/api/contas").get_json()), 1)

    def test_deposito_atualiza_saldo_e_extrato(self):
        conta = self.criar_conta(numero="00020", saldo_inicial="100.00")

        deposito = self.client.post(
            f"/api/contas/{conta['id']}/depositos",
            json={"valor": "25.50"},
        )

        self.assertEqual(deposito.status_code, 200)
        self.assertEqual(deposito.get_json()["saldo"], "125.50")

        extrato = self.client.get(
            f"/api/contas/{conta['id']}/extrato"
        ).get_json()
        self.assertEqual(extrato["conta"]["saldo"], "125.50")
        self.assertEqual(extrato["transacoes"][0]["tipo"], "DEPOSITO")
        self.assertEqual(extrato["transacoes"][0]["valor"], "25.50")
        self.assertEqual(extrato["transacoes"][0]["saldo_anterior"], "100.00")
        self.assertEqual(extrato["transacoes"][0]["saldo_atual"], "125.50")

    def test_saque_valido_e_saldo_insuficiente_nao_altera_banco(self):
        conta = self.criar_conta(numero="00030", saldo_inicial="100.00")

        saque = self.client.post(
            f"/api/contas/{conta['id']}/saques",
            json={"valor": "30.00"},
        )
        self.assertEqual(saque.status_code, 200)
        self.assertEqual(saque.get_json()["saldo"], "70.00")

        saque_invalido = self.client.post(
            f"/api/contas/{conta['id']}/saques",
            json={"valor": "100.00"},
        )
        self.assertEqual(saque_invalido.status_code, 400)

        extrato = self.client.get(
            f"/api/contas/{conta['id']}/extrato"
        ).get_json()
        self.assertEqual(extrato["conta"]["saldo"], "70.00")
        # Depósito inicial + saque válido. O saque recusado não gera transação.
        self.assertEqual(len(extrato["transacoes"]), 2)
        self.assertEqual(extrato["transacoes"][0]["tipo"], "SAQUE")

    def test_transferencia_atualiza_as_duas_contas_e_os_extratos(self):
        origem = self.criar_conta(
            nome="Lucas Martins",
            numero="00040",
            saldo_inicial="100.00",
        )
        destino = self.criar_conta(
            nome="Marina Souza",
            numero="00041",
            saldo_inicial="20.00",
        )

        response = self.client.post(
            f"/api/contas/{origem['id']}/transferencias",
            json={
                "conta_destino_id": destino["id"],
                "valor": "30.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["saldo_origem"], "70.00")
        self.assertEqual(response.get_json()["saldo_destino"], "50.00")

        contas = {
            conta["id"]: conta
            for conta in self.client.get("/api/contas").get_json()
        }
        self.assertEqual(contas[origem["id"]]["saldo"], "70.00")
        self.assertEqual(contas[destino["id"]]["saldo"], "50.00")

        extrato_origem = self.client.get(
            f"/api/contas/{origem['id']}/extrato"
        ).get_json()
        extrato_destino = self.client.get(
            f"/api/contas/{destino['id']}/extrato"
        ).get_json()

        self.assertEqual(
            extrato_origem["transacoes"][0]["tipo"],
            "TRANSFERENCIA ENVIADA",
        )
        self.assertEqual(
            extrato_destino["transacoes"][0]["tipo"],
            "TRANSFERENCIA RECEBIDA",
        )
        self.assertEqual(
            extrato_origem["transacoes"][0]["valor"],
            "30.00",
        )
        self.assertEqual(
            extrato_destino["transacoes"][0]["valor"],
            "30.00",
        )

    def test_transferencia_para_a_propria_conta_e_rejeitada(self):
        conta = self.criar_conta(numero="00050", saldo_inicial="100.00")

        response = self.client.post(
            f"/api/contas/{conta['id']}/transferencias",
            json={
                "conta_destino_id": conta["id"],
                "valor": "10.00",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["erro"],
            "A conta de origem e destino devem ser diferentes.",
        )

    def test_transferencia_rejeita_destino_invalido_ou_inexistente(self):
        conta = self.criar_conta(numero="00060", saldo_inicial="100.00")

        sem_destino = self.client.post(
            f"/api/contas/{conta['id']}/transferencias",
            json={"valor": "10.00"},
        )
        self.assertEqual(sem_destino.status_code, 400)
        self.assertEqual(
            sem_destino.get_json()["erro"],
            "Informe uma conta de destino válida.",
        )

        destino_inexistente = self.client.post(
            f"/api/contas/{conta['id']}/transferencias",
            json={"conta_destino_id": 9999, "valor": "10.00"},
        )
        self.assertEqual(destino_inexistente.status_code, 404)

        extrato = self.client.get(
            f"/api/contas/{conta['id']}/extrato"
        ).get_json()
        self.assertEqual(extrato["conta"]["saldo"], "100.00")
        self.assertEqual(len(extrato["transacoes"]), 1)

    def test_rotas_de_conta_inexistente_retornam_404(self):
        deposito = self.client.post(
            "/api/contas/9999/depositos",
            json={"valor": "10.00"},
        )
        extrato = self.client.get("/api/contas/9999/extrato")

        self.assertEqual(deposito.status_code, 404)
        self.assertEqual(extrato.status_code, 404)
        self.assertIn("erro", deposito.get_json())
        self.assertIn("erro", extrato.get_json())

    def test_resumo_reflete_saldos_e_movimentacoes(self):
        self.criar_conta(numero="00070", saldo_inicial="100.00")
        segunda = self.criar_conta(numero="00071", saldo_inicial="0.00")

        deposito = self.client.post(
            f"/api/contas/{segunda['id']}/depositos",
            json={"valor": "5.00"},
        )
        self.assertEqual(deposito.status_code, 200)

        resumo = self.client.get("/api/resumo")
        self.assertEqual(resumo.status_code, 200)
        self.assertEqual(resumo.get_json()["total_contas"], 2)
        self.assertEqual(resumo.get_json()["saldo_consolidado"], "105.00")
        self.assertEqual(resumo.get_json()["total_movimentacoes"], 2)


if __name__ == "__main__":
    unittest.main()
