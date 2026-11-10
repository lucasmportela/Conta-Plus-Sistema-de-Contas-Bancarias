# Revisão de segurança — Conta+

## Estado

Este repositório é um projeto educacional e **não está liberado para disponibilização pública aberta nem para uso financeiro real**. A revisão abaixo registra controles implementados, evidências de teste e pendências operacionais; não é uma certificação de segurança.

## Resultado da revisão atual

- GitHub Actions: **58 testes da suíte principal e 4 testes operacionais de integração aprovados** na execução mais recente.
- O workflow operacional executa testes de integração contra Redis 7 real, incluindo concorrência, TTL, bloqueio, expiração e reset.
- O fluxo SMTP tem testes automatizados para STARTTLS e SSL, além de integração com Mailpit local para comprovar envio e recebimento. A entrega real ainda depende de executar o workflow manual com secrets do provedor, validar o domínio e verificar a reputação do remetente.
- O smoke test do container valida inicialização com configuração de produção, HSTS, cookie Secure/HttpOnly/SameSite e escrita no volume montado. A topologia real de proxy e a terminação TLS ainda precisam ser verificadas no provedor de hospedagem.
- As fontes externas do Google Fonts foram removidas; CSS e fontes usam recursos locais. A política de privacidade continua sendo um aviso informativo e precisa identificar o operador, contato, fornecedores reais, bases legais e prazos de retenção.

**Conclusão:** os controles de aplicação e os testes automatizados evoluíram, mas não substituem teste de implantação, auditoria independente, operação segura ou revisão jurídica. Mantenha o Conta+ sem serviço público até concluir as pendências abaixo.

## Evidências operacionais adicionadas

- Redis real em serviço de CI: testes de contagem, bloqueio, expiração, TTL, reset e concorrência.
- SMTP local com Mailpit: teste de conexão, envio e confirmação de recebimento sem tráfego de e-mail externo.
- Docker: build e smoke test do container em modo produção, health endpoint, HSTS, cookie seguro e persistência SQLite.
- Segurança estática: pip-audit para dependências e Bandit para código Python.
- SMTP externo: workflow manual condicionado a secrets do provedor e destinatário de teste configurados pelo operador.

## Controles implementados

- Senhas armazenadas com scrypt via Werkzeug.
- Confirmação de e-mail obrigatória antes do login.
- Tokens de confirmação e recuperação armazenados somente como SHA-256, com expiração e uso único.
- Recuperação de senha incrementa a versão da sessão e invalida sessões anteriores.
- Respostas genéricas para cadastro, reenvio de confirmação e solicitação de recuperação, inclusive quando o SMTP falha, reduzindo enumeração de contas.
- Limitação de cadastro, login, reenvio e recuperação; SQLite para uma instância e Redis opcional para compartilhar os contadores.
- Identificação do cliente baseada em `ProxyFix` somente quando a aplicação está em produção e a quantidade de proxies confiáveis é explicitamente configurada.
- Lista de hosts permitidos, HTTPS obrigatório em produção, cookies Secure/HttpOnly/SameSite e HSTS.
- Proteção CSRF, isolamento por proprietário e cabeçalhos CSP, X-Frame-Options, nosniff e Referrer-Policy.
- Exportação autenticada em JSON, com somente dados do titular, referências a contas externas omitidas e cabeçalhos `no-store`; hashes, senhas, tokens, sessões e contadores de segurança não são exportados.
- Autoexclusão autenticada com senha atual, confirmação explícita, limitação de tentativas e remoção transacional de cadastro, contas, histórico e tokens.
- Política de privacidade publicada no caminho `/privacidade`.

## Exportação e proteção da cópia

A rota `GET /api/account/export` exige sessão autenticada e entrega um arquivo JSON como anexo, com `Cache-Control: no-store`. A exportação contém nome, e-mail, estado de confirmação, data de cadastro, contas e movimentações pertencentes ao usuário. Referências a contas de terceiros são omitidas. Senhas, hashes, tokens, dados de sessão e contadores técnicos não são incluídos. O arquivo é gerado em memória e não é persistido no servidor; depois do download, o usuário deve proteger a cópia no dispositivo e removê-la de locais compartilhados quando não precisar mais dela.

## Pré-requisitos para produção

- Configurar `SECRET_KEY` forte e persistente, `PUBLIC_BASE_URL` HTTPS, `TRUSTED_HOSTS` e `TRUSTED_PROXY_HOPS` com os valores reais do provedor.
- Configurar SMTP com credenciais secretas, TLS ou SSL, remetente autorizado e entrega monitorada.
- Configurar Redis gerenciado e compartilhado se houver mais de uma instância. O backend Redis compartilha somente os contadores de autenticação; SQLite não é adequado como banco principal compartilhado entre várias instâncias. Migrar dados da aplicação para PostgreSQL antes de escalar horizontalmente.
- Configurar armazenamento persistente em /data com permissões para UID/GID 10001 (usuário não-root appuser), backups criptografados, restauração testada, monitoramento e alertas.
- Definir e testar a retenção de backups e logs após autoexclusão. Os dados operacionais são removidos do banco ativo, mas cópias de segurança podem persistir até o fim do prazo de retenção.
- Validar domínio e e-mail do remetente, SPF, DKIM e DMARC.
- Testar os fluxos de confirmação e recuperação com o provedor SMTP real, incluindo falhas temporárias, rejeições e reenvio.
- Manter os testes de integração com Redis real no workflow operacional para detectar regressões no backend compartilhado.
- Validar em ambiente de homologação a terminação TLS, o número de proxies confiáveis, os cabeçalhos encaminhados, os hosts permitidos, cookies Secure e HSTS.
- Documentar a política de retenção e exclusão de dados, inclusive solicitações de titulares, logs e cópias de segurança.
- CSS e fontes da interface agora são servidos localmente; reavaliar qualquer novo fornecedor externo antes de adicioná-lo.
- Contratar revisão independente de autenticação, autorização, sessão, CSRF, XSS, SQL, dependências, configuração de infraestrutura e recuperação de incidentes. A revisão interna em docs/SECURITY_REVIEW.md não substitui essa avaliação.
- Rever a política de privacidade para identificar o operador, fornecedores, contato, bases legais, prazos e direitos aplicáveis à LGPD.
- Não utilizar dados pessoais ou financeiros reais.

## Configuração de proxy

`TRUSTED_PROXY_HOPS` deve corresponder exatamente ao número de proxies controlados e confiáveis que acrescentam os cabeçalhos X-Forwarded-* entre o cliente e o Flask. Confiar em saltos incorretos permite falsificação de IP, host ou protocolo. Nunca use ProxyFix com valores estimados nem aceite cabeçalhos encaminhados diretamente de clientes não confiáveis.

## Limitações conhecidas

- Redis não substitui a migração do banco principal: a aplicação ainda usa SQLite.
- O envio SMTP é síncrono e requer configuração/monitoramento operacional; a integração Mailpit não prova entregabilidade do provedor real.
- A política de privacidade é um modelo informativo do projeto, não aconselhamento jurídico.
- Contadores HMAC de prevenção a abuso de outras origens podem permanecer até o prazo curto de expiração configurado (24 horas por padrão); IP e e-mail não são persistidos em texto puro.
- O smoke test Docker é executado em CI, mas a implantação em provedor real, a topologia de proxy e o teste de restauração ainda não foram realizados.
