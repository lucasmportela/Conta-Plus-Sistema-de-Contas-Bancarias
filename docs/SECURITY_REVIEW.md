# Revisão técnica preliminar de segurança e privacidade — Conta+

**Data:** 12 de novembro de 2026  
**Escopo:** código-fonte, workflows de CI, configuração de produção, autenticação, persistência, e-mail, rate limiting, cabeçalhos HTTP e estado da demonstração hospedada.  
**Natureza:** revisão interna assistida e automatizada. **Não é auditoria independente, pentest, parecer jurídico ou certificação.**

## Decisão

**A demonstração de portfólio está publicada, mas o Conta+ não está aprovado para uso em produção nem para dados pessoais, bancários ou financeiros reais.**

A publicação atual utiliza Render Free, Turso como banco remoto e Brevo pela API HTTPS. A implantação bem-sucedida demonstra que a aplicação inicia no provedor; não comprova operação bancária segura, disponibilidade contínua, recuperação de desastre ou conformidade jurídica.

## Estado da publicação verificado

| Item | Evidência | Limite |
|---|---|---|
| Aplicação | https://conta-plus-demo-doxa.onrender.com | Demonstração educacional; não usar dados reais |
| Render | Serviço Free, Docker, uma instância, estado live no último deploy consultado | Plano gratuito pode suspender após inatividade |
| Health check | /api/health configurado no serviço | A configuração do health check não substitui monitoramento externo |
| Banco | Turso remoto configurado como banco principal da demonstração | Backup e restauração do Turso não foram demonstrados nesta revisão |
| E-mail | API HTTPS Brevo configurada; smoke test manual de envio concluído com sucesso durante a publicação | Teste pontual; não prova entregabilidade contínua nem autenticação de domínio próprio |
| GitHub Actions | Workflows de testes Python e operacionais aprovados no commit ee67df7 | CI não equivale a auditoria independente |
| Logs e métricas | Nenhum erro de aplicação posterior ao último deploy na consulta realizada | Métricas HTTP e logs de requisição estavam sem dados; não há evidência de tráfego ou monitoramento contínuo |

## Controles verificados no código

- Hash de senha scrypt via Werkzeug; tokens de confirmação e redefinição persistidos como SHA-256, com validade e uso único. O nome da tabela de token é validado por allowlist antes da consulta SQL.
- Confirmação de e-mail obrigatória, respostas genéricas para reduzir enumeração e revogação de sessões após redefinição de senha.
- CSRF em métodos mutáveis, autorização por proprietário e exportação/exclusão autenticadas.
- Cookies HttpOnly, SameSite e Secure em produção; hosts permitidos, ProxyFix com número explícito de saltos, CSP e HSTS quando a requisição é reconhecida como HTTPS.
- Limitador Redis implementado com scripts Lua atômicos, timeout de conexão e PING na inicialização.
- SMTP usa contexto TLS padrão com validação de certificado para STARTTLS/SSL; envio síncrono com timeout de 10 segundos.
- Fontes externas do Google Fonts removidas; CSS e fontes usam pilhas locais do sistema, e a CSP não autoriza origens externas de fontes/estilos.

## Testes automatizados e operacionais

A suíte principal contém **74 testes**:

- 8 testes das regras de negócio.
- 34 testes das rotas Flask.
- 9 testes da camada SQLite.
- 3 testes do backend de limitação com Redis simulado.
- 15 testes do serviço de e-mail.
- 5 testes de backup/restauração SQLite.

A automação operacional adiciona **6 testes**:

- 3 testes contra Redis 7 real, incluindo concorrência, bloqueio, expiração, TTL e reset.
- 1 teste SMTP com Mailpit local para confirmar o recebimento da mensagem.
- 2 testes de fluxos de confirmação, reenvio e recuperação de senha via Mailpit.

