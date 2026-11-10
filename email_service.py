"""Envio SMTP de mensagens transacionais do Conta+."""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr


def _enviar_com_oauth2(cliente, usuario):
    """Autentica no SMTP Outlook.com usando SASL XOAUTH2."""
    from hotmail_oauth import obter_token_acesso

    token = obter_token_acesso()
    resposta = f"user={usuario}\x01auth=Bearer {token}\x01\x01"
    try:
        codigo, _mensagem = cliente.auth(
            "XOAUTH2",
            lambda _desafio: resposta,
            initial_response_ok=True,
        )
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "A Microsoft recusou a autenticação OAuth2. "
            "Confira a conta autorizada, o consentimento SMTP.Send e o cache OAuth."
        ) from None
    if codigo != 235:
        raise RuntimeError(
            "O servidor Outlook.com não confirmou a autenticação OAuth2."
        )


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
    modo_autenticacao = os.getenv("MAIL_AUTH_MODE", "password").strip().lower()
    usar_tls = os.getenv("MAIL_USE_TLS", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    usar_ssl = os.getenv("MAIL_USE_SSL", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }

    if usar_tls and usar_ssl:
        raise RuntimeError("MAIL_USE_TLS e MAIL_USE_SSL não podem estar ativos juntos.")

    if modo_autenticacao not in {"password", "oauth2"}:
        raise RuntimeError("MAIL_AUTH_MODE deve ser password ou oauth2.")

    if modo_autenticacao == "oauth2":
        if servidor.lower() != "smtp-mail.outlook.com" or porta != 587:
            raise RuntimeError(
                "Para Hotmail, use smtp-mail.outlook.com na porta 587."
            )
        if not usar_tls or usar_ssl:
            raise RuntimeError(
                "O Hotmail exige STARTTLS: MAIL_USE_TLS=true e MAIL_USE_SSL=false."
            )
        if not usuario.lower().endswith("@hotmail.com"):
            raise RuntimeError("MAIL_USERNAME deve ser a conta pessoal @hotmail.com.")
        endereco_remetente = parseaddr(remetente)[1].strip().lower()
        if endereco_remetente != usuario.lower():
            raise RuntimeError(
                "O endereço de MAIL_FROM deve corresponder à conta Hotmail autorizada."
            )
    elif modo_autenticacao == "password" and not usuario:
        # Provedores SMTP sem autenticação continuam permitidos.
        senha = ""

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
            if modo_autenticacao == "oauth2":
                _enviar_com_oauth2(cliente, usuario)
            elif usuario:
                cliente.login(usuario, senha)
            cliente.send_message(mensagem)
    else:
        with smtplib.SMTP(servidor, porta, timeout=10) as cliente:
            cliente.ehlo()
            if usar_tls:
                cliente.starttls(context=contexto)
                cliente.ehlo()
            if modo_autenticacao == "oauth2":
                _enviar_com_oauth2(cliente, usuario)
            elif usuario:
                cliente.login(usuario, senha)
            cliente.send_message(mensagem)
