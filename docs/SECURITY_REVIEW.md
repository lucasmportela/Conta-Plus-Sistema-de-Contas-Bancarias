# Revisão técnica preliminar de segurança e privacidade — Conta+

**Data:** 10 de novembro de 2026  
**Escopo:** código-fonte, configuração de produção, autenticação, persistência, SMTP, Redis, cabeçalhos HTTP e automação de testes.  
**Natureza:** revisão interna assistida e automatizada. **Não é auditoria independente, pentest, parecer jurídico ou certificação.**

## Decisão

**Não liberar o Conta+ para acesso público aberto nem para dados financeiros reais.**

A aplicação tem controles relevantes implementados, mas a infraestrutura real ainda não foi configurada e validada. O banco principal é SQLite, o SMTP depende de um provedor e o Redis é apenas um backend opcional para contadores de segurança.

## Controles verificados no código

- Hash de senha scrypt via Werkzeug; tokens de confirmação e redefinição persistidos como SHA-256, com validade e uso único. O nome da tabela de token é validado por allowlist antes da consulta SQL.
- Confirmação de e-mail obrigatória, respostas genéricas para reduzir enumeração e revogação de sessões após redefinição de senha.
- CSRF em métodos mutáveis, autorização por proprietário e exportação/exclusão autenticadas.
- Cookies HttpOnly, SameSite e Secure em produção; hosts permitidos, ProxyFix com número explícito de saltos, CSP e HSTS quando a requisição é reconhecida como HTTPS.
- Limitador Redis implementado com scripts Lua atômicos, timeout de conexão e PING na inicialização.
- SMTP usa contexto TLS padrão com validação de certificado para STARTTLS/SSL; envio síncrono com timeout de 10 segundos.
- Fontes externas do Google Fonts removidas; CSS e fontes usam pilhas locais do sistema, e a CSP não autoriza origens externas de fontes/estilos.

## Testes automatizados e operacionais

A suíte principal mantém 58 testes. A automação operacional adiciona:
- Integração com Redis 7 real: contagem, bloqueio, expiração, TTL, reset e concorrência.
- Integração SMTP local com Mailpit: envio via SMTP e confirmação da mensagem recebida pela API do Mailpit. Não envia e-mail externo.
- Smoke test do container: build Docker, inicialização com APP_ENV de produção, health endpoint, HSTS, cookie Secure/HttpOnly/SameSite e persistência do arquivo SQLite no volume.
- Auditoria automatizada com pip-audit e Bandit.
- Workflow manual para testar o provedor SMTP real, condicionado a secrets do GitHub Actions configurados pelo operador.

## Achados e riscos remanescentes

| Severidade | Achado | Ação necessária |
|---|---|---|
| Alta | Nenhum provedor SMTP real foi validado ainda | Configurar secrets e executar o workflow manual; verificar recebimento, spam, SPF, DKIM e DMARC |
| Alta | Topologia de proxy e terminação TLS não foram exercitadas em provedor real | Confirmar os saltos de proxy e executar smoke test em homologação |
| Alta | SQLite é o banco principal | Manter uma única instância com disco persistente; migrar para PostgreSQL e testar migração/rollback antes de escalar |
| Alta | Ainda não houve auditoria independente | Contratar revisão externa de autenticação, autorização, sessão, CSRF, XSS, SQL, infraestrutura e recuperação |
| Média | Redis só compartilha contadores; não compartilha os dados da aplicação | Configurar Redis gerenciado com TLS/rede privada e manter uma instância até migrar o banco |
| Média | SMTP é síncrono e sem fila/retry persistente | Definir monitoramento, política de retry e alertas para falhas de entrega |
| Média | Backup e restauração reais não foram configurados/testados | Criar backups criptografados, testar restauração e documentar retenção/exclusão |
| Média | Aviso de privacidade não identifica operador, contato, fornecedores concretos, bases legais e prazos específicos | Completar dados reais do operador e obter revisão jurídica/privacidade adequada à LGPD |
| Baixa | HSTS é emitido quando Flask reconhece a requisição como HTTPS | Verificar X-Forwarded-Proto e cabeçalhos no proxy real; avaliar includeSubDomains somente se todos os subdomínios suportarem HTTPS |

## Privacidade

A interface deixou de carregar Google Fonts de terceiros, reduzindo uma transferência desnecessária de dados do navegador. O serviço SMTP, a hospedagem e Redis, se habilitado, continuam sendo fornecedores que o operador deverá identificar e avaliar. A política não deve afirmar conformidade com a LGPD sem definição de controlador/operador, finalidades, bases legais, prazos, canal de contato e procedimentos para direitos dos titulares.

## Evidência e limites

- Os testes de Mailpit demonstram conexão SMTP e recebimento em servidor local de captura, não entregabilidade na Internet.
- O workflow SMTP do provedor real é manual, exige confirmação explícita de envio e só executa quando MAIL_SERVER, MAIL_FROM e SMTP_TEST_RECIPIENT estão cadastrados como secrets no GitHub Actions. Ele envia uma única mensagem ao destinatário explicitamente configurado.
- O container executa como UID 10001 sem privilégios; o volume persistente precisa ser montado com propriedade/permissões para UID/GID 10001. O teste de container verifica a configuração de produção em CI, não a infraestrutura de um provedor de hospedagem.
- pip-audit detecta vulnerabilidades conhecidas nas dependências resolvidas; Bandit é análise estática, não prova ausência de falhas.
- Nenhum teste deve usar dados bancários reais.

## Critério para reavaliar a liberação

1. Todos os workflows operacionais e de segurança aprovados.
2. Teste do provedor SMTP real e autenticação do domínio de envio.
3. Homologação com HTTPS, proxy e host reais.
4. Backup e restauração demonstrados.
5. Migração para PostgreSQL antes de múltiplas instâncias.
6. Revisão externa independente e revisão da política de privacidade por profissional qualificado.
