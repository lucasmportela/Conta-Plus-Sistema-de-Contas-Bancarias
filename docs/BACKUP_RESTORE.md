# Procedimento de backup e restauração — Conta+

## Estado atual

O Conta+ possui uma ferramenta de backup/restauração para **arquivos SQLite locais** e testes automatizados com dados sintéticos. A demonstração hospedada utiliza **Turso como banco remoto principal**. A ferramenta scripts/backup_restore.py não cria nem restaura backups do Turso.

Até a revisão de 12 de novembro de 2026, não foi confirmada neste repositório uma rotina externa automatizada de backup, política de retenção ou restauração testada para o banco Turso da demonstração. O teste de CI valida somente o procedimento SQLite local.

A demonstração está publicamente acessível para fins de portfólio, mas não é um sistema bancário real. Utilize exclusivamente dados fictícios.

## Regras de proteção

- Backups podem conter nomes, e-mails, contas e movimentações. Trate-os como dados pessoais e confidenciais.
- Nunca envie bancos, backups ou chaves para Git, issues, logs ou artefatos públicos do GitHub Actions.
- O arquivo SQLite criado pela ferramenta recebe permissão POSIX 0600 quando o sistema de arquivos permite.
- A ferramenta não criptografa o arquivo. Antes de transferi-lo para armazenamento externo, criptografe-o com uma solução aprovada e mantenha a chave fora do servidor e do repositório.
- Defina acesso mínimo, MFA no provedor, retenção documentada, cópia fora do ambiente principal e alertas de falha.
- A exclusão de conta no banco ativo não remove imediatamente os dados já presentes em backups. O prazo de retenção deve ser definido e informado na política de privacidade.

## Criar e verificar um backup SQLite local

Use estes comandos somente para um banco SQLite local cujo caminho você conhece e controla:

    python scripts/backup_restore.py backup --source /caminho/conta_plus.db --destination /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3
    python scripts/backup_restore.py verify --database /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3

A cópia usa a API de backup do SQLite, que produz um snapshot consistente mesmo quando o banco está em uso. A ferramenta valida PRAGMA integrity_check, tabelas essenciais e PRAGMA foreign_key_check. Ela não substitui criptografia nem envio para armazenamento externo.

## Testar uma restauração SQLite sem tocar no banco ativo

Restaure primeiro para um caminho novo e separado:

    python scripts/backup_restore.py restore --backup /caminho-seguro/conta-plus-AAAA-MM-DD-HHMM.sqlite3 --destination /caminho/restore-validation.sqlite3
    python scripts/backup_restore.py verify --database /caminho/restore-validation.sqlite3

A ferramenta recusa sobrescrever um destino existente. Compare a quantidade de usuários, contas e movimentações com os registros esperados, sem expor dados em logs. Faça o teste em ambiente isolado e com autorização.

## Banco remoto Turso da demonstração

O banco hospedado não é um arquivo SQLite local acessível pelo script acima. Portanto:

1. Não execute os comandos SQLite deste documento supondo que eles façam backup do Turso.
2. Consulte a documentação e o painel atuais do Turso para escolher o mecanismo de backup/exportação compatível com o plano e a configuração da conta.
3. Defina destino separado, criptografia, controle de acesso, retenção, RPO e RTO.
4. Registre como restaurar em um banco separado sem sobrescrever o banco ativo.
5. Faça um exercício de restauração com dados fictícios e registre o resultado antes de considerar o procedimento operacional.
6. Não declare backup de produção configurado até que a rotina esteja ativa e uma restauração tenha sido demonstrada.

Este repositório não contém credenciais nem um procedimento executável de backup/restauração do Turso.

## Restauração de um banco SQLite local

1. Interrompa a aplicação que utiliza o arquivo para evitar novas gravações.
2. Preserve o banco atual como cópia separada; nunca sobrescreva a única cópia.
3. Descriptografe o backup somente em volume protegido e com acesso restrito.
4. Restaure para um novo caminho e execute verify.
5. Confirme a consistência dos dados e a versão do esquema antes de apontar a configuração local para o banco restaurado.
6. Reinicie a aplicação e valide login, isolamento por usuário e operações com contas de teste.
7. Registre data, responsável, origem do backup, resultado e duração do exercício.
8. Mantenha a cópia anterior até confirmar que o serviço está íntegro.

## Teste automatizado SQLite

    python -m unittest discover -s tests -p "test_backup_restore.py" -v
    python scripts/backup_restore.py self-test

O teste cria usuário, conta e movimentação fictícios em um diretório temporário, faz backup, altera a origem, restaura o snapshot e confirma que o estado original foi preservado. Nenhum dado real é utilizado.

## O que ainda precisa ser decidido/configurado pelo operador

- Mecanismo e destino de backup/exportação do Turso.
- Armazenamento externo criptografado e chave de criptografia.
- Frequência de backup, RPO e RTO.
- Retenção, exclusão e expiração de cópias antigas.
- Alertas, responsáveis e evidências de cada restauração.
- Exercício real de backup e restauração do banco remoto utilizado na demonstração.
