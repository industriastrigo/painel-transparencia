/* Projetos de Lei: tramitação e placar de votos nominais. */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, endereco, numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS, LIMITE_CONSULTA, SELO_SITUACAO
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { abrirDialogo, esqueleto, falha, falhaEmLinha } from '../nucleo/ui.js';

/* ---------------------------------------------------------------- proposições */

/** Preenche um seletor a partir dos valores que EXISTEM no acervo. */
async function preencherSeletor(seletor, rota, campo, rotuloTodos) {
  const alvo = $(seletor);
  const escolhido = alvo.value;
  const valores = await buscar(rota).catch(() => []);

  alvo.innerHTML = `<option value="">${rotuloTodos}</option>`
    + valores.map((v) => `<option value="${atributo(v[campo])}">`
      + `${escapar(v[campo])} (${contagem(v.quantidade)})</option>`).join('');

  // Mantém a escolha do usuário se ela continuar existindo depois de coletar.
  if (escolhido && valores.some((v) => String(v[campo]) === escolhido)) {
    alvo.value = escolhido;
  }
  alvo.disabled = valores.length === 0;
  return valores.length;
}

async function montarFiltrosDeProposicao() {
  const [situacoes] = await Promise.all([
    preencherSeletor('#filtro-situacao', '/api/proposicoes/situacoes',
                     'situacao', 'todas'),
    preencherSeletor('#filtro-tipo', '/api/proposicoes/tipos',
                     'sigla_tipo', 'todos'),
  ]);

  if (situacoes === 0) {
    $('#filtro-situacao').innerHTML =
      '<option value="">nenhuma situação no acervo</option>';
  }
}

async function carregarProposicoes() {
  const corpo = $('#tabela-proposicoes tbody');
  const resumo = $('#resumo-proposicoes');
  const botao = $('#buscar-proposicoes');
  corpo.innerHTML = `<tr><td colspan="5">${esqueleto(5)}</td></tr>`;
  botao.disabled = true;

  let linhas;
  try {
    linhas = await buscar('/api/proposicoes', {
      busca: $('#filtro-proposicao').value,
      situacao: $('#filtro-situacao').value,
      tipo: $('#filtro-tipo').value,
      de: $('#filtro-de').value,
      ate: $('#filtro-ate').value,
      limite: LIMITE_CONSULTA,
    });
  } catch (erro) {
    corpo.innerHTML = falhaEmLinha(5, 'Não deu para buscar as proposições.', erro);
    resumo.textContent = '';
    return;
  } finally {
    botao.disabled = false;
  }
  const filtrando = $('#filtro-situacao').value || $('#filtro-tipo').value
    || $('#filtro-proposicao').value || $('#filtro-de').value
    || $('#filtro-ate').value;

  if (!linhas.length) {
    corpo.innerHTML = `<tr><td colspan="5" class="vazio">${filtrando
      ? 'Nenhuma proposição neste recorte.'
      : 'Nenhuma proposição coletada. Use a aba Atualizar.'}</td></tr>`;
    resumo.textContent = '';
    return;
  }

  resumo.textContent = `${contagem(linhas.length)} proposiç${
    linhas.length === 1 ? 'ão' : 'ões'}`
    + (linhas.length === LIMITE_CONSULTA
      ? ` (limite da consulta — refine o filtro para ver o resto)` : '');

  corpo.innerHTML = linhas.map((p) => `
    <tr class="clicavel" tabindex="0" role="button"
        aria-label="Abrir ${atributo(p.identificador ?? 'proposição')}"
        data-casa="${atributo(p.casa)}" data-id="${atributo(p.id_proposicao)}">
      <td><span class="etiqueta">${txt(p.identificador ?? p.sigla_tipo)}</span></td>
      <td>${escapar((p.ementa ?? '').slice(0, 190))}${(p.ementa ?? '').length > 190 ? '…' : ''}</td>
      <td>${txt(p.nome_autor)}${p.partido_autor
        ? ` (${escapar(p.partido_autor)}-${escapar(p.uf_autor ?? '')})` : ''}${
        aNumero(p.qtd_autores) > 1
          ? `<br><span class="cadencia">e mais ${contagem(p.qtd_autores - 1)}</span>` : ''}</td>
      <td>${formatarData(p.data_apresentacao)}</td>
      <td>${txt(p.situacao)}${p.orgao_atual
        ? `<br><span class="cadencia">${escapar(p.orgao_atual)}</span>` : ''}</td>
    </tr>`).join('');

  $$('tr.clicavel', corpo).forEach((tr) => {
    const abrir = () => abrirProposicao(tr.dataset.casa, tr.dataset.id);
    tr.addEventListener('click', abrir);
    // A linha era clicável só com mouse: `role="button"` sem tecla é uma
    // promessa que a tela não cumpria.
    tr.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrir(); }
    });
  });
}

