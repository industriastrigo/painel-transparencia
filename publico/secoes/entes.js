/* Ficha técnica do município/estado (orçamento, saúde, educação, limites LRF). */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, endereco, numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { abrirDialogo, esqueleto, falha, falhaEmLinha } from '../nucleo/ui.js';
import { estado } from './mapa.js';

/* ---------------------------------------------------------- ficha do ente */

const POR_EXTENSO_PODER = {
  E: 'Executivo', L: 'Legislativo', J: 'Judiciário',
  M: 'Ministério Público', D: 'Defensoria',
};

/** Uma tabela dentro de um contêiner que rola.
 *
 *  Sem ele, uma tabela de seis colunas empurra a PÁGINA inteira para o lado
 *  no celular — o usuário perde a coluna da esquerda e não descobre por quê.
 *  Quem rola tem de ser a tabela. */
const tabela = (cabecalho, linhas) =>
  `<div class="rolagem"><table><thead><tr>${cabecalho}</tr></thead>`
  + `<tbody>${linhas}</tbody></table></div>`;

/** Cartão de número grande. Distingue ausência de valor com classe própria:
 *  "—" cinza e menor não compete visualmente com um número real ao lado. */
// `textoBruto` para o que já vem pronto e não é dinheiro nem contagem — uma
// taxa de presença, por exemplo. O cartão continua sendo o mesmo objeto na
// tela; só o miolo vem formatado de fora.
const cartaoNumero = (rotulo, valor, metrica, nota = '', exatoNaTela = false,
                      textoBruto = null) => {
  const v = aNumero(valor);
  const vazio = textoBruto == null && !Number.isFinite(v);
  // `exatoNaTela` para valor de NORMA: o subsídio é R$ 41.650,92 e a norma
  // diz isso com centavos. Arredondar um número que a lei fixa é reescrever
  // a lei — diferente de abreviar um total orçamentário de bilhões.
  const texto = textoBruto != null ? textoBruto
    : vazio ? '—'
    : (exatoNaTela ? dinheiroExato.format(v) : formatar(v, metrica));
  return `
    <div class="cartao">
      <div class="rotulo-numero">${escapar(rotulo)}</div>
      <div class="numero-grande${vazio ? ' ausente' : ''}"
           title="${atributo(exato(v, metrica))}">${escapar(texto)}</div>
      ${nota ? `<div class="nota-numero">${escapar(nota)}</div>` : ''}
    </div>`;
};

