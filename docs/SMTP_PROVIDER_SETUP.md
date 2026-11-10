# Configuração do teste SMTP real — Conta+

O teste real é manual e envia **uma única mensagem** para o endereço definido em SMTP_TEST_RECIPIENT. Não execute até ter autorização para usar o destinatário e credenciais do provedor.

## Secrets do GitHub Actions

No repositório, acesse **Settings → Secrets and variables → Actions → New repository secret**. Cadastre os valores diretamente no GitHub; não os envie em mensagens, commits, arquivos .env ou logs.

| Secret | Obrigatório | Uso |
|---|---|---|
| MAIL_SERVER | Sim | Host SMTP fornecido pelo provedor |
| MAIL_PORT | Não | Porta; padrão 587 |
| MAIL_USERNAME | Conforme o provedor | Usuário SMTP |
| MAIL_PASSWORD | Conforme o provedor | Senha ou token SMTP |
| MAIL_FROM | Sim | Endereço remetente autorizado |
| MAIL_USE_TLS | Não | Padrão true; STARTTLS |
| MAIL_USE_SSL | Não | Padrão false; SSL implícito |
| SMTP_TEST_RECIPIENT | Sim | Caixa de teste controlada e autorizada |

Não habilite MAIL_USE_TLS e MAIL_USE_SSL simultaneamente. Use a combinação de host, porta e segurança indicada pelo provedor. O remetente precisa estar autorizado/verificado. Se o provedor não exigir autenticação, deixe usuário e senha vazios.

## Executar o teste

1. Cadastre os secrets necessários.
2. Abra a aba **Actions** do repositório.
3. Selecione **Teste SMTP do provedor real**.
4. Clique em **Run workflow**.
5. Marque send_test somente quando confirmar que o destinatário configurado é uma caixa de teste autorizada.
6. Execute e acompanhe o job.
7. Confirme o recebimento na caixa de entrada e na pasta de spam.

O resultado positivo do job confirma que o servidor SMTP aceitou a mensagem; não comprova entregabilidade geral, reputação do domínio nem recebimento em todos os provedores.

## Validação do domínio

Depois do envio, valide no provedor DNS e em ferramentas apropriadas:

- SPF: política de envio publicada para o serviço autorizado.
- DKIM: assinatura habilitada e validada.
- DMARC: política e relatórios coerentes com SPF/DKIM.
- Alinhamento do domínio do remetente e monitoramento de rejeições/bounces.
- Fluxos de confirmação e recuperação no ambiente de homologação, usando contas e caixas controladas.

Não use dados financeiros ou endereços de terceiros sem autorização. Revogue/rotacione imediatamente qualquer credencial exposta.
