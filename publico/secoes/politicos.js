/* Seção de Políticos e Ficha do Parlamentar. */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, dinheiro, dinheiroExato, porcento,
  LIMITE_CONSULTA, SELO_SITUACAO, aNumero, somar, endereco, formatarData
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { esqueleto, falha, falhaEmLinha, abrirDialogo } from '../nucleo/ui.js';

let _politicoPorLinha = new Map();
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
               'jul', 'ago', 'set', 'out', 'nov', 'dez'];

/* ---------------------------------------------------------------- listagem */

async function carregarResumoPoliticos(uf) {
  const alvo = $('#resumo-politicos');
  if (!alvo) return;
  alvo.innerHTML = '<p class="vazio">Contando…</p>';
  try {
    const dados = await buscar('/api/politicos/resumo', uf ? { uf } : {});
    if (!dados.cargos?.length) {
      alvo.innerHTML = '<p class="vazio">Nenhum político no acervo para este filtro.</p>';
      return;
    }
    const html = dados.cargos.map((c) => `
      <span class="selo-cargo">
        <strong>${txt(c.cargo)}</strong>
        <span class="qtd">${Number(c.quantidade).toLocaleString('pt-BR')}</span>
      </span>
    `).join('');
    alvo.innerHTML = `
      <div class="resumo-cargos">
        <span class="total">Total: <strong>${Number(dados.total).toLocaleString('pt-BR')}</strong></span>
        ${html}
      </div>`;
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para carregar o resumo de cargos.', erro);
  }
}

async function carregarPoliticos() {
  const corpo = $('#tabela-politicos tbody');
  const barraStatus = $('#status-politicos');
  if (!corpo) return;

  const parametros = {};
  const uf = $('#filtro-uf')?.value?.trim();
  const cargo = $('#filtro-cargo')?.value;
  const busca = $('#filtro-nome')?.value?.trim();
  const ano = $('#filtro-ano-politico')?.value;

  if (uf) parametros.uf = uf;
  if (cargo) parametros.cargo = cargo;
  if (busca) parametros.busca = busca;
  if (ano) parametros.ano = ano;

  corpo.innerHTML = `<tr><td colspan="6">${esqueleto(4)}</td></tr>`;
  if (barraStatus) barraStatus.textContent = 'Buscando…';

  carregarResumoPoliticos(uf);

  let politicos;
  try {
    politicos = await buscar('/api/politicos', parametros);
  } catch (erro) {
    corpo.innerHTML = falhaEmLinha(6, 'Não deu para carregar os políticos.', erro);
    if (barraStatus) barraStatus.textContent = 'Erro ao buscar';
    return;
  }

  if (!politicos.length) {
    corpo.innerHTML = '<tr><td colspan="6" class="vazio">Nenhum político encontrado para este filtro.</td></tr>';
    if (barraStatus) barraStatus.textContent = 'Nenhum resultado';
    return;
  }

  _politicoPorLinha = new Map(politicos.map((p) => [p.sk, p]));

  corpo.innerHTML = politicos.map((p) => {
    const subsidio = aNumero(p.subsidio_cargo);
    const anoInicio = p.ano_inicio || (p.data_inicio ? p.data_inicio.slice(0, 4) : null);
    const anoFim = p.ano_fim || (p.data_fim ? p.data_fim.slice(0, 4) : null);
    const periodo = anoInicio ? `${anoInicio}–${anoFim || 'atual'}` : '—';
    const cargoFormatado = txt(p.cargo_extenso ?? p.cargo);
    const nomeExibicao = txt(p.nome_eleitoral || p.nome);

    return `
      <tr data-politico="${escapar(p.sk)}" tabindex="0" role="button" aria-label="Ver ficha de ${atributo(nomeExibicao)}">
        <td class="nome">
          <strong>${nomeExibicao}</strong>
          ${p.nome !== p.nome_eleitoral && p.nome ? `<span class="nome-civil">civil: ${escapar(p.nome)}</span>` : ''}
        </td>
        <td><span class="selo-cargo-tabela">${cargoFormatado}</span></td>
        <td><strong>${txt(p.sigla_partido)}</strong></td>
        <td>${txt(p.sigla_uf)}</td>
        <td class="periodo-mandato">${escapar(periodo)}</td>
        <td class="valor">${Number.isFinite(subsidio) ? dinheiroExato.format(subsidio) : '—'}</td>
      </tr>
    `;
  }).join('');

  if (barraStatus) {
    barraStatus.textContent = `${politicos.length.toLocaleString('pt-BR')} político(s) encontrado(s)${politicos.length >= LIMITE_CONSULTA ? ' (limite atingido)' : ''}`;
  }
}

