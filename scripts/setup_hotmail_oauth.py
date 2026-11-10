"""Autoriza uma conta pessoal Hotmail por OAuth2 Device Code Flow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import msal

from hotmail_oauth import (
    AUTHORITY,
    SCOPES,
    carregar_cache_configurada,
    salvar_cache_criptografado,
)


def main():
    cache, cache_path, fernet, client_id, username = carregar_cache_configurada()
    aplicacao = msal.PublicClientApplication(
        client_id,
        authority=AUTHORITY,
        token_cache=cache,
    )

    contas = aplicacao.get_accounts(username=username)
    if contas:
        resultado = aplicacao.acquire_token_silent(
            list(SCOPES),
            account=contas[0],
        )
        if resultado and resultado.get("access_token"):
            salvar_cache_criptografado(cache, cache_path, fernet)
            print("A conta Hotmail já está autorizada e o token foi renovado.")
            print(f"Cache OAuth criptografado: {cache_path}")
            return 0

    fluxo = aplicacao.initiate_device_flow(scopes=list(SCOPES))
    if "user_code" not in fluxo:
        print(
            "Não foi possível iniciar a autorização Microsoft. "
            "Confira o Client ID e se o fluxo de cliente público está habilitado.",
            file=sys.stderr,
        )
        return 1

    print(fluxo.get("message", "Siga as instruções de autenticação exibidas pela Microsoft."))
    sys.stdout.flush()
    resultado = aplicacao.acquire_token_by_device_flow(fluxo)

    if not resultado or not resultado.get("access_token"):
        print(
            "A autorização não foi concluída. Nenhum token foi exibido ou salvo.",
            file=sys.stderr,
        )
        return 1

    contas = aplicacao.get_accounts(username=username)
    if not contas:
        print(
            "A conta autenticada não corresponde a MAIL_USERNAME. "
            "Repita o processo usando a conta Hotmail configurada.",
            file=sys.stderr,
        )
        return 1

    salvar_cache_criptografado(cache, cache_path, fernet)
    print("Autorização Hotmail concluída. O cache foi salvo criptografado.")
    print(f"Arquivo local: {cache_path}")
    print("Não compartilhe esse arquivo nem a chave de criptografia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
