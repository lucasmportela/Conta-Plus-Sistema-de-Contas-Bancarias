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

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from conta import Conta, validar_valor
from database import (
    conectar, inicializar_banco, obter_conta, listar_contas, salvar_transacao,
    obter_bloqueio_login, registrar_falha_login, limpar_tentativas_login,
)

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY")
if APP_ENV == "production" and not SECRET_KEY:
    raise RuntimeError("Defina SECRET_KEY no ambiente de produção.")
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
)
app.json.ensure_ascii = False

if min(
    app.config["LOGIN_MAX_ATTEMPTS"],
    app.config["LOGIN_WINDOW_SECONDS"],
    app.config["LOGIN_BLOCK_SECONDS"],
    app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
) < 1:
    raise RuntimeError("As configurações de limitação de login devem ser maiores que zero.")

inicializar_banco()


def resposta_erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


def requer_autenticacao(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return resposta_erro("Autenticação necessária.", 401)
        return funcao(*args, **kwargs)
    return wrapper


def iniciar_sessao(usuario_id):
    session.clear()
    session["usuario_id"] = usuario_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True


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

    try:
        with conectar() as conn:
            cursor = conn.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash)
                VALUES (?, ?, ?)
                """,
                (nome, email, generate_password_hash(senha, method="scrypt")),
            )
            usuario_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return resposta_erro("Já existe uma conta de usuário com esse e-mail.", 409)

    iniciar_sessao(usuario_id)
    return jsonify({
        "mensagem": "Cadastro realizado com sucesso.",
        "usuario": {"id": usuario_id, "nome": nome, "email": email},
    }), 201


def chave_tentativas_login(email):
    """Gera uma chave HMAC sem armazenar e-mail ou endereço IP em texto puro."""
    origem = request.remote_addr or "desconhecido"
    identificador = f"{origem}\0{email}".encode("utf-8")
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
    with conectar() as conn:
        bloqueio = obter_bloqueio_login(
            conn,
            chave,
            agora,
            app.config["LOGIN_WINDOW_SECONDS"],
            app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
        )
    if bloqueio:
        return resposta_bloqueio_login(bloqueio)

    with conectar() as conn:
        usuario = conn.execute(
            "SELECT id, nome, email, senha_hash FROM usuarios WHERE email = ?",
            (email,),
        ).fetchone()

    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        with conectar() as conn:
            bloqueio = registrar_falha_login(
                conn,
                chave,
                agora,
                app.config["LOGIN_MAX_ATTEMPTS"],
                app.config["LOGIN_WINDOW_SECONDS"],
                app.config["LOGIN_BLOCK_SECONDS"],
                app.config["LOGIN_ATTEMPT_RETENTION_SECONDS"],
            )
        if bloqueio:
            return resposta_bloqueio_login(bloqueio)
        return resposta_erro("E-mail ou senha incorretos.", 401)

    with conectar() as conn:
        limpar_tentativas_login(conn, chave)

    iniciar_sessao(usuario["id"])
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
