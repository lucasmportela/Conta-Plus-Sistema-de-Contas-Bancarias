"""Testes de integração das rotas e dos controles de acesso do Conta+."""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database

_ORIGINAL_DB_PATH = database.DB_PATH
_TEST_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(prefix="conta_plus_api_tests_")
database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "conta_plus_test.db"

import app as app_module


class TestApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_module.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = _ORIGINAL_DB_PATH
        _TEST_DATABASE_DIRECTORY.cleanup()

    def setUp(self):
        database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "conta_plus_test.db"
        with database.conectar() as conn:
            conn.execute("DROP TABLE IF EXISTS transacoes")
            conn.execute("DROP TABLE IF EXISTS contas")
            conn.execute("DROP TABLE IF EXISTS usuarios")
        database.inicializar_banco()
        self.client = app_module.app.test_client()
        self.registrar(self.client)

    def token_csrf(self, client):
        return client.get("/api/csrf").get_json()["csrf_token"]

    def post_json(self, client, rota, dados):
        return client.post(
            rota,
            json=dados,
            headers={"X-CSRF-Token": self.token_csrf(client)},
        )

    def registrar(
        self,
        client,
        nome="Lucas Martins",
        email="lucas@example.com",
        senha="SenhaSegura123",
    ):
        return self.post_json(
            client,
            "/api/register",
            {"nome": nome, "email": email, "senha": senha},
        )

    def criar_conta(
        self,
        client=None,
        nome="Lucas Martins",
        numero="00001",
        saldo_inicial="0.00",
    ):
        client = client or self.client
        response = self.post_json(
            client,
            "/api/contas",
            {"nome": nome, "numero": numero, "saldo_inicial": saldo_inicial},
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
        self.assertIn("form-login", pagina.get_data(as_text=True))

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")

    def test_rotas_de_dados_exigem_autenticacao(self):
        anonimo = app_module.app.test_client()
        self.assertEqual(anonimo.get("/api/resumo").status_code, 401)
        self.assertEqual(anonimo.get("/api/contas").status_code, 401)
        self.assertEqual(anonimo.get("/api/me").status_code, 401)
        self.assertEqual(
            self.post_json(anonimo, "/api/contas", {
                "nome": "Conta Anônima", "numero": "ANON", "saldo_inicial": "0"
            }).status_code,
            401,
        )

    def test_cadastro_login_logout_e_hash_da_senha(self):
        cliente = app_module.app.test_client()
        cadastro = self.registrar(
            cliente, nome="Marina Souza", email="marina@example.com",
            senha="OutraSenha123",
        )
        self.assertEqual(cadastro.status_code, 201)
        self.assertEqual(cadastro.get_json()["usuario"]["email"], "marina@example.com")

        with database.conectar() as conn:
            usuario = conn.execute(
                "SELECT senha_hash FROM usuarios WHERE email = ?",
                ("marina@example.com",),
            ).fetchone()
        self.assertNotEqual(usuario["senha_hash"], "OutraSenha123")
        self.assertTrue(usuario["senha_hash"].startswith("scrypt:"))

        logout = self.post_json(cliente, "/api/logout", {})
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(cliente.get("/api/me").status_code, 401)

        senha_incorreta = self.post_json(
            cliente, "/api/login",
            {"email": "marina@example.com", "senha": "senha-errada"},
        )
        self.assertEqual(senha_incorreta.status_code, 401)

        login = self.post_json(
            cliente, "/api/login",
            {"email": "MARINA@example.com", "senha": "OutraSenha123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(cliente.get("/api/me").get_json()["usuario"]["nome"], "Marina Souza")

    def test_cadastro_valida_email_senha_e_email_duplicado(self):
        cliente = app_module.app.test_client()
        senha_fraca = self.registrar(
            cliente, email="fraca@example.com", senha="123",
        )
        self.assertEqual(senha_fraca.status_code, 400)

        cadastro = self.registrar(
            cliente, email="duplicado@example.com", senha="SenhaSegura123",
        )
        self.assertEqual(cadastro.status_code, 201)

        outro_cliente = app_module.app.test_client()
        duplicado = self.registrar(
            outro_cliente, email="DUPLICADO@example.com", senha="SenhaSegura456",
        )
        self.assertEqual(duplicado.status_code, 409)

    def test_requisicoes_mutaveis_exigem_token_csrf(self):
        anonimo = app_module.app.test_client()
        resposta = anonimo.post(
            "/api/register",
            json={"nome": "Teste", "email": "teste@example.com", "senha": "SenhaSegura123"},
        )
        self.assertEqual(resposta.status_code, 403)

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

        with database.conectar() as conn:
            registro = conn.execute(
                "SELECT owner_id FROM contas WHERE id = ?", (conta["id"],)
            ).fetchone()
        self.assertEqual(registro["owner_id"], self.client.get("/api/me").get_json()["usuario"]["id"])

    def test_criar_conta_rejeita_dados_invalidos(self):
        casos_invalidos = [
            {"nome": "Lu", "numero": "10001", "saldo_inicial": "0"},
            {"nome": "Lucas", "numero": "", "saldo_inicial": "0"},
            {"nome": "Lucas", "numero": "10003", "saldo_inicial": "-1"},
            {"nome": "Lucas", "numero": "10004", "saldo_inicial": "abc"},
        ]
        for dados in casos_invalidos:
            with self.subTest(dados=dados):
                response = self.post_json(self.client, "/api/contas", dados)
                self.assertEqual(response.status_code, 400)
                self.assertIn("erro", response.get_json())
        self.assertEqual(self.client.get("/api/contas").get_json(), [])

    def test_numero_de_conta_duplicado_e_rejeitado(self):
        self.criar_conta(numero="00010")
        response = self.post_json(
            self.client,
            "/api/contas",
            {"nome": "Marina Souza", "numero": "00010", "saldo_inicial": "50.00"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.client.get("/api/contas").get_json()), 1)

    def test_deposito_atualiza_saldo_e_extrato(self):
        conta = self.criar_conta(numero="00020", saldo_inicial="100.00")
        deposito = self.post_json(
            self.client, f"/api/contas/{conta['id']}/depositos", {"valor": "25.50"}
        )
        self.assertEqual(deposito.status_code, 200)
        self.assertEqual(deposito.get_json()["saldo"], "125.50")

        extrato = self.client.get(f"/api/contas/{conta['id']}/extrato").get_json()
        self.assertEqual(extrato["conta"]["saldo"], "125.50")
        self.assertEqual(extrato["transacoes"][0]["tipo"], "DEPOSITO")
        self.assertEqual(extrato["transacoes"][0]["saldo_anterior"], "100.00")
        self.assertEqual(extrato["transacoes"][0]["saldo_atual"], "125.50")

    def test_saque_valido_e_saldo_insuficiente_nao_altera_banco(self):
        conta = self.criar_conta(numero="00030", saldo_inicial="100.00")
        saque = self.post_json(
            self.client, f"/api/contas/{conta['id']}/saques", {"valor": "30.00"}
        )
        self.assertEqual(saque.status_code, 200)
        self.assertEqual(saque.get_json()["saldo"], "70.00")

        saque_invalido = self.post_json(
            self.client, f"/api/contas/{conta['id']}/saques", {"valor": "100.00"}
        )
        self.assertEqual(saque_invalido.status_code, 400)
        extrato = self.client.get(f"/api/contas/{conta['id']}/extrato").get_json()
        self.assertEqual(extrato["conta"]["saldo"], "70.00")
        self.assertEqual(len(extrato["transacoes"]), 2)

    def test_transferencia_atualiza_as_duas_contas_e_os_extratos(self):
        origem = self.criar_conta(
            nome="Lucas Martins", numero="00040", saldo_inicial="100.00"
        )
        destino = self.criar_conta(
            nome="Marina Souza", numero="00041", saldo_inicial="20.00"
        )
        response = self.post_json(
            self.client,
            f"/api/contas/{origem['id']}/transferencias",
            {"conta_destino_id": destino["id"], "valor": "30.00"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["saldo_origem"], "70.00")
        self.assertEqual(response.get_json()["saldo_destino"], "50.00")

        extrato_origem = self.client.get(f"/api/contas/{origem['id']}/extrato").get_json()
        extrato_destino = self.client.get(f"/api/contas/{destino['id']}/extrato").get_json()
        self.assertEqual(extrato_origem["transacoes"][0]["tipo"], "TRANSFERENCIA ENVIADA")
        self.assertEqual(extrato_destino["transacoes"][0]["tipo"], "TRANSFERENCIA RECEBIDA")

    def test_transferencia_para_a_propria_conta_e_rejeitada(self):
        conta = self.criar_conta(numero="00050", saldo_inicial="100.00")
        response = self.post_json(
            self.client,
            f"/api/contas/{conta['id']}/transferencias",
            {"conta_destino_id": conta["id"], "valor": "10.00"},
        )
        self.assertEqual(response.status_code, 400)

    def test_transferencia_rejeita_destino_invalido_ou_inexistente(self):
        conta = self.criar_conta(numero="00060", saldo_inicial="100.00")
        sem_destino = self.post_json(
            self.client, f"/api/contas/{conta['id']}/transferencias", {"valor": "10.00"}
        )
        self.assertEqual(sem_destino.status_code, 400)

        destino_inexistente = self.post_json(
            self.client,
            f"/api/contas/{conta['id']}/transferencias",
            {"conta_destino_id": 9999, "valor": "10.00"},
        )
        self.assertEqual(destino_inexistente.status_code, 404)

    def test_usuario_nao_acessa_contas_extratos_ou_operacoes_de_terceiros(self):
        conta_a = self.criar_conta(numero="USUARIO-A", saldo_inicial="100.00")

        cliente_b = app_module.app.test_client()
        cadastro_b = self.registrar(
            cliente_b, nome="Marina Souza", email="marina@example.com",
            senha="SenhaSegura456",
        )
        self.assertEqual(cadastro_b.status_code, 201)
        conta_b = self.criar_conta(
            cliente_b, nome="Marina Souza", numero="USUARIO-B", saldo_inicial="50.00"
        )

        lista_b = cliente_b.get("/api/contas").get_json()
        self.assertEqual([item["id"] for item in lista_b], [conta_b["id"]])
        self.assertEqual(cliente_b.get(f"/api/contas/{conta_a['id']}/extrato").status_code, 404)

        deposito = self.post_json(
            cliente_b, f"/api/contas/{conta_a['id']}/depositos", {"valor": "10.00"}
        )
        self.assertEqual(deposito.status_code, 404)

        transferencia = self.post_json(
            self.client,
            f"/api/contas/{conta_a['id']}/transferencias",
            {"conta_destino_id": conta_b["id"], "valor": "10.00"},
        )
        self.assertEqual(transferencia.status_code, 404)

        saldo_a = self.client.get(f"/api/contas/{conta_a['id']}/extrato").get_json()["conta"]["saldo"]
        saldo_b = cliente_b.get(f"/api/contas/{conta_b['id']}/extrato").get_json()["conta"]["saldo"]
        self.assertEqual(saldo_a, "100.00")
        self.assertEqual(saldo_b, "50.00")

    def test_resumo_considera_somente_dados_do_usuario(self):
        self.criar_conta(numero="00070", saldo_inicial="100.00")
        segunda = self.criar_conta(numero="00071", saldo_inicial="0.00")
        deposito = self.post_json(
            self.client, f"/api/contas/{segunda['id']}/depositos", {"valor": "5.00"}
        )
        self.assertEqual(deposito.status_code, 200)

        cliente_b = app_module.app.test_client()
        self.registrar(
            cliente_b, nome="Marina Souza", email="resumo@example.com",
            senha="SenhaSegura456",
        )
        self.criar_conta(cliente_b, nome="Marina", numero="00072", saldo_inicial="900.00")

        resumo = self.client.get("/api/resumo").get_json()
        self.assertEqual(resumo["total_contas"], 2)
        self.assertEqual(resumo["saldo_consolidado"], "105.00")
        self.assertEqual(resumo["total_movimentacoes"], 2)

        resumo_b = cliente_b.get("/api/resumo").get_json()
        self.assertEqual(resumo_b["total_contas"], 1)
        self.assertEqual(resumo_b["saldo_consolidado"], "900.00")
        self.assertEqual(resumo_b["total_movimentacoes"], 1)

    def test_rotas_de_conta_inexistente_retornam_404(self):
        deposito = self.post_json(
            self.client, "/api/contas/9999/depositos", {"valor": "10.00"}
        )
        extrato = self.client.get("/api/contas/9999/extrato")
        self.assertEqual(deposito.status_code, 404)
        self.assertEqual(extrato.status_code, 404)


if __name__ == "__main__":
    unittest.main()