Os dois workflows do GitHub Actions foram aprovados no commit ee67df7. Os testes Mailpit não enviam e-mails à Internet. O smoke test manual da API Brevo foi executado durante a publicação, mas não faz parte dos testes automatizados do CI.

O workflow também executa build e smoke test Docker, verificação de dependências com pip-audit e análise estática com Bandit. O teste Docker simula cabeçalhos HTTPS em CI e não prova, sozinho, a topologia de proxy do provedor.

## Achados e riscos remanescentes

| Severidade | Achado | Ação necessária |
|---|---|---|
| Alta | Não houve auditoria independente nem pentest | Contratar avaliação externa e documentar reteste |
| Alta | Backup e restauração do banco Turso não foram demonstrados | Definir cópia protegida, retenção, RPO/RTO e exercício de restauração específico do provedor |
| Alta | Política de privacidade ainda não define todos os elementos necessários | Confirmar responsável, bases legais, prazos, fornecedores, canal e direitos; obter revisão jurídica |
| Alta | Não há evidência de monitoramento contínuo ou alertas | Configurar verificações externas e alertas de disponibilidade, erros e falhas de e-mail |
| Média | Validação da cadeia de proxy/TLS no provedor não foi demonstrada de ponta a ponta | Confirmar cabeçalhos e TRUSTED_PROXY_HOPS no ambiente real |
| Média | O teste manual Brevo é pontual | Monitorar entregabilidade e autenticar domínio próprio com SPF, DKIM e DMARC, quando aplicável |
| Média | A aplicação utiliza uma instância e Turso; SQLite local permanece no desenvolvimento | Migrar para PostgreSQL e testar migração/rollback antes de escalar horizontalmente |
| Média | Redis compartilha apenas contadores, não os dados da aplicação | Não interpretar Redis como solução de banco multi-instância |
| Média | A ferramenta de backup do repositório cobre SQLite local, não Turso | Criar procedimento específico para o banco remoto |
| Baixa | Render Free pode suspender o serviço após inatividade | Informar o visitante sobre a possível demora no primeiro acesso |

## Privacidade

A demonstração publicada utiliza Render para hospedagem, Turso para persistência e Brevo para e-mails transacionais. A interface não carrega Google Fonts de terceiros. A política de privacidade precisa detalhar o papel desses fornecedores, as finalidades e bases legais aplicáveis, os prazos de retenção e o canal para solicitações dos titulares. Não se deve declarar conformidade com a LGPD sem avaliação adequada.

## Evidência e limites

- Os testes de Mailpit demonstram conexão SMTP e recebimento em servidor local de captura, não entregabilidade na Internet.
- O smoke test manual Brevo demonstra que o envio de teste funcionou naquele momento; não garante entrega futura, ausência de spam ou autenticação de domínio.
- O container executa como UID 10001 sem privilégios; o volume persistente precisa ser montado com propriedade/permissões para UID/GID 10001. O teste de container verifica configuração de produção em CI, não a infraestrutura completa de um provedor.
- pip-audit detecta vulnerabilidades conhecidas nas dependências resolvidas; Bandit é análise estática, não prova ausência de falhas.
- Os testes de backup/restauração usam dados sintéticos e SQLite local. Não comprovam backup, retenção ou restauração do banco Turso.
- Nenhum teste deve usar dados bancários reais.

## Critério para considerar produção

1. Auditoria independente concluída, achados críticos/altos tratados e reteste documentado.
2. Política de privacidade revisada, com responsável, finalidades, bases legais, fornecedores, prazos e canal de contato definidos.
3. Backup e restauração do banco de produção demonstrados, com criptografia, retenção e responsáveis.
4. Monitoramento, alertas, logs e resposta a incidentes definidos.
5. HTTPS, proxy, hosts, cookies e cabeçalhos verificados no ambiente real.
6. E-mail transacional monitorado e domínio autenticado quando aplicável.
7. Migração para PostgreSQL antes de múltiplas instâncias.
8. Testes de implantação e recuperação repetidos após mudanças relevantes.
