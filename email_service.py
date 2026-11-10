"""Envio SMTP de mensagens transacionais do Conta+."""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr


def _validar_configuracao_gmail(
    servidor, porta, usuario, senha, remetente, usar_tls, usar_ssl
):
    """Valida o uso de uma conta Gmail dedicada com senha de app."""
    if servidor.lower() != "smtp.gmail.com":
        return senha

    usuario = usuario.strip().lower()
    if not usuario.endswith("@gmail.com"):
        raise RuntimeError("Para Gmail SMTP, MAIL_USERNAME deve ser uma conta @gmail.com.")
    if not senha.strip():
        raise RuntimeError(
            "Configure MAIL_PASSWORD com uma senha de app do Google, não a senha normal."
        )

    endereco_remetente = parseaddr(remetente)[1].strip().lower()
    if endereco_remetente != usuario:
        raise RuntimeError(
            "O endereço de MAIL_FROM deve corresponder a MAIL_USERNAME no Gmail."
        )

    transporte_valido = (
        (porta == 587 and usar_tls and not usar_ssl)
        or (porta == 465 and usar_ssl and not usar_tls)
    )
    if not transporte_valido:
        raise RuntimeError(
            "Gmail SMTP exige porta 587 com STARTTLS ou porta 465 com SSL; "
            "habilite somente uma opção de criptografia."
        )

    # O Google exibe a senha de app agrupada em blocos; espaços não fazem parte da senha.
    return "".join(senha.split())


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

    if modo_autenticacao != "password":
        if modo_autenticacao == "oauth2":
            raise RuntimeError(
                "A autenticação OAuth2 da Microsoft foi removida. "
                "Configure Gmail SMTP com uma senha de app do Google."
            )
        raise RuntimeError("MAIL_AUTH_MODE deve ser password.")

    senha = _validar_configuracao_gmail(
        servidor, porta, usuario, senha, remetente, usar_tls, usar_ssl
    )
    if not usuario:
        # Servidores SMTP locais, como Mailpit, podem operar sem autenticação.
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
