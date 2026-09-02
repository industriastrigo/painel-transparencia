"""Normalização de nomes e geração de identificadores internos padronizados.

Regras de normalização de nomes próprios (PT-BR):
1. Conectivos e preposições em minúsculas (de, da, do, das, dos, e, em, para, com, por, del, d').
2. Numerais romanos em maiúsculas (I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII).
3. Sufixos geracionais capitalizados (Filho, Neto, Sobrinho, Júnior, Junior).
4. Tratamento de apóstrofos (D'Ávila, Sant'Anna).
5. Preservação integral de acentuação gráfica e remoção de espaços excessivos.

Regras de códigos internos:
1. Cargos: CAR_{PODER}_{ESFERA}_{CARGO}_{COMPLEMENTO}
2. Políticos: POL_{SLUG_NOME}
3. Ministros: CAR_MIN_EST_{PASTA} / MAG_STF_{SLUG_NOME}
4. Magistrados: MAG_{TRIBUNAL}_{SLUG_NOME}
"""

from __future__ import annotations

import re
import unicodedata

PREPOSICOES = frozenset({
    "de", "da", "do", "das", "dos", "e", "em", "para", "com", "por", "del", "d'"
})

ROMANOS = frozenset({
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"
})

SIGLAS_CONHECIDAS = frozenset({
    "stf", "stj", "tse", "tst", "stm", "cnj", "tjsp", "tjrj", "tjmg", "tjrs", "tjpr", "tjba",
    "trf1", "trf2", "trf3", "trf4", "trf5", "trf6", "trt", "tre", "mpf", "mpsp", "cgu", "tcu",
    "ibge", "bcb", "bndes", "inss", "fgts", "sus", "mec", "mme", "mds", "pcdp", "cpgf", "pncp",
    "ltda", "sa", "s/a", "s.a.", "s.a", "eireli", "me", "epp"
})


