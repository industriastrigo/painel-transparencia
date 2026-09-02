/* Seção Poder Legislativo — Congresso Nacional, Assembleias Legislativas, Câmaras Municipais, Cotas (CEAP) e Emendas. */

import { $, $$ } from '../nucleo/ui.js';
import { buscar } from '../nucleo/api.js';
import {
  txt, escapar, dinheiro, dinheiroCurto, contagem, porcentoExato, formatarNomeProprio
} from '../nucleo/formatadores.js';

let parlamentaresCache = [];

export async function carregarLegislativo() {
  const container = $('#legislativo-conteudo');
  if (!container) return;

  const seletorEsfera = $('#filtro-leg-esfera');
  const seletorCasa = $('#filtro-leg-casa');
  const seletorAno = $('#filtro-leg-ano');
  const inputBusca = $('#filtro-leg-busca');
  const btnBuscar = $('#btn-buscar-leg');

  const esfera = seletorEsfera?.value || 'federal';
  const casa = seletorCasa?.value || '';
  const ano = seletorAno?.value || '2026';
  const busca = inputBusca?.value?.trim() || '';

  container.innerHTML = '<div class="carregando">Carregando dados do Poder Legislativo...</div>';

  try {
    // 1. Carrega o Sumário e KPIs
    const params = new URLSearchParams({ esfera, ano });
    if (casa) params.set('casa', casa);

    const [sumario, cotas, parlamentares] = await Promise.all([
      buscar(`/api/legislativo/sumario?${params.toString()}`).catch(() => null),
      buscar(`/api/legislativo/cotas?ano=${ano}`).catch(() => null),
      buscar(`/api/legislativo/parlamentares?${params.toString()}&limite=50${busca ? `&busca=${encodeURIComponent(busca)}` : ''}`).catch(() => ({ parlamentares: [] })),
    ]);

    renderizarLegislativo(sumario, cotas, parlamentares);
  } catch (erro) {
    console.error('Erro ao carregar legislativo:', erro);
    container.innerHTML = `<div class="erro">Falha ao carregar dados do Poder Legislativo: ${escapar(erro.message)}</div>`;
  }
}

