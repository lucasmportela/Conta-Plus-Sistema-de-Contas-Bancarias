# Revisão de segurança — Conta+

## Estado

Este repositório é um projeto educacional. A lista abaixo documenta controles implementados e pré-requisitos ainda necessários; não é uma certificação de segurança nem autorização para uso financeiro real.

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
- Política de privacidade publicada no caminho `/privacidade`.

## Pré-requisitos para produção

- Configurar `SECRET_KEY` forte e persistente, `PUBLIC_BASE_URL` HTTPS, `TRUSTED_HOSTS` e `TRUSTED_PROXY_HOPS` com os valores reais do provedor.
- Configurar SMTP com credenciais secretas, TLS ou SSL, remetente autorizado e entrega monitorada.
- Configurar Redis gerenciado e compartilhado se houver mais de uma instância. O backend Redis compartilha somente os contadores de autenticação; SQLite não é adequado como banco principal compartilhado entre várias instâncias. Migrar dados da aplicação para PostgreSQL antes de escalar horizontalmente.
- Configurar armazenamento persistente, backups criptografados, restauração testada, monitoramento e alertas.
- Definir processo de exclusão de contas e retenção de dados; a aplicação ainda não oferece autoexclusão.
- Validar domínio e e-mail do remetente, SPF, DKIM e DMARC.
- Fazer revisão independente de autenticação, autorização, sessão, CSRF, XSS, SQL, dependências, configuração de infraestrutura e recuperação de incidentes.
- Rever a política de privacidade para identificar o operador, fornecedores, contato, bases legais, prazos e direitos aplicáveis à LGPD.
- Não utilizar dados pessoais ou financeiros reais.

## Configuração de proxy

`TRUSTED_PROXY_HOPS` deve corresponder exatamente ao número de proxies controlados e confiáveis que acrescentam os cabeçalhos X-Forwarded-* entre o cliente e o Flask. Confiar em saltos incorretos permite falsificação de IP, host ou protocolo. Nunca use ProxyFix com valores estimados nem aceite cabeçalhos encaminhados diretamente de clientes não confiáveis.

## Limitações conhecidas

- Redis não substitui a migração do banco principal: a aplicação ainda usa SQLite.
- O envio SMTP é síncrono e requer configuração/monitoramento operacional.
- A política de privacidade é um modelo informativo do projeto, não aconselhamento jurídico.
- A implementação precisa de teste de implantação em ambiente controlado antes de qualquer abertura pública.
