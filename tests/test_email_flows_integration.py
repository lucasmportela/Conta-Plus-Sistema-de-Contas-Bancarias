"""Fluxos completos de e-mail do Conta+ usando SMTP local Mailpit.

Valida cadastro, confirmação, reenvio de confirmação e recuperação de senha
sem enviar mensagens reais para a Internet.
"""
import json
import os
import re
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL_DB_PATH = database.DB_PATH
_TEST_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(prefix="conta_plus_mail_flow_")
database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "conta_plus_mail_flow.db"

import app as app_module

MAILPIT_API_URL = os.getenv(
    "MAILPIT_API_URL", "http://127.0.0.1:8025/api/v1/messages"
)


@unittest.skipUnless(
    os.getenv("MAIL_SERVER") and os.getenv("SMTP_TEST_RECIPIENT"),
    "Configure MAIL_SERVER e SMTP_TEST_RECIPIENT para testar os fluxos de e-mail.",
)
class TestEmailFlowsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_module.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = _ORIGINAL_DB_PATH
        _TEST_DATABASE_DIRECTORY.cleanup()

    def setUp(self):
        database.DB_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / f"mail_flow_{time.time_ns()}.db"
        database.inicializar_banco()
        self.client = app_module.app.test_client()

    def post_json(self, path, payload):
        csrf = self.client.get("/api/csrf").get_json()["csrf_token"]
        return self.client.post(
            path, json=payload, headers={"X-CSRF-Token": csrf}
        )

    def mailpit_messages(self):
        request = urllib.request.Request(
            MAILPIT_API_URL, headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, list):
            return payload
        return payload.get("messages", [])

    def latest_message(self, subject, recipient):
        last_error = None
        for _ in range(30):
            try:
                messages = self.mailpit_messages()
                for message in messages:
                    serialized = json.dumps(message, ensure_ascii=False).lower()
                    if subject.lower() in serialized and recipient.lower() in serialized:
                        message_id = message.get("ID") or message.get("id")
                        if message_id:
                            messages_base = MAILPIT_API_URL.removesuffix("/messages")
                            detail_url = messages_base + "/message/" + str(message_id)
                            request = urllib.request.Request(
                                detail_url, headers={"Accept": "application/json"}
                            )
                            with urllib.request.urlopen(request, timeout=5) as response:
                                return json.loads(response.read().decode("utf-8"))
            except Exception as error:
                last_error = error
            time.sleep(0.5)
        self.fail(f"Mensagem '{subject}' não chegou ao Mailpit. Erro: {last_error}")

    def token_from_message(self, message):
        body = message.get("Text", message.get("text", ""))
        for line in body.splitlines():
            if "token=" not in line:
                continue
            token = parse_qs(urlparse(line.strip()).query).get("token")
            if token:
                return token[0]
        self.fail(
            "A mensagem não contém um parâmetro token. "
            f"Corpo recebido: {body[:1500]!r}"
        )

    def test_cadastro_confirmacao_login_e_recuperacao_com_email_real_no_mailpit(self):
        recipient = f"cadastro-{time.time_ns()}@conta-plus.test"
        registration = self.post_json(
            "/api/register",
            {"nome": "Usuário Teste", "email": recipient, "senha": "SenhaSegura123"},
        )
        self.assertEqual(registration.status_code, 202)

        confirmation_email = self.latest_message(
            "Confirme seu e-mail", recipient
        )
        confirmation_token = self.token_from_message(confirmation_email)
        confirmation = self.post_json(
            "/api/verify-email", {"token": confirmation_token}
        )
        self.assertEqual(confirmation.status_code, 200)

        login = self.post_json(
            "/api/login", {"email": recipient, "senha": "SenhaSegura123"}
        )
        self.assertEqual(login.status_code, 200)

        reset_request = self.post_json(
            "/api/password-reset-request", {"email": recipient}
        )
        self.assertEqual(reset_request.status_code, 200)
        reset_email = self.latest_message("Redefinição de senha", recipient)
        reset_token = self.token_from_message(reset_email)

        reset = self.post_json(
            "/api/password-reset",
            {"token": reset_token, "senha": "NovaSenhaSegura456"},
        )
        self.assertEqual(reset.status_code, 200)

        old_password = self.post_json(
            "/api/login", {"email": recipient, "senha": "SenhaSegura123"}
        )
        self.assertEqual(old_password.status_code, 401)
        new_password = self.post_json(
            "/api/login", {"email": recipient, "senha": "NovaSenhaSegura456"}
        )
        self.assertEqual(new_password.status_code, 200)

    def test_reenvio_de_confirmacao_envia_novo_link_e_invalida_o_anterior(self):
        recipient = f"reenvio-{time.time_ns()}@conta-plus.test"
        registration = self.post_json(
            "/api/register",
            {"nome": "Usuário Reenvio", "email": recipient, "senha": "SenhaSegura123"},
        )
        self.assertEqual(registration.status_code, 202)

        first_email = self.latest_message("Confirme seu e-mail", recipient)
        first_token = self.token_from_message(first_email)

        resend = self.post_json(
            "/api/resend-verification", {"email": recipient}
        )
        self.assertEqual(resend.status_code, 200)

        second_email = self.latest_message("Confirme seu e-mail", recipient)
        second_token = self.token_from_message(second_email)
        self.assertNotEqual(first_token, second_token)

        old_link = self.post_json("/api/verify-email", {"token": first_token})
        self.assertEqual(old_link.status_code, 400)
        new_link = self.post_json("/api/verify-email", {"token": second_token})
        self.assertEqual(new_link.status_code, 200)


if __name__ == "__main__":
    unittest.main()
