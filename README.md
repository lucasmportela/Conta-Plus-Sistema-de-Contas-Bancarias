# Conta+ — Sistema de Contas Bancárias

Aplicação web demonstrativa para gerenciamento individual de contas bancárias, desenvolvida com Python, Flask e SQLite. O sistema oferece cadastro e login de usuários, isolamento de contas por proprietário, depósitos, saques, transferências e consulta de extratos.

> **Aviso:** este é um projeto educacional para portfólio. Não é um sistema bancário real e não deve ser utilizado para armazenar dinheiro ou dados financeiros verdadeiros.

## Funcionalidades

- Cadastro de usuários com e-mail único e senha armazenada por hash seguro.
- Login, logout e sessões autenticadas com expiração.
- Isolamento de contas e movimentações por usuário autenticado.
- Autorização no backend para impedir acesso a contas de terceiros.
- Proteção CSRF nas requisições que alteram dados.
- Cadastro de contas com titular, número e saldo inicial.
- Validação de nomes, números de conta e valores.
- Depósitos com atualização automática do saldo.
- Saques com bloqueio de saldo insuficiente.
- Transferências entre contas diferentes.
- Bloqueio de transferência para a própria conta.
- Extrato individual com histórico das movimentações.
- Painel com total de contas, saldo consolidado e quantidade de movimentações do usuário autenticado.
- Persistência local dos dados em SQLite, com vínculo entre contas e usuários.
- Interface responsiva para desktop e dispositivos móveis.

## Demonstração Visual

### Tela Inicial (Vazia)
Tela inicial do programa aguardando as primeiras entradas de dados para serem processados com a exibição de total de contas cadastradas, saldo consolidado de todas as contas e número total de movimentações registradas.
![Tela Inicial](docs/screenshots/tela-inicial.png)

### Tela Cadastro
Seção cadastro aguardando os dados nome do titular, número da conta e saldo inicial para cadastrar uma nova conta.
![Tela Cadastro](docs/screenshots/novo-cadastro.png)

### Tela Operação
Operação de movimentação de conta com as opções saque, depósito ou transferência para outra conta com especificação de conta e valor da operação.
![Tela Operação](docs/screenshots/tela-operacao.png)

### Tela Acompanhamento
Informações das contas cadastradas como saldo, nome do titular e número de conta.
![Tela Acompanhamento](docs/screenshots/tela-acompanhamento.png)

### Histórico Financeiro
Extrato de uma conta específica exibindo nome do titular, número da conta, saldo atual e transações realizadas com detalhes, data e horário.
![Histórico Financeiro](docs/screenshots/historico-financeiro.png)

As capturas de tela utilizadas neste README estão armazenadas em `docs/screenshots/`.

## Tecnologias utilizadas

**Back-end**
- Python
- Flask
- SQLite
- Decimal para cálculos monetários
- Werkzeug para hash de senhas e validação de credenciais
- Sessões Flask e proteção CSRF

**Front-end**
- HTML5
- CSS3
- JavaScript (Fetch API)

## Estrutura do projeto

```text
Conta-Plus-Sistema-de-Contas-Bancarias/
├── app.py
├── conta.py
├── database.py
├── requirements.txt
├── .gitignore
├── README.md
├── instance/
│   └── contas.db             # Criado automaticamente ao iniciar
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── tests/
│   ├── test_conta.py
│   ├── test_api.py
│   └── test_database.py
└── docs/
    └── screenshots/
        ├── tela-inicial.png
        ├── novo-cadastro.png
        ├── tela-operacao.png
        ├── tela-acompanhamento.png
        ├── historico-financeiro.png
        └── .gitkeep
```

## Como executar

### 1. Pré-requisitos

- Python 3.10 ou superior.
- pip.

### 2. Clone o repositório e entre na pasta do projeto

```bash
git clone https://github.com/lucasmportela/Conta-Plus-Sistema-de-Contas-Bancarias.git
cd Conta-Plus-Sistema-de-Contas-Bancarias
```

### 3. Crie o ambiente virtual e instale as dependências

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Windows Prompt de Comando:

```cmd
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 4. Inicie o servidor

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py
```

Windows Prompt de Comando:

```cmd
.venv\Scripts\python.exe app.py
```

Linux/macOS:

```bash
python app.py
```

O modo Debug fica desativado por padrão. Para habilitá-lo durante desenvolvimento local, defina `FLASK_DEBUG=true`. Quando `APP_ENV=production`, o modo Debug permanece desativado.

### 5. Abra a aplicação

Acesse no navegador:

```text
http://127.0.0.1:5000
```

O banco SQLite e as tabelas são criados automaticamente na primeira execução.

No ambiente local, uma chave de sessão aleatória é gerada automaticamente a cada inicialização. Para produção, configure uma chave persistente e secreta antes de iniciar o servidor:

