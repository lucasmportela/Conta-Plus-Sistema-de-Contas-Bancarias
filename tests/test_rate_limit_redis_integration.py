"""Testes de integração do limitador contra uma instância Redis real."""
import os
import secrets
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from rate_limit import LoginRateLimiter

REDIS_URL = os.getenv("REDIS_URL")


@unittest.skipUnless(REDIS_URL, "Defina REDIS_URL para executar a integração Redis.")
class TestRedisRateLimiterIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limiter = LoginRateLimiter("redis", REDIS_URL)
        cls.client = cls.limiter.client

    def setUp(self):
        self.key = secrets.token_hex(24)
        self.redis_key = self.limiter._key(self.key)

    def tearDown(self):
        self.client.delete(self.redis_key)

    def test_contagem_bloqueio_expiracao_e_reset_com_redis_real(self):
        agora = int(time.time())
        for _ in range(2):
            self.assertEqual(
                self.limiter.record_failure(self.key, agora, 3, 900, 30, 120),
                0,
            )
        self.assertEqual(
            self.limiter.record_failure(self.key, agora, 3, 900, 30, 120),
            30,
        )
        self.assertEqual(
            self.limiter.blocked_seconds(self.key, agora + 1, 900, 120),
            29,
        )
        self.assertEqual(
            self.limiter.blocked_seconds(self.key, agora + 31, 900, 120),
            0,
        )
        self.limiter.record_failure(self.key, agora + 32, 3, 900, 30, 120)
        self.limiter.reset(self.key)
        self.assertEqual(
            self.limiter.blocked_seconds(self.key, agora + 33, 900, 120),
            0,
        )
        self.assertFalse(self.client.exists(self.redis_key))

    def test_script_lua_mantem_limite_ativo_sob_concorrencia(self):
        agora = int(time.time())
        def registrar(_):
            return self.limiter.record_failure(
                self.key, agora, 5, 900, 60, 120
            )
        with ThreadPoolExecutor(max_workers=12) as executor:
            resultados = list(executor.map(registrar, range(12)))
        self.assertGreaterEqual(sum(valor > 0 for valor in resultados), 8)
        self.assertGreater(
            self.limiter.blocked_seconds(self.key, agora, 900, 120), 0
        )

    def test_chave_tem_ttl_de_retencao(self):
        agora = int(time.time())
        self.limiter.record_failure(self.key, agora, 5, 900, 60, 75)
        ttl = self.client.ttl(self.redis_key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 75)


if __name__ == "__main__":
    unittest.main()
