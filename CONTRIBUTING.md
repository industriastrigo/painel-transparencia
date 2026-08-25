# Como contribuir

O projeto existe para dar clareza sobre gastos públicos. A regra que organiza
tudo o mais é simples: **número que não veio da fonte não aparece na tela.**

## Antes de mexer

```bash
python -m pytest                     # 207 testes
node --test testes/teste_mapa.mjs    # 10 testes
```

E, para provar que os testes não dependem da ordem em que rodam:

```bash
python -m pytest testes/teste_cli.py testes/teste_de_para.py testes/teste_api.py
```

Se algum falhar só nessa ordem, é acoplamento entre testes — não um defeito do
código.

## Leia isto antes de escrever um coletor

`docs/08-armadilhas.md` lista cada erro já cometido aqui, com causa e conserto.
Não é histórico: é a lista das formas conhecidas de este projeto produzir um
número errado com cara de certo. Vários custaram dias.

Os três padrões que mais se repetem:

1. **Adivinhar nome de coluna.** A fonte muda o nome e o campo vira vazio, sem
   erro nenhum. Detecte, e quando não reconhecer, registre no log a lista real
   de colunas do arquivo.
2. **Somar sem olhar o nível.** Demonstrativo contábil tem hierarquia; somar
   pai e filho inflou a despesa dos estados em 5×.
3. **Testar a propriedade errada.** Um teste de concorrência que procura
   exceções passa enquanto as respostas se trocam entre si. Teste o resultado.

## Ao acrescentar uma fonte

1. Declare a tabela em `src/nucleo/esquema.py` — chave de negócio, partições e
   o contrato de colunas
2. Registre a URL e o freio em `src/nucleo/config.py`
3. Escreva o coletor em `src/coletores/`, no formato de `docs/04-coletores.md`
4. Registre em `src/coletores/orquestrador.py`
5. Escreva o teste **antes** de dar por pronto, e faça-o passar pelo mesmo
   caminho que o código usa em produção

## Estilo

Código e comentários em português. Comentário explica **por que**, não o que —
o que já está no código. Quando um trecho existe por causa de um defeito real,
o comentário conta qual foi: é o que impede alguém (inclusive eu) de
"simplificar" de volta para o bug.
