# E-mail transacional — Gmail SMTP

O Conta+ usa uma conta Gmail dedicada para enviar mensagens de confirmação de cadastro e recuperação de senha. Os usuários do sistema continuam podendo cadastrar qualquer endereço de e-mail, inclusive Hotmail e Outlook.

## 1. Crie uma conta exclusiva

Crie uma conta Google separada para o projeto. Evite usar sua caixa pessoal principal.

## 2. Ative a verificação em duas etapas

Entre na [Conta Google](https://myaccount.google.com/security), abra **Segurança** e habilite a **Verificação em duas etapas**.

## 3. Gere uma senha de app

1. Acesse [Senhas de app](https://myaccount.google.com/apppasswords).
2. Entre novamente, se solicitado.
3. Crie uma senha de app com o nome **Conta+**.
4. Copie a senha gerada e guarde-a em local seguro. O Google mostra a senha uma única vez; se perdê-la, gere outra.

A senha de app é diferente da senha normal da Conta Google. Ela só fica disponível com a verificação em duas etapas ativa e pode não aparecer em contas gerenciadas por uma organização, com Proteção Avançada ou configuradas apenas com chaves de segurança. O Google recomenda usar autenticação moderna sempre que possível; a senha de app é usada aqui porque o Conta+ integra com SMTP tradicional.

## 4. Configure o arquivo `.env`

Copie `.env.example` para `.env` e preencha os campos:

```dotenv
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=conta.exclusiva@gmail.com
MAIL_PASSWORD=senha-de-app-de-16-caracteres
MAIL_FROM="Conta+ <conta.exclusiva@gmail.com>"
MAIL_USE_TLS=true
MAIL_USE_SSL=false
```

Use o endereço Gmail completo tanto em `MAIL_USERNAME` quanto em `MAIL_FROM`. Se copiar a senha de app com espaços de agrupamento, o Conta+ remove esses espaços antes de autenticar.

Configuração alternativa com SSL direto:

- `MAIL_PORT=465`
- `MAIL_USE_TLS=false`
- `MAIL_USE_SSL=true`

Não habilite TLS e SSL ao mesmo tempo. O servidor, a porta e o modo de criptografia são validados pelo código.

## 5. Teste o envio real

Defina um destinatário de teste controlado e execute a partir da raiz do repositório:

Windows PowerShell:

```powershell
$env:SMTP_TEST_RECIPIENT = "seu-email-de-teste@example.com"
.\.venv\Scripts\python.exe scripts/smtp_provider_smoke.py
```

Linux/macOS:

```bash
SMTP_TEST_RECIPIENT="seu-email-de-teste@example.com" python scripts/smtp_provider_smoke.py
```

O script envia uma única mensagem. Confira a caixa de entrada e a pasta de spam do destinatário.

## Segurança

- Nunca use a senha normal da Conta Google em `MAIL_PASSWORD`.
- Não coloque a senha de app no código, no README, em commits, issues ou mensagens.
- O arquivo `.env` já está no `.gitignore`; mantenha os segredos também nas variáveis protegidas do provedor de hospedagem.
- Revogue a senha de app nas configurações da Conta Google se ela for exposta ou deixar de ser usada.
- O teste automatizado com Mailpit valida o transporte SMTP local, mas não comprova autenticação nem entregabilidade do Gmail.
- Esta configuração não publica o Conta+ nem autoriza o uso de dados bancários reais.
