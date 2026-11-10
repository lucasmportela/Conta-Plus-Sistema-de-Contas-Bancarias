"""Envio SMTP de mensagens transacionais do Conta+."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def enviar_email(destinatario, assunto, corpo):
    servidor = os.getenv("MAIL_SERVER", "").strip()
    remetente = os.getenv("MAIL_FROM", "").strip()
    if not servidor or not remetente:
        raise RuntimeError(
            "Configure MAIL_SERVER e MAIL_FROM para habilitar o envio de e-mails."
        )

    porta = int(os.getenv("MAIL_PORT", "587"))
    usuario = os.getenv("MAIL_USERNAME", "").strip()
    senha = os.getenv("MAIL_PASSWORD", "")
    usar_tls = os.getenv("MAIL_USE_TLS", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    usar_ssl = os.getenv("MAIL_USE_SSL", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if usar_tls and usar_ssl:
        raise RuntimeError("MAIL_USE_TLS e MAIL_USE_SSL não podem estar ativos juntos.")

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    contexto = ssl.create_default_context()
    if usar_ssl:
        with smtplib.SMTP_SSL(
            servidor, porta, timeout=10, context=contexto
        ) as cliente:
            if usuario:
                cliente.login(usuario, senha)
            cliente.send_message(mensagem)
    else:
        with smtplib.SMTP(servidor, porta, timeout=10) as cliente:
            cliente.ehlo()
            if usar_tls:
                cliente.starttls(context=contexto)
                cliente.ehlo()
            if usuario:
                cliente.login(usuario, senha)
            cliente.send_message(mensagem)
