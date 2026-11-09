import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conta import Conta, validar_valor


class TestConta(unittest.TestCase):
    def setUp(self):
        self.origem = Conta(1, "Lucas", "00001", Decimal("100.00"))
        self.destino = Conta(2, "Marina", "00002", Decimal("20.00"))

    def test_deposito_atualiza_saldo(self):
        movimento = self.origem.realizar_deposito("25.50")
        self.assertEqual(self.origem.saldo, Decimal("125.50"))
        self.assertEqual(movimento["saldo_anterior"], Decimal("100.00"))

    def test_saque_atualiza_saldo(self):
        self.origem.realizar_saque("40.00")
        self.assertEqual(self.origem.saldo, Decimal("60.00"))

    def test_saque_pode_zerar_saldo(self):
        self.origem.realizar_saque("100.00")
        self.assertEqual(self.origem.saldo, Decimal("0.00"))

    def test_saque_sem_saldo_suficiente(self):
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            self.origem.realizar_saque("101.00")

    def test_transferencia_atualiza_as_duas_contas(self):
        self.origem.transferir(self.destino, "30.00")
        self.assertEqual(self.origem.saldo, Decimal("70.00"))
        self.assertEqual(self.destino.saldo, Decimal("50.00"))

    def test_nao_permite_transferencia_para_si_mesma(self):
        with self.assertRaisesRegex(ValueError, "própria conta"):
            self.origem.transferir(self.origem, "10.00")

    def test_nao_permite_valor_zero(self):
        with self.assertRaises(ValueError):
            validar_valor("0")

    def test_saldo_inicial_zero_e_valido(self):
        conta = Conta(3, "Pedro", "00003", Decimal("0.00"))
        self.assertEqual(conta.saldo, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