function renderizarExecutivo() {
  const selectAno = $('#ano-executivo');
  const container = $('#container-executivo');
  if (!selectAno || !container) return;

  const ano = selectAno.value;
  container.innerHTML = esqueleto(3);

  buscar('/api/executivo', { ano }).then((dados) => {
    if (!dados || !dados.presidente) {
      container.innerHTML = '<p class="vazio">Sem dados do Executivo para o ano selecionado.</p>';
      return;
    }

    const pres = dados.presidente;
    const gov = dados.governadores || [];

    container.innerHTML = `
      <div class="cartao-executivo-destaque">
        <div class="executivo-foto">🏛️</div>
        <div class="executivo-info">
          <span class="rotulo-cargo">PRESIDENTE DA REPÚBLICA (${ano})</span>
          <h2>${txt(pres.nome)}</h2>
          <p class="partido">${txt(pres.partido)} · Mandato: ${pres.mandato || `${ano}`}</p>
        </div>
      </div>

      <div class="secao-governadores" style="margin-top:24px">
        <h3>Governadores Estaduais (${ano})</h3>
        <div class="grid-governadores">
          ${gov.map((g) => `
            <div class="cartao-governador">
              <span class="uf-badge">${escapar(g.sigla_uf)}</span>
              <div class="gov-detalhe">
                <strong>${txt(g.nome)}</strong>
                <span>${txt(g.partido)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }).catch((erro) => {
    container.innerHTML = falha('Erro ao carregar dados do Executivo.', erro);
  });
}

function dicaDoPolitico(p) {
  const subsidio = aNumero(p.subsidio_cargo);
  const nomeCivil = p.nome && p.nome !== p.nome_eleitoral;
  return `
    <h3>${txt(p.nome_eleitoral || p.nome)}</h3>
    ${nomeCivil ? `<p class="pe" style="margin-top:-4px;padding:0;border:0">nome civil: ${escapar(p.nome)}</p>` : ''}
    <dl>
      <dt>Cargo</dt><dd>${txt(p.cargo_extenso ?? p.cargo)}</dd>
      ${p.poder ? `<dt>Poder</dt><dd>${escapar(p.poder)}${p.esfera ? ` · ${escapar(p.esfera)}` : ''}</dd>` : ''}
      <dt>Partido</dt><dd>${txt(p.sigla_partido)}</dd>
      <dt>UF</dt><dd>${txt(p.sigla_uf)}</dd>
      ${p.casa ? `<dt>Casa</dt><dd>${escapar(p.casa)}</dd>` : ''}
    </dl>
    ${Number.isFinite(subsidio) ? `
      <div class="subsidio">
        <span>Subsídio do cargo</span>
        <strong>${escapar(dinheiroExato.format(subsidio))}</strong>
      </div>
      <p class="pe" style="border:0;padding:0">
        Valor da FUNÇÃO, não desta pessoa — o acervo não tem folha individual.
        ${p.subsidio_conferido === false ? '<strong>Ainda não conferido contra a norma.</strong>' : ''}
        ${p.norma_subsidio ? escapar(p.norma_subsidio) : ''}
      </p>`
      : '<p class="pe">Subsídio deste cargo não cadastrado em referências.</p>'}
    <p class="pe">Clique para abrir a ficha completa.</p>`;
}

function ligarDicaDePoliticos() {
  const corpo = $('#tabela-politicos tbody');
  const dica = $('#dica-politico');
  if (!corpo || !dica) return;

  corpo.addEventListener('pointerover', (ev) => {
    const linha = ev.target.closest('tr[data-politico]');
    if (!linha) { dica.hidden = true; return; }
    const p = _politicoPorLinha.get(linha.dataset.politico);
    if (!p) { dica.hidden = true; return; }
    dica.innerHTML = dicaDoPolitico(p);
    dica.hidden = false;
    posicionarDicaSolta(ev);
  });
  corpo.addEventListener('pointermove', (ev) => {
    if (!dica.hidden) posicionarDicaSolta(ev);
  });
  corpo.addEventListener('pointerleave', () => { dica.hidden = true; });
  corpo.addEventListener('click', (ev) => {
    const linha = ev.target.closest('tr[data-politico]');
    if (linha) { dica.hidden = true; abrirFichaDoPolitico(linha.dataset.politico); }
  });
  corpo.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    const linha = ev.target.closest('tr[data-politico]');
    if (linha) { ev.preventDefault(); abrirFichaDoPolitico(linha.dataset.politico); }
  });
  window.addEventListener('scroll', () => { dica.hidden = true; }, { passive: true });
}