async function abrirFicha(codIbge) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = esqueleto();
  abrirDialogo(dialogo, 'Ficha do ente');

  let f;
  try {
    f = await buscar(`/api/ente/${encodeURIComponent(codIbge)}`);
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para carregar a ficha deste ente.', erro);
    return;
  }
  if (!f || !f.ente) {
    alvo.innerHTML = '<p class="vazio">Ente não encontrado.</p>';
    return;
  }

  const r = f.resumo || {};
  const governantes = f.governantes ?? [];
  const legislativo = f.legislativo ?? [];
  const financas = f.financas ?? [];
  const funcoes = f.funcoes ?? [];
  const lrf = f.lrf ?? [];
  const indicadores = f.indicadores ?? [];

  alvo.innerHTML = `
    <h2 id="titulo-detalhe">${escapar(f.ente.nome)}${
      f.ente.sigla_uf && f.ente.nivel === 'municipio'
        ? ` <span style="color:var(--texto-fraco)">${escapar(f.ente.sigla_uf)}</span>` : ''}</h2>
    <p class="rodape-mapa">${escapar(f.ente.nivel)}${
      f.ente.regiao ? ` · região ${escapar(f.ente.regiao)}` : ''
      } · código IBGE ${escapar(f.ente.cod_ibge)}${
      f.ano ? ` · dados de ${escapar(f.ano)}` : ''}</p>

    ${resumoDeRisco(r)}

    <h2>Quanto entra e quanto sai</h2>
    <div class="tiras">
      ${cartaoNumero('Arrecadação', r.receita_total, 'receita_total')}
      ${cartaoNumero('Despesa total', r.despesa_total, 'despesa_total')}
      ${cartaoNumero('População', r.populacao, 'populacao')}
      ${cartaoNumero('Despesa por habitante', r.despesa_per_capita, 'despesa_per_capita')}
    </div>

    ${Number.isFinite(aNumero(r.dependencia_transferencia)) ? `
      <p class="rodape-mapa">
        <strong>${porcento.format(aNumero(r.dependencia_transferencia))}%</strong>
        da arrecadação veio de transferências, não de tributo próprio.
        ${aNumero(r.dependencia_transferencia) > 80
          ? ' É o número que explica a dependência do FPM.' : ''}</p>` : ''}

    <h2>Saúde, educação e a folha</h2>
    <div class="tiras">
      ${cartaoNumero('Saúde', r.despesa_saude, 'despesa_saude',
        Number.isFinite(aNumero(r.saude_per_capita))
          ? `${formatar(aNumero(r.saude_per_capita), 'despesa_per_capita')} por habitante` : '')}
      ${cartaoNumero('Educação', r.despesa_educacao, 'despesa_educacao',
        Number.isFinite(aNumero(r.educacao_per_capita))
          ? `${formatar(aNumero(r.educacao_per_capita), 'despesa_per_capita')} por habitante` : '')}
      ${cartaoNumero('Pessoal sobre a RCL', r.percentual_pessoal, 'percentual_pessoal',
        'limite da LRF')}
      ${cartaoNumero('Dívida líquida', r.divida_liquida, 'despesa_total', 'saldo, RGF')}
    </div>
    ${avisoLRF(r)}
    ${Number.isFinite(aNumero(r.despesa_saude))
      ? `<p class="rodape-mapa">Saúde e educação vêm do RREO Anexo 02, que é
         acumulado no exercício — vale o bimestre mais recente entregue, e não
         a soma dos seis. É outro recorte da mesma despesa: não se soma com a
         despesa por natureza abaixo.</p>` : ''}

    <h2>Quem governa</h2>
    ${governantes.length
      ? tabela('<th>Cargo</th><th>Nome</th><th>Partido</th><th>Mandato</th>',
          governantes.map((g) => `<tr>
            <td>${txt(g.cargo)}</td><td>${txt(g.nome)}</td>
            <td>${txt(g.sigla_partido)}</td>
            <td>${escapar(g.ano_inicio ?? '?')}–${escapar(g.ano_fim ?? '?')}</td>
          </tr>`).join(''))
      : `<p class="vazio">Nenhum mandato ligado a este ente.
         Rode o coletor do TSE — e, se ele já rodou, pode ser o nome da cidade
         que não casou com o cadastro do IBGE.</p>`}

    ${legislativo.length ? `<h2>Legislativo</h2>
      ${tabela('<th>Cargo</th><th>Quantidade</th>',
        legislativo.map((l) => `<tr><td>${txt(l.cargo)}</td>
          <td class="valor">${contagem(l.quantidade)}</td></tr>`).join(''))}` : ''}

    <h2>Em que gasta — por natureza</h2>
    ${financas.length ? (() => {
      const total = somar(financas);
      return tabela('<th>Natureza</th><th>Empenhado</th><th>Fatia</th>',
        financas.map((x) => `<tr>
          <td>${txt(x.natureza ?? x.cod_natureza)}</td>
          <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
            >${formatar(aNumero(x.valor), 'despesa_total')}</td>
          <td class="valor">${fatia(x.valor, total)}</td>
        </tr>`).join(''))
        + (funcoes.length ? `<p class="rodape-mapa">Pessoal, juros,
            investimentos: <strong>o quê</strong> foi comprado. A tabela
            seguinte mostra <strong>para quê</strong>. São dois recortes do
            mesmo dinheiro — somar os dois dobra a despesa do ente.</p>` : '');
    })() : '<p class="vazio">Despesa por natureza não coletada para este ente.</p>'}

    ${conferencia('a soma das categorias', f.conferencia_despesa)}

    ${funcoes.length ? `<h2>Para que gasta — por função de governo</h2>
      <p class="rodape-mapa">Do RREO Anexo 02, ${
        escapar(String(funcoes[0].periodo ?? '').replace('_', ' '))} de ${escapar(f.ano)}.
        Acumulado no exercício: é o retrato do bimestre mais recente entregue,
        não a soma dos bimestres.</p>
      ${(() => {
        const total = somar(funcoes);
        return tabela('<th>Função</th><th>Empenhado</th><th>Fatia</th>',
          funcoes.map((x) => `<tr>
            <td>${txt(x.funcao ?? x.cod_funcao)}</td>
            <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
              >${formatar(aNumero(x.valor), 'despesa_total')}</td>
            <td class="valor">${fatia(x.valor, total)}</td>
          </tr>`).join(''));
      })()}
      ${conferencia('a soma das funções', f.conferencia_funcao)}` : ''}

    ${lrf.length ? `<h2>Limites da Lei de Responsabilidade Fiscal</h2>
      <p class="rodape-mapa">Do RGF, ${
        escapar(String(lrf[0].periodo ?? '').replace('_', ' '))} de ${escapar(f.ano)}.
        O percentual <strong>e</strong> o limite vêm os dois do demonstrativo do
        próprio ente — o limite muda por esfera e por poder, então o painel não
        o calcula. Sem limite publicado, ele não afirma nada.</p>
      ${tabela(`<th>Poder</th><th>Pessoal</th><th>Receita corrente líquida</th>
                <th>% sobre a RCL</th><th>Prudencial</th><th>Limite</th>
                <th>Dívida líquida</th>`,
        lrf.map((x) => `<tr>
          <td>${escapar(POR_EXTENSO_PODER[x.poder] ?? x.poder ?? '—')}</td>
          <td class="valor">${formatar(aNumero(x.despesa_pessoal_liquida), 'despesa_total')}</td>
          <td class="valor">${formatar(aNumero(x.receita_corrente_liquida), 'despesa_total')}</td>
          <td class="valor">${seloLimite(x)}</td>
          <td class="valor">${formatar(aNumero(x.limite_prudencial), 'percentual_pessoal')}</td>
          <td class="valor">${formatar(aNumero(x.limite_maximo), 'percentual_pessoal')}</td>
          <td class="valor">${formatar(aNumero(x.divida_liquida), 'despesa_total')}</td>
        </tr>`).join(''))}` : ''}

    ${f.transferencias_uniao?.length ? `<h2>O que a União repassou</h2>
      <p class="rodape-mapa">Pago pelo Tesouro em ${escapar(f.ano)}, por modalidade.
        É outra medida da <strong>arrecadação</strong> acima, que é o que o
        próprio ente declarou ao SICONFI — as duas não batem, e nenhuma das
        duas está errada.</p>
      ${(() => {
        const total = somar(f.transferencias_uniao);
        return tabela('<th>Modalidade</th><th>Valor</th><th>Fatia</th>',
          f.transferencias_uniao.map((x) => `<tr>
            <td>${txt(x.transferencia ?? x.cod_transferencia)}</td>
            <td class="valor" title="${atributo(exato(aNumero(x.valor), 'transferencia_uniao'))}"
              >${formatar(aNumero(x.valor), 'transferencia_uniao')}</td>
            <td class="valor">${fatia(x.valor, total)}</td>
          </tr>`).join(''));
      })()}` : ''}

    ${f.credito ? `<h2>O que pediu emprestado</h2>
      <p class="rodape-mapa">Pedidos de Verificação de Limites protocolados no
        Tesouro (SADIPEM) em ${escapar(f.ano)}. <strong>Não é o saldo
        devedor</strong> — esse é a dívida líquida, acima. É o valor pleiteado
        na época, e parte dele pode nunca ter virado contrato.</p>
      <div class="tiras">
        ${cartaoNumero('Pleiteado', f.credito.valor_pleiteado, 'despesa_total')}
        ${cartaoNumero('Deferido', f.credito.valor_deferido, 'despesa_total')}
        ${cartaoNumero('Contratado', f.credito.valor_contratado, 'despesa_total')}
        ${cartaoNumero('Pedidos', f.credito.pleitos, 'populacao')}
      </div>
      ${f.credito_finalidade?.length
        ? tabela('<th>Finalidade</th><th>Credor</th><th>Valor deferido</th>',
            f.credito_finalidade.map((x) => `<tr>
              <td>${txt(x.finalidade)}</td>
              <td>${txt(x.credor ?? x.tipo_credor)}</td>
              <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
                >${formatar(aNumero(x.valor), 'despesa_total')}</td>
            </tr>`).join(''))
        : ''}` : ''}

    ${indicadores.length ? `<h2>Indicadores</h2>
      ${tabela('<th>Indicador</th><th>Ano</th><th>Valor</th>',
        indicadores.map((i) => {
          const v = formatarIndicador(i.valor, i.unidade);
          return `<tr>
            <td>${txt(i.rotulo ?? i.cod_metrica)}</td><td>${escapar(i.ano)}</td>
            <td class="valor" title="${atributo(v.title)}">${escapar(v.texto)}</td></tr>`;
        }).join(''))}` : ''}`;

  dialogo.setAttribute('aria-labelledby', 'titulo-detalhe');
}

