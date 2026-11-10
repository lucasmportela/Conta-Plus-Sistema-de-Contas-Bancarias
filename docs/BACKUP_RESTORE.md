# Procedimento de backup e restauração — Conta+

## Estado atual

O repositório agora contém uma ferramenta de backup/restauração SQLite e testes automatizados com dados sintéticos. Isso valida o procedimento do software, **não configura backup de produção nem prova uma restauração de infraestrutura real**. Não existe aqui um provedor de armazenamento, agenda, chave de criptografia ou política de retenção configurados.

O Conta+ deve continuar fora de publicação pública. O banco SQLite suporta apenas uma instância da aplicação por vez.

## Regras de proteção

- O backup contém nomes, e-mails, contas e movimentações. Trate-o como dado pessoal e confidencial.
- Nunca envie bancos, backups ou chaves para Git, issues, logs ou artefatos públicos do GitHub Actions.
- O arquivo é criado com permissão POSIX 0600 quando o sistema de arquivos permite.
- A ferramenta não criptografa o arquivo. Antes de transferi-lo para armazenamento externo, criptografe-o com uma solução aprovada (por exemplo, age, GPG ou KMS do provedor) e mantenha a chave fora do servidor e do repositório.
- Defina acesso mínimo, MFA no provedor, retenção documentada, cópia fora do ambiente principal e alertas de falha.
- A exclusão de conta no banco ativo não remove imediatamente os dados já presentes em backups. O prazo de retenção deve ser definido e informado na política de privacidade.

## Criar e verificar um backup

No host que possui o volume persistente, com o caminho real do banco:

    python scripts/backup_restore.py backup --source /data/conta_plus.db --destination /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3
    python scripts/backup_restore.py verify --database /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3

A cópia usa a API de backup do SQLite, que produz um snapshot consistente mesmo quando o banco está em uso. A ferramenta valida PRAGMA integrity_check, tabelas essenciais e PRAGMA foreign_key_check. Ela não substitui criptografia nem envio para armazenamento externo.

## Testar uma restauração sem tocar no banco ativo

Restaure primeiro para um caminho novo e separado:

    python scripts/backup_restore.py restore --backup /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3 --destination /data/restore-validation.sqlite3
    python scripts/backup_restore.py verify --database /data/restore-validation.sqlite3

A ferramenta recusa sobrescrever um destino existente. Compare a quantidade de usuários, contas e movimentações com os registros esperados, sem expor dados em logs. Faça o teste em ambiente isolado e com autorização.

## Restauração de produção

1. Declare manutenção e interrompa a aplicação para evitar novas gravações.
2. Preserve o banco atual como cópia de segurança separada; nunca sobrescreva a única cópia.
3. Descriptografe o backup apenas em volume protegido e com acesso restrito.
4. Restaure para um novo caminho e execute verify.
5. Confirme a consistência dos dados e a versão do esquema antes de apontar DATABASE_PATH para o banco restaurado.
6. Reinicie a aplicação, valide login, isolamento por usuário e operações com contas de teste.
7. Registre data, responsável, origem do backup, resultado e duração do exercício.
8. Mantenha a cópia anterior até confirmar que o serviço está íntegro.

## Teste automatizado

    python -m unittest discover -s tests -p "test_backup_restore.py" -v
    python scripts/backup_restore.py self-test

O teste cria usuário, conta e movimentação fictícios em um diretório temporário, faz backup, altera a origem, restaura o snapshot e confirma que o estado original foi preservado. Nenhum dado real é utilizado.

## O que ainda precisa ser decidido/configurado pelo operador

- Provedor e destino de armazenamento criptografado.
- Chave de criptografia e processo de rotação/recuperação.
- Frequência de backup e objetivo de ponto/tempo de recuperação (RPO/RTO).
- Retenção, exclusão e expiração de cópias antigas.
- Alertas, responsáveis e evidências de cada restauração.
- Exercício real de backup e restauração no provedor escolhido.
