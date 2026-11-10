from decimal import Decimal
from functools import wraps
from pathlib import Path
import hashlib
import hmac
import os
import time
import secrets
import sqlite3
from datetime import timedelta
from hashlib import sha256
from urllib.parse import urlencode, urljoin

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from flask import Flask, jsonify, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from conta import Conta, validar_valor
from database import (
    conectar, inicializar_banco, obter_conta, listar_contas, salvar_transacao,
)
from email_service import enviar_email
from rate_limit import LoginRateLimiter

app = Flask(__name__, template_folder="templates", static_folder="static")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY")
if APP_ENV == "production" and (not SECRET_KEY or len(SECRET_KEY) < 32):
    raise RuntimeError("Defina SECRET_KEY forte (mínimo de 32 caracteres) no ambiente de produção.")

TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
TRUSTED_HOSTS = [
    host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()
]
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
if APP_ENV == "production":
    if TRUSTED_PROXY_HOPS < 1:
        raise RuntimeError("Configure TRUSTED_PROXY_HOPS com a quantidade exata de proxies confiáveis.")
    if not TRUSTED_HOSTS:
        raise RuntimeError("Configure TRUSTED_HOSTS com os domínios permitidos.")
    if not PUBLIC_BASE_URL.startswith("https://"):
        raise RuntimeError("Configure PUBLIC_BASE_URL com a URL HTTPS pública.")
    public_host = PUBLIC_BASE_URL.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
    if public_host not in {host.lower() for host in TRUSTED_HOSTS}:
        raise RuntimeError("O domínio de PUBLIC_BASE_URL também deve constar em TRUSTED_HOSTS.")
    if not os.getenv("MAIL_SERVER") or not os.getenv("MAIL_FROM"):
        raise RuntimeError("Configure MAIL_SERVER e MAIL_FROM para envio de e-mails.")
    mail_tls = os.getenv("MAIL_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    mail_ssl = os.getenv("MAIL_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
    if mail_tls == mail_ssl:
        raise RuntimeError("Em produção, habilite exatamente uma opção: MAIL_USE_TLS ou MAIL_USE_SSL.")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)

DEBUG = (
    APP_ENV != "production"
    and os.getenv("FLASK_DEBUG", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)

app.config.update(
    SECRET_KEY=SECRET_KEY,
    DEBUG=DEBUG,
    JSON_AS_ASCII=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(APP_ENV == "production"),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=1024 * 1024,
    LOGIN_MAX_ATTEMPTS=int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")),
    LOGIN_WINDOW_SECONDS=int(os.getenv("LOGIN_WINDOW_SECONDS", "900")),
    LOGIN_BLOCK_SECONDS=int(os.getenv("LOGIN_BLOCK_SECONDS", "900")),
    LOGIN_ATTEMPT_RETENTION_SECONDS=int(os.getenv("LOGIN_ATTEMPT_RETENTION_SECONDS", "86400")),
    EMAIL_VERIFICATION_TTL=int(os.getenv("EMAIL_VERIFICATION_TTL", "3600")),
    PASSWORD_RESET_TTL=int(os.getenv("PASSWORD_RESET_TTL", "1800")),
    TRUSTED_HOSTS=TRUSTED_HOSTS if APP_ENV == "production" else None,
    PREFERRED_URL_SCHEME="https" if APP_ENV == "production" else "http",
)
app.json.ensure_ascii = False

if APP_ENV == "production":
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=TRUSTED_PROXY_HOPS,
        x_proto=TRUSTED_PROXY_HOPS,
        x_host=TRUSTED_PROXY_HOPS,
        x_port=TRUSTED_PROXY_HOPS,
    )

if min(
    app.config["LOGIN_MAX_ATTEMPTS"],
    app.config["LOGIN_WINDOW_SECONDS"],
    app.config["LOGIN_BLOCK_SECONDS"],
    app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    app.config["EMAIL_VERIFICATION_TTL"],
    app.config["PASSWORD_RESET_TTL"],
) < 1:
    raise RuntimeError("As configurações de segurança devem ser maiores que zero.")

