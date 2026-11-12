# Publicação gratuita do Conta+

Esta configuração publica uma **demonstração de portfólio**, não um sistema bancário de produção. Não utilize dinheiro real, documentos, senhas reutilizadas ou dados financeiros pessoais.

## Arquitetura

- **Render Free:** executa a aplicação Flask em Docker e fornece HTTPS e um endereço `onrender.com`.
- **Turso Free:** mantém os dados em um banco SQLite remoto, fora do sistema de arquivos temporário do Render.
- **Brevo Free:** envia confirmação de cadastro e recuperação de senha pela API HTTPS. O Render Free bloqueia as portas SMTP 25, 465 e 587.

O código continua usando SQLite localmente. Em produção, `DATABASE_BACKEND=turso` seleciona o banco remoto. Para e-mails, `MAIL_PROVIDER=brevo` seleciona a API; o SMTP Gmail continua disponível para desenvolvimento local.

## 1. Criar o banco Turso

1. Crie uma conta em [Turso](https://turso.tech/) e permaneça no plano Free.
2. Crie um banco chamado `conta-plus`.
3. Copie a URL de conexão do banco.
4. Crie um token de autenticação para esse banco e guarde-o em um gerenciador de senhas.

A documentação oficial do SDK Python mostra a conexão remota por `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN`: [Turso Python Quickstart](https://docs.turso.tech/sdk/python/quickstart).

Não coloque esses valores no repositório, em arquivos de exemplo ou em mensagens.

## 2. Preparar o envio de e-mails no Brevo

1. Crie uma conta no [Brevo](https://www.brevo.com/) e confira o limite do plano gratuito vigente.
2. Ative o recurso de e-mails transacionais, se solicitado.
3. Cadastre um remetente e conclua a verificação enviada para esse endereço.
4. Gere uma chave de API v3 e guarde-a em local seguro.

**Atenção ao remetente Gmail:** domínios gratuitos como `gmail.com` não podem ser autenticados com DKIM/DMARC no Brevo. O Brevo pode substituir o domínio do remetente por um domínio gerenciado por ele. A aplicação configura o endereço original como `Reply-To`, mas o campo "De" poderá aparecer com o domínio substituto do Brevo. Para usar um remetente próprio autenticado, é necessário controlar um domínio e configurar os registros DNS. Consulte [os requisitos de remetente do Brevo](https://help.brevo.com/hc/pt/articles/14925263522578-Satisfazer-os-requisitos-do-Gmail-Yahoo-e-Microsoft-para-remetentes-de-e-mail).

## 3. Publicar pelo Render Blueprint

1. Confirme que as alterações desta branch foram integradas à branch `main`.
2. Abra o [Render Dashboard](https://dashboard.render.com/).
3. Escolha **New + → Blueprint** e conecte o repositório `lucasmportela/Conta-Plus-Sistema-de-Contas-Bancarias`.
4. Selecione a branch `main` e o arquivo `render.yaml`.
5. Durante a criação, preencha os quatro valores solicitados:
   - `TURSO_DATABASE_URL`: URL do banco Turso.
   - `TURSO_AUTH_TOKEN`: token de acesso do banco.
   - `BREVO_API_KEY`: chave de API v3 do Brevo.
   - `MAIL_FROM`: remetente verificado no Brevo, por exemplo `Conta+ <seu-email@gmail.com>`.
6. Revise a tela de recursos e confirme que o serviço web está no plano **Free**. Não habilite recursos pagos ou cobrança por excedentes.
7. Inicie a implantação.

O Render fornece automaticamente `RENDER_EXTERNAL_HOSTNAME`. A aplicação usa esse valor para configurar `PUBLIC_BASE_URL` e `TRUSTED_HOSTS` sem precisar adivinhar o endereço público. O segredo `SECRET_KEY` é gerado pelo próprio Blueprint.

## 4. Validar a demonstração

Depois que o Render mostrar o deploy como concluído:

1. Abra a URL `onrender.com` atribuída ao serviço.
2. Verifique `/api/health`.
3. Faça um cadastro de teste com uma caixa de e-mail que você controla.
4. Confirme o cadastro pelo link recebido.
5. Entre na aplicação e crie contas inteiramente fictícias.
6. Teste depósito, saque, transferência e extrato.
7. Solicite recuperação de senha e confirme que a senha anterior deixa de funcionar.
8. Teste a exclusão da conta de demonstração.

Confira também os logs do Render. Não compartilhe links de confirmação, tokens, chaves ou capturas que contenham dados pessoais.

## Limitações importantes do plano gratuito

- O Render desliga serviços Free após 15 minutos sem tráfego; a próxima abertura pode levar cerca de um minuto.
- O sistema de arquivos do Render Free é temporário. Por isso, o banco principal é remoto no Turso, não o arquivo SQLite do container.
- O Render informa 750 horas gratuitas de instância por workspace/mês e pode suspender serviços ao atingir limites aplicáveis.
- O Render bloqueia saída SMTP pelas portas 25, 465 e 587; por isso o envio hospedado usa HTTPS.
- O Turso Free tem limites de uso. Confira sempre os limites e as regras de cobrança atuais no painel antes de habilitar qualquer opção de excedente.
- O plano gratuito e os limites dos provedores podem mudar. Revise os painéis periodicamente e não habilite upgrade automático.
- Uma demonstração pública não deve receber dados bancários reais. O Conta+ continua sendo um projeto educacional de portfólio.

Referências oficiais:
- [Limitações do Render Free](https://render.com/docs/free)
- [Blueprints do Render](https://render.com/docs/blueprint-spec)
- [Preços e limites do Turso](https://turso.tech/pricing)
- [Requisitos de remetente do Brevo](https://help.brevo.com/hc/pt/articles/14925263522578-Satisfazer-os-requisitos-do-Gmail-Yahoo-e-Microsoft-para-remetentes-de-e-mail)
