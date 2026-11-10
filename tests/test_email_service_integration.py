"""Teste SMTP de integração com Mailpit local; não envia e-mails externos."""
import os
import time
import unittest
import urllib.request
import uuid

from email_service import enviar_email

SMTP_TEST_RECIPIENT = os.getenv("SMTP_TEST_RECIPIENT")
MAILPIT_API_URL = os.getenv(
    "MAILPIT_API_URL", "http://127.0.0.1:8025/api/v1/messages"
)


@unittest.skipUnless(
    SMTP_TEST_RECIPIENT and os.getenv("MAIL_SERVER"),
    "Configure SMTP_TEST_RECIPIENT e MAIL_SERVER para testar SMTP.",
)
class TestEmailServiceIntegration(unittest.TestCase):
    def test_envia_e_confirma_recebimento_no_mailpit(self):
        marcador = uuid.uuid4().hex
        assunto = f"Conta+ SMTP integration {marcador}"
        corpo = f"Mensagem de teste operacional. Referência: {marcador}"
        enviar_email(SMTP_TEST_RECIPIENT, assunto, corpo)

        recebido = False
        ultima_resposta = ""
        for _ in range(30):
            requisicao = urllib.request.Request(
                MAILPIT_API_URL, headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(requisicao, timeout=5) as resposta:
                ultima_resposta = resposta.read().decode("utf-8")
            if marcador in ultima_resposta:
                recebido = True
                break
            time.sleep(0.5)
        self.assertTrue(
            recebido,
            msg="A mensagem não apareceu na API do Mailpit. Resposta: "
                + ultima_resposta[:1000],
        )


if __name__ == "__main__":
    unittest.main()
