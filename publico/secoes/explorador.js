/* Explorador de Dados (Data Lakehouse / GCP BigQuery Studio). */
import { $, $$ } from '../nucleo/ui.js';
import { escapar, atributo, txt, contagem, formatarData } from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { esqueleto, falha } from '../nucleo/ui.js';

let _arvoreDados = null;
let _tabelaAtiva = { dataset: 'fato', tabela: 'despesa_parlamentar' };
let _paginaAtual = 1;
const _limitePorPagina = 100;
let _buscaPreview = '';

/* ---------------------------------------------------------------- carga principal */

async function carregarExplorador() {
  const containerArvore = $('#explorador-arvore');
  if (!containerArvore) return;

  if (!_arvoreDados) {
    containerArvore.innerHTML = esqueleto(6);
    try {
      _arvoreDados = await buscar('/api/explorador/arvore');
    } catch (erro) {
      containerArvore.innerHTML = falha('Não deu para carregar a árvore de dados.', erro);
      return;
    }
  }

  renderizarArvore();
  ligarFiltroArvore();
  ligarAbasExplorador();
  ligarEditorSql();

  // Seleciona tabela padrão se nenhuma foi selecionada
  selecionarTabela(_tabelaAtiva.dataset, _tabelaAtiva.tabela);
}

/* ---------------------------------------------------------------- árvore GCP */

function renderizarArvore(filtroTexto = '') {
  const containerArvore = $('#explorador-arvore');
  if (!containerArvore || !_arvoreDados) return;

  const termo = filtroTexto.trim().toLowerCase();

  const htmlDatasets = _arvoreDados.datasets.map((ds) => {
    const tabelasFiltradas = ds.tabelas.filter((t) => {
      if (!termo) return true;
      return t.nome.toLowerCase().includes(termo) || (t.descricao && t.descricao.toLowerCase().includes(termo));
    });

    if (termo && tabelasFiltradas.length === 0) return '';

    const aberto = termo || ds.id === _tabelaAtiva.dataset ? 'open' : '';

    return `
      <details class="gcp-dataset" ${aberto} data-dataset="${escapar(ds.id)}">
        <summary class="gcp-dataset-header">
          <span class="gcp-chevron"><svg class="item-svg-inline" viewBox="0 0 24 24" width="10" height="10" style="margin-right:0"><polyline points="9 18 15 12 9 6"></polyline></svg></span>
          <span class="gcp-icone-pasta"><svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg></span>
          <strong class="gcp-dataset-nome">${escapar(ds.id)}</strong>
          <span class="gcp-badge-qtd">${tabelasFiltradas.length}</span>
        </summary>
        <ul class="gcp-lista-tabelas">
          ${tabelasFiltradas.map((t) => {
            const isAtiva = t.dataset === _tabelaAtiva.dataset && t.nome === _tabelaAtiva.tabela ? 'ativa' : '';
            const icone = t.tipo === 'view' ? '<svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>' : '<svg class="item-svg-inline" viewBox="0 0 24 24" width="13" height="13"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>';
            return `
              <li class="gcp-item-tabela ${isAtiva}" data-dataset="${escapar(t.dataset)}" data-tabela="${escapar(t.nome)}" role="button" tabindex="0">
                <span class="gcp-icone-tabela">${icone}</span>
                <span class="gcp-nome-tabela" title="${escapar(t.descricao || t.nome)}">${escapar(t.nome)}</span>
                <span class="gcp-tamanho-tabela">${t.linhas ? contagem(t.linhas) : '—'}</span>
              </li>
            `;
          }).join('')}
        </ul>
      </details>
    `;
  }).join('');

  containerArvore.innerHTML = `
    <div class="gcp-projeto-header">
      <span class="gcp-icone-proj"><svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="22.01"></line><line x1="15" y1="22" x2="15" y2="22.01"></line><line x1="9" y1="18" x2="9" y2="18.01"></line><line x1="15" y1="18" x2="15" y2="18.01"></line><line x1="9" y1="14" x2="9" y2="14.01"></line><line x1="15" y1="14" x2="15" y2="14.01"></line><line x1="9" y1="10" x2="9" y2="10.01"></line><line x1="15" y1="10" x2="15" y2="10.01"></line><line x1="9" y1="6" x2="9" y2="6.01"></line><line x1="15" y1="6" x2="15" y2="6.01"></line></svg></span>
      <div class="gcp-proj-info">
        <span class="gcp-proj-label">PROJETO</span>
        <strong>${escapar(_arvoreDados.projeto || 'painel-transparencia')}</strong>
      </div>
      <span class="gcp-badge-sgbd">DuckDB</span>
    </div>
    <div class="gcp-datasets-tree">
      ${htmlDatasets || '<p class="vazio" style="padding:10px">Nenhuma tabela encontrada com esse filtro.</p>'}
    </div>
  `;

  // Eventos de clique nas tabelas
  containerArvore.querySelectorAll('.gcp-item-tabela').forEach((item) => {
    item.addEventListener('click', () => {
      selecionarTabela(item.dataset.dataset, item.dataset.tabela);
    });
    item.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        selecionarTabela(item.dataset.dataset, item.dataset.tabela);
      }
    });
  });
}

