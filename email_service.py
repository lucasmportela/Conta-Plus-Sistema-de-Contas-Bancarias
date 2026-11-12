"""Envio de e-mails transacionais via SMTP local/Gmail ou API HTTPS Brevo."""

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, parseaddr


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

    return "".join(senha.split())


def _enviar_por_brevo(destinatario, assunto, corpo, remetente, api_key):
    """Envia uma mensagem transacional pela API HTTPS da Brevo."""
    nome_remetente, endereco_remetente = parseaddr(remetente)
    nome_destinatario, endereco_destinatario = parseaddr(destinatario)
    if not endereco_remetente or not endereco_destinatario:
        raise RuntimeError("Remetente ou destinatário inválido para o envio pela Brevo.")

    payload = {
        "sender": {"name": nome_remetente or "Conta+", "email": endereco_remetente},
        "to": [{
            "email": endereco_destinatario,
            **({"name": nome_destinatario} if nome_destinatario else {}),
        }],
        "subject": assunto,
        "textContent": corpo,
        "replyTo": {"email": endereco_remetente},
    }
    requisicao = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        # nosec B310: endpoint is a fixed HTTPS URL, never derived from user input.
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            if resposta.status not in (200, 201, 202):
                raise RuntimeError(
                    f"A API Brevo retornou um status inesperado: {resposta.status}."
                )
    except urllib.error.HTTPError as erro:
        # Não propaga headers, chave de API ou corpo bruto do provedor para os logs.
        raise RuntimeError(
            f"A API Brevo recusou o envio (HTTP {erro.code}). "
            "Confira a chave, o remetente validado e os limites da conta."
        ) from None
    except urllib.error.URLError:
        raise RuntimeError("Não foi possível conectar à API Brevo por HTTPS.") from None


def enviar_email(destinatario, assunto, corpo):
    remetente = os.getenv("MAIL_FROM", "").strip()
    if not remetente:
        raise RuntimeError("Configure MAIL_FROM para habilitar o envio de e-mails.")

    provedor = os.getenv("MAIL_PROVIDER", "smtp").strip().lower()
    if provedor == "brevo":
        api_key = os.getenv("BREVO_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Configure BREVO_API_KEY para usar o envio pela API Brevo.")
        _enviar_por_brevo(destinatario, assunto, corpo, remetente, api_key)
        return
    if provedor != "smtp":
        raise RuntimeError("MAIL_PROVIDER deve ser smtp ou brevo.")

    servidor = os.getenv("MAIL_SERVER", "").strip()
    if not servidor:
        raise RuntimeError("Configure MAIL_SERVER para habilitar o envio SMTP.")

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
