const API = "/api";
let operacaoAtual = "deposito";
let contasCache = [];
let csrfToken = "";

const elemento = (id) => document.getElementById(id);
const moeda = (valor) => Number(valor || 0).toLocaleString("pt-BR", {
  style: "currency", currency: "BRL",
});

async function requisicao(url, opcoes = {}, permitirRenovacaoCsrf = true) {
  const metodo = (opcoes.method || "GET").toUpperCase();
  const headers = { ...(opcoes.headers || {}) };
  if (opcoes.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(metodo)) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const resposta = await fetch(API + url, {
    ...opcoes,
    method: metodo,
    headers,
    credentials: "same-origin",
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    // O token pode ter expirado junto com a sessão. A primeira tentativa é
    // recusada antes de executar a operação; renove o token e tente uma vez.
    if (
      resposta.status === 403 &&
      permitirRenovacaoCsrf &&
      !["GET", "HEAD", "OPTIONS"].includes(metodo)
    ) {
      await atualizarTokenCsrf();
      return requisicao(url, opcoes, false);
    }

    const erro = new Error(dados.erro || "Não foi possível concluir a solicitação.");
    erro.status = resposta.status;
    if (resposta.status === 401 && !["/login", "/register"].includes(url)) {
      try {
        await atualizarTokenCsrf();
      } catch (_erroCsrf) {
        // A próxima tentativa poderá criar uma nova sessão anônima.
      }
      mostrarAutenticacao();
    }
    throw erro;
  }
  return dados;
}

async function atualizarTokenCsrf() {
  const dados = await requisicao("/csrf");
  csrfToken = dados.csrf_token;
}

function mostrarAutenticacao() {
  elemento("app-shell").classList.add("hidden");
  elemento("auth-view").classList.remove("hidden");
  elemento("auth-login").classList.remove("hidden");
  elemento("auth-register").classList.add("hidden");
  elemento("auth-feedback").textContent = "";
}

function mostrarFeedbackAutenticacao(mensagem) {
  elemento("auth-feedback").textContent = mensagem;
}

async function abrirPainel(usuario) {
  elemento("auth-view").classList.add("hidden");
  elemento("app-shell").classList.remove("hidden");
  elemento("usuario-atual").textContent = usuario.nome;
  await atualizarPainel();
}

elemento("mostrar-registro").addEventListener("click", () => {
  elemento("auth-login").classList.add("hidden");
  elemento("auth-register").classList.remove("hidden");
  mostrarFeedbackAutenticacao("");
});

elemento("mostrar-login").addEventListener("click", () => {
  elemento("auth-register").classList.add("hidden");
  elemento("auth-login").classList.remove("hidden");
  mostrarFeedbackAutenticacao("");
});

elemento("form-login").addEventListener("submit", async evento => {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const dados = Object.fromEntries(new FormData(formulario).entries());
  try {
    await requisicao("/login", { method: "POST", body: JSON.stringify(dados) });
    await atualizarTokenCsrf();
    const sessao = await requisicao("/me");
    formulario.reset();
    await abrirPainel(sessao.usuario);
  } catch (erro) {
    mostrarFeedbackAutenticacao(erro.message);
  }
});

elemento("form-registro").addEventListener("submit", async evento => {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const dados = Object.fromEntries(new FormData(formulario).entries());
  try {
    await requisicao("/register", { method: "POST", body: JSON.stringify(dados) });
    await atualizarTokenCsrf();
    const sessao = await requisicao("/me");
    formulario.reset();
    await abrirPainel(sessao.usuario);
  } catch (erro) {
    mostrarFeedbackAutenticacao(erro.message);
  }
});

elemento("botao-sair").addEventListener("click", async () => {
  try {
    await requisicao("/logout", { method: "POST", body: JSON.stringify({}) });
    await atualizarTokenCsrf();
    mostrarAutenticacao();
  } catch (erro) {
    notificar(erro.message, true);
  }
});

let toastTimer;
function notificar(mensagem, erro = false) {
  const toast = elemento("toast");
  toast.textContent = mensagem;
  toast.classList.toggle("error", erro);
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3500);
}

async function atualizarPainel() {
  try {
    const resultados = await Promise.all([
      requisicao("/resumo"),
      requisicao("/contas"),
    ]);
    const resumo = resultados[0];
    const contas = resultados[1];
    contasCache = contas;
    elemento("total-contas").textContent = resumo.total_contas;
    elemento("saldo-total").textContent = moeda(resumo.saldo_consolidado);
    elemento("total-movimentacoes").textContent = resumo.total_movimentacoes;
    elemento("count-label").textContent = contas.length + (contas.length === 1 ? " conta" : " contas");
    renderizarContas(contas);
    atualizarSelects(contas);
  } catch (erro) {
    if (erro.status === 401) {
      // Renova a sessão anônima e o token CSRF para permitir novo login
      // depois que a sessão autenticada expirar.
      try {
        await atualizarTokenCsrf();
      } catch (_erroCsrf) {
        // A tela de login continua disponível; uma nova tentativa pode renovar o token.
      }
      mostrarAutenticacao();
    } else {
      notificar(erro.message, true);
    }
  }
}