function ligarFiltroArvore() {
  const campoBusca = $('#filtro-arvore-tabelas');
  if (!campoBusca || campoBusca.dataset.ligado) return;
  campoBusca.dataset.ligado = 'true';

  campoBusca.addEventListener('input', () => {
    renderizarArvore(campoBusca.value);
  });
}

/* ---------------------------------------------------------------- seleção de tabela */

async function selecionarTabela(dataset, tabela) {
  _tabelaAtiva = { dataset, tabela };
  _paginaAtual = 1;
  _buscaPreview = '';

  // Atualiza classes na árvore
  $$('.gcp-item-tabela').forEach((el) => {
    const ativa = el.dataset.dataset === dataset && el.dataset.tabela === tabela;
    el.classList.toggle('ativa', ativa);
  });

  // Atualiza cabeçalho de trabalho
  const tituloHeader = $('#explorador-tabela-titulo');
  if (tituloHeader) {
    tituloHeader.innerHTML = `
      <span class="gcp-caminho-completo">
        <span class="proj">${escapar(_arvoreDados?.projeto || 'painel')}</span>.<span class="ds">${escapar(dataset)}</span>.<strong class="tb">${escapar(tabela)}</strong>
      </span>
    `;
  }

  // Preenche a query no console SQL
  const consoleSql = $('#editor-sql-texto');
  if (consoleSql) {
    consoleSql.value = `SELECT * 
  FROM ${escapar(tabela)}
 LIMIT 100;`;
  }

  // Carrega as abas da tabela
  await Promise.all([
    carregarEsquema(dataset, tabela),
    carregarDetalhes(dataset, tabela),
    carregarPreview(dataset, tabela, 1)
  ]);
}

/* ---------------------------------------------------------------- 1. Esquema */

async function carregarEsquema(dataset, tabela) {
  const alvo = $('#painel-esquema-conteudo');
  if (!alvo) return;
  alvo.innerHTML = esqueleto(5);

  let dadosEsquema;
  try {
    dadosEsquema = await buscar(`/api/explorador/tabela/${encodeURIComponent(dataset)}/${encodeURIComponent(tabela)}/esquema`);
  } catch (erro) {
    alvo.innerHTML = falha('Não foi possível carregar o esquema.', erro);
    return;
  }

  const colunas = dadosEsquema.colunas || [];
  if (!colunas.length) {
    alvo.innerHTML = '<p class="vazio">Nenhuma coluna encontrada.</p>';
    return;
  }

  alvo.innerHTML = `
    <div class="gcp-info-barra">
      <span>Campos do Esquema (${colunas.length} colunas)</span>
      <button class="secundario pequeno" id="btn-copiar-campos">Copiar Colunas</button>
    </div>
    <div class="rolagem" style="max-height: 480px">
      <table class="gcp-tabela-esquema">
        <thead>
          <tr>
            <th>Nome do Campo</th>
            <th>Tipo de Dado (GCP/BigQuery)</th>
            <th>Tipo Físico</th>
            <th>Modo</th>
            <th>Chave</th>
          </tr>
        </thead>
        <tbody>
          ${colunas.map((c) => {
            const tipoGcp = c.tipo_gcp || 'STRING';
            const modo = c.modo || 'NULLABLE';
            const tipoFisico = c.tipo || 'VARCHAR';
            return `
              <tr>
                <td><code class="gcp-coluna-nome">${escapar(c.nome || '')}</code></td>
                <td><span class="gcp-tag-tipo tipo-${escapar(tipoGcp.toLowerCase())}">${escapar(tipoGcp)}</span></td>
                <td class="tipo-fisico">${escapar(tipoFisico)}</td>
                <td><span class="gcp-modo ${escapar(modo.toLowerCase())}">${escapar(modo)}</span></td>
                <td>${c.is_pk ? '<span class="gcp-pk-badge" title="Chave de junção / PK"><svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><path d="M21 2l-2 2m-1.5 1.5L14 9l-1.5-1.5-4 4 1.5 1.5L8 15l-1.5-1.5-4 4 1.5 1.5L1 22h3l3-3 1.5 1.5L11 18l-1.5-1.5 4-4 1.5 1.5 3.5-3.5a5.5 5.5 0 1 0-7.78-7.78z"></path></svg>PK</span>' : '—'}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  $('#btn-copiar-campos')?.addEventListener('click', () => {
    const lista = colunas.map((c) => c.nome).join(', ');
    navigator.clipboard.writeText(lista);
    alert('Colunas copiadas para a área de transferência!');
  });
}

