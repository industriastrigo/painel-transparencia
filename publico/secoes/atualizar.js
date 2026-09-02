/* Atualização em segundo plano, acompanhamento e configuração de chave. */
import { $, $$ } from '../nucleo/ui.js';
import { escapar, txt } from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { estado, carregarMapa } from './mapa.js';

/* ------------------------------------------------------------- atualizar */

let relogioColeta = null;

async function montarCatalogo() {
  const alvo = $('#catalogo-fontes');
  let fontes;
  try {
    fontes = await buscar('/api/coleta/catalogo');
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para ler o catálogo de fontes.', erro);
    return;
  }
  if (!fontes.length) {
    alvo.innerHTML = '<p class="vazio">Catálogo indisponível.</p>';
    return;
  }
  fontes.forEach((f) => { ROTULOS_FONTE[f.fonte] = f.rotulo; });
  // Cada fonte traz COMO ela atualiza. Duas fontes marcadas na mesma tela
  // não significam a mesma coisa: a Câmara republica o ano corrente todo dia,
  // o SICONFI só fecha o exercício anterior, o TSE só muda a cada eleição.
  // Esconder isso faz a pessoa esperar dado que ainda não existe.
  alvo.innerHTML = fontes.map((f, i) => `
    <div class="fonte">
      <label class="opcao">
        <input type="checkbox" value="${atributo(f.fonte)}"
               aria-describedby="sobre-${i}"
               ${['camara', 'senado'].includes(f.fonte) ? 'checked' : ''}>
        <span>${escapar(f.rotulo)}</span>
        <span class="cadencia">${escapar(f.cadencia)}</span>
      </label>
      <div class="sobre-fonte" id="sobre-${i}">
        <dl>
          <dt>Recorte do ano</dt>
          <dd>${f.usa_ano ? escapar(f.periodo)
                          : `<span class="sem-ano">ignora o campo Ano</span>
                             — ${escapar(f.periodo)}`}</dd>
          <dt>Cada linha é</dt><dd>${escapar(f.granularidade)}</dd>
          <dt>Costuma levar</dt><dd>${escapar(f.duracao)}</dd>
        </dl>
        ${f.requer ? `<p class="exige">⚙ Precisa antes: ${escapar(f.requer)}</p>` : ''}
        ${f.observacao ? `<p>${escapar(f.observacao)}</p>` : ''}
      </div>
    </div>`).join('');
}

async function mostrarEstadoDaChave() {
  const cfg = await buscar('/api/config').catch(() => null);
  const cartao = $('#cartao-chave');
  const estado = $('#estado-chave');
  if (!cfg) { cartao.hidden = true; return; }

  const portal = cfg.portal_transparencia;
  cartao.hidden = false;
  estado.textContent = portal.configurada
    ? `Configurada (final ${portal.mascara}). Cole uma nova para substituir.`
    : 'Sem chave — as emendas parlamentares não podem ser coletadas.';
  $('#campo-chave').placeholder = portal.configurada
    ? 'substituir a chave atual' : 'cole aqui — a chave ou o bloco de exemplo';
}

async function salvarChave() {
  const campo = $('#campo-chave');
  const resposta = $('#resposta-chave');
  const botao = $('#salvar-chave');

  if (!campo.value.trim()) {
    resposta.textContent = 'Cole a chave antes de salvar.';
    return;
  }

  botao.disabled = true;
  resposta.textContent = 'salvando e testando…';

  // `try/finally`: sem ele, uma falha de rede pulava o `disabled = false` e
  // o botão Salvar ficava travado com "salvando e testando…" para sempre.
  let r;
  let corpo = {};
  try {
    r = await fetch('/api/config/chave-portal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave: campo.value }),
    });
    corpo = await r.json().catch(() => ({}));
  } catch (erro) {
    resposta.textContent = `Não deu para falar com o painel: ${erro.message}`;
    return;
  } finally {
    botao.disabled = false;
  }

  if (!r.ok) {
    resposta.textContent = corpo.detail || corpo.erro
      || `Não deu para salvar (${r.status}).`;
    return;
  }

  // Some da tela assim que sai daqui: não fica chave guardada no campo.
  campo.value = '';
  resposta.textContent = corpo.validada
    ? `Salva e ${corpo.mensagem}`
    : `Salva (${corpo.mascara}), mas ${corpo.mensagem}`;
  await mostrarEstadoDaChave();
}

function fontesMarcadas() {
  return [...$$('#catalogo-fontes input:checked')].map((i) => i.value);
}

