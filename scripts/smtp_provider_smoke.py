"""Smoke test manual do provedor Gmail SMTP do Conta+.

Execute somente após configurar MAIL_* e SMTP_TEST_RECIPIENT no ambiente.
O script envia uma única mensagem para o destinatário de teste configurado.
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from email_service import enviar_email

if os.getenv("MAIL_SERVER", "").strip().lower() != "smtp.gmail.com":
    raise SystemExit("Configure MAIL_SERVER=smtp.gmail.com para testar o Gmail.")
if not os.getenv("MAIL_USERNAME", "").strip() or not os.getenv("MAIL_PASSWORD", "").strip():
    raise SystemExit("Configure MAIL_USERNAME e MAIL_PASSWORD com a conta e senha de app do Google.")

destinatario = os.getenv("SMTP_TEST_RECIPIENT", "").strip()
if not destinatario:
    raise SystemExit("Defina SMTP_TEST_RECIPIENT com uma caixa de teste autorizada.")

marcador = uuid.uuid4().hex
enviar_email(
    destinatario,
    f"Conta+ - teste operacional Gmail SMTP {marcador}",
    (
        "Esta e uma mensagem automatica de teste da configuracao Gmail SMTP do Conta+.\n"
        f"Identificador: {marcador}\n"
        "Se recebeu esta mensagem, o servidor SMTP aceitou a entrega."
    ),
)
print("Servidor Gmail SMTP aceitou a mensagem de teste.")
print("Confira a caixa de entrada e a pasta de spam do destinatario configurado.")