/* ---------------------------------------------------------------- 2. Detalhes */

async function carregarDetalhes(dataset, tabela) {
  const alvo = $('#painel-detalhes-conteudo');
  if (!alvo) return;
  alvo.innerHTML = esqueleto(4);

  let d;
  try {
    d = await buscar(`/api/explorador/tabela/${encodeURIComponent(dataset)}/${encodeURIComponent(tabela)}/detalhes`);
  } catch (erro) {
    alvo.innerHTML = falha('Não foi possível carregar os detalhes.', erro);
    return;
  }

  alvo.innerHTML = `
    <div class="gcp-detalhes-grid">
      <div class="gcp-detalhes-card">
        <h3>Armazenamento e Lakehouse</h3>
        <dl>
          <dt>Formato</dt><dd>${escapar(d.formato)}</dd>
          <dt>Tipo de Tabela</dt><dd>${escapar(d.tipo)}</dd>
          <dt>Localização no Disco</dt><dd><code>${escapar(d.localizacao)}</code></dd>
          <dt>Tamanho Total</dt><dd><strong>${escapar(d.tamanho_formatado)}</strong> (${contagem(d.tamanho_bytes)} bytes)</dd>
          <dt>Total de Registros</dt><dd><strong>${contagem(d.total_linhas)}</strong> linhas</dd>
          <dt>Última Modificação</dt><dd>${escapar(d.modificado_em)}</dd>
        </dl>
      </div>

      <div class="gcp-detalhes-card">
        <h3>Esquema e Particionamento</h3>
        <dl>
          <dt>Particionamento Hive</dt><dd>${d.particionamento?.length ? d.particionamento.map((p) => `<code>${escapar(p)}</code>`).join(', ') : 'Nenhum (Tabela Única)'}</dd>
          <dt>Chaves Primárias (PK)</dt><dd>${d.chaves_primarias?.length ? d.chaves_primarias.map((k) => `<code>${escapar(k)}</code>`).join(', ') : 'sk'}</dd>
          <dt>Frequência de Atualização</dt><dd>${escapar(d.cadencia)}</dd>
          <dt>Descrição do Negócio</dt><dd>${escapar(d.descricao)}</dd>
        </dl>
      </div>
    </div>
  `;
}

/* ---------------------------------------------------------------- 3. Visualização (Preview 100 linhas) */