/** A linha de selos no alto da ficha.
 *
 *  O que o painel sabe afirmar sobre este ente, em três palavras, antes de
 *  qualquer tabela. Só entra selo cujo dado existe: ausência não vira selo
 *  neutro, vira silêncio. */
function resumoDeRisco(r) {
  const selos = [];

  if (r.acima_do_limite === true) {
    selos.push('<span class="selo risco">Pessoal acima do limite da LRF</span>');
  } else if (r.acima_do_limite === false) {
    selos.push('<span class="selo calmo">Pessoal dentro do limite da LRF</span>');
  }

  const dep = aNumero(r.dependencia_transferencia);
  if (Number.isFinite(dep) && dep >= 80) {
    selos.push(`<span class="selo atento">${porcento.format(dep)}% de dependência de transferências</span>`);
  }

  const receita = aNumero(r.receita_total);
  const despesa = aNumero(r.despesa_total);
  if (Number.isFinite(receita) && Number.isFinite(despesa) && despesa > receita) {
    selos.push('<span class="selo atento">Empenhou mais do que arrecadou</span>');
  }

  return selos.length
    ? `<p style="display:flex;gap:8px;flex-wrap:wrap;margin:16px 0">${selos.join('')}</p>`
    : '';
}

/** O percentual da folha com o veredito ao lado, em três estados.
 *
 *  Três, não dois: acima do limite, acima do prudencial (que é aviso, não
 *  infração) e dentro. O prudencial estava sendo calculado pela view e
 *  jogado fora pela tela. */
