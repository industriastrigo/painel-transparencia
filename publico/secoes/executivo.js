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

  const alvoGov = $('#executivo-governante');
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
    const nomeEnte = d.ente?.nome || (esfera === 'federal' ? 'Brasil' : 'Estado de ' + uf);

    // 1. Renderizar Topo / Governante
    if (alvoGov) {
      if (esfera === 'geral') {
        alvoGov.innerHTML = `
          <div class="cartao" style="border-left: 4px solid var(--realce, #38bdf8); background: var(--superficie-2, #202028); padding: 18px 22px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px">
              <div>
                <span class="selo calmo" style="text-transform:uppercase; font-size:11px; letter-spacing:0.5px">VISÃO GERAL CONSOLIDADA</span>
                <h2 style="margin:6px 0 3px 0; font-size:1.6rem; color:var(--texto, #fff)">Gastos do Poder Executivo</h2>
                <p class="rodape-mapa" style="margin:0; font-size:0.92rem; color:var(--texto-sutil, #888)">
                  Panorama consolidado das contas públicas, despesas executadas, contratos e suprimentos da União, dos 26 Estados, DF e Municípios.
                </p>
              </div>
              <div style="text-align:right">
                <span class="pe" style="display:block; color:var(--texto-fraco)">Abrangência do Painel</span>
                <strong style="font-size:1.15rem; color:var(--realce, #38bdf8)">Todas as Esferas de Governo</strong>
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
      blocoMandato.hidden = (esfera === 'geral');
    }

    if (seletorMandato) {
      if (!mandatos.length) {
        seletorMandato.innerHTML = '<option value="todos">Todos os Períodos</option>';
      } else {
        const anoAlvo = Number(d.ano_selecionado);
        const valorAtual = seletorMandato.value;
        const mandatoAtivo = mandatos.find((m) => m.ano_inicio <= anoAlvo && m.ano_fim >= anoAlvo) || mandatos[0];
        const chaveAtiva = `${mandatoAtivo.ano_inicio}_${mandatoAtivo.ano_fim}`;
        const chaveEscolhida = (valorAtual && (valorAtual === 'todos' || mandatos.some(m => `${m.ano_inicio}_${m.ano_fim}` === valorAtual)))
          ? valorAtual
          : chaveAtiva;

        seletorMandato.innerHTML = mandatos.map((m) => {
          const chave = `${m.ano_inicio}_${m.ano_fim}`;
          const sel = (chave === chaveEscolhida) ? 'selected' : '';
          const anosStr = (m.anos || []).join(',');
          return `<option value="${chave}" data-anos="${anosStr}" ${sel}>${escapar(m.rotulo || m.nome)}</option>`;
        }).join('') + `<option value="todos" data-anos="${(d.serie_anual || []).map(s => s.ano).join(',')}" ${chaveEscolhida === 'todos' ? 'selected' : ''}>Todos os Anos (${d.serie_anual?.[d.serie_anual.length - 1]?.ano || ''}–${d.serie_anual?.[0]?.ano || ''})</option>`;
      }
    }

    // 3. Popular Anos de Competência
    const seletorAno = $('#executivo-ano');
    if (seletorAno && d.serie_anual?.length) {
      const optMandato = seletorMandato?.selectedOptions?.[0];
      const anosPermitidos = (optMandato && optMandato.dataset?.anos)
        ? optMandato.dataset.anos.split(',').map(Number).filter(Boolean)
        : null;

      const anosLista = (anosPermitidos && anosPermitidos.length > 0)
        ? d.serie_anual.filter((s) => anosPermitidos.includes(s.ano))
        : d.serie_anual;

      const listaFinal = anosLista.length ? anosLista : d.serie_anual;
      const anoSelecionado = d.ano_selecionado || listaFinal[0]?.ano;

      seletorAno.innerHTML = listaFinal.map((s) =>
        `<option value="${s.ano}" ${s.ano === Number(anoSelecionado) ? 'selected' : ''}>${s.ano}</option>`
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
      seletorAno.value = String(anos[0]);
    }
    carregarExecutivo();
  });

  $('#executivo-ano')?.addEventListener('change', carregarExecutivo);
  $('#btn-atualizar-executivo')?.addEventListener('click', carregarExecutivo);
}

