const API = "/api";
let operacaoAtual = "deposito";
let contasCache = [];

const elemento = (id) => document.getElementById(id);
const moeda = (valor) => Number(valor || 0).toLocaleString("pt-BR", {
  style: "currency", currency: "BRL"
});

async function requisicao(url, opcoes = {}) {
  const resposta = await fetch(`${API}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || "Não foi possível concluir a solicitação.");
  return dados;
}

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
    const [resumo, contas] = await Promise.all([
      requisicao("/resumo"),
      requisicao("/contas"),
    ]);
    contasCache = contas;
    elemento("total-contas").textContent = resumo.total_contas;
    elemento("saldo-total").textContent = moeda(resumo.saldo_consolidado);
    elemento("total-movimentacoes").textContent = resumo.total_movimentacoes;
    elemento("count-label").textContent = `${contas.length} ${contas.length === 1 ? "conta" : "contas"}`;
    renderizarContas(contas);
    atualizarSelects(contas);
  } catch (erro) {
    notificar(erro.message, true);
  }
}

function renderizarContas(contas) {
  const corpo = elemento("lista-contas");
  if (!contas.length) {
    corpo.innerHTML = '<tr><td colspan="4" class="empty-state">Nenhuma conta cadastrada. Crie sua primeira conta acima.</td></tr>';
    return;
  }
  corpo.innerHTML = contas.map(conta => `
    <tr>
      <td><span class="account-name">${escapar(conta.nome)}</span><span class="account-sub">Titular da conta</span></td>
      <td>${escapar(conta.numero)}</td>
      <td class="balance-cell">${moeda(conta.saldo)}</td>
      <td><button class="table-action" data-extrato="${conta.id}">Ver extrato ↗</button></td>
    </tr>
  `).join("");
  corpo.querySelectorAll("[data-extrato]").forEach(botao => {
    botao.addEventListener("click", () => abrirExtrato(Number(botao.dataset.extrato)));
  });
}

function escapar(valor) {
  return String(valor).replace(/[&<>"']/g, caractere => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[caractere]);
}

function atualizarSelects(contas) {
  const origem = elemento("conta-origem");
  const destino = elemento("conta-destino");
  const valorOrigem = origem.value;
  const valorDestino = destino.value;
  origem.innerHTML = '<option value="">Selecione uma conta</option>' + contas.map(c =>
    `<option value="${c.id}">${escapar(c.nome)} · ${escapar(c.numero)}</option>`
  ).join("");
  destino.innerHTML = '<option value="">Selecione o destino</option>' + contas.map(c =>
    `<option value="${c.id}">${escapar(c.nome)} · ${escapar(c.numero)}</option>`
  ).join("");
  if (contas.some(c => String(c.id) === valorOrigem)) origem.value = valorOrigem;
  if (contas.some(c => String(c.id) === valorDestino)) destino.value = valorDestino;
}

elemento("form-conta").addEventListener("submit", async evento => {
  evento.preventDefault();

  // Guarde a referência antes do await: currentTarget deixa de estar disponível
  // depois que o navegador termina de despachar o evento.
  const formulario = evento.currentTarget;
  const form = new FormData(formulario);
  const dados = Object.fromEntries(form.entries());
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

  let rota = `/${origem}/${operacaoAtual === "transferencia" ? "transferencias" : operacaoAtual === "deposito" ? "depositos" : "saques"}`;
  const corpo = { valor };
  if (operacaoAtual === "transferencia") corpo.conta_destino_id = destino;

  try {
    const resultado = await requisicao(`/contas${rota}`, {
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
    const dados = await requisicao(`/contas/${contaId}/extrato`);
    elemento("extrato-titular").textContent = `${dados.conta.nome} · Conta ${dados.conta.numero} · Saldo ${moeda(dados.conta.saldo)}`;
    const conteudo = elemento("extrato-conteudo");
    if (!dados.transacoes.length) {
      conteudo.innerHTML = '<div class="statement-empty">Esta conta ainda não possui movimentações.</div>';
    } else {
      conteudo.innerHTML = dados.transacoes.map(item => `
        <div class="statement-row">
          <div><strong>${escapar(item.descricao)}</strong><small>${escapar(item.tipo)} · ${escapar(item.criado_em)}</small></div>
          <span class="statement-value">${moeda(item.valor)}</span>
        </div>
      `).join("");
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

atualizarPainel();
