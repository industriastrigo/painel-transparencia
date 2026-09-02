/* Utilitários de interface (DOM, placeholders e modais). */
import { escapar } from './formatadores.js';

export const $ = (sel, contexto = document) => contexto.querySelector(sel);
export const $$ = (sel, contexto = document) => [...contexto.querySelectorAll(sel)];

export const esqueleto = (linhas = 4, altura = 18) => `
  <div class="esqueleto" aria-busy="true" aria-label="Carregando">
    ${Array.from({ length: linhas }, () => `<div style="height:${altura}px"></div>`).join('')}
  </div>`;

export const falha = (mensagem, { tentar = null } = {}) => `
  <div class="falha" role="alert">
    <p>Não foi possível carregar: ${escapar(mensagem)}</p>
    ${tentar ? `<button class="secundario tentar" data-acao="${escapar(tentar)}">Tentar de novo</button>` : ''}
  </div>`;

export const falhaEmLinha = (colunas, oQue, erro = null) => {
  const cols = typeof colunas === 'number' ? colunas : 4;
  const msg = typeof colunas === 'string' ? colunas : (oQue || 'Erro ao carregar dados.');
  return `<tr><td colspan="${cols}">${falha(msg, erro ? { tentar: null } : {})}</td></tr>`;
};

export function abrirDialogo(dialogo, rotuloProvisorio) {
  if (!dialogo) return;
  dialogo.setAttribute('aria-label', rotuloProvisorio);
  dialogo.showModal();
}
