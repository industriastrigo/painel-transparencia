/* Seção Inicial / Apresentação do Projeto & FAQ Interativo - Indústrias Trigo */

import { $, $$ } from '../nucleo/ui.js';
import { trocarAba } from '../nucleo/abas.js';

export function carregarInicio() {
  configurarEventosInicio();
}

export function configurarEventosInicio() {
  // 1. Busca Estilo Google em Tempo Real
  const inputBusca = $('#busca-faq-glossario');
  const btnLimpar = $('#btn-limpar-busca-inicio');

  inputBusca?.addEventListener('input', (e) => {
    const termo = e.target.value.toLowerCase().trim();
    if (btnLimpar) btnLimpar.style.display = termo ? 'flex' : 'none';
    filtrarConteudoInicio(termo);
  });

  btnLimpar?.addEventListener('click', () => {
    if (inputBusca) {
      inputBusca.value = '';
      inputBusca.focus();
      btnLimpar.style.display = 'none';
      filtrarConteudoInicio('');
    }
  });

  // 2. Acordeão de FAQ (Abrir/Fechar)
  $$('.faq-item').forEach((item) => {
    const pergunta = item.querySelector('.faq-pergunta');
    pergunta?.addEventListener('click', () => {
      const estaAberto = item.classList.contains('aberto');
      // Fecha outros itens se quiser comportamento de sanfona única
      $$('.faq-item').forEach((out) => {
        if (out !== item) out.classList.remove('aberto');
      });
      if (!estaAberto) {
        item.classList.add('aberto');
      } else {
        item.classList.remove('aberto');
      }
    });
  });

  // 3. Botões de Navegação Rápida
  $$('[data-ir-aba]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const aba = btn.dataset.irAba;
      if (aba) trocarAba(aba, { focar: true });
    });
  });

  // 4. Botão de Login CTA
  $('#btn-cta-entrar')?.addEventListener('click', () => {
    const btnLogin = document.getElementById('btn-login-google') || document.getElementById('btn-abrir-perfil');
    if (btnLogin) btnLogin.click();
  });
}

function filtrarConteudoInicio(termo) {
  let encontradosFaq = 0;
  let encontradosGlossario = 0;

  // Filtra itens do FAQ
  $$('.faq-item').forEach((item) => {
    const texto = item.textContent.toLowerCase();
    const bateu = !termo || texto.includes(termo);
    item.style.display = bateu ? 'block' : 'none';
    if (bateu) encontradosFaq++;
    // Se digitou busca e bateu, já abre a resposta
    if (termo && bateu) item.classList.add('aberto');
    else if (!termo) item.classList.remove('aberto');
  });

  // Filtra itens do Glossário
  $$('.glossario-card-inicio').forEach((card) => {
    const texto = card.textContent.toLowerCase();
    const bateu = !termo || texto.includes(termo);
    card.style.display = bateu ? 'block' : 'none';
    if (bateu) encontradosGlossario++;
  });

  // Mensagem de nada encontrado
  const avisoVazio = $('#aviso-busca-sem-resultado');
  if (avisoVazio) {
    const total = encontradosFaq + encontradosGlossario;
    avisoVazio.style.display = total === 0 ? 'block' : 'none';
    if (total === 0) {
      avisoVazio.innerHTML = `Nenhum resultado encontrado para "<strong>${termo}</strong>". Tente buscar por termos como <em>empenho</em>, <em>teto</em>, <em>login</em>, <em>gastos</em> ou <em>município</em>.`;
    }
  }
}
