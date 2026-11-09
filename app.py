from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import sqlite3

from flask import Flask, jsonify, render_template, request

from conta import Conta, validar_valor
from database import conectar, inicializar_banco, obter_conta, listar_contas, salvar_transacao

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
DEBUG = (
    APP_ENV != "production"
    and os.getenv("FLASK_DEBUG", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
app.config.update(JSON_AS_ASCII=False, DEBUG=DEBUG)

inicializar_banco()


def resposta_erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


def carregar_conta(conn, conta_id):
    registro = obter_conta(conn, conta_id)
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
    return jsonify({"status": "ok", "mensagem": "API do Sistema de Contas Bancárias funcionando."})


@app.get("/api/resumo")
def resumo():
    with conectar() as conn:
        contas = listar_contas(conn)
        total_saldo = sum((Decimal(item["saldo"]) for item in contas), Decimal("0.00"))
        total_movimentacoes = conn.execute(
            "SELECT COUNT(*) AS total FROM transacoes"
        ).fetchone()["total"]
    return jsonify({
        "total_contas": len(contas),
        "saldo_consolidado": f"{total_saldo:.2f}",
        "total_movimentacoes": total_movimentacoes,
    })


@app.get("/api/contas")
def api_listar_contas():
    with conectar() as conn:
        contas = listar_contas(conn)
    return jsonify([dict(conta) for conta in contas])


@app.post("/api/contas")
def api_criar_conta():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", "")).strip()
    numero = str(dados.get("numero", "")).strip()
    try:
        saldo_inicial = validar_valor(dados.get("saldo_inicial", "0"), permitir_zero=True)
    except ValueError as erro:
        return resposta_erro(str(erro))

    if len(nome) < 3:
        return resposta_erro("O nome deve ter pelo menos 3 caracteres.")
    if not numero:
        return resposta_erro("Informe o número da conta.")

    try:
        with conectar() as conn:
            cursor = conn.execute(
                "INSERT INTO contas (nome, numero, saldo) VALUES (?, ?, ?)",
                (nome, numero, f"{saldo_inicial:.2f}"),
            )
            conta_id = cursor.lastrowid
            if saldo_inicial > 0:
                salvar_transacao(
                    conn, conta_id, "DEPOSITO INICIAL", "Depósito inicial",
                    saldo_inicial, Decimal("0.00"), saldo_inicial
                )
    except sqlite3.IntegrityError:
        return resposta_erro("Já existe uma conta com esse número.")

    return jsonify({
        "mensagem": "Conta criada com sucesso.",
        "conta": {
            "id": conta_id, "nome": nome, "numero": numero,
            "saldo": f"{saldo_inicial:.2f}"
        }
    }), 201


def processar_operacao(conta_id, tipo):
    dados = request.get_json(silent=True) or {}
    try:
        valor = validar_valor(dados.get("valor"))
    except ValueError as erro:
        return resposta_erro(str(erro))

    try:
        with conectar() as conn:
            conta = carregar_conta(conn, conta_id)
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
                "UPDATE contas SET saldo = ? WHERE id = ?",
                (f"{conta.saldo:.2f}", conta.id),
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
def api_depositar(conta_id):
    return processar_operacao(conta_id, "deposito")


@app.post("/api/contas/<int:conta_id>/saques")
def api_sacar(conta_id):
    return processar_operacao(conta_id, "saque")


@app.post("/api/contas/<int:conta_id>/transferencias")
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

    try:
        with conectar() as conn:
            origem = carregar_conta(conn, conta_id)
            destino = carregar_conta(conn, destino_id)
            if origem is None or destino is None:
                return resposta_erro("Conta de origem ou destino não encontrada.", 404)

            origem.transferir(destino, valor)

            conn.execute("UPDATE contas SET saldo = ? WHERE id = ?", (f"{origem.saldo:.2f}", origem.id))
            conn.execute("UPDATE contas SET saldo = ? WHERE id = ?", (f"{destino.saldo:.2f}", destino.id))

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
def api_extrato(conta_id):
    with conectar() as conn:
        conta = obter_conta(conn, conta_id)
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
