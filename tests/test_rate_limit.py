"""Testes do backend configurável de limitação de tentativas."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rate_limit import LoginRateLimiter


class FakeRedis:
    def __init__(self):
        self.pinged = False
        self.eval_calls = []
        self.deleted = []

    def ping(self):
        self.pinged = True
        return True

    def eval(self, script, num_keys, *args):
        self.eval_calls.append((script, num_keys, args))
        return 0 if len(self.eval_calls) == 1 else 900

    def delete(self, key):
        self.deleted.append(key)
        return 1


class TestLoginRateLimiter(unittest.TestCase):
    def test_backend_redis_inicializa_e_usa_script_atomico(self):
        cliente = FakeRedis()
        redis_fake = SimpleNamespace(
            Redis=SimpleNamespace(from_url=lambda *args, **kwargs: cliente)
        )
        with patch.dict(sys.modules, {"redis": redis_fake}):
            limiter = LoginRateLimiter("redis", "redis://localhost:6379/0")

        self.assertTrue(cliente.pinged)
        bloqueio = limiter.blocked_seconds("hash", 1000, 900, 86400)
        self.assertEqual(bloqueio, 0)
        bloqueio = limiter.record_failure("hash", 1000, 5, 900, 900, 86400)
        self.assertEqual(bloqueio, 900)
        self.assertEqual(len(cliente.eval_calls), 2)
        self.assertIn("'HSET'", cliente.eval_calls[1][0])
        self.assertIn("'EXPIRE'", cliente.eval_calls[1][0])

        limiter.reset("hash")
        self.assertEqual(cliente.deleted, ["conta-plus:login:hash"])

    def test_backend_redis_exige_url(self):
        with self.assertRaisesRegex(RuntimeError, "REDIS_URL"):
            LoginRateLimiter("redis", None)

    def test_backend_desconhecido_e_rejeitado(self):
        with self.assertRaisesRegex(RuntimeError, "sqlite ou redis"):
            LoginRateLimiter("memoria")


if __name__ == "__main__":
    unittest.main()
