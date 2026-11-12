# Escopo para auditoria independente — Conta+

## Objetivo

Contratar uma avaliação independente antes de qualquer uso em produção ou ampliação do projeto para além da demonstração educacional. A revisão interna e os testes automatizados do repositório não substituem esse trabalho.

## Escopo mínimo solicitado

1. **Autenticação:** cadastro, confirmação de e-mail, login, limitação de tentativas, recuperação de senha, tokens, expiração e revogação de sessões.
2. **Autorização e isolamento:** acesso cruzado entre usuários, contas, movimentações, exportação e autoexclusão.
3. **Sessão e navegador:** cookies, CSRF, CSP, XSS, clickjacking, cabeçalhos e gestão de sessão.
4. **Aplicação e dados:** SQL injection, validação de entrada, tratamento de erros, exposição de informações, integridade transacional e privacidade dos backups.
5. **E-mail e abuso:** enumeração de contas, abuso de envio, rate limiting, configuração TLS e proteção de credenciais.
6. **Infraestrutura:** TLS, proxy confiável, hosts permitidos, configuração do container, permissões do volume, segredos, logs, backups e restauração.
7. **Dependências e cadeia de suprimentos:** dependências Python, imagens Docker, GitHub Actions e permissões mínimas dos workflows.
8. **Privacidade/LGPD:** inventário de dados, finalidade, base legal, retenção, compartilhamento com fornecedores, direitos dos titulares e processo de incidentes. A avaliação jurídica deve ser feita por profissional habilitado.

## Condições de teste

- Usar ambiente de homologação isolado e dados exclusivamente sintéticos.
- Não acessar nem solicitar dados bancários reais.
- Definir previamente autorização, janela, endereços de origem e limites de teste.
- Não realizar teste destrutivo, DoS ou envio em massa.
- Registrar evidências sem copiar senhas, tokens, dados pessoais ou segredos.
- Comunicar imediatamente achados críticos e interromper testes que possam afetar disponibilidade ou confidencialidade.

## Entregáveis exigidos

- Relatório com escopo, metodologia, limitações e data.
- Achados classificados por severidade, impacto, probabilidade e evidência reproduzível.
- Recomendações específicas e critérios objetivos de correção.
- Resultado de reteste após as correções.
- Declaração clara do que não foi testado.
- Avaliação de privacidade separada da avaliação técnica, quando necessário.

## Critério de aceite

Não considerar a auditoria concluída apenas com uma reunião ou checklist. Exigir relatório escrito, tratamento de todos os achados críticos/altos e reteste documentado. Mesmo após a auditoria, a liberação depende de backup/restauração, monitoramento, política de privacidade e controles operacionais definidos e testados.

## Informações que o responsável pelo projeto precisa fornecer

- Identificação e contato do responsável pelo tratamento.
- Ambiente de hospedagem e região de processamento.
- Provedores de banco de dados e e-mail e serviços adicionais utilizados.
- Dados coletados, finalidades e prazos de retenção.
- Fluxo de exclusão, retenção em logs e expiração de backups.
- Contato para incidentes e solicitações dos titulares.

Não preencha essas informações por suposição; confirme com o responsável e obtenha revisão jurídica apropriada.