async function abrirProposicao(casa, id) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = '<p class="vazio">Carregando…</p>';
  dialogo.showModal();

  const detalhe = await buscar(`/api/proposicoes/${casa}/${id}`).catch(() => null);
  if (!detalhe) { alvo.innerHTML = '<p class="vazio">Não encontrada.</p>'; return; }

  const p = detalhe.proposicao;
  const oficial = endereco(p.url);
  const tramitacoes = detalhe.tramitacoes ?? [];
  const votacoes = detalhe.votacoes ?? [];

  alvo.innerHTML = `
    <h2>${txt(p.identificador)}</h2>
    ${p.situacao ? `<p><span class="etiqueta">${escapar(p.situacao)}</span>${
      p.orgao_atual ? ` <span class="rodape-mapa">em ${escapar(p.orgao_atual)}</span>` : ''
    }</p>` : ''}
    <p>${txt(p.ementa)}</p>
    <p class="rodape-mapa">Autor: <strong>${txt(p.nome_autor)}</strong>
      ${p.partido_autor ? `(${escapar(p.partido_autor)}-${escapar(p.uf_autor ?? '')})` : ''}
      · Apresentada em ${formatarData(p.data_apresentacao)}
      ${aNumero(p.qtd_autores) > 0 ? `· ${contagem(p.qtd_autores)} autor(es)` : ''}</p>
    ${oficial
      ? `<p><a class="fonte-oficial" href="${oficial}" target="_blank"
             rel="noopener noreferrer">Ver na fonte oficial</a></p>`
      : ''}

    <h2>Tramitação — todas as etapas</h2>
    ${tramitacoes.length ? `<div class="rolagem"><table><thead><tr>
        <th>Data</th><th>Órgão</th><th>Etapa</th></tr></thead><tbody>
      ${tramitacoes.map((t) => `<tr>
        <td>${formatarData(t.data_hora, true)}</td><td>${txt(t.orgao)}</td>
        <td>${txt(t.descricao_tramitacao ?? t.descricao_situacao)}${
          t.despacho ? `<br><span class="cadencia">${escapar(t.despacho)}</span>` : ''}
        </td></tr>`).join('')}
      </tbody></table></div>`
      : `<p class="vazio">${detalhe.tramitacao_sob_demanda
            ? 'A Câmara não publica tramitação no arquivo em lote: é uma '
              + 'consulta por proposição, e o acervo tem 153 mil.'
            : 'Tramitações não coletadas para esta proposição.'}</p>
         ${detalhe.tramitacao_sob_demanda
            ? `<p style="text-align:center"><button class="principal"
                 id="buscar-tramitacao">Buscar as etapas agora</button></p>`
            : ''}`}

    <h2>Votações</h2>
    ${votacoes.length ? votacoes.map((v) => `
      <div class="cartao" style="margin-bottom:12px">
        <strong>${formatarData(v.data_hora, true)} · ${escapar(v.sigla_orgao ?? '')}</strong>
        ${v.aprovada === true || v.aprovada === false
          ? `<span class="selo ${v.aprovada ? 'calmo' : 'risco'}"
                   style="margin-left:8px">${v.aprovada ? 'Aprovada' : 'Rejeitada'}</span>`
          : ''}
        <p>${txt(v.descricao)}</p>
        <div class="placar">
          <span class="sim">A favor: ${contagem(v.sim)}</span>
          <span class="nao">Contra: ${contagem(v.nao)}</span>
          <span>Abstenção: ${contagem(v.abstencao)}</span>
          <span>Outros: ${contagem(v.outros)}</span>
        </div>
        <button class="ver-votos discreto" data-casa="${atributo(casa)}"
                data-votacao="${atributo(v.id_votacao)}">Ver quem votou</button>
        <div class="lista-votos"></div>
      </div>`).join('')
      : '<p class="vazio">Sem votação nominal registrada para esta proposição.</p>'}`;

  // Uma requisição, no clique de quem quer ver ESTA proposição. Varrer as
  // 153 mil do acervo levaria mais de 42 h no freio de 1 req/s.
  alvo.querySelector('#buscar-tramitacao')?.addEventListener('click', async (ev) => {
    const botao = ev.currentTarget;
    botao.disabled = true;
    botao.textContent = 'Buscando na Câmara…';
    // `buscar` monta query string; aqui o verbo é POST, então vai direto no
    // fetch, como as outras escritas do painel.
    const r = await fetch(`${API}/api/proposicoes/${encodeURIComponent(casa)}/`
                          + `${encodeURIComponent(id)}/tramitacoes`,
                          { method: 'POST' })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .catch(() => null);
    if (!r) {
      botao.disabled = false;
      botao.textContent = 'A Câmara não respondeu. Tentar de novo';
      return;
    }
    abrirProposicao(casa, id);          // redesenha com as etapas no acervo
  });

  alvo.querySelectorAll('.ver-votos').forEach((b) => {
    b.addEventListener('click', async () => {
      const destino = b.nextElementSibling;
      destino.innerHTML = '<p class="vazio">Carregando…</p>';
      const r = await buscar(
        `/api/votacoes/${b.dataset.casa}/${b.dataset.votacao}/votos`).catch(() => null);
      if (!r || !r.votos.length) {
        destino.innerHTML = '<p class="vazio">Votos não disponíveis para esta '
          + 'votação. Rode o coletor em lote da Câmara.</p>';
        return;
      }
      destino.innerHTML = `<table><thead><tr>
          <th>Parlamentar</th><th>Partido</th><th>UF</th><th>Voto</th>
        </tr></thead><tbody>
        ${r.votos.map((v) => {
          const voto = String(v.voto ?? '');
          const classe = /^Sim/i.test(voto) ? 'sim'
            : /^N[ãa]o/i.test(voto) ? 'nao' : '';
          return `<tr>
          <td>${txt(v.nome_politico)}</td><td>${txt(v.sigla_partido)}</td>
          <td>${txt(v.sigla_uf)}</td>
          <td class="${classe}">${txt(v.voto)}</td></tr>`;
        }).join('')}
        </tbody></table>`;
    });
  });
}


export {
  preencherSeletor, montarFiltrosDeProposicao, carregarProposicoes,
  abrirProposicao
};
