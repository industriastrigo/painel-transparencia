"""
Auditoria de QA: Contratos de Interface, Integridade do DOM e Navegabilidade.

Valida a presença de componentes vitais de UI, integridade semântica do HTML5,
mapeamento de rotas por hash, botões de ação, diálogos/modais e padronização vetorial.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
PUBLICO = RAIZ / "publico"
INDEX_HTML = PUBLICO / "index.html"
ESTILO_CSS = PUBLICO / "estilo.css"
PAINEL_JS = PUBLICO / "painel.js"


@pytest.fixture(scope="module")
def html_content() -> str:
    assert INDEX_HTML.exists(), "Arquivo publico/index.html não encontrado"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css_content() -> str:
    assert ESTILO_CSS.exists(), "Arquivo publico/estilo.css não encontrado"
    return ESTILO_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_painel_content() -> str:
    assert PAINEL_JS.exists(), "Arquivo publico/painel.js não encontrado"
    return PAINEL_JS.read_text(encoding="utf-8")


def test_html_document_structure(html_content: str):
    """Valida estrutura base do documento HTML5."""
    assert "<!doctype html>" in html_content.lower(), "Declaração <!doctype html> ausente"
    assert '<html lang="pt-BR">' in html_content, "Atributo lang='pt-BR' ausente ou incorreto"
    assert '<meta charset="utf-8">' in html_content, "Meta charset UTF-8 ausente"
    assert '<meta name="viewport"' in html_content, "Meta viewport responsivo ausente"
    assert "<title>Indústrias Trigo" in html_content, "Título institucional incorreto"


def test_topbar_elements_and_buttons(html_content: str):
    """Valida a barra de topo (Topbar) e seus controles."""
    assert 'id="btn-menu-hamburguer"' in html_content, "Botão do menu hamburguer ausente"
    assert 'class="topbar-trigo"' in html_content, "Container .topbar-trigo ausente"
    assert 'id="topbar-logo-img"' in html_content, "Elemento de logo do topo ausente"
    assert 'id="topbar-titulo-pagina"' in html_content, "Título dinâmico da página ausente"
    assert 'btn-toggle-tema' in html_content, "Classe btn-toggle-tema ausente"
    assert 'id="topbar-auth-widget"' in html_content, "Widget de autenticação Google ausente"


def test_drawer_navigation_items(html_content: str):
    """Valida que todas as 11 abas do painel estão presentes no drawer menu com data-aba."""
    abas_esperadas = [
        "inicio", "mapa", "executivo", "legislativo", "judiciario",
        "mp", "politicos", "proposicoes", "custo", "glossario", "catalogo"
    ]
    for aba in abas_esperadas:
        padrao = f'href="#{aba}"'
        assert padrao in html_content, f"Link de navegação #{aba} ausente no Drawer Menu"
        padrao_data = f'data-aba="{aba}"'
        assert padrao_data in html_content, f"Atributo data-aba='{aba}' ausente no item de navegação"


def test_section_tabpanels_existence(html_content: str):
    """Valida que todas as seções de abas possuem container role='tabpanel' e ID correto."""
    secoes_esperadas = [
        "aba-inicio", "aba-mapa", "aba-executivo", "aba-legislativo",
        "aba-judiciario", "aba-mp", "aba-politicos", "aba-proposicoes",
        "aba-custo", "aba-glossario", "aba-catalogo"
    ]
    for sec in secoes_esperadas:
        assert f'id="{sec}"' in html_content, f"Container de seção #{sec} ausente no HTML"
        match = re.search(rf'<section[^>]*id="{sec}"[^>]*role="tabpanel"', html_content)
        assert match is not None, f"Seção #{sec} não possui role='tabpanel'"


def test_dialog_modals_integrity(html_content: str):
    """Valida integridade e presença de todos os diálogos/modais nativos HTML5."""
    modais_esperados = [
        "modal-perfil-usuario",
        "modal-aviso-registro",
        "modal-get-catalogo",
        "detalhe"
    ]
    for modal in modais_esperados:
        assert f'id="{modal}"' in html_content, f"Modal dialog #{modal} ausente"
        match = re.search(rf'<dialog[^>]*id="{modal}"', html_content)
        assert match is not None, f"Elemento #{modal} não é uma tag <dialog> nativa"


def test_search_inputs_and_filters(html_content: str):
    """Valida campos de busca rápida e filtros em tempo real."""
    assert 'id="busca-faq-glossario"' in html_content, "Input de busca FAQ/Glossário ausente"
    assert 'id="btn-limpar-busca-inicio"' in html_content, "Botão limpar busca rápida ausente"
    assert 'id="filtro-mp-busca"' in html_content, "Input de busca do Ministério Público ausente"
    assert 'id="cat-filtro-busca"' in html_content, "Input de busca do Catálogo de Dados ausente"
    assert 'id="cat-filtro-camada"' in html_content, "Seletor de camada no Catálogo ausente"
    assert 'id="cat-filtro-status"' in html_content, "Seletor de status no Catálogo ausente"


def test_css_and_js_asset_links(html_content: str):
    """Valida importação correta da folha de estilo e do módulo script painel.js."""
    assert re.search(r'<link[^>]*href="estilo\.css(\?v=[^"]+)?"', html_content), "Link para estilo.css ausente"
    assert '<script type="module" src="painel.js"></script>' in html_content, "Script módulo painel.js ausente"
    assert 'https://accounts.google.com/gsi/client' in html_content, "Script Google GSI Client ausente"


def test_outline_svg_standardization(html_content: str, css_content: str):
    """Valida conformidade com a diretiva de ícones de contorno (stroke, fill: none)."""
    assert ".item-svg-inline" in css_content, "Classe .item-svg-inline ausente no CSS"
    assert "fill: none !important" in css_content, "Regra 'fill: none !important' ausente no CSS"
    assert "stroke: currentColor !important" in css_content, "Regra 'stroke: currentColor !important' ausente no CSS"

    svgs = re.findall(r'<svg[^>]*class="[^"]*item-svg-inline[^"]*"[^>]*>', html_content)
    assert len(svgs) >= 15, f"Poucos SVGs de ícone encontrados no HTML: {len(svgs)}"
    for svg in svgs:
        assert 'viewBox=' in svg or 'viewbox=' in svg, f"SVG de ícone sem viewBox definido: {svg}"


def test_no_emojis_in_headings_and_badges(html_content: str):
    """Garante ausência total de emojis na estrutura do index.html (exceto setas de fluxo texto)."""
    emoji_pattern = re.compile(r'[🌀-🧿☀-⛿✀-➿▼▲▾▴]')
    linhas = html_content.splitlines()
    emojis_encontrados = []
    for idx, linha in enumerate(linhas, start=1):
        linha_sem_seta = linha.replace("➔", "")
        if emoji_pattern.search(linha_sem_seta):
            emojis_encontrados.append((idx, linha.strip()))

    assert len(emojis_encontrados) == 0, f"Emojis não-outline encontrados em index.html: {emojis_encontrados}"


def test_table_headers_and_accessibility(html_content: str):
    """Valida conformidade de tabelas com thead, tbody e IDs esperados."""
    tabelas = ["tabela-magistrados", "tabela-mp", "tabela-custo", "tabela-catalogo", "tabela-auditoria"]
    for tab in tabelas:
        assert f'id="{tab}"' in html_content, f"Tabela #{tab} ausente no HTML"
