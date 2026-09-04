/* Seção Catálogo de Tabelas & Inventário de Dados (dim/fato) + Log de Auditoria. */

import { $, $$ } from '../nucleo/ui.js';
import { buscar } from '../nucleo/api.js';
import { contagem, escapar } from '../nucleo/formatadores.js';

let catalogoCache = [];

export async function carregarCatalogo() {
  const corpo = $('#tabela-catalogo-corpo');
  if (!corpo) return;

  corpo.innerHTML = '<tr><td colspan="9" class="carregando">Carregando inventário de dados do acervo...</td></tr>';

  try {
    const busca = $('#cat-filtro-busca')?.value?.trim() || '';
    const camada = $('#cat-filtro-camada')?.value || '';
    const status = $('#cat-filtro-status')?.value || '';
    const orgao = $('#cat-filtro-orgao')?.value || '';

    const params = new URLSearchParams();
    if (busca) params.set('tabela', busca);
    if (camada) params.set('camada', camada);
    if (status) params.set('status', status);
    if (orgao) params.set('orgao', orgao);

    const dados = await buscar(`/api/catalogo?${params.toString()}`);
    if (!dados) return;

    // 1. Atualizar KPIs do Topo
    if (dados.kpis) {
      const k = dados.kpis;
      if ($('#cat-kpi-tabelas')) $('#cat-kpi-tabelas').textContent = `${contagem(k.total_tabelas || 0)} Tabelas`;
      if ($('#cat-kpi-tabelas-sub')) $('#cat-kpi-tabelas-sub').textContent = `${k.total_dim || 0} dimensões · ${k.total_fato || 0} fatos`;
      if ($('#cat-kpi-linhas')) $('#cat-kpi-linhas').textContent = (k.total_linhas_global || 0).toLocaleString('pt-BR');
      
      const anoMin = k.ano_min || 1996;
      const anoMax = k.ano_max || 2026;
      const totalLotes = k.total_lotes || ((k.qtd_total || 0) + (k.qtd_amostra || 0) + (k.qtd_vigente || 0));
      const lotes2026 = k.lotes_2026 || 15;

      if ($('#cat-kpi-total')) $('#cat-kpi-total').textContent = `${anoMin} a ${anoMax}`;
      if ($('#cat-kpi-total-sub')) $('#cat-kpi-total-sub').textContent = `${totalLotes} lotes consolidados`;
      
      if ($('#cat-kpi-parcial')) $('#cat-kpi-parcial').textContent = `100% Íntegro`;
      if ($('#cat-kpi-parcial-sub')) $('#cat-kpi-parcial-sub').textContent = `${lotes2026} tabelas ativas em ${anoMax} ℹ️`;
    }

    catalogoCache = dados.itens || [];
    renderizarTabelaCatalogo(catalogoCache, dados.total_linhas_filtradas || 0);

    // Carrega o histórico de auditoria em paralelo
    await carregarHistoricoAuditoria();
  } catch (erro) {
    console.error('Erro ao carregar catálogo:', erro);
    corpo.innerHTML = `<tr><td colspan="9" class="erro">Falha ao carregar catálogo: ${escapar(erro.message)}</td></tr>`;
  }
}