function seloLimite(x) {
  const pct = formatar(aNumero(x.percentual_pessoal), 'percentual_pessoal');
  if (x.acima_do_limite === true) return `<span class="selo risco">${pct}</span>`;
  if (x.acima_do_prudencial === true) return `<span class="selo atento">${pct}</span>`;
  if (x.acima_do_limite === false) return `<span class="selo calmo">${pct}</span>`;
  return pct;
}

/** Duas medidas do mesmo número por caminhos diferentes.
 *
 *  É a checagem que teria pego a despesa inflada em 5× no dia em que ela
 *  apareceu — e por isso ela fica na TELA, não só no teste. */
function conferencia(oQue, c) {
  if (!c) return '';
  const somado = aNumero(c.somado);
  const declarado = aNumero(c.declarado);
  if (!Number.isFinite(somado) || !Number.isFinite(declarado)) return '';

  const dif = Math.abs(somado - declarado);
  const bate = dif <= Math.max(1, Math.abs(declarado) * 0.001);
  return `<p class="rodape-mapa${bate ? '' : ' alerta'}">Conferência: ${escapar(oQue)}
    dá ${formatar(somado, 'despesa_total')} e o ente declarou
    ${formatar(declarado, 'despesa_total')} —
    ${bate ? 'batem.' : `<strong>divergem em ${formatar(dif, 'despesa_total')}</strong>.`}</p>`;
}


export { abrirFicha, resumoDeRisco, seloLimite, conferencia, tabela, cartaoNumero };