rate_limiter = LoginRateLimiter(
    backend=os.getenv("LOGIN_RATE_LIMIT_BACKEND", "sqlite").strip().lower(),
    redis_url=os.getenv("REDIS_URL"),
)
inicializar_banco()

MENSAGEM_CADASTRO = (
    "Se o endereço puder ser cadastrado, enviaremos um link de confirmação. "
    "Se não receber, use a opção de reenviar a confirmação."
)


def resposta_erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


def requer_autenticacao(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return resposta_erro("Autenticação necessária.", 401)
        with conectar() as conn:
            usuario = conn.execute(
                "SELECT session_version FROM usuarios WHERE id = ? AND email_verified = 1",
                (usuario_id,),
            ).fetchone()
        if (
            usuario is None
            or usuario["session_version"] != session.get("session_version")
        ):
            session.clear()
            return resposta_erro("Sessão expirada ou revogada. Entre novamente.", 401)
        return funcao(*args, **kwargs)
    return wrapper


def iniciar_sessao(usuario_id, session_version):
    session.clear()
    session["usuario_id"] = usuario_id
    session["session_version"] = session_version
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True


def hash_token(token):
    return sha256(token.encode("utf-8")).hexdigest()


def criar_token_seguro():
    return secrets.token_urlsafe(32)


def url_publica(endpoint, token):
    base = PUBLIC_BASE_URL or request.host_url.rstrip("/")
    caminho = url_for(endpoint, _external=False) + "?" + urlencode({"token": token})
    return urljoin(base + "/", caminho.lstrip("/"))


def enviar_confirmacao_email(email, token):
    link = url_publica("confirmar_email", token)
    enviar_email(
        email,
        "Confirme seu e-mail — Conta+",
        "Para ativar seu acesso ao Conta+, abra o link abaixo. "
        f"Ele expira em {app.config['EMAIL_VERIFICATION_TTL'] // 60} minutos.\n\n{link}\n\n"
        "Se você não solicitou este cadastro, ignore esta mensagem.",
    )


def enviar_recuperacao_senha(email, token):
    link = url_publica("redefinir_senha", token)
    enviar_email(
        email,
        "Redefinição de senha — Conta+",
        "Recebemos uma solicitação para redefinir sua senha. "
        f"O link expira em {app.config['PASSWORD_RESET_TTL'] // 60} minutos "
        "e pode ser usado uma única vez.\n\n"
        f"{link}\n\nSe você não solicitou a alteração, ignore esta mensagem.",
    )


def criar_token_de_conta(tabela, usuario_id, validade):
    token = criar_token_seguro()
    agora = int(time.time())
    with conectar() as conn:
        conn.execute(f"DELETE FROM {tabela} WHERE user_id = ?", (usuario_id,))
        conn.execute(
            f"INSERT INTO {tabela} (token_hash, user_id, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (hash_token(token), usuario_id, agora + validade, agora),
        )
    return token


@app.before_request
def aplicar_controles_de_transporte():
    if APP_ENV == "production":
        if not request.is_secure:
            return resposta_erro("A conexão HTTPS é obrigatória.", 400)
        host = request.host.split(":", 1)[0].lower()
        if host not in {item.lower() for item in TRUSTED_HOSTS}:
            return resposta_erro("Host não autorizado.", 400)
    return None


@app.after_request
def adicionar_cabecalhos_de_seguranca(resposta):
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    resposta.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'",
    )
    resposta.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    resposta.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.path.startswith("/api/") or request.path in {"/confirmar-email", "/redefinir-senha"}:
        resposta.headers.setdefault("Cache-Control", "no-store")
    if request.path in {"/confirmar-email", "/redefinir-senha"}:
        resposta.headers["Referrer-Policy"] = "no-referrer"
    if request.is_secure:
        resposta.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000"
        )
    return resposta