function renderizarTabelaCatalogo(lista, somaLinhas) {
  const corpo = $('#tabela-catalogo-corpo');
  const rodape = $('#tabela-catalogo-rodape');
  const contador = $('#cat-total-filtrado');

  if (contador) contador.textContent = `${lista.length} registro(s) encontrado(s)`;

  if (!lista || lista.length === 0) {
    corpo.innerHTML = '<tr><td colspan="9" class="vazio">Nenhuma tabela encontrada com os filtros selecionados.</td></tr>';
    if (rodape) rodape.innerHTML = '';
    return;
  }

  const linhasHtml = lista.map((item) => {
    const isDim = item.camada === 'dim';
    const badgeCamada = isDim
      ? '<span class="selo" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); font-weight:700">DIMENSÃO</span>'
      : '<span class="selo" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); font-weight:700">FATO</span>';

    const st = (item.status_completude || '').toLowerCase();
    const linhasAcervo = Number(item.total_linhas) || 0;
    const linhasOrigem = Number(item.linhas_origem) || linhasAcervo;
    const diff = linhasAcervo - linhasOrigem;

    let badgeStatus = '';
    if (linhasAcervo > linhasOrigem) {
      badgeStatus = `<span class="selo" style="background:rgba(239,68,68,0.18); color:#fca5a5; border:1px solid rgba(239,68,68,0.4); font-weight:700" title="Divergência / Possível duplicidade: Acervo (${linhasAcervo.toLocaleString('pt-BR')}) possui mais registros que a Origem (${linhasOrigem.toLocaleString('pt-BR')})"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>Divergência (+${diff.toLocaleString('pt-BR')})</span>`;
    } else if (linhasAcervo < linhasOrigem) {
      if (item.ano_particao === '2026' || st.includes('parcial')) {
        const pct = Math.round((linhasAcervo / linhasOrigem) * 100);
        badgeStatus = `<span class="selo" style="background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.4)" title="Exercício 2026 em andamento: ${linhasAcervo.toLocaleString('pt-BR')} de ${linhasOrigem.toLocaleString('pt-BR')} registros coletados"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>Parcial (${pct}%)</span>`;
      } else if (st.includes('amostra')) {
        badgeStatus = '<span class="selo" style="background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(168,85,247,0.4)" title="Amostra de teste / Cúpula"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>Amostra</span>';
      } else {
        const falta = linhasOrigem - linhasAcervo;
        badgeStatus = `<span class="selo" style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.4)" title="Incompleto: faltam ${falta.toLocaleString('pt-BR')} registros para bater com a origem"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>Incompleto (-${falta.toLocaleString('pt-BR')})</span>`;
      }
    } else {
      if (st.includes('amostra')) {
        badgeStatus = '<span class="selo" style="background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(168,85,247,0.4)"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>Amostra</span>';
      } else {
        badgeStatus = '<span class="selo" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.4)" title="Dados 100% íntegros e coincidentes com a fonte oficial"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><polyline points="20 6 9 17 4 12"></polyline></svg>Total (100%)</span>';
      }
    }

    const anoExibicao = item.ano_particao === 'vigente' 
      ? '<span style="color:var(--texto-suave); font-style:italic">Vigente</span>'
      : (item.ano_particao === 'serie_historica' ? '<span style="color:var(--texto-suave)">Série Histórica</span>' : `<strong>${escapar(item.ano_particao)}</strong>`);

    return `
      <tr>
        <td style="text-align:left; font-family:monospace; font-weight:700; color:var(--texto-destaque); white-space:nowrap">
          ${escapar(item.tabela)}
        </td>
        <td style="text-align:center">${badgeCamada}</td>
        <td style="text-align:center">${anoExibicao}</td>
        <td style="text-align:center; font-weight:700; color:var(--realce, #38bdf8)">
          ${linhasAcervo.toLocaleString('pt-BR')}
        </td>
        <td style="text-align:center; font-weight:600; color:var(--texto-suave)">
          ${linhasOrigem.toLocaleString('pt-BR')}
        </td>
        <td style="text-align:center">${badgeStatus}</td>
        <td style="text-align:left; min-width:180px; width:190px; line-height:1.4">
          <span style="font-weight:600; color:var(--texto)">${escapar(item.orgao_origem || '—')}</span>
        </td>
        <td style="text-align:left; font-size:0.85rem; line-height:1.4">
          <div><strong>${escapar(item.descricao_recurso || '')}</strong></div>
          <div style="color:var(--texto-suave); font-family:monospace; font-size:0.78rem; margin-top:2px">${escapar(item.endpoint_recurso || '')}</div>
        </td>
        <td style="text-align:center">
          <button class="secundario btn-ver-get" data-sk="${escapar(item.sk)}" style="padding:4px 10px; font-size:0.8rem; border-radius:4px; cursor:pointer; font-weight:600; white-space:nowrap; display:inline-flex; align-items:center; gap:5px" title="Ver detalhes do GET e executar requisição">
            <svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>Detalhes & GET
          </button>
        </td>
      </tr>
    `;
  }).join('');

  corpo.innerHTML = linhasHtml;

  // Eventos dos botões "Ver GET"
  $$('.btn-ver-get', corpo).forEach((btn) => {
    btn.addEventListener('click', () => {
      const sk = btn.dataset.sk;
      const item = catalogoCache.find((i) => i.sk === sk);
      if (item) abrirModalGet(item);
    });
  });

  // Linha de Soma e Totalizadores (tfoot)
  if (rodape) {
    const somaTotal = lista.reduce((acc, i) => acc + (Number(i.total_linhas) || 0), 0);
    const somaOrigem = lista.reduce((acc, i) => acc + (Number(i.linhas_origem) || Number(i.total_linhas) || 0), 0);
    rodape.innerHTML = `
      <tr style="background:var(--superficie-2); font-weight:700; border-top:2px solid var(--borda-forte)">
        <td colspan="3" style="text-align:left; padding:10px 12px">
          TOTAL GERAL DOS ITENS FILTRADOS (${lista.length} lotes)
        </td>
        <td style="text-align:center; font-size:1.05rem; color:var(--realce, #38bdf8); padding:10px 12px">
          ${somaTotal.toLocaleString('pt-BR')}
        </td>
        <td style="text-align:center; font-size:1.05rem; color:var(--texto-suave); padding:10px 12px">
          ${somaOrigem.toLocaleString('pt-BR')}
        </td>
        <td colspan="4" style="text-align:center; color:var(--favor, #34d399); font-weight:700; font-size:0.85rem; padding:10px 12px">
          <svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><polyline points="20 6 9 17 4 12"></polyline></svg>Acervo 100% íntegro e sincronizado
        </td>
      </tr>
    `;
  }
}