async function carregarPreview(dataset, tabela, pagina = 1, busca = '') {
  const alvo = $('#painel-preview-conteudo');
  if (!alvo) return;
  alvo.innerHTML = esqueleto(6);

  let resp;
  try {
    resp = await buscar(`/api/explorador/tabela/${encodeURIComponent(dataset)}/${encodeURIComponent(tabela)}/dados`, {
      pagina,
      limite: _limitePorPagina,
      busca: busca || undefined,
    });
  } catch (erro) {
    alvo.innerHTML = falha('Não foi possível carregar a visualização de dados.', erro);
    return;
  }

  const { colunas, linhas, total_linhas: totalLinhas, total_paginas: totalPaginas } = resp;
  _paginaAtual = pagina;
  _buscaPreview = busca;

  if (!linhas.length) {
    alvo.innerHTML = `
      <div class="gcp-preview-toolbar">
        <input id="campo-busca-preview" placeholder="Filtrar dados da amostra..." value="${escapar(busca)}" />
        <button id="btn-busca-preview" class="secundario">Filtrar</button>
      </div>
      <p class="vazio">Nenhum dado encontrado para esta tabela.</p>
    `;
    ligarBuscaPreview(dataset, tabela);
    return;
  }

  const inicioLinha = (pagina - 1) * _limitePorPagina + 1;
  const fimLinha = Math.min(pagina * _limitePorPagina, totalLinhas);

  alvo.innerHTML = `
    <div class="gcp-preview-toolbar">
      <div class="gcp-busca-bloco">
        <input id="campo-busca-preview" placeholder="Filtrar texto nas colunas..." value="${escapar(busca)}" />
        <button id="btn-busca-preview" class="secundario">Filtrar</button>
        ${busca ? `<button id="btn-limpa-busca-preview" class="secundario">Limpar</button>` : ''}
      </div>
      <div class="gcp-paginacao-bloco">
        <span class="gcp-paginacao-info">Mostrando <strong>${contagem(inicioLinha)}–${contagem(fimLinha)}</strong> de <strong>${contagem(totalLinhas)}</strong></span>
        <button class="secundario pequeno" id="btn-pag-anterior" ${pagina <= 1 ? 'disabled' : ''}>◀ Anterior</button>
        <span class="gcp-pag-contador">Pág. ${pagina} de ${totalPaginas}</span>
        <button class="secundario pequeno" id="btn-pag-proxima" ${pagina >= totalPaginas ? 'disabled' : ''}>Próxima ▶</button>
      </div>
    </div>

    <div class="rolagem gcp-preview-grid-wrap" style="max-height: 520px">
      <table class="gcp-tabela-preview">
        <thead>
          <tr>
            <th class="col-num" title="Número da Linha">#</th>
            ${colunas.map((col) => `<th title="${atributo(col)}">${escapar(col)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${linhas.map((row, idx) => `
            <tr>
              <td class="col-num" title="Linha ${inicioLinha + idx}">${inicioLinha + idx}</td>
              ${colunas.map((col) => {
                const val = row[col];
                if (val === null || val === undefined) return '<td class="nulo" title="null">null</td>';
                const strVal = String(val);
                const attrVal = atributo(strVal);
                if (typeof val === 'number') return `<td class="valor-num" title="${attrVal}">${escapar(strVal)}</td>`;
                return `<td title="${attrVal}">${escapar(strVal)}</td>`;
              }).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  ligarBuscaPreview(dataset, tabela);

  $('#btn-pag-anterior')?.addEventListener('click', () => {
    if (_paginaAtual > 1) carregarPreview(dataset, tabela, _paginaAtual - 1, _buscaPreview);
  });

  $('#btn-pag-proxima')?.addEventListener('click', () => {
    if (_paginaAtual < totalPaginas) carregarPreview(dataset, tabela, _paginaAtual + 1, _buscaPreview);
  });
}

function ligarBuscaPreview(dataset, tabela) {
  const campo = $('#campo-busca-preview');
  const btn = $('#btn-busca-preview');
  const btnLimpar = $('#btn-limpa-busca-preview');

  let timerBusca = null;
  const executar = (manterFoco = false) => {
    if (!campo) return;
    const val = campo.value.trim();
    carregarPreview(dataset, tabela, 1, val).then(() => {
      if (manterFoco) {
        const novoCampo = $('#campo-busca-preview');
        if (novoCampo) {
          novoCampo.focus();
          novoCampo.setSelectionRange(novoCampo.value.length, novoCampo.value.length);
        }
      }
    });
  };

  btn?.addEventListener('click', () => executar(true));
  campo?.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      clearTimeout(timerBusca);
      executar(true);
    }
  });

  campo?.addEventListener('input', () => {
    clearTimeout(timerBusca);
    timerBusca = setTimeout(() => {
      executar(true);
    }, 450);
  });

  btnLimpar?.addEventListener('click', () => {
    if (campo) campo.value = '';
    carregarPreview(dataset, tabela, 1, '').then(() => {
      $('#campo-busca-preview')?.focus();
    });
  });
}

/* ---------------------------------------------------------------- 4. Editor SQL */

function ligarEditorSql() {
  const btnExecutar = $('#btn-executar-sql');
  const btnExportarCsv = $('#btn-exportar-csv');
  const btnExportarJson = $('#btn-exportar-json');
  const campoSql = $('#editor-sql-texto');

  if (!btnExecutar || btnExecutar.dataset.ligado) return;
  btnExecutar.dataset.ligado = 'true';

  btnExecutar.addEventListener('click', executarConsultaSql);
  campoSql?.addEventListener('keydown', (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
      ev.preventDefault();
      executarConsultaSql();
    }
  });

  btnExportarCsv?.addEventListener('click', () => exportarConsulta('csv'));
  btnExportarJson?.addEventListener('click', () => exportarConsulta('json'));
}

async function executarConsultaSql() {
  const campoSql = $('#editor-sql-texto');
  const alvoResultado = $('#sql-resultado-container');
  const statusMsg = $('#sql-status-msg');
  if (!campoSql || !alvoResultado) return;

  const sql = campoSql.value.trim();
  if (!sql) return;

  alvoResultado.innerHTML = esqueleto(5);
  if (statusMsg) statusMsg.textContent = 'Executando consulta no DuckDB...';

  try {
    const resp = await fetch('/api/explorador/consulta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, limite: 1000 }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alvoResultado.innerHTML = `<div class="falha" role="alert"><p>Erro SQL: ${escapar(err.detail || 'Falha na consulta.')}</p></div>`;
      if (statusMsg) statusMsg.textContent = 'Falha na execução.';
      return;
    }

    const data = await resp.json();
    const { colunas, linhas, total_linhas: total, tempo_ms: tempo } = data;

    if (statusMsg) {
      statusMsg.innerHTML = `<svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><polyline points="20 6 9 17 4 12"></polyline></svg>Consulta concluída em <strong>${tempo} ms</strong> (${contagem(total)} linhas retornadas)`;
    }

    if (!linhas.length) {
      alvoResultado.innerHTML = '<p class="vazio" style="padding:16px">Consulta executada com sucesso, nenhum registro retornado.</p>';
      return;
    }

    alvoResultado.innerHTML = `
      <div class="rolagem gcp-preview-grid-wrap" style="max-height: 480px">
        <table class="gcp-tabela-preview">
          <thead>
            <tr>
              <th class="col-num" title="Número da Linha">#</th>
              ${colunas.map((col) => `<th title="${atributo(col)}">${escapar(col)}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${linhas.map((row, idx) => `
              <tr>
                <td class="col-num" title="Linha ${idx + 1}">${idx + 1}</td>
                ${colunas.map((col) => {
                  const val = row[col];
                  if (val === null || val === undefined) return '<td class="nulo" title="null">null</td>';
                  const strVal = String(val);
                  const attrVal = atributo(strVal);
                  if (typeof val === 'number') return `<td class="valor-num" title="${attrVal}">${escapar(strVal)}</td>`;
                  return `<td title="${attrVal}">${escapar(strVal)}</td>`;
                }).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (erro) {
    alvoResultado.innerHTML = falha('Erro de comunicação ao executar query.', erro);
    if (statusMsg) statusMsg.textContent = 'Erro de comunicação.';
  }
}

async function exportarConsulta(formato = 'csv') {
  const campoSql = $('#editor-sql-texto');
  if (!campoSql) return;
  const sql = campoSql.value.trim();
  if (!sql) {
    alert('Digite uma consulta SQL para exportar.');
    return;
  }

  try {
    const resp = await fetch('/api/explorador/exportar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, formato }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(`Erro ao exportar: ${err.detail || 'Falha na exportação.'}`);
      return;
    }

    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `extracao_${_tabelaAtiva.tabela || 'dados'}.${formato}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (erro) {
    alert(`Erro ao baixar arquivo: ${erro}`);
  }
}

/* ---------------------------------------------------------------- abas do explorador */

function ligarAbasExplorador() {
  const botoes = $$('.gcp-tab-btn');
  const paineis = $$('.gcp-painel-tab');

  botoes.forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
      botoes.forEach((b) => b.setAttribute('aria-selected', 'false'));
      paineis.forEach((p) => { p.hidden = true; });

      btn.setAttribute('aria-selected', 'true');
      const painel = $(`#painel-${btn.dataset.painel}`);
      if (painel) painel.hidden = false;
    });
  });
}

export { carregarExplorador, selecionarTabela };