function renderizarContas(contas) {
  const corpo = elemento("lista-contas");
  if (!contas.length) {
    corpo.innerHTML = '<tr><td colspan="4" class="empty-state">Nenhuma conta cadastrada. Crie sua primeira conta acima.</td></tr>';
    return;
  }
  corpo.innerHTML = contas.map(conta => (
    '<tr>' +
      '<td><span class="account-name">' + escapar(conta.nome) + '</span><span class="account-sub">Titular da conta</span></td>' +
      '<td>' + escapar(conta.numero) + '</td>' +
      '<td class="balance-cell">' + moeda(conta.saldo) + '</td>' +
      '<td><button class="table-action" data-extrato="' + Number(conta.id) + '">Ver extrato ↗</button></td>' +
    '</tr>'
  )).join("");
  corpo.querySelectorAll("[data-extrato]").forEach(botao => {
    botao.addEventListener("click", () => abrirExtrato(Number(botao.dataset.extrato)));
  });
}

function escapar(valor) {
  return String(valor).replace(/[&<>"']/g, caractere => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[caractere]);
}

function atualizarSelects(contas) {
  const origem = elemento("conta-origem");
  const destino = elemento("conta-destino");
  const valorOrigem = origem.value;
  const valorDestino = destino.value;
  origem.innerHTML = '<option value="">Selecione uma conta</option>' + contas.map(conta =>
    '<option value="' + Number(conta.id) + '">' + escapar(conta.nome) + ' · ' + escapar(conta.numero) + '</option>'
  ).join("");
  destino.innerHTML = '<option value="">Selecione o destino</option>' + contas.map(conta =>
    '<option value="' + Number(conta.id) + '">' + escapar(conta.nome) + ' · ' + escapar(conta.numero) + '</option>'
  ).join("");
  if (contas.some(conta => String(conta.id) === valorOrigem)) origem.value = valorOrigem;
  if (contas.some(conta => String(conta.id) === valorDestino)) destino.value = valorDestino;
}

elemento("form-conta").addEventListener("submit", async evento => {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const dados = Object.fromEntries(new FormData(formulario).entries());
  try {
    const resultado = await requisicao("/contas", {
      method: "POST", body: JSON.stringify(dados),
    });
    formulario.reset();
    notificar(resultado.mensagem);
    await atualizarPainel();
  } catch (erro) {
    notificar(erro.message, true);
  }
});

document.querySelectorAll(".operation-tab").forEach(botao => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".operation-tab").forEach(item => item.classList.remove("active"));
    botao.classList.add("active");
    operacaoAtual = botao.dataset.operation;
    elemento("destino-wrap").classList.toggle("hidden", operacaoAtual !== "transferencia");
  });
});

elemento("form-operacao").addEventListener("submit", async evento => {
  evento.preventDefault();
  const origem = elemento("conta-origem").value;
  const destino = elemento("conta-destino").value;
  const valor = elemento("valor-operacao").value;
  if (!origem) return notificar("Selecione a conta de origem.", true);
  if (operacaoAtual === "transferencia" && !destino) return notificar("Selecione a conta de destino.", true);

  const operacao = operacaoAtual === "transferencia" ? "transferencias" :
    operacaoAtual === "deposito" ? "depositos" : "saques";
  const corpo = { valor };
  if (operacaoAtual === "transferencia") corpo.conta_destino_id = destino;

  try {
    const resultado = await requisicao("/contas/" + origem + "/" + operacao, {
      method: "POST", body: JSON.stringify(corpo),
    });
    elemento("valor-operacao").value = "";
    notificar(resultado.mensagem);
    await atualizarPainel();
  } catch (erro) {
    notificar(erro.message, true);
  }
});

async function abrirExtrato(contaId) {
  try {
    const dados = await requisicao("/contas/" + contaId + "/extrato");
    elemento("extrato-titular").textContent =
      dados.conta.nome + " · Conta " + dados.conta.numero + " · Saldo " + moeda(dados.conta.saldo);
    const conteudo = elemento("extrato-conteudo");
    if (!dados.transacoes.length) {
      conteudo.innerHTML = '<div class="statement-empty">Esta conta ainda não possui movimentações.</div>';
    } else {
      conteudo.innerHTML = dados.transacoes.map(item => (
        '<div class="statement-row">' +
          '<div><strong>' + escapar(item.descricao) + '</strong><small>' +
          escapar(item.tipo) + ' · ' + escapar(item.criado_em) + '</small></div>' +
          '<span class="statement-value">' + moeda(item.valor) + '</span>' +
        '</div>'
      )).join("");
    }
    elemento("modal-extrato").showModal();
  } catch (erro) {
    notificar(erro.message, true);
  }
}

elemento("fechar-extrato").addEventListener("click", () => elemento("modal-extrato").close());
elemento("modal-extrato").addEventListener("click", evento => {
  if (evento.target === elemento("modal-extrato")) elemento("modal-extrato").close();
});

async function iniciarAplicacao() {
  try {
    await atualizarTokenCsrf();
    const sessao = await requisicao("/me");
    await abrirPainel(sessao.usuario);
  } catch (erro) {
    mostrarAutenticacao();
    if (erro.status && erro.status !== 401) {
      mostrarFeedbackAutenticacao(erro.message);
    }
  }
}

iniciarAplicacao();