@app.before_request
def proteger_requisicoes_mutaveis():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        esperado = session.get("csrf_token")
        recebido = request.headers.get("X-CSRF-Token", "")
        if not esperado or not recebido or not hmac.compare_digest(esperado, recebido):
            return resposta_erro("Token CSRF ausente ou inválido.", 403)


def carregar_conta(conn, conta_id, usuario_id):
    registro = obter_conta(conn, conta_id, usuario_id)
    if registro is None:
        return None
    return Conta(
        id=registro["id"],
        nome=registro["nome"],
        numero=registro["numero"],
        saldo=Decimal(registro["saldo"]),
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "mensagem": "API do Sistema de Contas Bancárias funcionando.",
    })


@app.get("/api/csrf")
def api_csrf():
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify({"csrf_token": session["csrf_token"]})


@app.post("/api/register")
def api_registrar():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", "")).strip()
    email = str(dados.get("email", "")).strip().lower()
    senha = str(dados.get("senha", ""))

    if len(nome) < 3 or len(nome) > 80:
        return resposta_erro("O nome deve ter entre 3 e 80 caracteres.")
    if len(email) > 254 or email.count("@") != 1 or "." not in email.rsplit("@", 1)[-1]:
        return resposta_erro("Informe um endereço de e-mail válido.")
    if len(senha) < 10 or len(senha) > 128:
        return resposta_erro("A senha deve ter entre 10 e 128 caracteres.")

    chave_cadastro = chave_tentativas_login("", "register")
    agora = int(time.time())
    bloqueio = rate_limiter.blocked_seconds(
        chave_cadastro, agora, app.config["LOGIN_WINDOW_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)
    bloqueio = rate_limiter.record_failure(
        chave_cadastro, agora, app.config["LOGIN_MAX_ATTEMPTS"],
        app.config["LOGIN_WINDOW_SECONDS"], app.config["LOGIN_BLOCK_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)

    try:
        with conectar() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                (nome, email, generate_password_hash(senha, method="scrypt")),
            )
            usuario_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # A resposta não revela se o endereço já está cadastrado.
        return jsonify({"mensagem": MENSAGEM_CADASTRO}), 202

    token = criar_token_de_conta(
        "email_verification_tokens", usuario_id,
        app.config["EMAIL_VERIFICATION_TTL"],
    )
    try:
        enviar_confirmacao_email(email, token)
    except Exception:
        # Não diferencia falha de entrega de um e-mail já cadastrado.
        # O usuário pode solicitar o reenvio pela tela de login.
        app.logger.exception("Falha ao enviar e-mail de confirmação.")

    return jsonify({"mensagem": MENSAGEM_CADASTRO}), 202


@app.post("/api/verify-email")
def api_confirmar_email():
    dados = request.get_json(silent=True) or {}
    token = str(dados.get("token", ""))
    if not token or len(token) > 200:
        return resposta_erro("Link de confirmação inválido ou expirado.", 400)

    agora = int(time.time())
    with conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        registro = conn.execute(
            """
            SELECT user_id FROM email_verification_tokens
            WHERE token_hash = ? AND expires_at > ? AND used_at IS NULL
            """,
            (hash_token(token), agora),
        ).fetchone()
        if registro is None:
            return resposta_erro("Link de confirmação inválido ou expirado.", 400)
        conn.execute(
            "UPDATE usuarios SET email_verified = 1 WHERE id = ?",
            (registro["user_id"],),
        )
        conn.execute(
            "UPDATE email_verification_tokens SET used_at = ? WHERE token_hash = ?",
            (agora, hash_token(token)),
        )
        conn.execute(
            "DELETE FROM email_verification_tokens WHERE user_id = ? AND token_hash != ?",
            (registro["user_id"], hash_token(token)),
        )
    return jsonify({"mensagem": "E-mail confirmado. Agora você pode entrar."})


@app.post("/api/resend-verification")
def api_reenviar_confirmacao():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email", "")).strip().lower()
    chave = chave_tentativas_login(email, "resend-verification")
    agora = int(time.time())
    bloqueio = rate_limiter.blocked_seconds(
        chave, agora, app.config["LOGIN_WINDOW_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)
    bloqueio = rate_limiter.record_failure(
        chave, agora, app.config["LOGIN_MAX_ATTEMPTS"],
        app.config["LOGIN_WINDOW_SECONDS"], app.config["LOGIN_BLOCK_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT id, email FROM usuarios WHERE email = ? AND email_verified = 0",
            (email,),
        ).fetchone()
    if usuario:
        token = criar_token_de_conta(
            "email_verification_tokens", usuario["id"],
            app.config["EMAIL_VERIFICATION_TTL"],
        )
        try:
            enviar_confirmacao_email(usuario["email"], token)
        except Exception:
            app.logger.exception("Falha ao reenviar confirmação de e-mail.")
    return jsonify({
        "mensagem": "Se houver um cadastro pendente para esse endereço, enviaremos um novo link."
    })


@app.post("/api/password-reset-request")
def api_solicitar_recuperacao():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email", "")).strip().lower()
    chave = chave_tentativas_login(email, "password-reset")
    agora = int(time.time())
    bloqueio = rate_limiter.blocked_seconds(
        chave, agora, app.config["LOGIN_WINDOW_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)
    bloqueio = rate_limiter.record_failure(
        chave, agora, app.config["LOGIN_MAX_ATTEMPTS"],
        app.config["LOGIN_WINDOW_SECONDS"], app.config["LOGIN_BLOCK_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT id, email FROM usuarios WHERE email = ? AND email_verified = 1",
            (email,),
        ).fetchone()
    if usuario:
        token = criar_token_de_conta(
            "password_reset_tokens", usuario["id"],
            app.config["PASSWORD_RESET_TTL"],
        )
        try:
            enviar_recuperacao_senha(usuario["email"], token)
        except Exception:
            app.logger.exception("Falha ao enviar recuperação de senha.")
    return jsonify({
        "mensagem": "Se existir uma conta confirmada para esse endereço, enviaremos instruções de recuperação."
    })


@app.post("/api/password-reset")
def api_redefinir_senha():
    dados = request.get_json(silent=True) or {}
    token = str(dados.get("token", ""))
    senha = str(dados.get("senha", ""))
    if len(senha) < 10 or len(senha) > 128:
        return resposta_erro("A senha deve ter entre 10 e 128 caracteres.")
    if not token or len(token) > 200:
        return resposta_erro("Link de recuperação inválido ou expirado.", 400)

    agora = int(time.time())
    token_hash = hash_token(token)
    with conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        registro = conn.execute(
            """
            SELECT user_id FROM password_reset_tokens
            WHERE token_hash = ? AND expires_at > ? AND used_at IS NULL
            """,
            (token_hash, agora),
        ).fetchone()
        if registro is None:
            return resposta_erro("Link de recuperação inválido ou expirado.", 400)
        conn.execute(
            "UPDATE usuarios SET senha_hash = ?, session_version = session_version + 1 "
            "WHERE id = ? AND email_verified = 1",
            (generate_password_hash(senha, method="scrypt"), registro["user_id"]),
        )
        conn.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?",
            (agora, token_hash),
        )
        conn.execute(
            "DELETE FROM password_reset_tokens WHERE user_id = ? AND token_hash != ?",
            (registro["user_id"], token_hash),
        )
    return jsonify({"mensagem": "Senha redefinida. Entre novamente com a nova senha."})


@app.get("/confirmar-email")
def confirmar_email():
    return render_template("index.html")


@app.get("/redefinir-senha")
def redefinir_senha():
    return render_template("index.html")


@app.get("/privacidade")
def politica_privacidade():
    return render_template("privacy.html")

def chave_tentativas_login(email, acao="login"):
    """Gera uma chave HMAC sem armazenar e-mail ou endereço IP em texto puro."""
    origem = request.remote_addr or "desconhecido"
    identificador = f"{acao}\0{origem}\0{email}".encode("utf-8")
    segredo = app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(segredo, identificador, hashlib.sha256).hexdigest()


def resposta_bloqueio_login(segundos):
    resposta, status = resposta_erro(
        "Muitas tentativas de login. Aguarde antes de tentar novamente.",
        429,
    )
    resposta.headers["Retry-After"] = str(max(1, int(segundos)))
    return resposta, status


@app.post("/api/login")
def api_login():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email", "")).strip().lower()
    senha = str(dados.get("senha", ""))

    chave = chave_tentativas_login(email)
    agora = int(time.time())
    bloqueio = rate_limiter.blocked_seconds(
        chave, agora, app.config["LOGIN_WINDOW_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)

    with conectar() as conn:
        usuario = conn.execute(
            "SELECT id, nome, email, senha_hash, email_verified, session_version "
            "FROM usuarios WHERE email = ?",
            (email,),
        ).fetchone()

    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        bloqueio = rate_limiter.record_failure(
            chave, agora, app.config["LOGIN_MAX_ATTEMPTS"],
            app.config["LOGIN_WINDOW_SECONDS"], app.config["LOGIN_BLOCK_SECONDS"],
            app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
        )
        if bloqueio:
            return resposta_bloqueio_login(bloqueio)
        return resposta_erro("E-mail ou senha incorretos.", 401)

    if not usuario["email_verified"]:
        return resposta_erro(
            "Confirme seu e-mail antes de entrar. Se necessário, solicite um novo link.",
            403,
        )

    rate_limiter.reset(chave)
    iniciar_sessao(usuario["id"], usuario["session_version"])
    return jsonify({
        "mensagem": "Login realizado com sucesso.",
        "usuario": {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"]},
    })

@app.post("/api/logout")
@requer_autenticacao
def api_logout():
    session.clear()
    return jsonify({"mensagem": "Sessão encerrada com sucesso."})


@app.get("/api/me")
@requer_autenticacao
def api_me():
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT id, nome, email FROM usuarios WHERE id = ?",
            (session["usuario_id"],),
        ).fetchone()
    if usuario is None:
        session.clear()
        return resposta_erro("Sessão inválida. Entre novamente.", 401)
    return jsonify({"usuario": dict(usuario)})




@app.get("/api/account/export")
@requer_autenticacao
def api_exportar_dados():
    """Baixa uma cópia JSON dos dados pertencentes ao usuário autenticado."""
    usuario_id = session["usuario_id"]
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT nome, email, email_verified, criado_em FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        if usuario is None:
            session.clear()
            return resposta_erro("Sessão inválida. Entre novamente.", 401)

        contas = conn.execute(
            """
            SELECT id, nome, numero, saldo, criada_em
            FROM contas
            WHERE owner_id = ?
            ORDER BY id
            """,
            (usuario_id,),
        ).fetchall()
        transacoes = conn.execute(
            """
            SELECT
                t.id,
                t.conta_id,
                t.tipo,
                CASE
                    WHEN t.conta_relacionada_id IS NOT NULL
                         AND (relacionada.id IS NULL OR relacionada.owner_id != ?)
                    THEN 'Movimentação relacionada a uma conta externa'
                    ELSE t.descricao
                END AS descricao,
                t.valor,
                t.saldo_anterior,
                t.saldo_atual,
                CASE
                    WHEN relacionada.owner_id = ? THEN t.conta_relacionada_id
                    ELSE NULL
                END AS conta_relacionada_id,
                t.criado_em
            FROM transacoes AS t
            INNER JOIN contas AS propria ON propria.id = t.conta_id
            LEFT JOIN contas AS relacionada ON relacionada.id = t.conta_relacionada_id
            WHERE propria.owner_id = ?
            ORDER BY t.id
            """,
            (usuario_id, usuario_id, usuario_id),
        ).fetchall()

    exportacao = {
        "produto": "Conta+",
        "versao_exportacao": 1,
        "exportado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "usuario": {
            "nome": usuario["nome"],
            "email": usuario["email"],
            "email_confirmado": bool(usuario["email_verified"]),
            "criado_em": usuario["criado_em"],
        },
        "contas": [dict(conta) for conta in contas],
        "transacoes": [dict(transacao) for transacao in transacoes],
        "observacao": (
            "Esta cópia contém somente dados associados às contas do usuário autenticado. "
            "Senhas, hashes de senha, tokens, sessões e contadores de segurança não são incluídos."
        ),
    }

    resposta = jsonify(exportacao)
    nome_arquivo = time.strftime("conta-plus-dados-%Y%m%d.json", time.gmtime())
    resposta.headers["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    resposta.headers["Cache-Control"] = "no-store, private"
    resposta.headers["Pragma"] = "no-cache"
    return resposta


@app.get("/api/resumo")
@requer_autenticacao
def resumo():
    usuario_id = session["usuario_id"]
    with conectar() as conn:
        contas = listar_contas(conn, usuario_id)
        total_saldo = sum(
            (Decimal(item["saldo"]) for item in contas),
            Decimal("0.00"),
        )
        total_movimentacoes = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM transacoes AS t
            INNER JOIN contas AS c ON c.id = t.conta_id
            WHERE c.owner_id = ?
            """,
            (usuario_id,),
        ).fetchone()["total"]
    return jsonify({
        "total_contas": len(contas),
        "saldo_consolidado": f"{total_saldo:.2f}",
        "total_movimentacoes": total_movimentacoes,
    })


@app.get("/api/contas")
@requer_autenticacao
def api_listar_contas():
    with conectar() as conn:
        contas = listar_contas(conn, session["usuario_id"])
    return jsonify([dict(conta) for conta in contas])


@app.post("/api/contas")
@requer_autenticacao
def api_criar_conta():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", "")).strip()
    numero = str(dados.get("numero", "")).strip()
    try:
        saldo_inicial = validar_valor(
            dados.get("saldo_inicial", "0"),
            permitir_zero=True,
        )
    except ValueError as erro:
        return resposta_erro(str(erro))

    if len(nome) < 3 or len(nome) > 80:
        return resposta_erro("O nome deve ter entre 3 e 80 caracteres.")
    if not numero or len(numero) > 20:
        return resposta_erro("Informe um número de conta válido.")

    try:
        with conectar() as conn:
            cursor = conn.execute(
                """
                INSERT INTO contas (owner_id, nome, numero, saldo)
                VALUES (?, ?, ?, ?)
                """,
                (session["usuario_id"], nome, numero, f"{saldo_inicial:.2f}"),
            )
            conta_id = cursor.lastrowid
            if saldo_inicial > 0:
                salvar_transacao(
                    conn, conta_id, "DEPOSITO INICIAL", "Depósito inicial",
                    saldo_inicial, Decimal("0.00"), saldo_inicial
                )
    except sqlite3.IntegrityError:
        return resposta_erro("Já existe uma conta com esse número.", 409)

    return jsonify({
        "mensagem": "Conta criada com sucesso.",
        "conta": {
            "id": conta_id,
            "nome": nome,
            "numero": numero,
            "saldo": f"{saldo_inicial:.2f}",
        },
    }), 201


def processar_operacao(conta_id, tipo):
    dados = request.get_json(silent=True) or {}
    try:
        valor = validar_valor(dados.get("valor"))
    except ValueError as erro:
        return resposta_erro(str(erro))

    usuario_id = session["usuario_id"]
    try:
        with conectar() as conn:
            conta = carregar_conta(conn, conta_id, usuario_id)
            if conta is None:
                return resposta_erro("Conta não encontrada.", 404)

            if tipo == "deposito":
                movimento = conta.realizar_deposito(valor)
                descricao = "Depósito"
                tipo_db = "DEPOSITO"
            else:
                movimento = conta.realizar_saque(valor)
                descricao = "Saque"
                tipo_db = "SAQUE"

            conn.execute(
                "UPDATE contas SET saldo = ? WHERE id = ? AND owner_id = ?",
                (f"{conta.saldo:.2f}", conta.id, usuario_id),
            )
            salvar_transacao(
                conn, conta.id, tipo_db, descricao, valor,
                movimento["saldo_anterior"], movimento["saldo_atual"]
            )
    except ValueError as erro:
        return resposta_erro(str(erro))

    return jsonify({
        "mensagem": f"{descricao} realizado com sucesso.",
        "saldo": f"{conta.saldo:.2f}",
    })


@app.post("/api/contas/<int:conta_id>/depositos")
@requer_autenticacao
def api_depositar(conta_id):
    return processar_operacao(conta_id, "deposito")


@app.post("/api/contas/<int:conta_id>/saques")
@requer_autenticacao
def api_sacar(conta_id):
    return processar_operacao(conta_id, "saque")


@app.post("/api/contas/<int:conta_id>/transferencias")
@requer_autenticacao
def api_transferir(conta_id):
    dados = request.get_json(silent=True) or {}
    destino_id = dados.get("conta_destino_id")
    if destino_id is None or str(destino_id).strip() == "":
        return resposta_erro("Informe uma conta de destino válida.")

    try:
        destino_id = int(destino_id)
    except (TypeError, ValueError):
        return resposta_erro("Informe uma conta de destino válida.")

    try:
        valor = validar_valor(dados.get("valor"))
    except ValueError as erro:
        return resposta_erro(str(erro))

    if destino_id == conta_id:
        return resposta_erro("A conta de origem e destino devem ser diferentes.")

    usuario_id = session["usuario_id"]
    try:
        with conectar() as conn:
            origem = carregar_conta(conn, conta_id, usuario_id)
            destino = carregar_conta(conn, destino_id, usuario_id)
            if origem is None or destino is None:
                return resposta_erro("Conta de origem ou destino não encontrada.", 404)

            origem.transferir(destino, valor)

            conn.execute(
                "UPDATE contas SET saldo = ? WHERE id = ? AND owner_id = ?",
                (f"{origem.saldo:.2f}", origem.id, usuario_id),
            )
            conn.execute(
                "UPDATE contas SET saldo = ? WHERE id = ? AND owner_id = ?",
                (f"{destino.saldo:.2f}", destino.id, usuario_id),
            )

            salvar_transacao(
                conn, origem.id, "TRANSFERENCIA ENVIADA",
                f"Transferência enviada para {destino.nome} (conta {destino.numero})",
                valor, origem.saldo + valor, origem.saldo, destino.id
            )
            salvar_transacao(
                conn, destino.id, "TRANSFERENCIA RECEBIDA",
                f"Transferência recebida de {origem.nome} (conta {origem.numero})",
                valor, destino.saldo - valor, destino.saldo, origem.id
            )
    except ValueError as erro:
        return resposta_erro(str(erro))

    return jsonify({
        "mensagem": "Transferência realizada com sucesso.",
        "saldo_origem": f"{origem.saldo:.2f}",
        "saldo_destino": f"{destino.saldo:.2f}",
    })


@app.get("/api/contas/<int:conta_id>/extrato")
@requer_autenticacao
def api_extrato(conta_id):
    usuario_id = session["usuario_id"]
    with conectar() as conn:
        conta = obter_conta(conn, conta_id, usuario_id)
        if conta is None:
            return resposta_erro("Conta não encontrada.", 404)
        transacoes = conn.execute(
            """
            SELECT id, tipo, descricao, valor, saldo_anterior, saldo_atual, criado_em
            FROM transacoes
            WHERE conta_id = ?
            ORDER BY id DESC
            """,
            (conta_id,),
        ).fetchall()

    return jsonify({
        "conta": dict(conta),
        "transacoes": [dict(item) for item in transacoes],
    })


@app.delete("/api/account")
@requer_autenticacao
def api_excluir_conta():
    dados = request.get_json(silent=True) or {}
    senha_atual = str(dados.get("senha_atual", ""))
    confirmacao = str(dados.get("confirmacao", ""))

    if not senha_atual or len(senha_atual) > 128:
        return resposta_erro("Informe sua senha atual.")
    if confirmacao != "EXCLUIR":
        return resposta_erro('Digite exatamente "EXCLUIR" para confirmar.')

    usuario_id = session["usuario_id"]
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT email FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
    if usuario is None:
        session.clear()
        return resposta_erro("Sessão inválida. Entre novamente.", 401)

    chave = chave_tentativas_login(usuario["email"], "account-delete")
    agora = int(time.time())
    bloqueio = rate_limiter.blocked_seconds(
        chave, agora, app.config["LOGIN_WINDOW_SECONDS"],
        app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
    )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)

    senha_invalida = False
    usuario_ausente = False
    with conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        credencial = conn.execute(
            "SELECT senha_hash FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        if credencial is None:
            usuario_ausente = True
        elif not check_password_hash(credencial["senha_hash"], senha_atual):
            senha_invalida = True
        else:
            # Remove referências a contas do titular em históricos de terceiros
            # antes de apagar as contas, sem expor novamente nome ou número.
            conn.execute(
                """
                UPDATE transacoes
                SET conta_relacionada_id = NULL,
                    descricao = 'Movimentação relacionada a uma conta removida'
                WHERE conta_relacionada_id IN (
                    SELECT id FROM contas WHERE owner_id = ?
                )
                AND conta_id NOT IN (
                    SELECT id FROM contas WHERE owner_id = ?
                )
                """,
                (usuario_id, usuario_id),
            )
            # O histórico pertencente às contas do titular é removido por completo.
            conn.execute(
                """
                DELETE FROM transacoes
                WHERE conta_id IN (SELECT id FROM contas WHERE owner_id = ?)
                """,
                (usuario_id,),
            )
            conn.execute("DELETE FROM contas WHERE owner_id = ?", (usuario_id,))
            conn.execute(
                "DELETE FROM email_verification_tokens WHERE user_id = ?",
                (usuario_id,),
            )
            conn.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ?",
                (usuario_id,),
            )
            conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))

    if usuario_ausente:
        session.clear()
        return resposta_erro("Sessão inválida. Entre novamente.", 401)

    if senha_invalida:
        bloqueio = rate_limiter.record_failure(
            chave, agora, app.config["LOGIN_MAX_ATTEMPTS"],
            app.config["LOGIN_WINDOW_SECONDS"], app.config["LOGIN_BLOCK_SECONDS"],
            app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
        )
        if bloqueio:
            return resposta_bloqueio_login(bloqueio)
        return resposta_erro("Senha atual incorreta.", 403)

    # Remove contadores desta origem. Contadores de outras origens permanecem
    # somente até a expiração curta configurada para prevenção de abuso.
    for acao in ("login", "resend-verification", "password-reset", "account-delete"):
        try:
            rate_limiter.reset(chave_tentativas_login(usuario["email"], acao))
        except Exception:
            app.logger.exception("Falha ao limpar contador temporário de segurança.")

    session.clear()
    return jsonify({
        "mensagem": "Sua conta e os dados associados foram excluídos com sucesso."
    })


@app.errorhandler(404)
def nao_encontrado(_erro):
    if request.path.startswith("/api/"):
        return resposta_erro("Recurso não encontrado.", 404)
    return "Página não encontrada", 404


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=DEBUG,
    )
