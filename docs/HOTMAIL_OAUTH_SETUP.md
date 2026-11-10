# Configurar Hotmail no Conta+

O Conta+ envia confirmação de cadastro e recuperação de senha usando uma conta pessoal @hotmail.com por SMTP do Outlook.com com OAuth2 (Modern Auth) e SASL XOAUTH2. **Não use a senha normal do Hotmail nem senha de aplicativo.**

## 1. Registrar o aplicativo Microsoft

1. Entre em https://entra.microsoft.com/ com uma conta Microsoft.
2. Abra Identity → Applications → App registrations → New registration.
3. Dê um nome, por exemplo, Conta+ SMTP.
4. Em Supported account types, escolha Personal Microsoft accounts only.
5. Registre o aplicativo e copie o Application (client) ID. Ele será MS_CLIENT_ID; não é uma senha.
6. Abra Authentication → Advanced settings e habilite Allow public client flows para permitir o Device Code Flow.
7. Em API permissions, adicione a permissão delegada SMTP.Send do recurso Office 365 Exchange Online, se ela estiver disponível para o registro. A autorização interativa também solicitará consentimento para o escopo SMTP.

Não crie client secret: o fluxo implementado é de cliente público e não usa segredo de aplicativo.

## 2. Configurar as variáveis

Copie o arquivo de exemplo:

Windows PowerShell:

~~~powershell
Copy-Item .env.example .env
~~~

Edite .env e informe:
- MAIL_USERNAME: endereço Hotmail completo;
- MAIL_FROM: o mesmo endereço (pode manter o nome de exibição Conta+);
- MS_CLIENT_ID: Application (client) ID do registro;
- MS_TOKEN_CACHE_ENCRYPTION_KEY: chave Fernet gerada localmente.

Gere a chave Fernet no PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
~~~

Copie o resultado para MS_TOKEN_CACHE_ENCRYPTION_KEY no .env. Guarde uma cópia segura dessa chave fora do repositório. Ela não pode ser recuperada a partir do cache criptografado.

As configurações SMTP devem permanecer:
- MAIL_AUTH_MODE=oauth2
- MAIL_SERVER=smtp-mail.outlook.com
- MAIL_PORT=587
- MAIL_USE_TLS=true
- MAIL_USE_SSL=false

O cache criptografado é salvo por padrão em instance/hotmail_msal_cache.enc, que não deve ser versionado. O diretório instance/ já está no .gitignore.

## 3. Autorizar a conta Hotmail

Com o ambiente virtual e as dependências instaladas, execute na raiz do repositório:

~~~powershell
.\.venv\Scripts\python.exe scripts/setup_hotmail_oauth.py
~~~

O terminal exibirá uma URL e um código de dispositivo. Abra a URL, entre na conta Hotmail pretendida e aceite a permissão solicitada. O script confere se a conta autenticada corresponde a MAIL_USERNAME e grava o cache criptografado.

A Microsoft usa o Device Code Flow, que permite autenticar a conta em um navegador e devolver tokens ao script local. A biblioteca MSAL usa o cache para renovar tokens silenciosamente; se o consentimento for revogado ou o cache ficar inválido, execute novamente o script.

## 4. Testar uma mensagem

Defina SMTP_TEST_RECIPIENT com uma caixa de e-mail sua ou outra caixa de teste cujo uso esteja autorizado. Depois execute:

~~~powershell
$env:SMTP_TEST_RECIPIENT = "seu-destinatario-de-teste@example.com"
.\.venv\Scripts\python.exe scripts/smtp_provider_smoke.py
~~~

O teste envia uma única mensagem. Confirme a chegada na caixa de entrada e na pasta de spam. O aceite pelo SMTP não garante entregabilidade geral.

## 5. Produção e armazenamento

O cache contém credenciais de renovação e é criptografado com Fernet. Em produção:
- guarde MS_CLIENT_ID e MS_TOKEN_CACHE_ENCRYPTION_KEY em secrets do provedor;
- mantenha MS_TOKEN_CACHE_FILE em armazenamento persistente e restrito (por padrão, /data/hotmail_msal_cache.enc em produção);
- transfira o cache inicial para o servidor por canal administrativo seguro, nunca por commit, issue, log ou chat;
- mantenha uma cópia de recuperação da chave Fernet fora do servidor;
- restrinja permissões do arquivo a somente o usuário do processo;
- não execute múltiplas instâncias escrevendo no mesmo cache sem coordenação;
- reautorize a conta se o refresh token for revogado ou a Microsoft exigir consentimento novamente.

O projeto ainda não foi autorizado na conta real nem teve entrega real validada. A integração Mailpit no GitHub Actions testa apenas SMTP local; depois da autorização, faça o teste controlado acima antes de habilitar cadastro e recuperação para usuários reais.

## Referências oficiais

- https://support.microsoft.com/pt-br/office/configura%C3%A7%C3%B5es-pop-imap-e-smtp-para-outlook-com
- https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth
- https://learn.microsoft.com/pt-br/entra/identity-platform/v2-oauth2-device-code
- https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
