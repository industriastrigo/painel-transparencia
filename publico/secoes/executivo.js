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
  const esfera = $('#executivo-esfera')?.value || 'geral';
  const uf = $('#executivo-uf')?.value || 'SP';
  const codIbge = $('#executivo-municipio')?.value || '';
  const ano = $('#executivo-ano')?.value ? Number($('#executivo-ano').value) : null;

  const alvoGov = $('#executivo-dashboard-principal') || $('#executivo-governante');
  const alvoComp = $('#executivo-painel-comparativo');
  const alvoMacro = $('#executivo-termometro-macro');
  const alvoDefasagem = $('#executivo-conteudo-defasagem');
  const alvoPib = $('#executivo-conteudo-pib');
  const alvoSaldo = $('#executivo-resultado-saldo');
  const alvoLrf = $('#executivo-conteudo-lrf');
  const alvoFuncao = $('#executivo-gastos-funcao');
  const alvoSerie = $('#executivo-serie-anual');

  const titFiscal = $('#executivo-titulo-fiscal');
  const titCartoes = $('#executivo-titulo-cartoes');
  const subCartoes = $('#executivo-subtitulo-cartoes');
  const titViagens = $('#executivo-titulo-viagens');
  const subViagens = $('#executivo-subtitulo-viagens');
  const titContratos = $('#executivo-titulo-contratos');
  const subContratos = $('#executivo-subtitulo-contratos');

  if (alvoGov) alvoGov.innerHTML = esqueleto(3);
  if (alvoComp) alvoComp.innerHTML = esqueleto(3);
  if (alvoMacro) alvoMacro.innerHTML = esqueleto(2);
  if (alvoDefasagem) alvoDefasagem.innerHTML = esqueleto(3);
  if (alvoPib) alvoPib.innerHTML = esqueleto(3);
  if (alvoSaldo) alvoSaldo.innerHTML = esqueleto(3);
  if (alvoLrf) alvoLrf.innerHTML = esqueleto(3);
  if (alvoFuncao) alvoFuncao.innerHTML = esqueleto(4);
  if (alvoSerie) alvoSerie.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/mandato', {
      esfera,
      sigla_uf: esfera === 'estadual' || esfera === 'municipal' ? uf : 'BR',
      cod_ibge: esfera === 'municipal' ? codIbge : undefined,
      ano: ano || undefined,
    });

    const gov = d.governante;
    const pres = d.presidente_exercicio;
    const nomeEnte = d.ente?.nome || (esfera === 'federal' ? 'Brasil' : 'Estado de ' + uf);

    // 1. Renderizar Topo / Dashboard do Governante ou Presidente
    if (alvoGov) {
      if (esfera === 'geral' || esfera === 'federal') {
        const presGov = pres?.governante || gov;
        const salarioPres = presGov?.salario ? aNumero(presGov.salario) : 46366.19;
        alvoGov.innerHTML = `
          <div class="cartao" style="border-left: 4px solid var(--realce, #38bdf8); background: var(--superficie-2, #202028); padding: 20px 24px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px">
              <div>
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px">
                  <span class="selo calmo" style="text-transform:uppercase; font-size:11px; letter-spacing:0.5px">EXERCÍCIO DO PRESIDENTE DA REPÚBLICA</span>
                  <span class="badge-metodo" style="font-size:10px">Governo Federal · União</span>
                </div>
                <h2 style="margin:4px 0 2px 0; font-size:1.65rem; color:var(--texto, #fff)">${txt(presGov?.nome || 'Presidente da República')}</h2>
                <p class="rodape-mapa" style="margin:0; font-size:0.95rem">
                  ${presGov?.sigla_partido ? `<strong>${escapar(presGov.sigla_partido)}</strong> · ` : ''}
                  Chefe de Estado e do Governo Federal · 
                  Mandato: <strong>${escapar(presGov?.ano_inicio || 2023)} a ${escapar(presGov?.ano_fim || 2027)}</strong>
                </p>
              </div>
              <div style="text-align:right">
                <span class="pe" style="display:block; color:var(--texto-fraco)">Subsídio mensal do cargo</span>
                <strong style="font-size:1.35rem; color:var(--texto)">${Number.isFinite(salarioPres) ? dinheiroExato.format(salarioPres) : 'R$ 46.366,19'}</strong>
                <p class="pe" style="margin:2px 0 0 0">${escapar(presGov?.norma_salario || 'Decreto Legislativo nº 172/2022')}</p>
              </div>
            </div>

            <div class="tiras" style="margin-top:16px">
              <div class="tira">
                <span>Arrecadação Federal (União)</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${dinheiro.format(pres?.receita_uniao || 0)}</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">receitas totais do ano</span>
                </div>
              </div>
              <div class="tira">
                <span>Despesa Federal Executada</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${dinheiro.format(pres?.despesa_uniao || 0)}</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">orçamento executado</span>
                </div>
              </div>
              <div class="tira">
                <span>Resultado Primário da União</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="color:${(pres?.resultado_primario || 0) >= 0 ? 'var(--calmo, #10b981)' : 'var(--risco, #ef4444)'}; font-size:1.15rem">
                    ${(pres?.resultado_primario || 0) >= 0 ? '✅ +' : '⚠️ '}${porcentoExato.format((pres?.receita_uniao ? ((pres?.resultado_primario || 0) / pres.receita_uniao * 100) : 0))}% (${(pres?.resultado_primario || 0) >= 0 ? 'SUPERÁVIT' : 'DÉFICIT'})
                  </strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">
                    ${dinheiro.format(pres?.resultado_primario || 0)} (${porcentoExato.format(pres?.pib_brasil ? ((pres?.resultado_primario || 0) / pres.pib_brasil * 100) : 0)}% do PIB)
                  </span>
                </div>
              </div>
              <div class="tira">
                <span>Gasto Federal per capita</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${dinheiro.format(pres?.despesa_per_capita || 0)} / hab.</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">média por habitante</span>
                </div>
              </div>
            </div>
          </div>`;
      } else if (!gov) {
        alvoGov.innerHTML = `<p class="vazio">Sem dados de governante cadastrado no período para ${escapar(nomeEnte)}.</p>`;
      } else {
        const salario = aNumero(gov.salario);
        alvoGov.innerHTML = `
          <div class="cartao" style="border-left: 4px solid var(--realce, #38bdf8); background: var(--superficie); padding: 18px 22px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px">
              <div>
                <span class="selo calmo" style="text-transform:uppercase; font-size:11px; letter-spacing:0.5px">${escapar(gov.cargo || 'Governante')}</span>
                <h2 style="margin:4px 0 2px 0; font-size:1.45rem">${txt(gov.nome)}</h2>
                <p class="rodape-mapa" style="margin:0">
                  ${gov.sigla_partido ? `<strong>${escapar(gov.sigla_partido)}</strong> · ` : ''}
                  ${escapar(nomeEnte)} (${escapar(d.ente?.sigla_uf || '')}) · 
                  Mandato: <strong>${escapar(gov.ano_inicio || '')} a ${escapar(gov.ano_fim || 'Atual')}</strong>
                </p>
              </div>
              <div style="text-align:right">
                <span class="pe" style="display:block; color:var(--texto-fraco)">Subsídio mensal do cargo</span>
                <strong style="font-size:1.35rem; color:var(--texto)">${Number.isFinite(salario) ? dinheiroExato.format(salario) : '—'}</strong>
                ${gov.norma_salario ? `<p class="pe" style="margin:2px 0 0 0">${escapar(gov.norma_salario)}</p>` : ''}
              </div>
            </div>
          </div>`;
      }
    }

    // 2. Renderizar Painel Comparativo Interfederativo (quando Governador ou Prefeito for selecionado)
    if (alvoComp) {
      if ((esfera === 'estadual' || esfera === 'municipal') && d.comparativo_federativo) {
        alvoComp.hidden = false;
        const comp = d.comparativo_federativo;
        const esferasComp = comp.esferas || [];
        alvoComp.innerHTML = `
          <div class="cartao" style="border-top: 3px solid #8b5cf6; background: var(--superficie-2, #202028); padding: 18px 22px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px">
              <div>
                <h2 style="margin:0; font-size:1.35rem; color:var(--texto, #fff)">
                  🏛️ Painel Comparativo Interfederativo (${escapar(d.ano_selecionado)})
                </h2>
                <p class="rodape-mapa" style="margin:2px 0 0 0">
                  Comparação direta de arrecadação, despesa per capita e gestão fiscal entre a <strong>União (Presidente)</strong>, o <strong>Estado (Governador)</strong> ${esfera === 'municipal' ? 'e o <strong>Município (Prefeito)</strong>' : ''}:
                </p>
              </div>
              <span class="badge-metodo">Benchmarking Fiscal</span>
            </div>

            <div class="painel" style="display:grid; grid-template-columns: repeat(${esferasComp.length}, 1fr); gap:14px; margin-bottom:14px">
              ${esferasComp.map((ec) => `
                <div class="cartao" style="background:var(--superficie); border-left:3px solid ${ec.nivel === 'federal' ? '#38bdf8' : (ec.nivel === 'estadual' ? '#10b981' : '#f59e0b')}">
                  <span class="selo neutro" style="font-size:10px; text-transform:uppercase">${escapar(ec.titulo)}</span>
                  <h4 style="margin:4px 0 2px 0; font-size:1.15rem">${txt(ec.governante)}</h4>
                  <p class="pe" style="margin:0 0 8px 0; color:var(--texto-fraco)">${escapar(ec.cargo)} · <strong>${escapar(ec.partido || '—')}</strong></p>
                  
                  <div style="display:flex; flex-direction:column; gap:4px; font-size:0.88rem">
                    <div style="display:flex; justify-content:space-between">
                      <span style="color:var(--texto-fraco)">Arrecadação:</span>
                      <strong>${dinheiroCurto.format(ec.receita)}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between">
                      <span style="color:var(--texto-fraco)">Despesa Total:</span>
                      <strong>${dinheiroCurto.format(ec.despesa)}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between">
                      <span style="color:var(--texto-fraco)">Gasto/Habitante:</span>
                      <strong style="color:var(--realce, #38bdf8)">${dinheiro.format(ec.despesa_per_capita)}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between">
                      <span style="color:var(--texto-fraco)">Pessoal (RCL):</span>
                      <strong style="color:${ec.pessoal_rcl_pct > 54 ? 'var(--risco)' : 'var(--calmo)'}">${porcentoExato.format(ec.pessoal_rcl_pct)}%</strong>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>

            <table style="width:100%">
              <thead>
                <tr>
                  <th>Esfera de Governo</th>
                  <th>Líder do Executivo</th>
                  <th>População Atendida</th>
                  <th>Orçamento Executado</th>
                  <th>Gasto por Cidadão</th>
                  <th>Resultado Fiscal</th>
                  <th>Pessoal (LRF)</th>
                </tr>
              </thead>
              <tbody>
                ${esferasComp.map((ec) => `
                  <tr>
                    <td><strong>${escapar(ec.titulo)}</strong></td>
                    <td>${txt(ec.governante)} (${escapar(ec.partido || '—')})</td>
                    <td class="valor">${numero.format(ec.populacao)} hab.</td>
                    <td class="valor">${dinheiro.format(ec.despesa)}</td>
                    <td class="valor"><strong style="color:var(--realce, #38bdf8)">${dinheiro.format(ec.despesa_per_capita)}</strong></td>
                    <td class="valor"><span class="selo ${ec.saldo >= 0 ? 'calmo' : 'risco'}" style="font-size:11px">${ec.saldo >= 0 ? 'SUPERÁVIT' : 'DÉFICIT'} ${dinheiroCurto.format(Math.abs(ec.saldo))}</span></td>
                    <td class="valor"><span class="selo ${ec.pessoal_rcl_pct > 54 ? 'risco' : 'calmo'}" style="font-size:11px">${porcentoExato.format(ec.pessoal_rcl_pct)}%</span></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } else {
        alvoComp.hidden = true;
        alvoComp.innerHTML = '';
      }
    }


    // 2. Renderizar Termômetro Macroeconômico
    if (alvoMacro && d.macroeconomia) {
      const m = d.macroeconomia;
      alvoMacro.innerHTML = `
        <div class="tira">
          <span>IPCA (Inflação no Ano)</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="color:var(--realce, #38bdf8); font-size:1.15rem">${porcentoExato.format(m.ipca)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">ao ano (IBGE)</span>
          </div>
        </div>
        <div class="tira">
          <span>Taxa Selic (Juros Copom)</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="color:var(--realce, #38bdf8); font-size:1.15rem">${porcentoExato.format(m.selic)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">meta anual (Bacen)</span>
          </div>
        </div>
        <div class="tira">
          <span>Taxa de Desemprego (PNAD)</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="font-size:1.15rem">${porcentoExato.format(m.desemprego)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">desocupação (IBGE)</span>
          </div>
        </div>
        <div class="tira">
          <span>População no Bolsa Família</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="color:var(--alerta, #f59e0b); font-size:1.15rem">${porcentoExato.format(m.bolsa_familia_pct)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">${numero.format(m.bolsa_familia_familias)} famílias</span>
          </div>
        </div>
        <div class="tira">
          <span>Câmbio Médio (USD / BRL)</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="font-size:1.15rem">R$ ${m.cambio_dolar.toFixed(2)}</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">cotação média anual</span>
          </div>
        </div>
        <div class="tira">
          <span>Carga Tributária Bruta</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="font-size:1.15rem">${porcentoExato.format(m.carga_tributaria)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">do PIB nacional</span>
          </div>
        </div>
        <div class="tira">
          <span>Dívida Bruta do Governo</span>
          <div style="display:flex; flex-direction:column; align-items:flex-end">
            <strong style="font-size:1.15rem">${porcentoExato.format(m.divida_pib)}%</strong>
            <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">do PIB (DBGG)</span>
          </div>
        </div>
      `;
    }

    // 3. Renderizar Defasagem Fiscal (Resultado Primário vs Nominal)
    if (alvoDefasagem && d.defasagem_fiscal) {
      const f = d.defasagem_fiscal;
      const supPrim = f.superavit_primario;
      const supNom = f.superavit_nominal;
      const pctPrim = (f.receita_primaria && f.receita_primaria > 0) ? (f.resultado_primario / f.receita_primaria * 100) : 0;
      const pctNom = (f.receita_primaria && f.receita_primaria > 0) ? (f.resultado_nominal / f.receita_primaria * 100) : 0;
      alvoDefasagem.innerHTML = `
        <div class="painel grid-duas-colunas">
          <!-- Resultado Primário -->
          <div class="cartao" style="background:var(--superficie-2); border-left:4px solid ${supPrim ? '#10b981' : '#ef4444'}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start">
              <div>
                <span class="selo ${supPrim ? 'calmo' : 'risco'}" style="font-weight:bold; font-size:11px">
                  ${supPrim ? '✅ SUPERÁVIT PRIMÁRIO' : '⚠️ DÉFICIT PRIMÁRIO'}
                </span>
                <h3 style="margin:6px 0 0 0; font-size:1.6rem; color:${supPrim ? 'var(--calmo, #10b981)' : 'var(--risco, #ef4444)'}">
                  ${supPrim ? '+' : ''}${porcentoExato.format(pctPrim)}%
                </h3>
                <div style="font-size:1.15rem; font-weight:bold; color:var(--texto); margin-top:2px">
                  ${dinheiro.format(f.resultado_primario)}
                </div>
              </div>
              <span class="badge-metodo" style="font-size:10px">Sem juros</span>
            </div>
            <p class="pe" style="margin:6px 0 10px 0; color:var(--texto-fraco)">
              <strong>Fórmula:</strong> Receitas Primárias (R$ ${dinheiroCurto.format(f.receita_primaria)}) − Despesas Primárias (R$ ${dinheiroCurto.format(f.despesa_primaria)}).
            </p>
            <div class="tiras" style="margin-bottom:8px">
              <div class="tira"><span>Receita Primária</span><strong>${dinheiro.format(f.receita_primaria)}</strong></div>
              <div class="tira"><span>Despesa Primária (Custeio)</span><strong>${dinheiro.format(f.despesa_primaria)}</strong></div>
            </div>
            <p class="pe" style="margin:0; font-size:0.82rem; color:var(--texto-sutil)">
              💡 <em>Mede se o governo arrecada o suficiente para custear a máquina pública (saúde, educação, segurança e funcionalismo) antes de pagar os juros da dívida.</em>
            </p>
          </div>

          <!-- Resultado Nominal -->
          <div class="cartao" style="background:var(--superficie-2); border-left:4px solid ${supNom ? '#10b981' : '#ef4444'}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start">
              <div>
                <span class="selo ${supNom ? 'calmo' : 'risco'}" style="font-weight:bold; font-size:11px">
                  ${supNom ? '✅ SUPERÁVIT NOMINAL' : '⚠️ DÉFICIT NOMINAL'}
                </span>
                <h3 style="margin:6px 0 0 0; font-size:1.6rem; color:${supNom ? 'var(--calmo, #10b981)' : 'var(--risco, #ef4444)'}">
                  ${supNom ? '+' : ''}${porcentoExato.format(pctNom)}%
                </h3>
                <div style="font-size:1.15rem; font-weight:bold; color:var(--texto); margin-top:2px">
                  ${dinheiro.format(f.resultado_nominal)}
                </div>
              </div>
              <span class="badge-metodo" style="font-size:10px">Com juros da dívida</span>
            </div>
            <p class="pe" style="margin:6px 0 10px 0; color:var(--texto-fraco)">
              <strong>Fórmula:</strong> Resultado Primário − Juros & Encargos da Dívida Pública (R$ ${dinheiroCurto.format(f.juros_encargos_divida)}).
            </p>
            <div class="tiras" style="margin-bottom:8px">
              <div class="tira"><span>Resultado Primário Base</span><strong>${dinheiro.format(f.resultado_primario)}</strong></div>
              <div class="tira"><span>Juros Nominais da Dívida</span><strong style="color:var(--risco, #ef4444)">− ${dinheiro.format(f.juros_encargos_divida)}</strong></div>
            </div>
            <p class="pe" style="margin:0; font-size:0.82rem; color:var(--texto-sutil)">
              💡 <em>Mede o fechamento contábil global. Quando negativo, o Estado precisou emitir novos títulos da dívida pública para cobrir o custo dos juros.</em>
            </p>
          </div>
        </div>
      `;
    }

    // 4. Renderizar PIB & Contas Nacionais (Demanda e Oferta)
    if (alvoPib && d.macroeconomia) {
      const p = d.macroeconomia;
      const dem = p.otica_demanda;
      const ofe = p.otica_oferta;
      alvoPib.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; margin-bottom:16px; padding:12px 18px; background:var(--superficie-2); border-radius:8px">
          <div>
            <span class="pe" style="color:var(--texto-fraco)">Produto Interno Bruto (PIB Total do Ente)</span>
            <h3 style="margin:2px 0 0 0; font-size:1.6rem; color:var(--realce, #38bdf8)">${dinheiro.format(p.pib_total)}</h3>
          </div>
          <div>
            <span class="pe" style="color:var(--texto-fraco)">PIB per Capita</span>
            <strong style="font-size:1.2rem; display:block">${dinheiro.format(p.pib_per_capita)} / hab.</strong>
          </div>
          <div>
            <span class="pe" style="color:var(--texto-fraco)">Crescimento Real do PIB</span>
            <strong style="font-size:1.2rem; display:block; color:${p.crescimento_real >= 0 ? 'var(--calmo, #10b981)' : 'var(--risco, #ef4444)'}">
              ${p.crescimento_real >= 0 ? '+' : ''}${porcentoExato.format(p.crescimento_real)}%
            </strong>
          </div>
        </div>

        <div class="painel grid-duas-colunas">
          <!-- Ótica da Demanda -->
          <div class="cartao" style="background:var(--superficie-2)">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
              <h3 style="margin:0; font-size:1.15rem">🛒 Ótica da Demanda (Despesa)</h3>
              <span class="badge-metodo" style="font-size:10px">PIB = C + I + G + (X − M)</span>
            </div>
            <p class="pe" style="color:var(--texto-fraco); margin-top:0">Quem comprou o que foi produzido na economia:</p>
            <table style="width:100%">
              <thead><tr><th>Componente da Demanda</th><th>Valor</th><th>% do PIB</th></tr></thead>
              <tbody>
                <tr>
                  <td><strong>(C) Consumo das Famílias</strong><br><small style="color:var(--texto-fraco)">Bens de consumo, comércio e serviços</small></td>
                  <td class="valor">${dinheiro.format(dem.consumo_familias)}</td>
                  <td class="valor">${dem.pct_consumo}%</td>
                </tr>
                <tr>
                  <td><strong>(G) Gastos do Governo</strong><br><small style="color:var(--texto-fraco)">Serviços públicos e administração</small></td>
                  <td class="valor">${dinheiro.format(dem.gastos_governo)}</td>
                  <td class="valor">${dem.pct_governo}%</td>
                </tr>
                <tr>
                  <td><strong>(I) Investimentos (FBCF)</strong><br><small style="color:var(--texto-fraco)">Máquinas, infraestrutura e construção</small></td>
                  <td class="valor">${dinheiro.format(dem.investimentos_fbcf)}</td>
                  <td class="valor">${dem.pct_investimentos}%</td>
                </tr>
                <tr>
                  <td><strong>(X − M) Balança Líquida</strong><br><small style="color:var(--texto-fraco)">Exportações (${dinheiroCurto.format(dem.exportacoes)}) − Importações (${dinheiroCurto.format(dem.importacoes)})</small></td>
                  <td class="valor">${dinheiro.format(dem.balanca_liquida)}</td>
                  <td class="valor">${dem.pct_balanca}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Ótica da Oferta -->
          <div class="cartao" style="background:var(--superficie-2)">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
              <h3 style="margin:0; font-size:1.15rem">🏭 Ótica da Oferta (Produção / VAB)</h3>
              <span class="badge-metodo" style="font-size:10px">VAB + Impostos Líquidos</span>
            </div>
            <p class="pe" style="color:var(--texto-fraco); margin-top:0">Valor Adicionado Bruto gerado por cada setor produtivo:</p>
            <table style="width:100%">
              <thead><tr><th>Setor Econômico</th><th>Valor</th><th>% do PIB</th></tr></thead>
              <tbody>
                <tr>
                  <td><strong>Setor de Serviços</strong><br><small style="color:var(--texto-fraco)">Comércio, finanças, tecnologia e transporte</small></td>
                  <td class="valor">${dinheiro.format(ofe.servicos)}</td>
                  <td class="valor">${ofe.pct_servicos}%</td>
                </tr>
                <tr>
                  <td><strong>Setor Industrial</strong><br><small style="color:var(--texto-fraco)">Manufatura, construção civil e energia</small></td>
                  <td class="valor">${dinheiro.format(ofe.industria)}</td>
                  <td class="valor">${ofe.pct_industria}%</td>
                </tr>
                <tr>
                  <td><strong>Agropecuária</strong><br><small style="color:var(--texto-fraco)">Agricultura, pecuária e silvicultura</small></td>
                  <td class="valor">${dinheiro.format(ofe.agropecuaria)}</td>
                  <td class="valor">${ofe.pct_agro}%</td>
                </tr>
                <tr>
                  <td><strong>Impostos Líquidos s/ Produtos</strong><br><small style="color:var(--texto-fraco)">ICMS, IPI, PIS/Cofins deduzidos de subsídios</small></td>
                  <td class="valor">${dinheiro.format(ofe.impostos_produtos)}</td>
                  <td class="valor">${ofe.pct_impostos}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      `;
    }


    // Atualização dinâmica dos títulos das seções
    if (titFiscal) {
      titFiscal.textContent = esfera === 'geral'
        ? `Resultado Fiscal Consolidado (${escapar(d.ano_selecionado)})`
        : `Situação Orçamentária — ${nomeEnte} (${escapar(d.ano_selecionado)})`;
    }

    if (titCartoes) {
      if (esfera === 'geral') {
        titCartoes.textContent = '💳 Gastos com Cartões de Pagamento & Suprimentos do Poder Executivo';
        if (subCartoes) subCartoes.textContent = 'Gastos efetuados com cartões de pagamento e suprimentos de fundos no Poder Executivo (Federal, Estadual e Municipal).';
      } else if (esfera === 'federal') {
        titCartoes.textContent = '💳 Cartão de Pagamento do Governo Federal (CPGF) — Presidência & Ministérios';
        if (subCartoes) subCartoes.textContent = 'Gastos efetuados com o Cartão de Pagamento do Governo Federal pela Presidência da República e Ministérios.';
      } else {
        titCartoes.textContent = `💳 Cartões de Pagamento & Suprimentos — ${nomeEnte}${gov ? ' (' + gov.nome + ')' : ''}`;
        if (subCartoes) subCartoes.textContent = `Despesas e suprimentos de fundos executados pelas Secretarias e órgãos de ${nomeEnte}.`;
      }
    }

    if (titViagens) {
      if (esfera === 'geral') {
        titViagens.textContent = '✈️ Viagens a Serviço, Diárias & Passagens Oficiais do Poder Executivo';
        if (subViagens) subViagens.textContent = 'Custos de passagens aéreas, diárias e hospedagem de comitivas e viagens oficiais de gestores públicos.';
      } else if (esfera === 'federal') {
        titViagens.textContent = '✈️ Viagens a Serviço (PCDP) — Presidência da República & Ministérios';
        if (subViagens) subViagens.textContent = 'Custos de passagens aéreas, diárias e hospedagem de viagens oficiais de ministros e comitivas federais.';
      } else {
        titViagens.textContent = `✈️ Viagens Oficiais & Diárias — ${nomeEnte}`;
        if (subViagens) subViagens.textContent = `Missões oficiais e diárias de viagens do ${gov ? gov.cargo + ' ' + gov.nome : 'Governo'} e Secretários de ${nomeEnte}.`;
      }
    }

    if (titContratos) {
      if (esfera === 'geral') {
        titContratos.textContent = '📜 Grandes Contratos Públicos, Licitações & Fornecedores do Poder Executivo';
        if (subContratos) subContratos.textContent = 'Contratos administrativos de grande porte e principais fornecedores do Poder Executivo.';
      } else if (esfera === 'federal') {
        titContratos.textContent = '📜 Contratos Públicos Federais (PNCP) — Governo Federal';
        if (subContratos) subContratos.textContent = 'Contratos administrativos federais firmados, com destaque para dispensas, inexigibilidades e fornecedores.';
      } else {
        titContratos.textContent = `📜 Contratos Públicos & Licitações — ${nomeEnte}`;
        if (subContratos) subContratos.textContent = `Contratos e fornecedores de infraestrutura, saúde, educação e serviços de ${nomeEnte}.`;
      }
    }

    // 2. Popular Seletor de Mandatos
    const seletorMandato = $('#executivo-mandato');
    const blocoMandato = $('#bloco-executivo-mandato');
    const mandatos = d.mandatos_disponiveis || [];

    if (blocoMandato) {
      blocoMandato.hidden = false;
    }

    if (seletorMandato && mandatos.length) {
      const anoAlvo = Number(d.ano_selecionado);
      const mandatoAtivo = mandatos.find((m) => (m.anos && m.anos.includes(anoAlvo)) || (m.ano_inicio <= anoAlvo && m.ano_fim >= anoAlvo)) || mandatos[0];
      const chaveAtiva = `${mandatoAtivo.ano_inicio}_${mandatoAtivo.ano_fim}`;

      seletorMandato.innerHTML = mandatos.map((m) => {
        const chave = `${m.ano_inicio}_${m.ano_fim}`;
        const sel = (chave === chaveAtiva) ? 'selected' : '';
        const anosStr = (m.anos || []).join(',');
        return `<option value="${chave}" data-anos="${anosStr}" ${sel}>${escapar(m.rotulo || m.nome)}</option>`;
      }).join('');

      // 3. Popular Anos de Competência (estritamente os anos do mandato selecionado)
      const seletorAno = $('#executivo-ano');
      if (seletorAno) {
        const anosMandato = mandatoAtivo.anos && mandatoAtivo.anos.length ? mandatoAtivo.anos : [anoAlvo];
        seletorAno.innerHTML = anosMandato.map((a) =>
          `<option value="${a}" ${a === anoAlvo ? 'selected' : ''}>${a}</option>`
        ).join('');
      }
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
        const pctSaldo = (receita && receita > 0) ? (saldo / receita * 100) : 0;
        alvoSaldo.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <span style="font-size:1.1rem">Situação Orçamentária (${escapar(d.ano_selecionado)}):</span>
              <div style="display:flex; flex-direction:column; align-items:flex-end">
                <span class="selo ${superavit ? 'calmo' : 'risco'}" style="font-size:1.05rem; font-weight:bold">
                  ${superavit ? '✅ +' : '⚠️ '}${porcentoExato.format(pctSaldo)}% (${superavit ? 'SUPERÁVIT' : 'DÉFICIT'})
                </span>
                <span style="font-size:0.95rem; color:var(--texto); font-weight:600; margin-top:3px">
                  ${Number.isFinite(saldo) ? dinheiro.format(Math.abs(saldo)) : ''}
                </span>
              </div>
            </div>
            <div class="tiras">
              <div class="tira">
                <span>Arrecadação Total</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${Number.isFinite(receita) ? dinheiro.format(receita) : '—'}</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">receita arrecadada</span>
                </div>
              </div>
              <div class="tira">
                <span>Despesa Executada</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${Number.isFinite(despesa) ? dinheiro.format(despesa) : '—'}</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">orçamento liquidado</span>
                </div>
              </div>
              <div class="tira">
                <span>Despesa por habitante</span>
                <div style="display:flex; flex-direction:column; align-items:flex-end">
                  <strong style="font-size:1.15rem">${Number.isFinite(atual.despesa_per_capita) ? dinheiro.format(atual.despesa_per_capita) : '—'}</strong>
                  <span style="font-size:0.82rem; color:var(--texto-fraco); margin-top:2px">média per capita</span>
                </div>
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

  // Carregar blocos (Cartões, Viagens e Contratos) com o recorte selecionado
  await Promise.all([
    carregarCartoesExecutivo(esfera, uf, codIbge, ano),
    carregarViagensExecutivo(esfera, uf, codIbge, ano),
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
    const d = await buscar('/api/executivo/cartoes', {
      esfera: esfera || undefined,
      sigla_uf: esfera === 'estadual' || esfera === 'municipal' ? uf : undefined,
      cod_ibge: esfera === 'municipal' ? codIbge : undefined,
      ano: ano || undefined,
    });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total Gasto no Cartão</span><strong>${dinheiro.format(d.total_gasto || 0)}</strong></div>
        <div class="tira"><span>Transações Registradas</span><strong>${numero.format(d.total_transacoes || 0)}</strong></div>
        <div class="tira"><span>Órgãos Portadores</span><strong>${numero.format(d.total_orgaos || 0)}</strong></div>
      `;
    }
    const listaFav = d.favorecidos || d.por_favorecido || [];
    const listaOrg = d.orgaos || d.por_orgao || [];
    const listaTrans = d.transacoes || d.maiores_gastos || [];

    if (alvoFav) {
      alvoFav.innerHTML = listaFav.length ? `
        <table><thead><tr><th>Estabelecimento</th><th>Total Gasto</th></tr></thead><tbody>
        ${listaFav.slice(0, 8).map((f) => `<tr><td>${txt(f.nome || f.nome_favorecido)}</td><td class="valor">${dinheiro.format(f.valor || f.total_gasto || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de favorecidos no recorte selecionado.</p>';
    }
    if (alvoOrg) {
      alvoOrg.innerHTML = listaOrg.length ? `
        <table><thead><tr><th>Órgão / Secretaria</th><th>Total Gasto</th></tr></thead><tbody>
        ${listaOrg.slice(0, 8).map((o) => `<tr><td>${txt(o.nome || o.nome_orgao)}</td><td class="valor">${dinheiro.format(o.valor || o.total_gasto || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de órgãos no recorte selecionado.</p>';
    }
    if (alvoTrans) {
      alvoTrans.innerHTML = listaTrans.length ? `
        <table><thead><tr><th>Data</th><th>Órgão</th><th>Favorecido / Estabelecimento</th><th>Portador</th><th>Valor</th></tr></thead><tbody>
        ${listaTrans.slice(0, 15).map((t) => `<tr>
          <td style="white-space:nowrap">${formatarData(t.data || t.data_transacao)}</td>
          <td>${txt(t.orgao || t.nome_orgao)}</td>
          <td><strong>${txt(t.favorecido || t.nome_favorecido)}</strong></td>
          <td>${txt(t.portador || t.nome_portador || '—')}</td>
          <td class="valor">${dinheiro.format(t.valor || 0)}</td>
        </tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de transações no recorte selecionado.</p>';
    }
  } catch (e) {
    if (alvoTopo) alvoTopo.innerHTML = falha(e.message);
  }
}

export async function carregarViagensExecutivo(esfera, uf, codIbge, ano) {
  const alvoTopo = $('#executivo-topo-viagens');
  const alvoDest = $('#executivo-viagens-destinos');
  const alvoOrg = $('#executivo-viagens-orgaos');
  const alvoMaior = $('#executivo-viagens-maiores');

  if (alvoTopo) alvoTopo.innerHTML = esqueleto(2);
  if (alvoDest) alvoDest.innerHTML = esqueleto(3);
  if (alvoOrg) alvoOrg.innerHTML = esqueleto(3);
  if (alvoMaior) alvoMaior.innerHTML = esqueleto(4);

  try {
    const d = await buscar('/api/executivo/viagens', {
      esfera: esfera || undefined,
      sigla_uf: esfera === 'estadual' || esfera === 'municipal' ? uf : undefined,
      cod_ibge: esfera === 'municipal' ? codIbge : undefined,
      ano: ano || undefined,
    });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total em Viagens</span><strong>${dinheiro.format(d.total_gasto || d.total_viagens || 0)}</strong></div>
        <div class="tira"><span>Passagens Aéreas</span><strong>${dinheiro.format(d.total_passagens || 0)}</strong></div>
        <div class="tira"><span>Diárias Pagas</span><strong>${dinheiro.format(d.total_diarias || 0)}</strong></div>
      `;
    }
    const listaDest = d.destinos || d.por_destino || [];
    const listaOrg = d.orgaos || d.por_orgao || [];
    const listaMaior = d.maiores || d.maiores_viagens || [];

    if (alvoDest) {
      alvoDest.innerHTML = listaDest.length ? `
        <table><thead><tr><th>Destino</th><th>Total Gasto</th></tr></thead><tbody>
        ${listaDest.slice(0, 8).map((x) => `<tr><td>${txt(x.destino)}</td><td class="valor">${dinheiro.format(x.valor || x.total_gasto || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de destinos no recorte selecionado.</p>';
    }
    if (alvoOrg) {
      alvoOrg.innerHTML = listaOrg.length ? `
        <table><thead><tr><th>Órgão / Secretaria</th><th>Total</th></tr></thead><tbody>
        ${listaOrg.slice(0, 8).map((x) => `<tr><td>${txt(x.orgao || x.nome_orgao)}</td><td class="valor">${dinheiro.format(x.valor || x.total_gasto || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de viagens por órgão.</p>';
    }
    if (alvoMaior) {
      alvoMaior.innerHTML = listaMaior.length ? `
        <table><thead><tr><th>Data / Período</th><th>Beneficiário</th><th>Órgão / Cargo</th><th>Destino</th><th>Motivo</th><th>Total</th></tr></thead><tbody>
        ${listaMaior.slice(0, 15).map((m) => `<tr>
          <td style="white-space:nowrap">${m.data_inicio ? (m.data_fim && m.data_fim !== m.data_inicio ? `${formatarData(m.data_inicio)} a ${formatarData(m.data_fim)}` : formatarData(m.data_inicio)) : '—'}</td>
          <td><strong>${txt(m.nome || m.nome_viajante)}</strong></td>
          <td>${txt(m.cargo || m.orgao || 'Servidor')}</td>
          <td>${txt(m.destino)}</td>
          <td>${txt(m.motivo)}</td>
          <td class="valor">${dinheiro.format(m.valor || m.valor_total || 0)}</td>
        </tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem viagens registradas no recorte selecionado.</p>';
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
      sigla_uf: esfera === 'estadual' || esfera === 'municipal' ? uf : undefined,
      cod_ibge: esfera === 'municipal' ? codIbge : undefined,
      ano: ano || undefined,
    });
    if (alvoTopo) {
      alvoTopo.innerHTML = `
        <div class="tira"><span>Total Contratado</span><strong>${dinheiro.format(d.total_contratado || 0)}</strong></div>
        <div class="tira"><span>Contratos Firmados</span><strong>${numero.format(d.quantidade_contratos || d.total_contratos || 0)}</strong></div>
        <div class="tira"><span>Dispensas / Inexigibilidades</span><strong>${numero.format(d.dispensas_inexigibilidades || 0)}</strong></div>
      `;
    }
    const listaForn = d.fornecedores || d.por_fornecedor || [];
    const listaMod = d.modalidades || d.por_modalidade || [];
    const listaMaior = d.maiores || d.maiores_contratos || [];

    if (alvoForn) {
      alvoForn.innerHTML = listaForn.length ? `
        <table><thead><tr><th>Fornecedor</th><th>Total Contratado</th></tr></thead><tbody>
        ${listaForn.slice(0, 8).map((f) => `<tr><td>${txt(f.fornecedor || f.nome_fornecedor)}</td><td class="valor">${dinheiro.format(f.valor || f.total_contratado || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de fornecedores no recorte selecionado.</p>';
    }
    if (alvoMod) {
      alvoMod.innerHTML = listaMod.length ? `
        <table><thead><tr><th>Modalidade</th><th>Total</th></tr></thead><tbody>
        ${listaMod.slice(0, 8).map((m) => `<tr><td>${txt(m.modalidade || m.modalidade_licitacao)}</td><td class="valor">${dinheiro.format(m.valor || m.total_contratado || 0)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem dados de modalidades no recorte selecionado.</p>';
    }
    if (alvoMaior) {
      alvoMaior.innerHTML = listaMaior.length ? `
        <table><thead><tr><th>Data / Vigência</th><th>Objeto</th><th>Fornecedor</th><th>Modalidade</th><th>Valor</th></tr></thead><tbody>
        ${listaMaior.slice(0, 15).map((c) => `<tr>
          <td style="white-space:nowrap">${c.data_inicio || c.data_inicio_vigencia ? `${formatarData(c.data_inicio || c.data_inicio_vigencia)} a ${formatarData(c.data_fim || c.data_fim_vigencia)}` : '—'}</td>
          <td><strong>${txt(c.objeto)}</strong></td>
          <td>${txt(c.fornecedor || c.nome_fornecedor)}</td>
          <td><span class="selo neutro" style="font-size:11px">${txt(c.modalidade || c.modalidade_licitacao || 'Contrato')}</span></td>
          <td class="valor">${dinheiro.format(c.valor || c.valor_atualizado || 0)}</td>
        </tr>`).join('')}
        </tbody></table>` : '<p class="vazio">Sem contratos registrados no recorte selecionado.</p>';
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
    const blocoMandato = $('#bloco-executivo-mandato');

    if (esfera === 'geral') {
      if (blocoUf) blocoUf.hidden = true;
      if (blocoMun) blocoMun.hidden = true;
      if (blocoMandato) blocoMandato.hidden = true;
    } else if (esfera === 'federal') {
      if (blocoUf) blocoUf.hidden = true;
      if (blocoMun) blocoMun.hidden = true;
      if (blocoMandato) blocoMandato.hidden = false;
    } else if (esfera === 'estadual') {
      if (blocoUf) blocoUf.hidden = false;
      if (blocoMun) blocoMun.hidden = true;
      if (blocoMandato) blocoMandato.hidden = false;
    } else {
      if (blocoUf) blocoUf.hidden = false;
      if (blocoMun) blocoMun.hidden = false;
      if (blocoMandato) blocoMandato.hidden = false;
      popularMunicipiosExecutivo($('#executivo-uf')?.value);
    }
    const seletorMandato = $('#executivo-mandato');
    if (seletorMandato) seletorMandato.value = '';
    const seletorAno = $('#executivo-ano');
    if (seletorAno) seletorAno.value = '';
    carregarExecutivo();
  });

  $('#executivo-uf')?.addEventListener('change', (e) => {
    if ($('#executivo-esfera')?.value === 'municipal') {
      popularMunicipiosExecutivo(e.target.value);
    }
    const seletorMandato = $('#executivo-mandato');
    if (seletorMandato) seletorMandato.value = '';
    const seletorAno = $('#executivo-ano');
    if (seletorAno) seletorAno.value = '';
    carregarExecutivo();
  });

  $('#executivo-municipio')?.addEventListener('change', () => {
    const seletorMandato = $('#executivo-mandato');
    if (seletorMandato) seletorMandato.value = '';
    const seletorAno = $('#executivo-ano');
    if (seletorAno) seletorAno.value = '';
    carregarExecutivo();
  });

  $('#executivo-mandato')?.addEventListener('change', (e) => {
    const opt = e.target.selectedOptions?.[0];
    const anos = opt?.dataset?.anos ? opt.dataset.anos.split(',').map(Number).filter(Boolean) : null;
    const seletorAno = $('#executivo-ano');
    if (seletorAno && anos && anos.length) {
      seletorAno.innerHTML = anos.map(a => `<option value="${a}">${a}</option>`).join('');
      seletorAno.value = String(anos[0]);
    }
    carregarExecutivo();
  });

  $('#executivo-ano')?.addEventListener('change', carregarExecutivo);
  $('#btn-atualizar-executivo')?.addEventListener('click', carregarExecutivo);
}