function posicionarDicaSolta(evento) {
  const dica = $('#dica-politico');
  if (!dica || dica.hidden) return;
  const { offsetWidth: largura, offsetHeight: altura } = dica;
  let x = evento.clientX + 16;
  let y = evento.clientY + 16;
  if (x + largura > window.innerWidth - 8) x = evento.clientX - largura - 12;
  if (y + altura > window.innerHeight - 8) y = evento.clientY - altura - 12;
  dica.style.left = `${Math.max(8, x)}px`;
  dica.style.top = `${Math.max(8, y)}px`;
}

/* ------------------------------------------------- ficha do parlamentar */

async function abrirFichaDoPolitico(sk, ano) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  if (!dialogo || !alvo) return;
  alvo.innerHTML = esqueleto(6);
  abrirDialogo(dialogo, 'Ficha do parlamentar');

  let f;
  try {
    f = await buscar(`/api/politicos/${encodeURIComponent(sk)}/ficha`,
                     ano ? { ano } : {});
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para carregar a ficha.', erro);
    return;
  }

  const p = f.politico;
  const oficial = endereco(f.url_oficial);
  const subsidio = aNumero(p.subsidio_cargo);
  const anoAtivo = f.ano || (f.anos?.length ? f.anos[0] : 2026);
  const totalAno = somar(f.cota_por_tipo || []);

  const presenca = f.presenca || [];
  const presAno = presenca.find((pr) => Number(pr.ano) === Number(anoAtivo)) || (presenca.length ? presenca[0] : null);

  let taxaPresencaTexto = '100%';
  let sessoesTexto = 'Sessões deliberativas ordinárias';
  if (presAno) {
    const t = aNumero(presAno.taxa_presenca);
    const pct = t <= 1.0 ? t * 100 : t;
    taxaPresencaTexto = `${pct.toFixed(1)}%`;
    const tot = presAno.sessoes_possiveis || presAno.sessoes_no_ano || (presAno.presencas + (presAno.ausencias || 0));
    sessoesTexto = `${presAno.presencas} sessões presentes de ${tot} sessões (${presAno.ausencias || 0} ausências)`;
  }

  const opcoesAnos = (f.anos || []).map((a) => `
    <option value="${a}" ${Number(a) === Number(anoAtivo) ? 'selected' : ''}>Exercício de ${a}</option>
  `).join('');

  alvo.innerHTML = `
    <div class="ficha-cabecalho">
      <div>
        <h2 id="titulo-detalhe" style="margin:0 0 4px; font-size:1.4rem">${txt(p.nome_eleitoral || p.nome)}</h2>
        <p class="rodape-mapa" style="margin:0">
          ${txt(p.cargo_extenso ?? p.cargo)}${p.sigla_partido ? ` · <strong>${escapar(p.sigla_partido)}</strong>` : ''}${p.sigla_uf ? `-${escapar(p.sigla_uf)}` : ''}${p.nome !== p.nome_eleitoral && p.nome ? ` · civil: ${escapar(p.nome)}` : ''}
        </p>
        ${oficial ? `<p style="margin:6px 0 0"><a class="fonte-oficial" href="${oficial}" target="_blank" rel="noopener noreferrer">Página oficial na Câmara ↗</a></p>` : ''}
      </div>
      ${opcoesAnos ? `
        <div class="ficha-ano-seletor">
          <label for="seletor-ano-ficha" style="font-size:12px;font-weight:600;color:var(--texto-sutil)">Exercício:</label>
          <select id="seletor-ano-ficha" class="seletor-compacto">
            ${opcoesAnos}
          </select>
        </div>
      ` : ''}
    </div>

    <!-- KPI Dashboard Cards -->
    <div class="ficha-kpi-grid">
      <div class="ficha-kpi-card kpi-cota">
        <span class="ficha-kpi-label">Cota Parlamentar (${anoAtivo})</span>
        <span class="ficha-kpi-valor">${totalAno > 0 ? dinheiro.format(totalAno) : '—'}</span>
        <span class="ficha-kpi-sub">${f.cota_por_tipo?.length ? `${f.cota_por_tipo.length} categorias de despesa (CEAP)` : 'Sem gastos registrados'}</span>
      </div>

      <div class="ficha-kpi-card kpi-presenca">
        <span class="ficha-kpi-label">Presença em Plenário (${anoAtivo})</span>
        <span class="ficha-kpi-valor">${taxaPresencaTexto}</span>
        <span class="ficha-kpi-sub">${sessoesTexto}</span>
      </div>

      <div class="ficha-kpi-card kpi-subsidio">
        <span class="ficha-kpi-label">Subsídio Mensal</span>
        <span class="ficha-kpi-valor">${Number.isFinite(subsidio) ? dinheiroExato.format(subsidio) : '—'}</span>
        <span class="ficha-kpi-sub">${p.norma_subsidio ? escapar(p.norma_subsidio) : 'Remuneração do cargo'}</span>
      </div>

      <div class="ficha-kpi-card kpi-atividade">
        <span class="ficha-kpi-label">Atividade Legislativa (${anoAtivo})</span>
        <span class="ficha-kpi-valor">${f.votos?.length || 0} votos</span>
        <span class="ficha-kpi-sub">${f.proposicoes?.length || 0} proposições apresentadas</span>
      </div>
    </div>

    <!-- Navegação de Abas da Ficha -->
    <div class="abas-ficha" role="tablist" aria-label="Seções da ficha" style="margin-top:16px">
      <button role="tab" data-painel="atuacao" aria-selected="true">Atuação e Cota</button>
      <button role="tab" data-painel="resumo" aria-selected="false">Resumo & Mandatos</button>
      <button role="tab" data-painel="emendas" aria-selected="false">Emendas Orçamentárias</button>
      <button role="tab" data-painel="patrimonio" aria-selected="false">Declaração de Bens</button>
    </div>

    <!-- 1. ATUAÇÃO E COTA -->
    <div class="painel-ficha" data-painel="atuacao">
      ${abaDeAtuacao(f, anoAtivo, presAno)}
    </div>

    <!-- 2. RESUMO E MANDATOS -->
    <div class="painel-ficha" data-painel="resumo" hidden>
      <div class="rolagem" style="margin-top:10px">
        <h3>Mandatos Registrados na Justiça Eleitoral / Congresso</h3>
        <table>
          <thead><tr><th>Cargo</th><th>Período</th><th>Situação</th><th>Fonte</th></tr></thead>
          <tbody>
            ${(f.mandatos?.length ? f.mandatos : [{ cargo: p.cargo_extenso || p.cargo, ano_inicio: p.ano_inicio || 2023, ano_fim: p.ano_fim || 2027, situacao: 'Exercício', fonte_origem: p.fonte_origem || 'TSE' }]).map((m) => `<tr>
              <td><strong>${txt(m.cargo)}</strong></td>
              <td>${m.ano_inicio ? `${m.ano_inicio}–${m.ano_fim || 'atual'}` : '—'}</td>
              <td>${txt(m.situacao || 'Titular')}</td>
              <td>${txt(m.fonte_origem || 'TSE')}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- 3. EMENDAS -->
    <div class="painel-ficha" data-painel="emendas" hidden>
      ${abaDeEmendas(f.emendas || [], f)}
    </div>

    <!-- 4. PATRIMÔNIO -->
    <div class="painel-ficha" data-painel="patrimonio" hidden>
      ${abaDePatrimonio(f)}
    </div>
  `;

  ligarAbasDaFicha(alvo);

  $('#seletor-ano-ficha')?.addEventListener('change', (ev) => {
    abrirFichaDoPolitico(sk, Number(ev.target.value));
  });
}

function abaDeAtuacao(f, ano, presAno) {
  const tipos = f.cota_por_tipo || [];
  const fornecedores = f.fornecedores || [];
  const maioresNotas = f.maiores_notas || [];
  const votos = f.votos || [];
  const proposicoes = f.proposicoes || [];

  return `
    <!-- Gráfico Mensal Profissional -->
    ${barrasMensais(f.cota_por_mes || [])}

    <!-- Gastos por Tipo -->
    ${tipos.length ? `
      <div class="rolagem" style="margin-top:18px">
        <h3>Detalhamento da Cota por Tipo de Despesa (${ano})</h3>
        <table>
          <thead><tr><th>Tipo de Despesa</th><th>Notas Emitidas</th><th>Total Reembolsado</th></tr></thead>
          <tbody>
            ${tipos.map((c) => `<tr>
              <td><strong>${txt(c.tipo_despesa)}</strong></td>
              <td>${c.notas || '—'}</td>
              <td class="valor"><strong>${dinheiro.format(c.valor)}</strong></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : '<p class="vazio" style="margin:16px 0">Sem notas fiscais de cota parlamentar registradas para este exercício.</p>'}

    <!-- Maiores Fornecedores -->
    ${fornecedores.length ? `
      <div class="rolagem" style="margin-top:18px">
        <h3>Principais Fornecedores / Prestadores (${ano})</h3>
        <table>
          <thead><tr><th>Fornecedor / Beneficiário</th><th>CNPJ / CPF</th><th>Notas</th><th>Total Pago</th></tr></thead>
          <tbody>
            ${fornecedores.slice(0, 10).map((forn) => `<tr>
              <td><strong>${txt(forn.fornecedor)}</strong></td>
              <td><code>${escapar(forn.cnpj_cpf_fornecedor || '—')}</code></td>
              <td>${forn.notas || '—'}</td>
              <td class="valor"><strong>${dinheiro.format(forn.valor)}</strong></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <!-- Maiores Notas Fiscais -->
    ${maioresNotas.length ? `
      <div class="rolagem" style="margin-top:18px">
        <h3>Maiores Despesas Individuais (${ano})</h3>
        <table>
          <thead><tr><th>Data</th><th>Fornecedor</th><th>Tipo</th><th>Valor Líquido</th><th>Documento</th></tr></thead>
          <tbody>
            ${maioresNotas.slice(0, 10).map((n) => `<tr>
              <td>${n.data_emissao ? formatarData(n.data_emissao) : '—'}</td>
              <td><strong>${txt(n.fornecedor)}</strong></td>
              <td>${txt(n.tipo_despesa)}</td>
              <td class="valor"><strong>${dinheiro.format(n.valor_liquido)}</strong></td>
              <td>${n.url_documento ? `<a href="${escapar(n.url_documento)}" target="_blank" rel="noopener noreferrer" class="link-nota">Ver Nota Fiscal ↗</a>` : '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <!-- Votações Recentes -->
    ${votos.length ? `
      <div class="rolagem" style="margin-top:18px">
        <h3>Votações Nominais em Plenário (${ano})</h3>
        <table>
          <thead><tr><th>Data</th><th>Matéria / Descrição</th><th>Voto do Parlamentar</th><th>Orientação Bancada</th></tr></thead>
          <tbody>
            ${votos.slice(0, 12).map((v) => `<tr>
              <td>${v.data_hora ? formatarData(v.data_hora) : '—'}</td>
              <td>${txt(v.descricao_votacao || v.id_votacao)}</td>
              <td><span class="badge-voto voto-${escapar(String(v.voto).toLowerCase().trim())}">${escapar(v.voto || '—')}</span></td>
              <td>${v.orientacao ? `${escapar(v.orientacao)} (${escapar(v.sigla_bancada || '')})` : '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <!-- Projetos de Lei -->
    ${proposicoes.length ? `
      <div class="rolagem" style="margin-top:18px">
        <h3>Projetos de Lei Apresentados (${ano})</h3>
        <table>
          <thead><tr><th>Proposição</th><th>Ementa</th><th>Data</th><th>Situação</th></tr></thead>
          <tbody>
            ${proposicoes.slice(0, 10).map((prop) => `<tr>
              <td><strong>${prop.url ? `<a href="${escapar(prop.url)}" target="_blank" rel="noopener">${escapar(prop.sigla_tipo)} ${prop.numero}/${prop.ano} ↗</a>` : `${escapar(prop.sigla_tipo)} ${prop.numero}/${prop.ano}`}</strong></td>
              <td>${txt(prop.ementa)}</td>
              <td>${prop.data_apresentacao ? formatarData(prop.data_apresentacao) : '—'}</td>
              <td>${txt(prop.situacao || 'Em tramitação')}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}
  `;
}

function abaDeEmendas(emendas, f) {
  if (!emendas.length) {
    return '<p class="vazio" style="padding:20px">Nenhuma emenda orçamentária vinculada a este parlamentar no exercício selecionado.</p>';
  }

  const totalEmpenhado = emendas.reduce((s, e) => s + (aNumero(e.valor_empenhado) || 0), 0);
  const totalPago = emendas.reduce((s, e) => s + (aNumero(e.valor_pago) || 0), 0);

  return `
    <div class="ficha-kpi-grid">
      <div class="ficha-kpi-card kpi-cota">
        <span class="ficha-kpi-label">Total Empenhado em Emendas</span>
        <span class="ficha-kpi-valor">${dinheiro.format(totalEmpenhado)}</span>
        <span class="ficha-kpi-sub">${emendas.length} emendas registradas</span>
      </div>
      <div class="ficha-kpi-card kpi-presenca">
        <span class="ficha-kpi-label">Total Efetivamente Pago</span>
        <span class="ficha-kpi-valor">${dinheiro.format(totalPago)}</span>
        <span class="ficha-kpi-sub">${totalEmpenhado > 0 ? `${((totalPago / totalEmpenhado) * 100).toFixed(1)}% do empenhado` : 'Pago pelo Tesouro'}</span>
      </div>
    </div>

    ${f.emendas_por_funcao?.length ? `
      <div class="rolagem" style="margin-top:16px">
        <h3>Destinação por Área / Função</h3>
        <table>
          <thead><tr><th>Área / Função</th><th>Quantidade</th><th>Total Empenhado</th><th>Total Pago</th></tr></thead>
          <tbody>
            ${f.emendas_por_funcao.map((ef) => `<tr>
              <td><strong>${txt(ef.funcao)}</strong></td>
              <td>${ef.quantidade}</td>
              <td class="valor"><strong>${dinheiro.format(ef.empenhado)}</strong></td>
              <td class="valor">${dinheiro.format(ef.pago)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <div class="rolagem" style="margin-top:16px">
      <h3>Detalhamento das Emendas</h3>
      <table>
        <thead><tr><th>Código</th><th>Tipo</th><th>Área</th><th>Localidade</th><th>Valor Empenhado</th><th>Valor Pago</th></tr></thead>
        <tbody>
          ${emendas.map((e) => `<tr>
            <td><code>${escapar(e.codigo_emenda || '—')}</code></td>
            <td>${txt(e.tipo_emenda)}</td>
            <td>${txt(e.funcao || 'Geral')}</td>
            <td>${txt(e.localidade || 'Nacional')}</td>
            <td class="valor"><strong>${dinheiro.format(e.valor_empenhado)}</strong></td>
            <td class="valor">${dinheiro.format(e.valor_pago)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function abaDePatrimonio(f) {
  const bens = f.bens_declarados || [];
  const historico = f.patrimonio_historico || [];

  if (!bens.length && !historico.length) {
    return `
      <div style="padding:24px; text-align:center; background:var(--superficie-2); border-radius:8px; border:1px solid var(--borda); margin-top:12px">
        <span style="font-size:2.5rem">📋</span>
        <h3 style="margin:10px 0 6px">Declaração de Bens do TSE</h3>
        <p style="color:var(--texto-fraco); max-width:520px; margin:0 auto 12px; font-size:13px; line-height:1.5">
          A declaração de bens é prestada pelo candidato no registro de candidatura junto à Justiça Eleitoral.
          O acervo atual ainda não possui declarações importadas para este político ou o cargo não exigiu registro no TSE no ano atual.
        </p>
        <span class="selo-situacao">Fonte: DivulgaCandContas / TSE</span>
      </div>
    `;
  }

  const totalDeclarado = bens.reduce((s, b) => s + (aNumero(b.valor_bem) || 0), 0);

  return `
    <div class="ficha-kpi-grid">
      <div class="ficha-kpi-card kpi-cota">
        <span class="ficha-kpi-label">Patrimônio Total Declarado</span>
        <span class="ficha-kpi-valor">${dinheiro.format(totalDeclarado)}</span>
        <span class="ficha-kpi-sub">${bens.length} bens cadastrados no TSE</span>
      </div>
    </div>

    ${historico.length ? `
      <div class="rolagem" style="margin-top:16px">
        <h3>Evolução Patrimonial por Eleição</h3>
        <table>
          <thead><tr><th>Ano da Eleição</th><th>Cargo Concorrido</th><th>Qtd. Bens</th><th>Total Declarado</th></tr></thead>
          <tbody>
            ${historico.map((h) => `<tr>
              <td><strong>${h.ano_eleicao}</strong></td>
              <td>${txt(h.cargo)}</td>
              <td>${h.total_bens}</td>
              <td class="valor"><strong>${dinheiro.format(h.total_declarado)}</strong></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <div class="rolagem" style="margin-top:16px">
      <h3>Detalhamento dos Bens Declarados</h3>
      <table>
        <thead><tr><th>Ano</th><th>Tipo do Bem</th><th>Descrição</th><th>Valor Declarado</th></tr></thead>
        <tbody>
          ${bens.map((b) => `<tr>
            <td>${b.ano_eleicao || '—'}</td>
            <td><strong>${txt(b.tipo_bem)}</strong></td>
            <td>${txt(b.descricao_bem)}</td>
            <td class="valor"><strong>${dinheiro.format(b.valor_bem)}</strong></td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function barrasMensais(meses) {
  if (!meses.length) return '';
  const valores = meses.map((m) => aNumero(m.valor) || 0);
  const max = Math.max(...valores, 1);
  const total = valores.reduce((a, b) => a + b, 0);
  const media = meses.length ? total / meses.length : 0;

  const mesesCompletos = Array.from({ length: 12 }, (_, i) => {
    const numMes = i + 1;
    const item = meses.find((m) => Number(m.mes) === numMes);
    const val = aNumero(item?.valor) || 0;
    const notas = item?.notas || 0;
    const pct = Math.min(100, Math.max(0, Math.round((val / max) * 100)));
    const textoTopo = val >= 1000 ? `R$ ${(val / 1000).toFixed(1)}k` : (val > 0 ? `R$ ${Math.round(val)}` : '');
    return {
      mes: numMes,
      nome: MESES[i],
      valor: val,
      notas,
      pct,
      textoTopo
    };
  });

  return `
    <div class="grafico-mensal-card">
      <div class="grafico-mensal-header">
        <div>
          <h3>Evolução Mensal da Cota Parlamentar</h3>
          <span class="grafico-sub">Média de gastos: <strong>${dinheiro.format(media)}/mês</strong> · Total acumulado: <strong>${dinheiro.format(total)}</strong></span>
        </div>
        <div class="grafico-legenda">
          <span class="legenda-item"><span class="legenda-cor"></span> Reembolsos CEAP</span>
        </div>
      </div>

      <div class="grafico-trilhos-wrap">
        <div class="grafico-linhas-guia">
          <div class="linha-guia"><span>${dinheiro.format(max)}</span></div>
          <div class="linha-guia"><span>${dinheiro.format(max / 2)}</span></div>
          <div class="linha-guia"><span>R$ 0</span></div>
        </div>

        <div class="grafico-barras-grid">
          ${mesesCompletos.map((m) => `
            <div class="coluna-mes ${m.valor > 0 ? 'ativa' : 'zerada'}"
                 title="${m.nome.toUpperCase()}: ${dinheiroExato.format(m.valor)} (${m.notas} notas fiscais)">
              <span class="valor-topo">${m.textoTopo}</span>
              <div class="trilho-haste">
                <div class="haste-barra" style="height: ${m.pct}%;"></div>
              </div>
              <span class="rotulo-mes">${m.nome.toUpperCase()}</span>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function ligarAbasDaFicha(raiz) {
  const botoes = raiz.querySelectorAll('.abas-ficha button');
  const paineis = raiz.querySelectorAll('.painel-ficha');
  botoes.forEach((b) => {
    b.addEventListener('click', (ev) => {
      ev.stopPropagation();
      botoes.forEach((btn) => btn.setAttribute('aria-selected', 'false'));
      paineis.forEach((p) => { p.hidden = true; });
      b.setAttribute('aria-selected', 'true');
      const painel = raiz.querySelector(`.painel-ficha[data-painel="${b.dataset.painel}"]`);
      if (painel) painel.hidden = false;
    });
  });
}

export {
  carregarResumoPoliticos, carregarPoliticos, renderizarExecutivo,
  dicaDoPolitico, ligarDicaDePoliticos, posicionarDicaSolta,
  abrirFichaDoPolitico, abaDeAtuacao, abaDeEmendas,
  abaDePatrimonio, barrasMensais, ligarAbasDaFicha
};
