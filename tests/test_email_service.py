"""Testes do envio SMTP e dos canais criptografados."""
import os
import unittest
from unittest.mock import patch

from email_service import enviar_email


class FakeSMTP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self, **kwargs):
        self.calls.append(("starttls", kwargs))

    def login(self, usuario, senha):
        self.calls.append(("login", usuario, senha))

    def auth(self, mecanismo, authobject, initial_response_ok=True):
        resposta = authobject(None)
        self.calls.append(("auth", mecanismo, resposta, initial_response_ok))
        return 235, b"2.7.0 Authentication successful"

    def send_message(self, mensagem):
        self.calls.append(("send_message", mensagem))


class TestEmailService(unittest.TestCase):
    def configuracao(self, **extra):
        valores = {
            "MAIL_SERVER": "smtp.example.test",
            "MAIL_PORT": "587",
            "MAIL_USERNAME": "usuario",
            "MAIL_PASSWORD": "senha-de-teste",
            "MAIL_FROM": "Conta+ <nao-responda@example.test>",
            "MAIL_USE_TLS": "true",
            "MAIL_USE_SSL": "false",
        }
        valores.update(extra)
        return patch.dict(os.environ, valores, clear=True)

    def test_envia_email_com_starttls_e_autenticacao(self):
        cliente = FakeSMTP()
        contexto = object()
        with self.configuracao(), \
             patch("email_service.smtplib.SMTP", return_value=cliente) as smtp, \
             patch("email_service.ssl.create_default_context", return_value=contexto):
            enviar_email("destino@example.test", "Assunto", "Corpo")

        smtp.assert_called_once_with("smtp.example.test", 587, timeout=10)
        self.assertEqual(cliente.calls[0], ("ehlo",))
        self.assertEqual(cliente.calls[1], ("starttls", {"context": contexto}))
        self.assertEqual(cliente.calls[2], ("ehlo",))
        self.assertEqual(cliente.calls[3], ("login", "usuario", "senha-de-teste"))
        self.assertEqual(cliente.calls[4][0], "send_message")
        mensagem = cliente.calls[4][1]
        self.assertEqual(mensagem["To"], "destino@example.test")
        self.assertEqual(mensagem["Subject"], "Assunto")

    def test_envia_email_com_ssl_direto(self):
        cliente = FakeSMTP()
        contexto = object()
        with self.configuracao(MAIL_PORT="465", MAIL_USE_TLS="false", MAIL_USE_SSL="true"), \
             patch("email_service.smtplib.SMTP_SSL", return_value=cliente) as smtp_ssl, \
             patch("email_service.ssl.create_default_context", return_value=contexto):
            enviar_email("destino@example.test", "Assunto", "Corpo")

        smtp_ssl.assert_called_once_with(
            "smtp.example.test", 465, timeout=10, context=contexto
        )
        self.assertEqual(cliente.calls[0], ("login", "usuario", "senha-de-teste"))
        self.assertEqual(cliente.calls[1][0], "send_message")

    def test_rejeita_configuracao_sem_servidor_ou_remetente(self):
        with self.configuracao(MAIL_SERVER=""):
            with self.assertRaisesRegex(RuntimeError, "MAIL_SERVER"):
                enviar_email("destino@example.test", "Assunto", "Corpo")

        with self.configuracao(MAIL_FROM=""):
            with self.assertRaisesRegex(RuntimeError, "MAIL_SERVER"):
                enviar_email("destino@example.test", "Assunto", "Corpo")

    def test_rejeita_starttls_e_ssl_ativos_ao_mesmo_tempo(self):
        with self.configuracao(MAIL_USE_TLS="true", MAIL_USE_SSL="true"):
            with self.assertRaisesRegex(RuntimeError, "não podem estar ativos juntos"):
                enviar_email("destino@example.test", "Assunto", "Corpo")

    def test_envia_email_hotmail_com_oauth2_xoauth2(self):
        cliente = FakeSMTP()
        contexto = object()
        configuracao = self.configuracao(
            MAIL_AUTH_MODE="oauth2",
            MAIL_SERVER="smtp-mail.outlook.com",
            MAIL_PORT="587",
            MAIL_USERNAME="conta@hotmail.com",
            MAIL_PASSWORD="",
            MAIL_FROM="Conta+ <conta@hotmail.com>",
            MAIL_USE_TLS="true",
            MAIL_USE_SSL="false",
        )
        with configuracao, \
             patch("email_service.smtplib.SMTP", return_value=cliente) as smtp, \
             patch("email_service.ssl.create_default_context", return_value=contexto), \
             patch("hotmail_oauth.obter_token_acesso", return_value="token-falso-de-teste"):
            enviar_email("destino@example.test", "Assunto", "Corpo")

        smtp.assert_called_once_with("smtp-mail.outlook.com", 587, timeout=10)
        self.assertEqual(cliente.calls[0], ("ehlo",))
        self.assertEqual(cliente.calls[1], ("starttls", {"context": contexto}))
        self.assertEqual(cliente.calls[2], ("ehlo",))
        autenticacao = cliente.calls[3]
        self.assertEqual(autenticacao[0:2], ("auth", "XOAUTH2"))
        self.assertEqual(
            autenticacao[2],
            "user=conta@hotmail.com\x01auth=Bearer token-falso-de-teste\x01\x01",
        )
        self.assertTrue(autenticacao[3])
        self.assertEqual(cliente.calls[4][0], "send_message")

    def test_hotmail_rejeita_remetente_diferente_da_conta_autorizada(self):
        with self.configuracao(
            MAIL_AUTH_MODE="oauth2",
            MAIL_SERVER="smtp-mail.outlook.com",
            MAIL_USERNAME="conta@hotmail.com",
            MAIL_FROM="Conta+ <outra@hotmail.com>",
        ):
            with self.assertRaisesRegex(RuntimeError, "deve corresponder"):
                enviar_email("destino@example.test", "Assunto", "Corpo")

    def test_hotmail_nao_aceita_autenticacao_por_senha(self):
        with self.configuracao(
            MAIL_AUTH_MODE="password",
            MAIL_SERVER="smtp-mail.outlook.com",
            MAIL_USERNAME="conta@hotmail.com",
            MAIL_PASSWORD="senha-normal",
            MAIL_FROM="conta@hotmail.com",
        ):
            with self.assertRaisesRegex(RuntimeError, "exigem autenticação OAuth2"):
                enviar_email("destino@example.test", "Assunto", "Corpo")

    def test_hotmail_rejeita_smtp_sem_starttls(self):
        with self.configuracao(
            MAIL_AUTH_MODE="oauth2",
            MAIL_SERVER="smtp-mail.outlook.com",
            MAIL_USERNAME="conta@hotmail.com",
            MAIL_FROM="conta@hotmail.com",
            MAIL_USE_TLS="false",
            MAIL_USE_SSL="false",
        ):
            with self.assertRaisesRegex(RuntimeError, "exige STARTTLS"):
                enviar_email("destino@example.test", "Assunto", "Corpo")


if __name__ == "__main__":
    unittest.main()
