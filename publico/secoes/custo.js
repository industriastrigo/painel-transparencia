/* Custo do Estado: subsídios, folha e comparativo de poderes/mandatos. */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, endereco, numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS, LIMITE_CONSULTA, SELO_SITUACAO
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { esqueleto, falha, falhaEmLinha } from '../nucleo/ui.js';
import { cartaoNumero } from './entes.js';

const FALHOU = Symbol('falhou');

/* ------------------------------------------------------------- custo */

let _filtrosIniciados = false;

async function carregarCusto() {
  const seletorAno = $('#custo-ano');
  const seletorPoder = $('#custo-filtro-poder');

  // Inicializa o seletor de anos se ainda não foi populado
  if (seletorAno && !seletorAno.options.length) {
    const anosDisponiveis = [2026, 2025, 2024, 2023, 2022, 2021, 2020];
    anosDisponiveis.forEach((a) => {
      const opt = new Option(`Exercício ${a}`, a);
      if (a === 2024) opt.selected = true;
      seletorAno.add(opt);
    });
  }

  // Liga os ouvintes de evento dos filtros uma única vez
  if (!_filtrosIniciados) {
    _filtrosIniciados = true;
    seletorAno?.addEventListener('change', () => carregarCusto());
    seletorPoder?.addEventListener('change', () => carregarCusto());
  }

  const ano = seletorAno?.value ? Number(seletorAno.value) : 2024;
  const poder = seletorPoder?.value || undefined;

  $('#tabela-custo tbody').innerHTML = `<tr><td colspan="5">${esqueleto(4)}</td></tr>`;
  const [cargos, resumo] = await Promise.all([
    buscar('/api/custo/cargos', poder ? { poder } : {}).catch(() => FALHOU),
    buscar('/api/custo/resumo', { ...(ano ? { ano } : {}), ...(poder ? { poder } : {}) }).catch(() => FALHOU),
  ]);

  renderizarTopoDeCusto(resumo);
  renderizarAvisosDeCusto(resumo);
  renderizarTabelaDeCusto(cargos);
  renderizarLateralDeCusto(resumo);
}

function renderizarTopoDeCusto(resumo) {
  const alvo = $('#topo-custo');
  if (!resumo || resumo === FALHOU) { alvo.innerHTML = ''; return; }

  const estimado = somar(resumo.estimado_por_poder || [], 'custo_estimado');
  const ocupantes = somar(resumo.estimado_por_poder || [], 'ocupantes');
  // Só estes entram no valor. `somar` ignora custo nulo mas somava
  // TODOS os ocupantes, então o rótulo cobria 64.323 pessoas e o
  // número cobria 594.
  const comSubsidio = somar(resumo.estimado_por_poder || [], 'ocupantes_com_subsidio');

  // A cobertura ao lado do número, não escondida num aviso. A soma de 27 UFs
  // e a de 5.570 municípios são grandezas diferentes e se parecem igualmente
  // com "o total do Brasil" — quem lê precisa ver de quantos entes ela veio.
  // CADA CARTÃO DIZ DE QUE ANO ELE É.
  const nota = (valor, entesDoBloco, anoDoBloco) => {
    if (valor == null) return 'nada coletado ainda';
    const partes = [];
    if (entesDoBloco) partes.push(`${contagem(entesDoBloco)} ente(s) do acervo`);
    if (anoDoBloco) partes.push(String(anoDoBloco));
    return partes.join(' · ');
  };

  alvo.innerHTML =
    cartaoNumero('Arrecadação de estados e municípios', resumo.arrecadacao,
                 'receita_total',
                 nota(resumo.arrecadacao, resumo.arrecadacao_entes,
                      resumo.ano_arrecadacao ?? resumo.ano))
    + cartaoNumero('Despesa de estados e municípios', resumo.despesa_subnacional,
                   'despesa_total',
                   nota(resumo.despesa_subnacional, resumo.despesa_entes,
                        resumo.ano_despesa_subnacional ?? resumo.ano))
    + cartaoNumero('Subsídios (estimativa)', estimado || null, 'despesa_total',
                   comSubsidio
                     ? `${contagem(comSubsidio)} de ${contagem(ocupantes)} `
                       + 'ocupantes têm subsídio cadastrado × 13,33'
                     : 'ocupantes × subsídio × 13,33');
}

function renderizarAvisosDeCusto(resumo) {
  const alvo = $('#avisos-custo');
  if (!alvo) return;
  const avisos = resumo?.avisos || [];
  if (!avisos.length) {
    alvo.innerHTML = '';
    return;
  }
  alvo.innerHTML = `
    <details class="aviso-expansivel atencao" style="margin-top:10px; margin-bottom:14px">
      <summary>
        <div class="expansivel-titulo">
          <span class="icone-guia"><svg class="item-svg-inline" viewBox="0 0 24 24" width="16" height="16"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></span>
          <strong>Leia antes de citar estes números (${avisos.length} observações metodológicas)</strong>
          <span class="seta-expandir"><svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><polyline points="6 9 12 15 18 9"></polyline></svg></span>
        </div>
      </summary>
      <div class="expansivel-conteudo">
        ${avisos.map((a) => `<div>· ${escapar(a)}</div>`).join('')}
      </div>
    </details>
  `;
}