def remover_acentos(texto: str) -> str:
    """Remove diacríticos/acentos mantendo os caracteres base ASCII."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def gerar_slug_codigo(texto: str | None) -> str:
    """Gera um slug em caixa alta sem acentos para identificadores internos.

    Exemplo: "Luiz Inácio Lula da Silva" -> "LUIZ_INACIO_LULA_DA_SILVA"
    """
    if not texto:
        return ""
    limpo = remover_acentos(str(texto).strip().upper())
    slug = re.sub(r"[^A-Z0-9]+", "_", limpo).strip("_")
    return slug


def normalizar_nome_proprio(texto: str | None) -> str:
    """Formata um nome próprio em Title Case elegante segundo normas do PT-BR.

    Exemplos:
        "LUIZ INACIO LULA DA SILVA" -> "Luiz Inacio Lula da Silva"
        "ALEXANDRE DE MORAES" -> "Alexandre de Moraes"
        "DOM PEDRO II" -> "Dom Pedro II"
        "MANUELA D'AVILA" -> "Manuela D'Avila"
        "ANTONIO CARLOS MAGALHAES NETO" -> "Antonio Carlos Magalhaes Neto"
    """
    if not texto or not isinstance(texto, str):
        return ""

    limpo = " ".join(texto.strip().split())
    if not limpo:
        return ""

    palavras = limpo.split(" ")
    resultado: list[str] = []

    for i, p in enumerate(palavras):
        p_low = p.lower()

        # Numerais romanos (ex: Pedro II)
        if p_low in ROMANOS:
            resultado.append(p_low.upper())
            continue

        # Siglas conhecidas (ex: STF, LTDA, S.A.)
        if p_low in SIGLAS_CONHECIDAS:
            resultado.append(p_low.upper())
            continue

        # Preposições / conectivos (minúsculas se não for a primeira palavra)
        if i > 0 and p_low in PREPOSICOES:
            resultado.append(p_low)
            continue

        # Apóstrofo (ex: D'Ávila, Sant'Anna)
        if "'" in p:
            partes = p.split("'")
            resultado.append("'".join(
                pt.capitalize() if j == 0 or pt.lower() not in PREPOSICOES else pt.lower()
                for j, pt in enumerate(partes)
            ))
            continue

        # Palavra padrão: primeira letra maiúscula e o restante minúsculo
        resultado.append(p.capitalize())

    return " ".join(resultado)


def gerar_cod_cargo_interno(
    cargo: str | None,
    poder: str = "executivo",
    esfera: str = "federal",
    uf: str | None = None,
    cod_ibge: str | None = None
) -> str:
    """Gera o código interno padronizado para um cargo público ou eletivo.

    Exemplos:
        ("presidente", "executivo", "federal") -> "CAR_EXEC_FED_PRESIDENTE"
        ("governador", "executivo", "estadual", uf="SP") -> "CAR_EXEC_EST_GOVERNADOR_SP"
        ("prefeito", "executivo", "municipal", cod_ibge="3550308") -> "CAR_EXEC_MUN_PREFEITO_3550308"
        ("ministro_stf", "judiciario", "federal") -> "CAR_JUD_FED_MINISTRO_STF"
    """
    cargo_limpo = gerar_slug_codigo(cargo or "GERAL")
    poder_map = {
        "executivo": "EXEC", "legislativo": "LEG", "judiciario": "JUD",
        "ministerio_publico": "MP", "tribunal_contas": "TC"
    }
    esfera_map = {
        "federal": "FED", "estadual": "EST", "municipal": "MUN", "geral": "GERAL"
    }

    sigla_poder = poder_map.get(str(poder).lower(), "GERAL")
    sigla_esfera = esfera_map.get(str(esfera).lower(), "FED")

    partes = ["CAR", sigla_poder, sigla_esfera, cargo_limpo]

    if sigla_esfera == "EST" and uf:
        partes.append(uf.upper())
    elif sigla_esfera == "MUN" and cod_ibge:
        partes.append(str(cod_ibge))

    return "_".join(partes)


def gerar_cod_politico_interno(
    nome: str | None,
    cpf: str | None = None,
    id_origem: str | None = None
) -> str:
    """Gera o código interno padronizado para um político ou governante.

    Exemplos:
        "LUIZ INACIO LULA DA SILVA" -> "POL_LUIZ_INACIO_LULA_DA_SILVA"
        "JAIR MESSIAS BOLSONARO" -> "POL_JAIR_MESSIAS_BOLSONARO"
        "TARCISIO GOMES DE FREITAS" -> "POL_TARCISIO_GOMES_DE_FREITAS"
    """
    slug_nome = gerar_slug_codigo(nome or "DESCONHECIDO")
    return f"POL_{slug_nome}"


def gerar_cod_magistrado_interno(
    nome: str | None,
    tribunal: str | None = None,
    cargo: str | None = None
) -> str:
    """Gera o código interno padronizado para um magistrado ou ministro de tribunal.

    Exemplos:
        ("Alexandre de Moraes", "STF") -> "MAG_STF_ALEXANDRE_DE_MORAES"
        ("Luís Roberto Barroso", "STF") -> "MAG_STF_LUIS_ROBERTO_BARROSO"
    """
    slug_nome = gerar_slug_codigo(nome or "DESCONHECIDO")
    slug_trib = gerar_slug_codigo(tribunal or "JUD")
    return f"MAG_{slug_trib}_{slug_nome}"


def gerar_cod_ministro_estado_interno(
    pasta_ou_orgao: str | None,
    nome: str | None = None
) -> str:
    """Gera o código interno padronizado para um ministro de Estado.

    Exemplos:
        ("Ministério da Fazenda", "Fernando Haddad") -> "MIN_EST_MINISTERIO_DA_FAZENDA_FERNANDO_HADDAD"
    """
    slug_pasta = gerar_slug_codigo(pasta_ou_orgao or "ESTADO")
    if nome:
        slug_nome = gerar_slug_codigo(nome)
        return f"MIN_EST_{slug_pasta}_{slug_nome}"
    return f"MIN_EST_{slug_pasta}"


def gerar_cod_membro_mp_interno(
    nome: str | None,
    ramo: str | None = None,
    cargo: str | None = None,
    uf: str | None = None
) -> str:
    """Gera o código interno padronizado para um membro do Ministério Público.

    Exemplos:
        ("Paulo Gonet Branco", "MPF") -> "MP_MPF_PAULO_GONET_BRANCO"
        ("Mário Luiz Sarrubbo", "MPSP", uf="SP") -> "MP_MPSP_MARIO_LUIZ_SARRUBBO"
    """
    slug_nome = gerar_slug_codigo(nome or "DESCONHECIDO")
    slug_ramo = gerar_slug_codigo(ramo or (f"MPE_{uf}" if uf else "MP"))
    return f"MP_{slug_ramo}_{slug_nome}"

