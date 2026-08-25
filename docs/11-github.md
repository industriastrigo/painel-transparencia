# 11 — Publicar e manter no GitHub

## Antes de tudo: o que NÃO vai para o repositório

Três coisas ficam de fora, e vale saber por quê antes de publicar:

| Fica fora | Motivo |
|---|---|
| `.env` | guarda a chave da CGU. Chave publicada em repositório é chave comprometida — inclusive se você apagar depois, porque o histórico do git guarda tudo. |
| `dados/` | de 2 a 5 GB, e **reprodutível**: qualquer pessoa refaz rodando os coletores. Repositório é para código, não para acervo. |
| `logs/` | ruído local, muda a cada execução. |

`referencias/subsidios.csv` **vai** — é dado curado, parte do projeto, e
precisa estar visível para poder ser conferido.

Há uma trava: `scripts/conferir-segredos.bat` roda antes de cada envio e
recusa o commit se `.env` ou `dados/` estiverem versionados. O CI repete a
verificação a cada push, então nem um commit feito por outro caminho passa.

---

## Passo 1 — criar a conta e a organização

1. Acesse **github.com** → *Sign up*
2. Crie a conta pessoal (ela é sempre necessária; a organização vem depois)
3. Confirme o e-mail
4. Para ter o nome **Indústrias Trigo** como dono do projeto:
   foto do perfil → *Your organizations* → *New organization* → plano **Free**

   O GitHub não aceita espaço nem acento no identificador da organização, então
   o endereço fica `industrias-trigo` (ou `industriastrigo`) e o nome de
   exibição, esse sim livre, fica **Indústrias Trigo**. O repositório vira
   `github.com/industrias-trigo/painel-transparencia`.

> A organização é opcional. Publicar na conta pessoal funciona igual, e dá
> para transferir o repositório para a organização depois sem perder nada.

---

## Passo 2 — criar o repositório vazio

Na organização (ou na sua conta): **New repository**

| Campo | Valor |
|---|---|
| Repository name | `painel-transparencia` |
| Description | Painel de dados públicos: quem governa, quanto arrecada, quanto gasta e quem votou o quê |
| Visibility | **Public** — é um projeto de transparência; código fechado contradiz o propósito |
| Add a README | **não marque** |
| Add .gitignore | **não marque** |
| Choose a license | **não marque** |

As três últimas ficam desmarcadas porque o projeto já traz README, `.gitignore`
e LICENSE prontos — marcar criaria conflito no primeiro envio.

---

## Passo 3 — autenticar a máquina

O jeito mais simples no Windows, e você já tem o atalho na Área de Trabalho:

1. Abra o **GitHub Desktop**
2. *File* → *Options* → *Accounts* → *Sign in*
3. Entre com a conta das Indústrias Trigo

Isso guarda a credencial no Gerenciador de Credenciais do Windows, e o `git`
da linha de comando passa a usá-la sozinho. Não é preciso criar token nem
digitar senha depois.

---

## Passo 4 — primeira publicação

Dê dois cliques em **`CONFIGURAR GITHUB.bat`**, na pasta do projeto.

Ele pergunta o usuário/organização e o nome do repositório, e então:

1. cria o repositório local (`git init`)
2. confere a identidade (nome e e-mail)
3. **roda a trava de segredos**
4. faz o primeiro commit
5. envia para o GitHub

Se o envio falhar, quase sempre é autenticação — volte ao passo 3.

---

## Passo 5 — o dia a dia

A cada alteração que você quiser publicar, dois cliques em
**`SALVAR NO GITHUB.bat`**.

Ele mostra o que mudou, pede uma descrição (ou usa data e hora se você só
apertar Enter), comita e envia.

### Sobre publicar automaticamente a cada alteração

Dá para fazer, e eu **não recomendo** como padrão. Três razões:

- **Histórico ilegível.** Um commit por salvamento produz centenas de
  "Atualização de 25/08 14:32" e nenhum deles conta o que mudou. Quando você
  precisar achar quando um número quebrou, o histórico não ajuda.
- **Estado quebrado publicado.** Salvar no meio de uma edição publica código
  que não roda. O CI acusa falha e o selo do repositório fica vermelho sem que
  nada esteja de fato errado com o projeto.
- **Risco de segredo.** Publicação automática dispara antes de você conferir.
  A trava existe justamente porque o automático não pensa.

O meio-termo que funciona: **`AGENDAR ENVIO.bat`** cria uma tarefa diária às
19h que envia o que houver, com a mensagem do dia. Você trabalha o dia
inteiro, e à noite o que ficou pronto sobe. É automático o suficiente para não
depender de você lembrar, e espaçado o bastante para o histórico continuar
legível.

---

## O que roda sozinho no GitHub

`.github/workflows/testes.yml` executa a cada push:

| Job | O que confere |
|---|---|
| `python` | os 216 testes, e depois roda os arquivos **fora de ordem** para provar que não há acoplamento entre eles |
| `javascript` | os 14 testes da projeção do mapa e da escala de cor |
| `segredos` | que `.env` e `dados/` não foram versionados e que não há chave de API no código |

O selo verde na página do repositório é a primeira evidência, para quem chega
de fora, de que os números da tela passam por verificação.

---

## Situações comuns

**"Updates were rejected because the remote contains work that you do not have
localmente"** — alguém (ou você, de outra máquina) alterou o repositório.
Resolva com:

```bash
git pull --rebase
```

e rode `SALVAR NO GITHUB.bat` de novo.

**"Author identity unknown" / "empty ident name (for <>) not allowed"** — o git
não sabe quem assina o commit. O `CONFIGURAR GITHUB.bat` pergunta e grava
sozinho; se ainda assim aparecer, grave na mão, dentro da pasta do projeto:

```bash
git config --global user.email "voce@exemplo.com"
git config --global user.name "Seu Nome"
```

**"src refspec main does not match any"** — não é problema de rede nem de
senha: **não existe commit nenhum** para enviar. Sempre vem depois de um commit
que falhou (quase sempre o de identidade, acima). Resolva a causa e rode o
`.bat` de novo.

**Publiquei o `.env` por engano.** Trocar a chave é obrigatório — apagar o
arquivo não basta, porque o histórico guarda. Gere uma nova em
portaldatransparencia.gov.br e cole no painel; a antiga fica inutilizável.
Depois, para limpar o histórico, use `git filter-repo` ou o BFG.

**Quero mover para a organização depois.** Settings → General → Danger Zone →
Transfer ownership. Os links antigos continuam redirecionando.
