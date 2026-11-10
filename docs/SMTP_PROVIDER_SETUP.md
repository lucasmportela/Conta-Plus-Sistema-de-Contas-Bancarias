# E-mail transacional — Conta Hotmail

Para contas pessoais @hotmail.com, o Conta+ usa SMTP do Outlook.com com OAuth2/Modern Auth. A autenticação por senha normal ou senha de aplicativo não é utilizada.

Consulte HOTMAIL_OAUTH_SETUP.md para:
- registrar o aplicativo no Microsoft Entra;
- conceder a permissão delegada SMTP.Send;
- autorizar a conta com Device Code Flow;
- manter o cache de tokens criptografado;
- executar um teste controlado de envio.

Configuração SMTP fixa da conta pessoal:
- Host: smtp-mail.outlook.com
- Porta: 587
- Criptografia: STARTTLS
- Autenticação: OAuth2 / XOAUTH2
- Usuário e remetente: o mesmo endereço @hotmail.com.

Não coloque senha, token, cache OAuth ou chave Fernet no Git. Não envie credenciais por mensagens. O teste real envia apenas uma mensagem para o endereço controlado configurado em SMTP_TEST_RECIPIENT.

A integração Mailpit do CI continua sendo o teste automatizado de transporte SMTP local; ela não comprova autenticação ou entrega no Hotmail.
