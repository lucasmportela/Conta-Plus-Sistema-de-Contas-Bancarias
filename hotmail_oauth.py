"""Autenticação OAuth2/XOAUTH2 para contas pessoais Hotmail/Outlook.com."""

import os
import tempfile
import threading
from pathlib import Path

import msal
from cryptography.fernet import Fernet, InvalidToken

AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ("https://outlook.office.com/SMTP.Send",)
_CACHE_LOCK = threading.RLock()


def carregar_cache_configurada():
    """Carrega o cache MSAL criptografado e as configurações da conta."""
    client_id = os.getenv("MS_CLIENT_ID", "").strip()
    username = os.getenv("MAIL_USERNAME", "").strip().lower()
    encryption_key = os.getenv("MS_TOKEN_CACHE_ENCRYPTION_KEY", "").strip()

    if not client_id:
        raise RuntimeError("Configure MS_CLIENT_ID para autenticar a conta Hotmail.")
    if not username:
        raise RuntimeError("Configure MAIL_USERNAME com o endereço completo @hotmail.com.")
    if not encryption_key:
        raise RuntimeError("Configure MS_TOKEN_CACHE_ENCRYPTION_KEY para proteger o cache OAuth.")

    try:
        fernet = Fernet(encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise RuntimeError(
            "MS_TOKEN_CACHE_ENCRYPTION_KEY inválida. Gere uma chave Fernet válida."
        ) from None

    default_path = (
        "/data/hotmail_msal_cache.enc"
        if os.getenv("APP_ENV", "").strip().lower() == "production"
        else "instance/hotmail_msal_cache.enc"
    )
    cache_path = Path(os.getenv("MS_TOKEN_CACHE_FILE", default_path))
    cache = msal.SerializableTokenCache()

    if cache_path.exists():
        try:
            serialized = fernet.decrypt(cache_path.read_bytes()).decode("utf-8")
            cache.deserialize(serialized)
        except (InvalidToken, UnicodeDecodeError, ValueError):
            raise RuntimeError(
                "Não foi possível abrir o cache OAuth criptografado. "
                "Confira a chave e o arquivo configurados."
            ) from None

    return cache, cache_path, fernet, client_id, username


def salvar_cache_criptografado(cache, cache_path, fernet):
    """Persiste o cache MSAL criptografado, com escrita atômica e permissão restrita."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    conteudo = fernet.encrypt(cache.serialize().encode("utf-8"))
    descritor, temporario = tempfile.mkstemp(
        prefix=f".{cache_path.name}.",
        suffix=".tmp",
        dir=str(cache_path.parent),
    )
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        try:
            os.chmod(temporario, 0o600)
        except OSError:
            pass
        os.replace(temporario, cache_path)
        try:
            os.chmod(cache_path, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def obter_token_acesso():
    """Obtém ou renova silenciosamente o token delegado SMTP.Send."""
    with _CACHE_LOCK:
        cache, cache_path, fernet, client_id, username = carregar_cache_configurada()
        aplicacao = msal.PublicClientApplication(
            client_id,
            authority=AUTHORITY,
            token_cache=cache,
        )
        contas = aplicacao.get_accounts(username=username)
        if not contas:
            raise RuntimeError(
                "A conta Hotmail ainda não foi autorizada. "
                "Execute python scripts/setup_hotmail_oauth.py."
            )

        resultado = aplicacao.acquire_token_silent(
            list(SCOPES),
            account=contas[0],
        )
        if cache.has_state_changed:
            salvar_cache_criptografado(cache, cache_path, fernet)

        if not resultado or not resultado.get("access_token"):
            raise RuntimeError(
                "Não foi possível renovar a autorização OAuth do Hotmail. "
                "Execute novamente python scripts/setup_hotmail_oauth.py."
            )

        return resultado["access_token"]
