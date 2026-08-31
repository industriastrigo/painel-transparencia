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

async function carregarCusto() {
  $('#tabela-custo tbody').innerHTML = `<tr><td colspan="5">${esqueleto(4)}</td></tr>`;
  const [cargos, resumo] = await Promise.all([
    buscar('/api/custo/cargos').catch(() => FALHOU),
    buscar('/api/custo/resumo').catch(() => FALHOU),
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
  //
  // As fontes têm calendários diferentes: o RREO é bimestral e já publica o
  // exercício corrente; o DCA, de onde vêm arrecadação e despesa total, é
  // anual e sai no seguinte. Fixar UM ano para a aba inteira fazia a
  // arrecadação de 2025 desaparecer da tela assim que 2026 passava a existir
  // pela metade — com o número no disco. Melhor mostrar 2025 dizendo 2025.
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
  const avisos = resumo?.avisos || [];
  alvo.innerHTML = avisos.length
    ? `<div class="aviso"><strong>Leia antes de citar estes números</strong>
       ${avisos.map((a) => `<div>· ${escapar(a)}</div>`).join('')}</div>`
    : '';
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
      <td class="valor">${contagem(c.ocupantes)}</td>
      <td class="valor">${c.valor_mensal == null ? '—'
        : escapar(dinheiro.format(c.valor_mensal))}
        ${c.valor_mensal != null && !c.conferido
          ? ' <span class="nao-conferido" title="valor transcrito e ainda não conferido contra a norma">⚠ a conferir</span>'
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
      <h2 style="margin-top:20px">${escapar(titulo)}</h2>
      ${nota ? `<p class="rodape-mapa">${escapar(nota)}</p>` : ''}
      ${tabela('<th>Item</th><th>Valor</th>',
        linhas.map((l) => `<tr>
          <td>${txt(l[rotulo])}${l.esfera
            ? ` <span class="cadencia">${escapar(l.esfera)}</span>` : ''}${
            extra && l[extra] != null
              ? `<br><span class="cadencia">${contagem(l[extra])} ocupantes</span>` : ''}</td>
          <td class="valor" title="${atributo(exato(aNumero(l[campo]), 'despesa_total'))}"
            >${l.completo === false ? '≥ ' : ''}${formatar(aNumero(l[campo]), 'despesa_total')}${
            l.completo === false
              ? `<br><span class="nao-conferido" title="A coleta deste recorte terminou como '${
                  atributo(l.situacao_coleta || 'incompleta')}': o valor é um piso, não o total apurado."
                  >⚠ coleta incompleta</span>`
              : ''}${l.linhas != null
              ? `<br><span class="cadencia">${contagem(l.linhas)} linha(s)</span>` : ''}</td>
        </tr>`).join('')
        + `<tr><td><strong>Total</strong></td>
             <td class="valor"><strong>${piso(total)}</strong></td></tr>`)}`;
  };

  const conteudo =
    bloco('Despesa por função', resumo.despesa_por_funcao || [], 'funcao',
          'valor', `Valor empenhado em ${resumo.ano ?? '—'} — o que de fato saiu.`)
    + bloco('Custo medido federal', resumo.custo_medido_federal || [],
            'conjunto', 'valor', 'Apurado pelo Tesouro/SIC.')
    + bloco('Subsídios por poder (estimativa)',
            resumo.estimado_por_poder || [], 'poder', 'custo_estimado',
            'Conta, não medição — ocupantes × subsídio × 13,33.', 'ocupantes');

  alvo.innerHTML = conteudo
    || '<p class="vazio">Colete SICONFI, Tesouro e Referências para preencher.</p>';
}


export {
  carregarCusto,
  renderizarTopoDeCusto, renderizarAvisosDeCusto, renderizarTabelaDeCusto,
  renderizarLateralDeCusto
};