async function dispararColeta() {
  const fontes = fontesMarcadas();
  const aviso = $('#aviso-coleta');
  if (!fontes.length) {
    aviso.textContent = 'Marque ao menos uma fonte.';
    return;
  }

  const ano = $('#coleta-ano').value;
  const corpo = {
    fontes,
    ano: ano ? Number(ano) : null,
    nivel: $('#coleta-nivel').value,
    uf: $('#coleta-uf').value.trim().toUpperCase() || null,
  };

  $('#botao-atualizar').disabled = true;
  aviso.textContent = 'iniciando…';

  let resp;
  try {
    resp = await fetch('/api/coleta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
  } catch (erro) {
    // Mesmo defeito de `salvarChave`: sem isto o botão Atualizar ficava
    // desabilitado e o aviso preso em "iniciando…", sem saída.
    aviso.textContent = `Não deu para falar com o painel: ${erro.message}`;
    $('#botao-atualizar').disabled = false;
    return;
  }

  if (resp.status === 409) {
    aviso.textContent = 'Já existe uma atualização rodando — espere terminar.';
    $('#botao-atualizar').disabled = false;
    acompanharColeta();
    return;
  }
  if (!resp.ok) {
    aviso.textContent = `Não deu para iniciar (${resp.status}).`;
    $('#botao-atualizar').disabled = false;
    return;
  }

  aviso.textContent = '';
  renderizarColeta(await resp.json());
  acompanharColeta();
}

/** Acompanha a coleta em andamento.
 *
 *  Três correções sobre a versão anterior, todas do mesmo tipo — laço que
 *  não sabia parar:
 *
 *  1. **Sem trava de requisição em voo.** `/api/coleta` durante uma coleta
 *     pesada leva mais de 2 s; os ticks se acumulavam e as respostas chegavam
 *     fora de ordem, fazendo a barra de progresso ANDAR PARA TRÁS.
 *  2. **Falha do polling era `return` mudo.** API fora do ar no meio da
 *     coleta = painel congelado no último estado conhecido, para sempre, sem
 *     dizer nada.
 *  3. **Nunca parava.** Se a tarefa travasse em `executando`, o relógio
 *     seguia batendo com o usuário em outra aba e a máquina desligada.
 */
function acompanharColeta() {
  if (relogioColeta) clearInterval(relogioColeta);
  let emVoo = false;
  let falhasSeguidas = 0;

  relogioColeta = setInterval(async () => {
    if (emVoo) return;
    if (document.hidden) return;   // aba escondida: nada para atualizar
    emVoo = true;
    let tarefa;
    try {
      tarefa = await buscar('/api/coleta');
      falhasSeguidas = 0;
    } catch (erro) {
      falhasSeguidas += 1;
      if (falhasSeguidas >= 5) {
        pararColeta();
        $('#aviso-coleta').textContent =
          'Perdi contato com o painel. A coleta pode continuar rodando no '
          + 'servidor — recarregue a página para reencontrá-la.';
      }
      return;
    } finally {
      emVoo = false;
    }

    renderizarColeta(tarefa);
    if (tarefa.situacao === 'executando') return;

    pararColeta();
    $('#botao-atualizar').disabled = false;
    // O armazém mudou: recria as views e recarrega o que está na tela.
    await fetch('/api/recarregar', { method: 'POST' }).catch(() => {});
    // O ano escolhido pelo usuário é preservado: `carregarAnos` reatribuía
    // `estado.ano` para o mais recente e o mapa saltava de exercício sozinho,
    // no fim de uma coleta que podia ter durado horas.
    const anoEscolhido = estado.ano;
    await carregarAnos();
    if (anoEscolhido && [...$('#ano').options].some((o) => Number(o.value) === anoEscolhido)) {
      estado.ano = anoEscolhido;
      $('#ano').value = String(anoEscolhido);
    }
    malhasEmCache.clear();
    abasCarregadas.clear();   // o acervo mudou: toda aba precisa reler
    await carregarSituacao().catch(() => {});
    await carregarMapa().catch(() => {});
    if ($('#tabela-proposicoes tbody').children.length) {
      await montarFiltrosDeProposicao();
      await carregarProposicoes();
    }
  }, 2000);
}

function pararColeta() {
  if (relogioColeta) clearInterval(relogioColeta);
  relogioColeta = null;
}

// Sair da página com um relógio batendo deixa requisição em voo sem dono.
window.addEventListener('beforeunload', pararColeta);

/** Rótulo legível de cada fonte, preenchido pelo catálogo da API. A lista de
 *  etapas mostrava o nome interno (`siconfi_rgf`) enquanto a lista de seleção,
 *  logo acima, mostrava o nome por extenso — duas telas falando da mesma
 *  coisa com nomes diferentes. */
const ROTULOS_FONTE = {};

const SINAIS = {
  aguardando: '·', executando: '▸', ok: '✓', parcial: '!', erro: '✕',
  configuracao: '⚙',
};

const ROTULO_ETAPA = {
  aguardando: 'aguardando', executando: 'coletando', ok: 'ok',
  parcial: 'parcial', erro: 'erro', configuracao: 'falta configurar',
};

function renderizarColeta(tarefa) {
  const alvo = $('#progresso-coleta');
  if (!tarefa || tarefa.situacao === 'nenhuma') {
    alvo.innerHTML = '<p class="vazio">Nenhuma atualização em andamento.</p>';
    return;
  }

  const p = tarefa.progresso || { feitas: 0, total: 0 };
  const emAndamento = tarefa.situacao === 'executando';

  // "8/8 fontes" com um ✓ verde escondia que uma delas terminou parcial —
  // e era justamente a que deixou a aba Custo do Estado vazia. O resumo
  // agora conta por desfecho, não por conclusão.
  const porSituacao = {};
  (tarefa.etapas || []).forEach((e) => {
    porSituacao[e.situacao] = (porSituacao[e.situacao] || 0) + 1;
  });
  const problemas = Object.entries(porSituacao)
    .filter(([s]) => !['ok', 'aguardando', 'executando'].includes(s))
    .map(([s, n]) => `${n} ${ROTULO_ETAPA[s] ?? s}`);

  const pct = p.total ? Math.round((p.feitas / p.total) * 100) : 0;
  const duracao = tarefa.inicio
    ? formatarData(tarefa.fim || tarefa.inicio, true) : '';

  alvo.innerHTML = `
    <p class="rodape-mapa" role="status">
      Atualização #${escapar(tarefa.id)} · ${emAndamento
        ? `rodando ${escapar(tarefa.fonte_atual ?? '')}` : escapar(tarefa.situacao)}
      · ${p.feitas}/${p.total} fontes${problemas.length
        ? ` · <strong>${escapar(problemas.join(', '))}</strong>` : ''}
      ${duracao ? `· ${emAndamento ? 'desde' : 'terminou'} ${duracao}` : ''}
    </p>
    <div class="progresso-trilho" role="progressbar" aria-valuemin="0"
         aria-valuemax="100" aria-valuenow="${pct}"
         aria-label="Progresso da atualização">
      <i style="width:${pct}%"></i>
    </div>
    <ul class="etapas">
      ${(tarefa.fontes || []).map((f) => {
        const e = (tarefa.etapas || []).find((x) => x.fonte === f)
          || { situacao: 'aguardando', detalhe: '', erros: [] };
        return `<li class="${escapar(e.situacao)}">
          <span class="sinal" aria-hidden="true">${SINAIS[e.situacao] ?? '·'}</span>
          <span>${escapar(ROTULOS_FONTE[f] ?? f)}</span>
          <span class="cadencia">${escapar(ROTULO_ETAPA[e.situacao] ?? e.situacao)}</span>
          ${e.detalhe ? `<span class="detalhe">${escapar(e.detalhe)}</span>` : ''}
          ${(e.erros || []).slice(0, 3).map((m) =>
            `<span class="detalhe">${escapar(m)}</span>`).join('')}
        </li>`;
      }).join('')}
    </ul>`;

  const registro = $('#log-coleta');
  const linhas = tarefa.linhas || [];
  registro.hidden = linhas.length === 0;
  const colado = registro.scrollTop + registro.clientHeight
    >= registro.scrollHeight - 30;
  // Só as últimas: numa coleta municipal de três horas o array só cresce, e
  // o log inteiro era reconstruído a cada dois segundos. O que interessa é o
  // fim dele.
  const ULTIMAS = 400;
  const recorte = linhas.slice(-ULTIMAS);
  registro.innerHTML = (linhas.length > ULTIMAS
      ? `<span class="hora">… ${contagem(linhas.length - ULTIMAS)} linha(s) `
        + `anteriores omitidas; o log completo está em logs/</span>\n` : '')
    + recorte.map((l) =>
      `<span class="hora">${escapar(l.hora)}</span> `
      + `<span class="${escapar(l.nivel)}">${escapar(l.texto)}</span>`).join('\n');
  if (colado) registro.scrollTop = registro.scrollHeight;
}


export {
  montarCatalogo, mostrarEstadoDaChave, salvarChave, fontesMarcadas,
  dispararColeta, acompanharColeta, pararColeta, renderizarColeta
};
