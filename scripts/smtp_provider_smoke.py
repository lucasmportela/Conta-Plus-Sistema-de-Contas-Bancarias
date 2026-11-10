"""Smoke test manual do provedor SMTP real do Conta+.

Execute somente após configurar MAIL_* e SMTP_TEST_RECIPIENT no ambiente.
O script envia uma única mensagem para o destinatário de teste configurado.
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from email_service import enviar_email

if os.getenv("MAIL_AUTH_MODE", "").strip().lower() != "oauth2":
    raise SystemExit("Configure MAIL_AUTH_MODE=oauth2 para testar o Hotmail.")

destinatario = os.getenv("SMTP_TEST_RECIPIENT", "").strip()
if not destinatario:
    raise SystemExit("Defina SMTP_TEST_RECIPIENT com uma caixa de teste autorizada.")

marcador = uuid.uuid4().hex
enviar_email(
    destinatario,
    f"Conta+ - teste operacional SMTP {marcador}",
    (
        "Esta e uma mensagem automatica de teste da configuracao SMTP do Conta+.\n"
        f"Identificador: {marcador}\n"
        "Se recebeu esta mensagem, o servidor SMTP aceitou a entrega."
    ),
)
print("Servidor SMTP aceitou a mensagem de teste.")
print("Confira a caixa de entrada e a pasta de spam do destinatario configurado.")
