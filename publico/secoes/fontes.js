/* Lista de fontes e painel de situação das APIs oficiais. */
import { $, $$ } from '../nucleo/ui.js';
import { escapar, txt, contagem, formatarData, SELO_SITUACAO } from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import { falha, falhaEmLinha } from '../nucleo/ui.js';

const FALHOU = Symbol('falhou');

/* ---------------------------------------------------------------- fontes */

async function carregarSituacao() {
  const saude = await buscar('/api/saude').catch(() => FALHOU);
  const alvo = $('#situacao-fontes');
  if (!alvo) return;
  if (saude === FALHOU) {
    alvo.innerHTML = falha('Não deu para ler a situação das fontes.');
    return;
  }
  if (!saude || !saude.fontes?.length) {
    alvo.innerHTML = '<p class="vazio">Nenhuma coleta registrada. '
      + 'Rode <code>python -m src.scripts.coletar --tudo</code>.</p>';
    return;
  }
  alvo.innerHTML = `<table><thead><tr>
      <th>Fonte</th><th>Recurso</th><th>Linhas</th><th>Situação</th><th>Lido em</th>
    </tr></thead><tbody>
    ${saude.fontes.map((f) => `<tr>
      <td>${txt(f.fonte)}</td><td>${txt(f.recurso)}</td>
      <td class="valor">${contagem(f.linhas)}</td>
      <td><span class="selo ${SELO_SITUACAO[f.situacao] ?? 'neutro'}"
          >${txt(f.situacao)}</span></td>
      <td>${formatarData(f.lido_em, true)}</td></tr>`).join('')}
    </tbody></table>`;
}

export { carregarSituacao };