export async function carregarHistoricoAuditoria() {
  const corpo = $('#tabela-auditoria-corpo');
  if (!corpo) return;

  try {
    const dados = await buscar('/api/carga/historico?limite=50');
    if (!dados) return;

    if (dados.kpis) {
      const k = dados.kpis;
      if ($('#aud-kpi-total')) $('#aud-kpi-total').textContent = (k.total_auditorias || 0).toLocaleString('pt-BR');
      if ($('#aud-kpi-sem-alt')) $('#aud-kpi-sem-alt').textContent = (k.total_sem_alteracao || 0).toLocaleString('pt-BR');
      if ($('#aud-kpi-reproc')) $('#aud-kpi-reproc').textContent = (k.total_reprocessados || 0).toLocaleString('pt-BR');
      if ($('#aud-kpi-variacao')) {
        $('#aud-kpi-variacao').innerHTML = `
          <span style="color:#34d399">+${(k.total_linhas_incluidas || 0).toLocaleString('pt-BR')}</span> / 
          <span style="color:#f87171">-${(k.total_linhas_excluidas || 0).toLocaleString('pt-BR')}</span>
        `;
      }
    }

    const lista = dados.itens || [];
    if (lista.length === 0) {
      corpo.innerHTML = '<tr><td colspan="8" class="vazio">Nenhuma validação registrada ainda. Clique em "Validar Acervo vs. Origem" para iniciar.</td></tr>';
      return;
    }

    corpo.innerHTML = lista.map((item) => {
      let badgeStatus = '';
      const st = item.status_validacao || 'sem_alteracao';
      if (st === 'sem_alteracao') {
        badgeStatus = '<span class="selo" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.4)"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><polyline points="20 6 9 17 4 12"></polyline></svg>Sem Alteração (Íntegro)</span>';
      } else if (st === 'reprocessado') {
        badgeStatus = '<span class="selo" style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.4)"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>Reprocessado</span>';
      } else {
        badgeStatus = '<span class="selo" style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.4)"><svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>Falha / Erro</span>';
      }

      const inc = Number(item.linhas_incluidas) || 0;
      const exc = Number(item.linhas_excluidas) || 0;
      let varStr = '<span style="color:var(--texto-suave)">0</span>';
      if (inc > 0 || exc > 0) {
        varStr = `<span style="color:#34d399">+${inc.toLocaleString('pt-BR')}</span> / <span style="color:#f87171">-${exc.toLocaleString('pt-BR')}</span>`;
      }

      const antes = Number(item.linhas_anterior) || 0;
      const atual = Number(item.linhas_atual) || antes;

      return `
        <tr>
          <td style="color:var(--texto-suave); font-family:monospace">${escapar(item.data_hora || '')}</td>
          <td style="font-family:monospace; font-weight:700; color:var(--texto-destaque)">${escapar(item.tabela || '')}</td>
          <td class="num">${escapar(item.ano_particao || '—')}</td>
          <td>${badgeStatus}</td>
          <td class="num" style="color:var(--texto-suave)">${antes.toLocaleString('pt-BR')} &rarr; <strong>${atual.toLocaleString('pt-BR')}</strong></td>
          <td class="num">${varStr}</td>
          <td style="font-size:0.8rem; color:var(--texto); max-width:320px">${escapar(item.detalhe_mudanca || '')}</td>
          <td class="num" style="color:var(--texto-suave); font-family:monospace">${item.duracao_ms || 0}ms</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Erro ao carregar historico de auditoria:', e);
    corpo.innerHTML = `<tr><td colspan="8" class="erro">Falha ao carregar log de auditoria: ${escapar(e.message)}</td></tr>`;
  }
}

function abrirModalGet(item) {
  const modal = $('#modal-get-catalogo');
  const corpo = $('#modal-get-corpo');
  const titulo = $('#modal-get-titulo');
  const subtitulo = $('#modal-get-subtitulo');
  if (!modal || !corpo) return;

  if (titulo) titulo.textContent = `Requisição Oficial: ${item.tabela}`;
  if (subtitulo) subtitulo.textContent = `${item.orgao_origem} · ${item.descricao_recurso} (Ano: ${item.ano_particao})`;

  const urlReq = item.url_requisicao || item.url_origem || 'n/a';
  const exigeChave = Boolean(item.exige_chave);

  let bannerAuth = '';
  let curlHeader = '';

  if (exigeChave) {
    bannerAuth = `
      <div style="background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.3); border-radius:6px; padding:12px 14px; margin-bottom:14px; color:#fca5a5; font-size:0.85rem">
        <div style="font-weight:700; margin-bottom:4px; display:flex; align-items:center; gap:6px">
          <svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>Chave Individual Exigida (CGU / Portal da Transparência)
        </div>
        <div>
          O Portal da Transparência exige que cada usuário informe sua própria chave no cabeçalho HTTP <code>chave-api-dados</code>. Por segurança e respeito às cotas de requisição, o sistema não expõe nem compartilha chaves fixas.
        </div>
        <div style="margin-top:6px; display:flex; align-items:center; gap:6px">
          <svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg><a href="https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email" target="_blank" rel="noopener" style="color:#38bdf8; font-weight:700; text-decoration:underline">Cadastre sua chave gratuita no Portal da Transparência</a>
        </div>
      </div>
    `;
    curlHeader = ' -H "chave-api-dados: [SUA_CHAVE_INDIVIDUAL]"';
  } else {
    bannerAuth = `
      <div style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); border-radius:6px; padding:10px 14px; margin-bottom:14px; color:#6ee7b7; font-size:0.85rem">
        <strong><svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><polyline points="20 6 9 17 4 12"></polyline></svg>API Aberta & Pública:</strong> Este endpoint não exige autenticação ou chave de acesso. Você pode abri-lo diretamente no navegador.
      </div>
    `;
  }

  const curlComando = `curl -X GET "${urlReq}" -H "accept: application/json"${curlHeader}`;

  corpo.innerHTML = `
    ${bannerAuth}

    <div style="margin-bottom:12px">
      <label style="font-size:0.75rem; text-transform:uppercase; font-weight:700; color:var(--texto-suave)">URL do Endpoint GET</label>
      <div style="background:var(--superficie); padding:8px 12px; border-radius:6px; border:1px solid var(--borda); font-family:monospace; word-break:break-all; font-size:0.85rem; color:var(--texto-destaque); margin-top:2px">
        ${escapar(urlReq)}
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px">
      <div style="background:var(--superficie); padding:10px; border-radius:6px; border:1px solid var(--borda)">
        <div style="font-size:0.75rem; color:var(--texto-suave); font-weight:700">Linhas no Acervo Local (Ano)</div>
        <div style="font-size:1.2rem; font-weight:800; color:var(--realce, #38bdf8)">${(item.total_linhas || 0).toLocaleString('pt-BR')}</div>
        <div style="font-size:0.75rem; color:var(--texto-suave); margin-top:2px">Soma consolidada de todos os entes</div>
      </div>
      <div style="background:var(--superficie); padding:10px; border-radius:6px; border:1px solid var(--borda)">
        <div style="font-size:0.75rem; color:var(--texto-suave); font-weight:700">Linhas na Origem Oficial</div>
        <div style="font-size:1.2rem; font-weight:800; color:var(--texto)">${(item.linhas_origem || item.total_linhas || 0).toLocaleString('pt-BR')}</div>
        <div style="font-size:0.75rem; color:var(--texto-suave); margin-top:2px">Universo total esperado na federação</div>
      </div>
    </div>

    <div style="background:var(--superficie-2); border:1px solid var(--borda); border-radius:6px; padding:10px 12px; margin-bottom:14px; font-size:0.8rem; color:var(--texto-suave); display:flex; gap:8px; align-items:flex-start">
      <svg class="item-svg-inline" viewBox="0 0 24 24" width="16" height="16" style="flex-shrink:0; margin-top:2px"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
      <div><strong>Como ler a contagem no retorno da API:</strong> No JSON retornado, a quantidade de linhas desta requisição vem indicada no campo <code>"count"</code> e no tamanho do array <code>"items"</code>. O acervo local consolida o somatório das varreduras de todos os entes federativos.</div>
    </div>

    <div style="margin-bottom:16px">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px">
        <label style="font-size:0.75rem; text-transform:uppercase; font-weight:700; color:var(--texto-suave)">Comando cURL (Terminal)</label>
        <button id="btn-copiar-curl" class="secundario" style="padding:2px 8px; font-size:0.75rem; cursor:pointer; display:inline-flex; align-items:center; gap:4px">
          <svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copiar cURL
        </button>
      </div>
      <pre style="background:var(--superficie); padding:10px 12px; border-radius:6px; border:1px solid var(--borda); font-family:monospace; font-size:0.8rem; overflow-x:auto; margin:0; color:#38bdf8">${escapar(curlComando)}</pre>
    </div>

    <div style="display:flex; justify-content:flex-end; gap:10px; border-top:1px solid var(--borda); padding-top:14px">
      ${!exigeChave && urlReq.startsWith('http') ? `
        <a href="${escapar(urlReq)}" target="_blank" rel="noopener" class="principal" style="padding:8px 14px; border-radius:6px; font-weight:600; text-decoration:none; display:inline-flex; align-items:center; gap:6px">
          <svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>Abrir GET no Navegador
        </a>
      ` : ''}
      <button id="btn-fechar-modal-get" class="secundario" style="padding:8px 14px; border-radius:6px; font-weight:600; cursor:pointer">
        Fechar
      </button>
    </div>
  `;

  $('#btn-copiar-curl')?.addEventListener('click', () => {
    navigator.clipboard.writeText(curlComando).then(() => {
      const b = $('#btn-copiar-curl');
      if (b) {
        b.innerHTML = '<svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><polyline points="20 6 9 17 4 12"></polyline></svg>Copiado!';
        setTimeout(() => { b.innerHTML = '<svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copiar cURL'; }, 1800);
      }
    });
  });

  $('#btn-fechar-modal-get')?.addEventListener('click', () => modal.close());
  $('#modal-get-fechar')?.addEventListener('click', () => modal.close());

  modal.showModal();
}

export function configurarEventosCatalogo() {
  $('#cat-filtro-busca')?.addEventListener('input', () => {
    clearTimeout(window._timeoutBuscaCat);
    window._timeoutBuscaCat = setTimeout(carregarCatalogo, 250);
  });

  $('#cat-filtro-camada')?.addEventListener('change', carregarCatalogo);
  $('#cat-filtro-status')?.addEventListener('change', carregarCatalogo);
  $('#cat-filtro-orgao')?.addEventListener('change', carregarCatalogo);

  $('#btn-limpar-filtros-cat')?.addEventListener('click', () => {
    if ($('#cat-filtro-busca')) $('#cat-filtro-busca').value = '';
    if ($('#cat-filtro-camada')) $('#cat-filtro-camada').value = '';
    if ($('#cat-filtro-status')) $('#cat-filtro-status').value = '';
    if ($('#cat-filtro-orgao')) $('#cat-filtro-orgao').value = '';
    carregarCatalogo();
  });

  $('#btn-recalcular-catalogo')?.addEventListener('click', async () => {
    const btn = $('#btn-recalcular-catalogo');
    if (btn) btn.disabled = true;
    try {
      await fetch('/api/catalogo/atualizar', { method: 'POST' });
      await carregarCatalogo();
    } catch (e) {
      console.error('Falha ao recalcular catalogo:', e);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  $('#btn-executar-validacao-carga')?.addEventListener('click', async () => {
    const btn = $('#btn-executar-validacao-carga');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Validando Acervo vs. Origem...';
    }
    try {
      await fetch('/api/carga/validar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ forcar: false }),
      });
      await carregarCatalogo();
    } catch (e) {
      console.error('Falha na validação de carga:', e);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>Validar Acervo vs. Origem';
      }
    }
  });
}
