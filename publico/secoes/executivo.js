/* Poder Executivo: Mandatos, Gestão Fiscal, Cartões Corporativos (CPGF), Viagens e Contratos. */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, endereco, numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { esqueleto, falha, falhaEmLinha } from '../nucleo/ui.js';

let _ufsExecutivoCarregadas = false;

export async function popularMunicipiosExecutivo(uf) {
  const seletorMun = $('#executivo-municipio');
  if (!seletorMun) return;
  seletorMun.innerHTML = '<option value="">Carregando municípios...</option>';
  try {
    const municipios = await buscar('/api/executivo/municipios', { uf: uf || 'SP' });
    seletorMun.innerHTML = (municipios || []).map((m) =>
      `<option value="${escapar(m.cod_ibge)}">${escapar(m.nome)}</option>`
    ).join('');
  } catch (e) {
    seletorMun.innerHTML = '<option value="">Erro ao carregar</option>';
  }
}

export async function carregarExecutivo() {
  const esfera = $('#executivo-esfera')?.value || 'estadual';
  const uf = $('#executivo-uf')?.value || 'SP';
  const codIbge = $('#executivo-municipio')?.value || '';
  const ano = $('#executivo-ano')?.value ? Number($('#executivo-ano').value) : null;

  const alvoGov = $('#executivo-governante');
  const alvoSaldo = $('#executivo-resultado-saldo');
  const alvoLrf = $('#executivo-conteudo-lrf');
  const alvoFuncao = $('#executivo-gastos-funcao');
  const alvoSerie = $('#executivo-serie-anual');

  if (alvoGov) alvoGov.innerHTML = esqueleto(3);
  if (alvoSaldo) alvoSaldo.innerHTML = esqueleto(3);
  if (alvoLrf) alvoLrf.innerHTML = esqueleto(3);
  if (alvoFuncao) alvoFuncao.innerHTML = esqueleto(4);
  if (alvoSerie) alvoSerie.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/mandato', {
      esfera,
      sigla_uf: esfera !== 'federal' ? uf : 'BR',
      cod_ibge: esfera === 'municipal' ? codIbge : undefined,
      ano: ano || undefined,
    });

    // 1. Renderizar Governante
    const gov = d.governante;
    if (alvoGov) {
      if (!gov) {
        alvoGov.innerHTML = '<p class="vazio">Sem dados de governante cadastrado no período.</p>';
      } else {
        const salario = aNumero(gov.salario);
        alvoGov.innerHTML = `
          <div class="cartao" style="border-left: 4px solid var(--accent, #1a73e8); background: var(--superficie);">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px">
              <div>
                <span class="selo calmo" style="text-transform:uppercase; font-size:11px; letter-spacing:0.5px">${escapar(gov.cargo || 'Governante')}</span>
                <h2 style="margin:4px 0 2px 0; font-size:1.4rem">${txt(gov.nome)}</h2>
                <p class="rodape-mapa" style="margin:0">
                  ${gov.sigla_partido ? `<strong>${escapar(gov.sigla_partido)}</strong> · ` : ''}
                  ${escapar(d.ente?.nome || '')} (${escapar(d.ente?.sigla_uf || '')}) · 
                  Mandato: <strong>${escapar(gov.ano_inicio || '')} a ${escapar(gov.ano_fim || 'Atual')}</strong>
                </p>
              </div>
              <div style="text-align:right">
                <span class="pe" style="display:block; color:var(--texto-fraco)">Subsídio mensal do cargo</span>
                <strong style="font-size:1.3rem; color:var(--texto)">${Number.isFinite(salario) ? dinheiroExato.format(salario) : '—'}</strong>
                ${gov.norma_salario ? `<p class="pe" style="margin:2px 0 0 0">${escapar(gov.norma_salario)}</p>` : ''}
              </div>
            </div>
          </div>`;
      }
    }

    // 2. Anos de Competência
    const seletorAno = $('#executivo-ano');
    if (seletorAno && d.serie_anual?.length) {
      const anoSelecionado = d.ano_selecionado || d.serie_anual[0]?.ano;
      seletorAno.innerHTML = d.serie_anual.map((s) =>
        `<option value="${s.ano}" ${s.ano === anoSelecionado ? 'selected' : ''}>${s.ano}</option>`
      ).join('');
    }

    // 3. Resultado Fiscal (Superávit / Déficit)
    const atual = d.ano_atual;
    if (alvoSaldo) {
      if (!atual || (atual.receita == null && atual.despesa == null)) {
        alvoSaldo.innerHTML = '<p class="vazio">Sem dados fiscais coletados para este exercício.</p>';
      } else {
        const saldo = aNumero(atual.saldo);
        const superavit = saldo >= 0;
        const receita = aNumero(atual.receita);
        const despesa = aNumero(atual.despesa);
        alvoSaldo.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <span style="font-size:1.1rem">Situação Orçamentária (${escapar(d.ano_selecionado)}):</span>
              <span class="selo ${superavit ? 'calmo' : 'risco'}" style="font-size:1rem; font-weight:bold">
                ${superavit ? '✅ SUPERÁVIT' : '⚠️ DÉFICIT'} ${Number.isFinite(saldo) ? dinheiro.format(Math.abs(saldo)) : ''}
              </span>
            </div>
            <div class="tiras">
              <div class="tira">
                <span>Arrecadação Total</span>
                <strong>${Number.isFinite(receita) ? dinheiro.format(receita) : '—'}</strong>
              </div>
              <div class="tira">
                <span>Despesa Executada</span>
                <strong>${Number.isFinite(despesa) ? dinheiro.format(despesa) : '—'}</strong>
              </div>
              <div class="tira">
                <span>Despesa por habitante</span>
                <strong>${Number.isFinite(atual.despesa_per_capita) ? dinheiro.format(atual.despesa_per_capita) : '—'}</strong>
              </div>
            </div>
          </div>`;
      }
    }

    // 4. LRF e Pessoal
    if (alvoLrf) {
      const lrf = d.lrf;
      if (!lrf || lrf.percentual_pessoal == null) {
        alvoLrf.innerHTML = '<p class="vazio">Demonstrativo da LRF ainda não publicado no SICONFI para este ano.</p>';
      } else {
        const pct = aNumero(lrf.percentual_pessoal);
        const limite = aNumero(lrf.limite_maximo) || 54;
        const acima = lrf.acima_do_limite;
        alvoLrf.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:10px">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <span>Gastos com Pessoal (RCL):</span>
              <span class="selo ${acima ? 'risco' : 'calmo'}" style="font-weight:bold; font-size:1.1rem">
                ${Number.isFinite(pct) ? porcentoExato.format(pct) : '—'}%
              </span>
            </div>
            <p class="pe" style="margin:0">
              Limite Máximo Legal: <strong>${porcento.format(limite)}%</strong> da Receita Corrente Líquida (RCL).
              ${acima ? '<br><strong style="color:var(--risco)">⚠️ O Ente excedeu o teto legal da Lei de Responsabilidade Fiscal.</strong>' : ' Ente cumpre o limite fiscal.'}
            </p>
          </div>`;
      }
    }

    // 5. Funções de Governo (Áreas de Investimento)
    if (alvoFuncao) {
      const funcoes = d.despesas_funcao || [];
      if (!funcoes.length) {
        alvoFuncao.innerHTML = '<p class="vazio">Sem detalhamento de funções no DCA/RREO para este ano.</p>';
      } else {
        const totalFuncoes = funcoes.reduce((s, f) => s + (aNumero(f.valor) || 0), 0);
        alvoFuncao.innerHTML = `
          <table style="width:100%">
            <thead><tr><th>Área / Função</th><th>Valor Executado</th><th>% do Total</th></tr></thead>
            <tbody>
              ${funcoes.slice(0, 10).map((f) => {
                const val = aNumero(f.valor);
                const pct = totalFuncoes > 0 ? (val / totalFuncoes) * 100 : 0;
                return `<tr>
                  <td><strong>${escapar(f.funcao || 'Outras')}</strong></td>
                  <td class="valor">${dinheiro.format(val)}</td>
                  <td class="valor">${porcento.format(pct)}%</td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>`;
      }
    }

    // 6. Série Histórica
    if (alvoSerie) {
      const serie = d.serie_anual || [];
      if (!serie.length) {
        alvoSerie.innerHTML = '<p class="vazio">Histórico não disponível.</p>';
      } else {
        alvoSerie.innerHTML = `
          <table style="width:100%">
            <thead><tr><th>Ano</th><th>Arrecadação</th><th>Despesa</th><th>Resultado</th></tr></thead>
            <tbody>
              ${serie.map((s) => {
                const saldo = aNumero(s.saldo);
                const sup = saldo >= 0;
                return `<tr style="${s.ano === d.ano_selecionado ? 'font-weight:bold; background:rgba(255,255,255,0.05)' : ''}">
                  <td>${s.ano}</td>
                  <td class="valor">${Number.isFinite(s.receita) ? dinheiro.format(s.receita) : '—'}</td>
                  <td class="valor">${Number.isFinite(s.despesa) ? dinheiro.format(s.despesa) : '—'}</td>
                  <td class="valor">
                    <span class="selo ${sup ? 'calmo' : 'risco'}" style="font-size:11px">
                      ${Number.isFinite(saldo) ? dinheiro.format(saldo) : '—'}
                    </span>
                  </td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>`;
      }
    }

  } catch (erro) {
    if (alvoGov) alvoGov.innerHTML = falha(erro.message);
  }

  // Carregar blocos federais (Cartões, Viagens e Contratos)
  await Promise.all([
    carregarCartoesExecutivo(esfera, uf, codIbge, ano),
    carregarViagensExecutivo(ano),
    carregarContratosExecutivo(esfera, uf, codIbge, ano),
  ]);
}

export async function carregarCartoesExecutivo(esfera, uf, codIbge, ano) {
  const alvoTopo = $('#executivo-topo-cartoes');
  const alvoFav = $('#executivo-cartoes-favorecidos');
  const alvoOrg = $('#executivo-cartoes-orgaos');
  const alvoTrans = $('#executivo-cartoes-transacoes');

  if (alvoTopo) alvoTopo.innerHTML = esqueleto(2);
  if (alvoFav) alvoFav.innerHTML = esqueleto(3);
  if (alvoOrg) alvoOrg.innerHTML = esqueleto(3);
  if (alvoTrans) alvoTrans.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/cartoes', { ano: ano || undefined });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total Gasto no Cartão</span><strong>${dinheiro.format(d.total_gasto || 0)}</strong></div>
        <div class="tira"><span>Transações Registradas</span><strong>${numero.format(d.total_transacoes || 0)}</strong></div>
        <div class="tira"><span>Órgãos Portadores</span><strong>${numero.format(d.total_orgaos || 0)}</strong></div>
      `;
    }
    if (alvoFav) {
      alvoFav.innerHTML = (d.favorecidos || []).length ? `
        <table><thead><tr><th>Estabelecimento</th><th>Total Gasto</th></tr></thead><tbody>
        ${d.favorecidos.slice(0, 8).map((f) => `<tr><td>${txt(f.nome)}</td><td class="valor">${dinheiro.format(f.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de favorecidos.</p>';
    }
    if (alvoOrg) {
      alvoOrg.innerHTML = (d.orgaos || []).length ? `
        <table><thead><tr><th>Órgão / Ministério</th><th>Total Gasto</th></tr></thead><tbody>
        ${d.orgaos.slice(0, 8).map((o) => `<tr><td>${txt(o.nome)}</td><td class="valor">${dinheiro.format(o.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de órgãos.</p>';
    }
    if (alvoTrans) {
      alvoTrans.innerHTML = (d.transacoes || []).length ? `
        <table><thead><tr><th>Data</th><th>Órgão</th><th>Favorecido</th><th>Valor</th></tr></thead><tbody>
        ${d.transacoes.slice(0, 10).map((t) => `<tr><td>${formatarData(t.data)}</td><td>${txt(t.orgao)}</td><td>${txt(t.favorecido)}</td><td class="valor">${dinheiro.format(t.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de transações.</p>';
    }
  } catch (e) {
    if (alvoTopo) alvoTopo.innerHTML = falha(e.message);
  }
}

export async function carregarViagensExecutivo(ano, orgao) {
  const alvoTopo = $('#executivo-topo-viagens');
  const alvoDest = $('#executivo-viagens-destinos');
  const alvoOrg = $('#executivo-viagens-orgaos');
  const alvoMaior = $('#executivo-viagens-maiores');

  if (alvoTopo) alvoTopo.innerHTML = esqueleto(2);
  if (alvoDest) alvoDest.innerHTML = esqueleto(3);
  if (alvoOrg) alvoOrg.innerHTML = esqueleto(3);
  if (alvoMaior) alvoMaior.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/viagens', { ano: ano || undefined, orgao: orgao || undefined });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total em Viagens</span><strong>${dinheiro.format(d.total_viagens || 0)}</strong></div>
        <div class="tira"><span>Passagens Aéreas</span><strong>${dinheiro.format(d.total_passagens || 0)}</strong></div>
        <div class="tira"><span>Diárias Pagas</span><strong>${dinheiro.format(d.total_diarias || 0)}</strong></div>
      `;
    }
    if (alvoDest) {
      alvoDest.innerHTML = (d.destinos || []).length ? `
        <table><thead><tr><th>Destino</th><th>Total Gasto</th></tr></thead><tbody>
        ${d.destinos.slice(0, 8).map((x) => `<tr><td>${txt(x.destino)}</td><td class="valor">${dinheiro.format(x.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de destinos.</p>';
    }
    if (alvoOrg) {
      alvoOrg.innerHTML = (d.orgaos || []).length ? `
        <table><thead><tr><th>Órgão</th><th>Total</th></tr></thead><tbody>
        ${d.orgaos.slice(0, 8).map((x) => `<tr><td>${txt(x.orgao)}</td><td class="valor">${dinheiro.format(x.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de viagens por órgão.</p>';
    }
    if (alvoMaior) {
      alvoMaior.innerHTML = (d.maiores || []).length ? `
        <table><thead><tr><th>Beneficiário</th><th>Destino</th><th>Motivo</th><th>Total</th></tr></thead><tbody>
        ${d.maiores.slice(0, 10).map((m) => `<tr><td>${txt(m.nome)}</td><td>${txt(m.destino)}</td><td>${txt(m.motivo)}</td><td class="valor">${dinheiro.format(m.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem viagens registradas.</p>';
    }
  } catch (e) {
    if (alvoTopo) alvoTopo.innerHTML = falha(e.message);
  }
}

export async function carregarContratosExecutivo(esfera, uf, codIbge, ano) {
  const alvoTopo = $('#executivo-topo-contratos');
  const alvoForn = $('#executivo-contratos-fornecedores');
  const alvoMod = $('#executivo-contratos-modalidades');
  const alvoMaior = $('#executivo-contratos-maiores');

  if (alvoTopo) alvoTopo.innerHTML = esqueleto(2);
  if (alvoForn) alvoForn.innerHTML = esqueleto(3);
  if (alvoMod) alvoMod.innerHTML = esqueleto(3);
  if (alvoMaior) alvoMaior.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/contratos', {
      esfera: esfera || undefined,
      sigla_uf: uf || undefined,
      ano: ano || undefined,
    });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total Contratado</span><strong>${dinheiro.format(d.total_contratado || 0)}</strong></div>
        <div class="tira"><span>Contratos Firmados</span><strong>${numero.format(d.quantidade_contratos || 0)}</strong></div>
        <div class="tira"><span>Dispensas / Inexigibilidades</span><strong>${numero.format(d.dispensas_inexigibilidades || 0)}</strong></div>
      `;
    }
    if (alvoForn) {
      alvoForn.innerHTML = (d.fornecedores || []).length ? `
        <table><thead><tr><th>Fornecedor</th><th>Total Contratado</th></tr></thead><tbody>
        ${d.fornecedores.slice(0, 8).map((f) => `<tr><td>${txt(f.fornecedor)}</td><td class="valor">${dinheiro.format(f.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de fornecedores.</p>';
    }
    if (alvoMod) {
      alvoMod.innerHTML = (d.modalidades || []).length ? `
        <table><thead><tr><th>Modalidade</th><th>Total</th></tr></thead><tbody>
        ${d.modalidades.slice(0, 8).map((m) => `<tr><td>${txt(m.modalidade)}</td><td class="valor">${dinheiro.format(m.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de modalidades.</p>';
    }
    if (alvoMaior) {
      alvoMaior.innerHTML = (d.maiores || []).length ? `
        <table><thead><tr><th>Objeto</th><th>Fornecedor</th><th>Vigência</th><th>Valor</th></tr></thead><tbody>
        ${d.maiores.slice(0, 10).map((c) => `<tr><td>${txt(c.objeto)}</td><td>${txt(c.fornecedor)}</td><td>${formatarData(c.data_inicio)} a ${formatarData(c.data_fim)}</td><td class="valor">${dinheiro.format(c.valor)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem contratos registrados.</p>';
    }
  } catch (e) {
    if (alvoTopo) alvoTopo.innerHTML = falha(e.message);
  }
}

export function configurarEventosExecutivo() {
  $('#executivo-esfera')?.addEventListener('change', (e) => {
    const esfera = e.target.value;
    const blocoUf = $('#bloco-executivo-uf');
    const blocoMun = $('#bloco-executivo-municipio');
    if (esfera === 'federal') {
      if (blocoUf) blocoUf.hidden = true;
      if (blocoMun) blocoMun.hidden = true;
    } else if (esfera === 'estadual') {
      if (blocoUf) blocoUf.hidden = false;
      if (blocoMun) blocoMun.hidden = true;
    } else {
      if (blocoUf) blocoUf.hidden = false;
      if (blocoMun) blocoMun.hidden = false;
      popularMunicipiosExecutivo($('#executivo-uf')?.value);
    }
    carregarExecutivo();
  });

  $('#executivo-uf')?.addEventListener('change', (e) => {
    if ($('#executivo-esfera')?.value === 'municipal') {
      popularMunicipiosExecutivo(e.target.value);
    }
    carregarExecutivo();
  });

  $('#executivo-municipio')?.addEventListener('change', carregarExecutivo);
  $('#executivo-ano')?.addEventListener('change', carregarExecutivo);
  $('#btn-atualizar-executivo')?.addEventListener('click', carregarExecutivo);
}
