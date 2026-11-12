# Segurança e estado de publicação — Conta+

## Estado atual

Este repositório é público e a aplicação possui uma **demonstração de portfólio acessível pela Internet**:

- Demonstração: https://conta-plus-demo-doxa.onrender.com
- Hospedagem: Render Free, serviço Docker de uma instância.
- Banco da demonstração: Turso, acessado por URL e token configurados como variáveis secretas no Render.
- E-mail transacional hospedado: API HTTPS do Brevo.
- Health check configurado no Render: /api/health.

A publicação pública é limitada a uma demonstração educacional. **Não é um sistema bancário real, não está aprovado para produção e não deve receber dados pessoais, bancários ou financeiros reais.** O plano gratuito do Render pode suspender o serviço após inatividade; a primeira abertura pode demorar.

## Evidências verificadas em 12 de novembro de 2026

- GitHub Actions: **74 testes da suíte principal e 6 testes operacionais adicionais** aprovados nos workflows do commit ee67df7.
- Os 6 testes operacionais cobrem 3 testes com Redis real e 3 testes SMTP/fluxos de e-mail via Mailpit local.
- O smoke test manual da API HTTPS do Brevo foi concluído com sucesso durante a configuração da demonstração. É uma validação pontual, não um monitoramento de entregabilidade nem uma auditoria de SPF, DKIM ou DMARC.
- O serviço Render consta como live no último deploy consultado. O deploy atual usa o commit ee67df7 e tem health check configurado em /api/health.
- Não foram encontrados erros de aplicação posteriores ao último deploy na consulta de logs realizada. As métricas HTTP e os registros de requisições estavam sem dados nessa consulta; portanto, isso não comprova tráfego nem monitoramento contínuo.
- O workflow de CI executa build e smoke test Docker com cabeçalhos HTTPS simulados. Isso não substitui uma validação independente de toda a cadeia de proxy e TLS no provedor real.

## Controles implementados

- Senhas armazenadas com scrypt via Werkzeug.
- Confirmação de e-mail obrigatória antes do login.
- Tokens de confirmação e recuperação persistidos somente como SHA-256, com expiração e uso único.
- Recuperação de senha incrementa a versão da sessão e invalida sessões anteriores.
- Respostas genéricas para cadastro, reenvio de confirmação e solicitação de recuperação, reduzindo enumeração de contas.
- Limitação de cadastro, login, reenvio e recuperação; SQLite para uma instância e Redis opcional para compartilhar os contadores.
- Identificação do cliente baseada em ProxyFix somente em produção e com quantidade explícita de proxies confiáveis.
- Lista de hosts permitidos, HTTPS obrigatório em produção, cookies Secure/HttpOnly/SameSite e HSTS.
- Proteção CSRF, isolamento por proprietário e cabeçalhos CSP, X-Frame-Options, nosniff e Referrer-Policy.
- Exportação autenticada em JSON, com somente dados do titular, referências a contas externas omitidas e cabeçalhos no-store; hashes, senhas, tokens, sessões e contadores de segurança não são exportados.
- Autoexclusão autenticada com senha atual, confirmação explícita, limitação de tentativas e remoção transacional de cadastro, contas, histórico e tokens associados.
- Política de privacidade disponível no caminho /privacidade.

## Infraestrutura da demonstração

- **Render:** serviço Docker Free, uma instância, health check /api/health e domínio onrender.com.
- **Turso:** banco remoto compatível com SQLite, usado como banco principal na demonstração. O arquivo SQLite local continua sendo usado no desenvolvimento.
- **Brevo:** envio de confirmação e recuperação pela API HTTPS; o Render Free bloqueia as portas SMTP tradicionais.
- **Rate limiting:** o Blueprint configura o backend SQLite, apropriado para a instância única atual. Redis não está configurado como serviço nessa publicação.
- **Backups:** o script do repositório cobre SQLite local. Não há evidência de rotina externa de backup e restauração do banco Turso configurada e testada para a demonstração.

## Pendências antes de qualquer uso em produção

1. Contratar auditoria independente de autenticação, autorização, sessão, CSRF, XSS, SQL, infraestrutura, dependências e recuperação de incidentes. O escopo está em docs/INDEPENDENT_AUDIT_SCOPE.md.
2. Definir e testar uma rotina de backup e restauração específica para o banco Turso, com cópia protegida, retenção, responsável, RPO/RTO e exercício de recuperação documentado.
3. Completar a política de privacidade com identificação do responsável pelo tratamento, finalidades, bases legais, prazos de retenção, fornecedores, canal de contato e procedimento para direitos dos titulares; obter revisão jurídica adequada à LGPD.
4. Configurar monitoramento e alertas de disponibilidade, erros, uso de recursos, falhas de e-mail e limites dos provedores.
5. Validar a cadeia real de HTTPS/proxy, cabeçalhos encaminhados, hosts permitidos, cookies Secure e o valor de TRUSTED_PROXY_HOPS no ambiente hospedado.
6. Validar a entregabilidade de e-mail de forma continuada. Para um remetente de domínio próprio, configurar e verificar SPF, DKIM e DMARC; o teste manual da API Brevo não substitui essa etapa.
7. Migrar o banco principal para PostgreSQL e testar migração/rollback antes de executar múltiplas instâncias. Redis compartilha somente os contadores de autenticação, não os dados da aplicação.
8. Definir retenção e exclusão para logs, backups e dados mantidos pelos fornecedores.

## Exportação e proteção da cópia

A rota GET /api/account/export exige sessão autenticada e entrega um arquivo JSON como anexo, com Cache-Control: no-store. A exportação contém nome, e-mail, estado de confirmação, data de cadastro, contas e movimentações pertencentes ao usuário. Referências a contas de terceiros são omitidas. Senhas, hashes, tokens, dados de sessão e contadores técnicos não são incluídos. O arquivo é gerado em memória; depois do download, o usuário deve proteger a cópia no dispositivo e removê-la de locais compartilhados quando não precisar mais dela.

## Configuração de proxy

TRUSTED_PROXY_HOPS deve corresponder exatamente ao número de proxies controlados e confiáveis que acrescentam cabeçalhos X-Forwarded-* entre o cliente e o Flask. O render.yaml atual define 1 salto para a demonstração no Render. Essa configuração deve ser reavaliada se a topologia mudar. Confiar em saltos incorretos permite falsificação de IP, host ou protocolo.

## Limitações conhecidas

- A demonstração usa uma instância e banco Turso remoto; Redis não torna o banco principal multi-instância.
- O envio de e-mail é síncrono e depende do provedor; Mailpit valida transporte local, não entregabilidade na Internet.
- A política de privacidade é um aviso informativo, não aconselhamento jurídico nem declaração de conformidade com a LGPD.
- Contadores HMAC de prevenção a abuso podem permanecer até o prazo curto de expiração configurado (24 horas por padrão); IP e e-mail não são persistidos em texto puro no contador.
- Os testes de backup/restauração usam dados sintéticos e SQLite local; não comprovam backup ou recuperação do Turso.
- Não utilize dados pessoais, bancários ou financeiros reais na demonstração.
