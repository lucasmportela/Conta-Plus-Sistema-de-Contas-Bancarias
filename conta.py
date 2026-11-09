from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENTAVO = Decimal("0.01")


def validar_valor(valor, permitir_zero=False):
    """Converte um valor para Decimal e valida se é positivo (ou zero, se permitido)."""
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Informe um valor numérico válido.")

    if not numero.is_finite():
        raise ValueError("O valor informado é inválido.")

    numero = numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if numero < 0 or (numero == 0 and not permitir_zero):
        raise ValueError("O valor deve ser maior que zero.")
    return numero


class Conta:
    """Representa uma conta bancária e concentra as regras de movimentação."""

    def __init__(self, id, nome, numero, saldo=Decimal("0.00")):
        self.id = id
        self.nome = nome
        self.numero = numero
        self.saldo = validar_valor(saldo, permitir_zero=True)

    def realizar_deposito(self, valor):
        valor = validar_valor(valor)
        anterior = self.saldo
        self.saldo = (self.saldo + valor).quantize(CENTAVO)
        return {"saldo_anterior": anterior, "saldo_atual": self.saldo}

    def realizar_saque(self, valor):
        valor = validar_valor(valor)
        if valor > self.saldo:
            raise ValueError("Saldo insuficiente para realizar o saque.")

        anterior = self.saldo
        self.saldo = (self.saldo - valor).quantize(CENTAVO)
        return {"saldo_anterior": anterior, "saldo_atual": self.saldo}

    def transferir(self, conta_destino, valor):
        if self.id == conta_destino.id:
            raise ValueError("Não é possível transferir para a própria conta.")

        valor = validar_valor(valor)
        if valor > self.saldo:
            raise ValueError("Saldo insuficiente para realizar a transferência.")

        self.saldo = (self.saldo - valor).quantize(CENTAVO)
        conta_destino.saldo = (conta_destino.saldo + valor).quantize(CENTAVO)
        return True
