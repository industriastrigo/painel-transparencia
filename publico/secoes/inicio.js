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

function normalizarTexto(s) {
  return (s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function gerarVariantesToken(palavra) {
  const norm = normalizarTexto(palavra);
  if (!norm) return [];
  const variantes = new Set([norm]);

  // Regra 1: Plurais em -ões / -ãos / -ães <-> -ão (cartão/cartões, votação/votações)
  if (norm.endsWith('ao')) {
    variantes.add(norm.slice(0, -2) + 'oes');
    variantes.add(norm.slice(0, -2) + 'aos');
    variantes.add(norm.slice(0, -2) + 'aes');
  } else if (norm.endsWith('oes') || norm.endsWith('aos') || norm.endsWith('aes')) {
    variantes.add(norm.slice(0, -3) + 'ao');
  }

  // Regra 2: Plurais em -ns <-> -m (viagens <-> viagem, passagens <-> passagem)
  if (norm.endsWith('ns')) {
    variantes.add(norm.slice(0, -2) + 'm');
  } else if (norm.endsWith('m')) {
    variantes.add(norm.slice(0, -1) + 'ns');
  }

  // Regra 3: Plurais em -ores / -eres / -ires <-> -or / -er / -ir (servidores <-> servidor)
  if (norm.endsWith('ores')) {
    variantes.add(norm.slice(0, -2));
  } else if (norm.endsWith('or')) {
    variantes.add(norm + 'es');
  }

  // Regra 4: Plurais em -ais / -eis / -ois <-> -al / -el / -ol (fiscais <-> fiscal)
  if (norm.endsWith('ais')) {
    variantes.add(norm.slice(0, -2) + 'l');
  } else if (norm.endsWith('al')) {
    variantes.add(norm.slice(0, -1) + 'is');
  }

  // Regra 5: Plural regular -s (gastos <-> gasto, emendas <-> emenda, diárias <-> diária)
  if (norm.endsWith('s') && norm.length > 3) {
    variantes.add(norm.slice(0, -1));
  } else if (norm.length > 2) {
    variantes.add(norm + 's');
  }

  return Array.from(variantes);
}

function textoBateComBusca(texto, termoBusca) {
  const termoNorm = normalizarTexto(termoBusca);
  if (!termoNorm) return true;

  const textoNorm = normalizarTexto(texto);
  if (textoNorm.includes(termoNorm)) return true;

  const tokens = termoNorm.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true;

  return tokens.every((token) => {
    const variantes = gerarVariantesToken(token);
    return variantes.some((v) => textoNorm.includes(v));
  });
}

function filtrarConteudoInicio(termo) {
  let encontradosFaq = 0;
  let encontradosGlossario = 0;
  const termoNorm = normalizarTexto(termo);

  // Filtra itens do FAQ
  $$('.faq-item').forEach((item) => {
    const bateu = textoBateComBusca(item.textContent, termo);
    item.style.display = bateu ? 'block' : 'none';
    if (bateu) encontradosFaq++;
    // Se digitou busca e bateu, já abre a resposta
    if (termoNorm && bateu) item.classList.add('aberto');
    else if (!termoNorm) item.classList.remove('aberto');
  });

  // Filtra itens do Glossário
  $$('.glossario-card-inicio').forEach((card) => {
    const bateu = textoBateComBusca(card.textContent, termo);
    card.style.display = bateu ? 'block' : 'none';
    if (bateu) encontradosGlossario++;
  });

  // Mensagem de nada encontrado (Protegida contra XSS)
  const avisoVazio = $('#aviso-busca-sem-resultado');
  if (avisoVazio) {
    const total = encontradosFaq + encontradosGlossario;
    avisoVazio.style.display = total === 0 ? 'block' : 'none';
    if (total === 0) {
      avisoVazio.textContent = '';
      const textoPrefix = document.createTextNode('Nenhum resultado encontrado para "');
      const strongTermo = document.createElement('strong');
      strongTermo.textContent = termo;
      const textoSufix = document.createTextNode('". Tente buscar por termos como empenho, teto, despesas, gastos ou município.');
      avisoVazio.appendChild(textoPrefix);
      avisoVazio.appendChild(strongTermo);
      avisoVazio.appendChild(textoSufix);
    }
  }
}