function renderizarTabelaDeCusto(cargos) {
  const corpo = $('#tabela-custo tbody');
  if (cargos === FALHOU) {
    corpo.innerHTML = falhaEmLinha(5, 'Não deu para ler os cargos.');
    return;
  }
  if (!cargos.length) {
    corpo.innerHTML = '<tr><td colspan="5" class="vazio">'
      + 'Nenhum cargo com subsídio no acervo. Se você já rodou '
      + '<strong>Referências</strong>, confira o arquivo '
      + '<code>referencias/subsidios.csv</code>.'
      + '</td></tr>';
    return;
  }

  corpo.innerHTML = cargos.map((c) => {
    // A API controla este endereço, e um `href` aceita `javascript:` — o
    // `rel="noopener"` não protege contra isso. Só http e https passam.
    const norma = endereco(c.url_norma);
    return `
    <tr>
      <td>${txt(c.cargo)}${c.ramo ? `<br><span class="cadencia">${escapar(c.ramo)}</span>` : ''}
        ${c.poder ? `<br><span class="cadencia">${escapar(c.poder)}${
          c.esfera ? ` · ${escapar(c.esfera)}` : ''}</span>` : ''}</td>
      <td class="centrado"><strong>${contagem(c.ocupantes)}</strong></td>
      <td class="valor">${c.valor_mensal == null ? '—'
        : escapar(dinheiro.format(c.valor_mensal))}
        ${c.valor_mensal != null && !c.conferido
          ? ' <span class="nao-conferido" title="valor transcrito e ainda não conferido contra a norma"><svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>a conferir</span>'
          : ''}</td>
      <td class="valor">${c.custo_anual_estimado == null ? '—'
        : escapar(dinheiro.format(c.custo_anual_estimado))}</td>
      <td>${norma
        ? `<a class="fonte-oficial" href="${norma}" target="_blank"
             rel="noopener noreferrer">${txt(c.norma ?? 'norma')}</a>`
        : txt(c.norma)}
        ${c.observacao ? `<br><span class="cadencia">${escapar(c.observacao)}</span>` : ''}</td>
    </tr>`;
  }).join('');
}

function tabela(cabecalho, corpo) {
  return `
    <div class="rolagem" style="margin-top:8px; margin-bottom:18px">
      <table class="tabela-lateral">
        <thead><tr>${cabecalho}</tr></thead>
        <tbody>${corpo}</tbody>
      </table>
    </div>
  `;
}

function renderizarLateralDeCusto(resumo) {
  const alvo = $('#lateral-custo');
  if (resumo === FALHOU) { alvo.innerHTML = falha('Resumo indisponível.'); return; }
  if (!resumo) { alvo.innerHTML = '<p class="vazio">Sem dados.</p>'; return; }

  const bloco = (titulo, linhas, rotulo, campo, nota, extra) => {
    if (!linhas.length) return '';
    const total = somar(linhas, campo);
    // Recorte cuja coleta terminou `parcial` ou `erro` não vira valor apurado:
    // vira PISO, com o selo e a contagem de linhas ao lado. O total do bloco
    // herda o piso, porque somar um número completo com um truncado devolve um
    // truncado — e a soma é justamente onde a marca se perderia.
    const parcial = linhas.some((l) => l.completo === false);
    const piso = (v) => (parcial ? '≥ ' : '') + formatar(v, 'despesa_total');
    return `
      <h3 style="margin-top:16px; margin-bottom:4px; font-size:var(--t-base); color:var(--realce)">${escapar(titulo)}</h3>
      ${nota ? `<p class="rodape-mapa" style="margin-bottom:8px">${escapar(nota)}</p>` : ''}
      ${tabela('<th>Item / Poder</th><th>Valor Executado</th>',
        linhas.map((l) => `<tr>
          <td><strong>${txt(l[rotulo])}</strong>${l.esfera
            ? ` <span class="badge-subsidio">${escapar(l.esfera)}</span>` : ''}${
            extra && l[extra] != null
              ? `<br><span class="cadencia">${contagem(l[extra])} ocupantes</span>` : ''}</td>
          <td class="valor" title="${atributo(exato(aNumero(l[campo]), 'despesa_total'))}"
            >${l.completo === false ? '≥ ' : ''}${formatar(aNumero(l[campo]), 'despesa_total')}${
            l.completo === false
              ? `<br><span class="nao-conferido" title="A coleta deste recorte terminou como '${
                  atributo(l.situacao_coleta || 'incompleta')}': o valor é um piso, não o total apurado."
                  ><svg class="item-svg-inline" viewBox="0 0 24 24" width="12" height="12"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>coleta incompleta</span>`
              : ''}${l.linhas != null
              ? `<br><span class="cadencia">${contagem(l.linhas)} linha(s)</span>` : ''}</td>
        </tr>`).join('')
        + `<tr class="linha-total"><td><strong>Total</strong></td>
             <td class="valor"><strong>${piso(total)}</strong></td></tr>`)}`;
  };

  const conteudo =
    bloco('Despesa por Função (SICONFI)', resumo.despesa_por_funcao || [], 'funcao',
          'valor', `Valor empenhado e liquidado em ${resumo.ano ?? '—'}.`)
    + bloco('Custo Medido Federal (Por Poder)', resumo.custo_medido_federal || [],
            'conjunto', 'valor', 'Apurado pelo Tesouro Nacional e Balanço Geral da União.')
    + bloco('Estimativa de Subsídios por Poder',
            resumo.estimado_por_poder || [], 'poder', 'custo_estimado',
            'Folha-base estimada: ocupantes × subsídio × 13,33.', 'ocupantes');

  alvo.innerHTML = conteudo
    || '<p class="vazio">Colete SICONFI, Tesouro e Referências para preencher.</p>';
}


export {
  carregarCusto,
  renderizarTopoDeCusto, renderizarAvisosDeCusto, renderizarTabelaDeCusto,
  renderizarLateralDeCusto
};