function renderizarLegislativo(sumario, cotas, dadosParlamentares) {
  const container = $('#legislativo-conteudo');
  if (!container) return;

  const k = sumario?.kpis || {};
  const bancadas = sumario?.bancadas || [];
  const categoriasCota = cotas?.categorias || [];
  const fornecedoresCota = cotas?.fornecedores || [];
  const listaParlamentares = dadosParlamentares?.parlamentares || [];

  const totalCadeirasBancadas = bancadas.reduce((acc, b) => acc + (b.vagas || 0), 0);
  const totalPctBancadas = (totalCadeirasBancadas / (k.total_parlamentares || totalCadeirasBancadas || 1)) * 100;

  const totalNotasCota = categoriasCota.reduce((acc, c) => acc + (c.documentos || 0), 0);
  const totalGastoCota = categoriasCota.reduce((acc, c) => acc + (c.total_gasto || 0), 0);

  const totalTransacoesForn = fornecedoresCota.reduce((acc, f) => acc + (f.transacoes || 0), 0);
  const totalRecebidoForn = fornecedoresCota.reduce((acc, f) => acc + (f.total_recebido || 0), 0);

  container.innerHTML = `
    <!-- KPIs do Poder Legislativo -->
    <div class="tiras" style="margin-top:14px; margin-bottom:18px">
      <div class="tira">
        <span>Parlamentares em Exercício</span>
        <div style="display:flex; flex-direction:column; align-items:flex-end">
          <strong style="font-size:1.15rem; color:var(--realce, #38bdf8)">${contagem(k.total_parlamentares || 0)}</strong>
          <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">${contagem(k.total_partidos || 0)} partidos representados</span>
        </div>
      </div>
      <div class="tira">
        <span>Cota Parlamentar (CEAP / CEAPS)</span>
        <div style="display:flex; flex-direction:column; align-items:flex-end">
          <strong style="font-size:1.15rem">${dinheiro.format(k.total_cota_parlamentar || 0)}</strong>
          <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">${contagem(k.total_documentos_cota || 0)} reembolsos emitidos</span>
        </div>
      </div>
      <div class="tira">
        <span>Emendas ao Orçamento (Pagas)</span>
        <div style="display:flex; flex-direction:column; align-items:flex-end">
          <strong style="font-size:1.15rem; color:var(--calmo, #10b981)">${dinheiro.format(k.total_emendas_pagas || 0)}</strong>
          <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">de ${dinheiroCurto.format(k.total_emendas_empenhadas || 0)} empenhados</span>
        </div>
      </div>
      <div class="tira">
        <span>Subsídio Parlamentar</span>
        <div style="display:flex; flex-direction:column; align-items:flex-end">
          <strong style="font-size:1.15rem">${dinheiro.format(k.subsidio_parlamentar_mensal || 0)} / mês</strong>
          <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">fixado por lei</span>
        </div>
      </div>
    </div>

    <!-- Painel de Bancadas e Cotas Parlamentares -->
    <div class="painel" style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:18px; align-items:stretch">
      <!-- Distribuição por Bancada -->
      <div class="cartao" style="background:var(--superficie-2); display:flex; flex-direction:column; justify-content:space-between; height:100%; min-height:480px">
        <div>
          <h3>Composição das Bancadas Partidárias</h3>
          <p class="rodape-mapa" style="margin-top:-4px; margin-bottom:12px">Distribuição de cadeiras por partido na casa legislativa.</p>
        </div>
        <div class="rolagem" style="flex:1; max-height:420px; overflow-y:auto; display:flex; flex-direction:column; justify-content:space-between">
          <table class="tabela" style="width:100%">
            <thead>
              <tr>
                <th>Partido</th>
                <th class="num">Cadeiras</th>
                <th class="num">Proporção</th>
              </tr>
            </thead>
            <tbody>
              ${bancadas.map((b) => {
                const total = k.total_parlamentares || 1;
                const pct = (b.vagas / total) * 100;
                return `
                  <tr>
                    <td><strong>${escapar(b.partido)}</strong></td>
                    <td class="num">${contagem(b.vagas)}</td>
                    <td class="num">${porcentoExato.format(pct)}%</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
            <tfoot>
              <tr style="border-top:2px solid var(--borda-forte, #475569); background:var(--superficie-3, rgba(255,255,255,0.06)); font-weight:bold">
                <td><strong>TOTAL / SOMA</strong></td>
                <td class="num"><strong style="color:var(--realce, #38bdf8)">${contagem(totalCadeirasBancadas)}</strong></td>
                <td class="num"><strong>${porcentoExato.format(totalPctBancadas)}%</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Maiores Tipos de Gastos na Cota Parlamentar -->
      <div class="cartao" style="background:var(--superficie-2); display:flex; flex-direction:column; justify-content:space-between; height:100%; min-height:480px">
        <div>
          <h3>Gastos por Tipo de Cota Parlamentar (CEAP)</h3>
          <p class="rodape-mapa" style="margin-top:-4px; margin-bottom:12px">Principais despesas indenizadas do mandato parlamentar.</p>
        </div>
        <div class="rolagem" style="flex:1; max-height:420px; overflow-y:auto; display:flex; flex-direction:column; justify-content:space-between">
          <table class="tabela" style="width:100%">
            <thead>
              <tr>
                <th>Categoria da Despesa</th>
                <th class="num">Notas</th>
                <th class="num">Total Gasto</th>
              </tr>
            </thead>
            <tbody>
              ${categoriasCota.map((c) => `
                <tr>
                  <td><strong>${escapar(c.categoria)}</strong></td>
                  <td class="num">${contagem(c.documentos)}</td>
                  <td class="num">${dinheiro.format(c.total_gasto)}</td>
                </tr>
              `).join('')}
            </tbody>
            <tfoot>
              <tr style="border-top:2px solid var(--borda-forte, #475569); background:var(--superficie-3, rgba(255,255,255,0.06)); font-weight:bold">
                <td><strong>TOTAL / SOMA</strong></td>
                <td class="num"><strong style="color:var(--realce, #38bdf8)">${contagem(totalNotasCota)}</strong></td>
                <td class="num"><strong style="color:var(--calmo, #10b981)">${dinheiro.format(totalGastoCota)}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>

    <!-- Maiores Fornecedores da Cota Parlamentar -->
    <div class="cartao" style="background:var(--superficie-2); margin-bottom:18px">
      <h3>Maiores Fornecedores / Empresas Favorecidas na Cota (CEAP)</h3>
      <p class="rodape-mapa" style="margin-top:-4px; margin-bottom:12px">Empresas e prestadores que mais receberam recursos de cotas dos parlamentares.</p>
      <div class="rolagem">
        <table class="tabela">
          <thead>
            <tr>
              <th>Fornecedor / Razão Social</th>
              <th>CNPJ / CPF</th>
              <th class="num">Transações</th>
              <th class="num">Total Recebido</th>
            </tr>
          </thead>
          <tbody>
            ${fornecedoresCota.map((f) => `
              <tr>
                <td><strong>${escapar(f.fornecedor)}</strong></td>
                <td><span class="subtexto">${escapar(f.cnpj_cpf)}</span></td>
                <td class="num">${contagem(f.transacoes)}</td>
                <td class="num"><strong>${dinheiro.format(f.total_recebido)}</strong></td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr style="border-top:2px solid var(--borda-forte, #475569); background:var(--superficie-3, rgba(255,255,255,0.06)); font-weight:bold">
              <td colspan="2"><strong>TOTAL / SOMA (Maiores Favorecidos)</strong></td>
              <td class="num"><strong style="color:var(--realce, #38bdf8)">${contagem(totalTransacoesForn)}</strong></td>
              <td class="num"><strong style="color:var(--calmo, #10b981)">${dinheiro.format(totalRecebidoForn)}</strong></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- Lista / Tabela de Parlamentares -->
    <div class="cartao">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px">
        <h2>Parlamentares & Fichas de Mandato</h2>
        <span class="badge-metodo">${contagem(listaParlamentares.length)} listados</span>
      </div>
      <div class="rolagem" style="margin-top:12px">
        <table class="tabela">
          <thead>
            <tr>
              <th>Código Interno</th>
              <th>Nome Formatado</th>
              <th>Nome Extraído (Fonte)</th>
              <th>Cargo</th>
              <th>Partido</th>
              <th>UF / Base</th>
              <th>Mandato</th>
            </tr>
          </thead>
          <tbody>
            ${listaParlamentares.length === 0 ? `
              <tr><td colspan="7" class="vazio">Nenhum parlamentar encontrado para o filtro.</td></tr>
            ` : listaParlamentares.map((p) => `
              <tr>
                <td><code>${escapar(p.cod_politico_interno || '—')}</code></td>
                <td><strong>${escapar(p.nome_formatado || p.nome)}</strong></td>
                <td><span class="subtexto">${escapar(p.nome_extraido || p.nome)}</span></td>
                <td><span class="cargo-texto">${escapar(formatarNomeProprio(p.cargo))}</span></td>
                <td><span class="selo padrao">${escapar(p.sigla_partido || '—')}</span></td>
                <td>${escapar(p.sigla_uf || p.base_eleitoral || 'BR')}</td>
                <td>${escapar(p.ano_inicio || '')}–${escapar(p.ano_fim || '')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

export function inicializarEventosLegislativo() {
  const btnBuscar = $('#btn-buscar-leg');
  const seletorEsfera = $('#filtro-leg-esfera');
  const seletorCasa = $('#filtro-leg-casa');
  const seletorAno = $('#filtro-leg-ano');
  const inputBusca = $('#filtro-leg-busca');

  if (btnBuscar) btnBuscar.addEventListener('click', carregarLegislativo);
  if (seletorEsfera) seletorEsfera.addEventListener('change', carregarLegislativo);
  if (seletorCasa) seletorCasa.addEventListener('change', carregarLegislativo);
  if (seletorAno) seletorAno.addEventListener('change', carregarLegislativo);
  if (inputBusca) {
    inputBusca.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') carregarLegislativo();
    });
  }
}