## 🔌 API REST

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/health` | Público | Verifica se a API está ativa |
| GET | `/api/csrf` | Público | Obtém token CSRF para a sessão |
| POST | `/api/register` | Público + CSRF | Cria usuário e inicia sessão |
| POST | `/api/login` | Público + CSRF | Autentica usuário |
| POST | `/api/logout` | Autenticado + CSRF | Encerra a sessão |
| GET | `/api/me` | Autenticado | Retorna o usuário da sessão |
| GET | `/api/resumo` | Autenticado | Retorna indicadores das contas do usuário |
| GET | `/api/contas` | Autenticado | Lista somente as próprias contas |
| POST | `/api/contas` | Autenticado + CSRF | Cria conta vinculada ao usuário |
| POST | `/api/contas/<id>/depositos` | Proprietário + CSRF | Realiza depósito |
| POST | `/api/contas/<id>/saques` | Proprietário + CSRF | Realiza saque |
| POST | `/api/contas/<id>/transferencias` | Mesmo proprietário + CSRF | Transfere entre contas próprias |
| GET | `/api/contas/<id>/extrato` | Proprietário | Consulta o próprio extrato |

As rotas protegidas exigem sessão autenticada. Requisições POST, PUT, PATCH e DELETE também exigem o cabeçalho `X-CSRF-Token`, obtido em `GET /api/csrf`.

### Exemplo de criação de conta

```json
{
  "nome": "Lucas Martins",
  "numero": "00001",
  "saldo_inicial": "150.00"
}
```

### Exemplo de depósito ou saque

```json
{
  "valor": "50.00"
}
```

### Exemplo de transferência

```json
{
  "conta_destino_id": 2,
  "valor": "25.00"
}
```

## Testes automatizados

A suíte utiliza `unittest` e o cliente de testes do Flask. Os testes de integração criam bancos SQLite temporários, isolados dos dados locais da aplicação.

**Total: 32 testes automatizados — 8 testes unitários das regras de negócio, 16 testes de integração das rotas Flask e 8 testes da camada SQLite.**

**Cobertura:**

- **Testes unitários (`test_conta.py`):** regras de depósito, saque, transferência e validação de valores.
- **Testes das rotas (`test_api.py`):** cadastro, login, logout, hash de senha, CSRF, autenticação obrigatória, isolamento entre usuários, contas, depósitos, saques, transferências, extratos e resumo.
- **Testes do banco (`test_database.py`):** criação de tabelas e índices, persistência, commit, rollback, unicidade, integridade referencial, consultas por proprietário e migração de banco legado.

Execute toda a suíte a partir da raiz do repositório (a pasta que contém `app.py`, `conta.py` e `tests/`):

```bash
python -m unittest discover -s tests -v
```

No Windows, sem ativar o ambiente virtual:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os mesmos testes são executados automaticamente pelo GitHub Actions a cada push ou pull request direcionado à branch `main`.

## Regras de negócio

- O nome do titular deve conter pelo menos 3 caracteres.
- O número da conta deve ser único.
- O saldo inicial pode ser zero ou positivo.
- Depósitos, saques e transferências exigem valores maiores que zero.
- Não é permitido sacar ou transferir um valor superior ao saldo disponível.
- Uma conta não pode transferir para ela mesma.
- Os valores monetários são tratados com `Decimal` para evitar imprecisões comuns de ponto flutuante.
- Cada movimentação é registrada no extrato da conta correspondente.

## Limitações e segurança

O Conta+ agora implementa autenticação e autorização com isolamento de dados por usuário, mas continua sendo um projeto educacional de portfólio — não um serviço bancário pronto para produção.

- Senhas são armazenadas com hash scrypt via Werkzeug; senhas em texto puro não são persistidas.
- Sessões são renovadas no login, expiram após 30 minutos de inatividade e usam cookies `HttpOnly` e `SameSite=Lax`; em produção, o cookie também recebe `Secure`.
- Requisições que alteram dados exigem token CSRF.
- Consultas, extratos, depósitos, saques e transferências verificam o proprietário no backend. Transferências entre contas de usuários diferentes são recusadas.
- O cadastro público ainda não inclui confirmação de e-mail, recuperação de senha ou limitação de tentativas de login. Antes de abrir a aplicação à Internet, implemente esses controles, monitoração, HTTPS e política de privacidade.
- Não insira dados pessoais, bancários ou financeiros reais.
- O modo Debug fica desativado por padrão; em produção, configure `APP_ENV=production` e uma `SECRET_KEY` forte e aleatória por variável de ambiente.
- Contas existentes em bancos antigos recebem `owner_id = NULL` na migração e ficam invisíveis para todos os usuários. Faça backup antes de atualizar e atribua registros legados a seus proprietários por um procedimento administrativo confiável, se necessário. Não atribua automaticamente esses registros ao primeiro usuário cadastrado.
- Para uso real, ainda seriam necessários controles adicionais, como limitação de tentativas, auditoria, gestão segura de dados, backups, proteção contra concorrência e revisão de segurança independente.

## Autor

**Lucas Martins Portela**  
Desenvolvedor Back-end Júnior

- GitHub: [@lucasmportela](https://github.com/lucasmportela)

---

Desenvolvido para praticar Python, orientação a objetos, APIs REST, persistência de dados e integração entre front-end e back-end.
