"""Testes do cache OAuth2 criptografado do Hotmail."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from hotmail_oauth import carregar_cache_configurada, salvar_cache_criptografado


class FakeCache:
    def serialize(self):
        return '{"refresh_token":"segredo-de-teste"}'


class TestHotmailOAuthCache(unittest.TestCase):
    def test_persiste_cache_criptografado_sem_texto_secreto(self):
        chave = Fernet.generate_key()
        fernet = Fernet(chave)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "hotmail_cache.enc"
            salvar_cache_criptografado(FakeCache(), caminho, fernet)
            conteudo = caminho.read_bytes()

            self.assertNotIn(b"segredo-de-teste", conteudo)
            self.assertEqual(
                fernet.decrypt(conteudo).decode("utf-8"),
                '{"refresh_token":"segredo-de-teste"}',
            )
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(caminho.stat().st_mode), 0o600)

    def test_rejeita_cache_com_chave_de_criptografia_incorreta(self):
        chave_correta = Fernet.generate_key()
        chave_errada = Fernet.generate_key()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "hotmail_cache.enc"
            caminho.write_bytes(Fernet(chave_correta).encrypt(b"{}"))
            ambiente = {
                "MS_CLIENT_ID": "client-id-de-teste",
                "MAIL_USERNAME": "conta@hotmail.com",
                "MS_TOKEN_CACHE_ENCRYPTION_KEY": chave_errada.decode("ascii"),
                "MS_TOKEN_CACHE_FILE": str(caminho),
            }
            with patch.dict(os.environ, ambiente, clear=True):
                with self.assertRaisesRegex(RuntimeError, "cache OAuth criptografado"):
                    carregar_cache_configurada()

    def test_rejeita_chave_fernet_invalida(self):
        ambiente = {
            "MS_CLIENT_ID": "client-id-de-teste",
            "MAIL_USERNAME": "conta@hotmail.com",
            "MS_TOKEN_CACHE_ENCRYPTION_KEY": "chave-invalida",
        }
        with patch.dict(os.environ, ambiente, clear=True):
            with self.assertRaisesRegex(RuntimeError, "chave Fernet válida"):
                carregar_cache_configurada()

    def test_exige_client_id_da_aplicacao_microsoft(self):
        ambiente = {
            "MAIL_USERNAME": "conta@hotmail.com",
            "MS_TOKEN_CACHE_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }
        with patch.dict(os.environ, ambiente, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MS_CLIENT_ID"):
                carregar_cache_configurada()


if __name__ == "__main__":
    unittest.main()
