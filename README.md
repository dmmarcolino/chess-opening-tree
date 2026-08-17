# Árvore de aberturas

Site pessoal que importa suas partidas do Lichess e do Chess.com (de
quantos nicks você quiser em cada site), monta uma árvore de todos os
lances jogados (separada por cor, combinando todos os nicks) e mostra o
aproveitamento (vitória/empate/derrota) em cada nó — para identificar em
quais aberturas você vai bem e em quais precisa estudar mais.

Os nicks são cadastrados direto pelo site (botão ⚙ no topo). A
importação roda automaticamente uma vez por semana, e também pode ser
disparada na hora pelo botão **↻ Atualizar agora**.

A navegação é posição a posição, como um explorador de aberturas
(Lichess Explorer, ChessBase): um tabuleiro mostra onde você está, um
breadcrumb no topo deixa voltar pra qualquer ponto do caminho com um
clique, e a lista de lances mostra só as opções *daquela posição
específica* — os lances irmãos (ex.: outras respostas de brancas no
lance 1) somem da tela depois que você escolhe um caminho, exatamente
pra não poluir a navegação. O tabuleiro é desenhado no navegador
reaplicando a sequência de lances com a
[chess.js](https://github.com/jhlywa/chess.js) (carregada via CDN,
`cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.js`) — não precisa
de nenhum dado extra no JSON pra isso, só a lista de lances que já
existia.

As peças são o conjunto **Merida**, de Armando Hernandez Marroquin
(licença GPLv2+), embutidas diretamente no `index.html` como símbolos
SVG — baixadas do repositório público do [lichess-org/lila](https://github.com/lichess-org/lila/tree/master/public/piece/merida)
(veja a licença completa em
[COPYING.md](https://github.com/lichess-org/lila/blob/master/COPYING.md)).
Por serem SVG embutido, não dependem de nenhuma fonte instalada no
computador de quem acessa — renderizam igual em qualquer navegador.

## Estrutura

```
.
├── index.html                    # site (front-end estático, sem build step)
├── apps-script/Code.gs           # backend leve (Google Apps Script): guarda os nicks e dispara o workflow
├── data/
│   ├── raw/                      # PGNs brutos baixados (um arquivo por nick)
│   ├── config.json               # ultima lista de nicks lida do Apps Script
│   ├── tree_white.json           # árvore combinada de quando você joga de brancas
│   └── tree_black.json           # árvore combinada de quando você joga de pretas
├── scripts/
│   ├── fetch_config.py           # busca a lista de nicks cadastrados no site
│   ├── fetch_lichess.py          # baixa partidas de 1 nick via API do Lichess
│   ├── fetch_chesscom.py         # baixa partidas de 1 nick via API do Chess.com
│   └── build_tree.py             # monta a árvore + estatísticas a partir dos PGNs
└── .github/workflows/update-tree.yml   # roda tudo automaticamente (agendado ou sob demanda)
```

## Por que um Apps Script e não só um campo no site?

O site é estático (GitHub Pages), então ele sozinho não tem como "lembrar"
os nicks entre visitas nem avisar o robô do GitHub Actions sobre eles.
Também não dá pra colocar um token do GitHub direto no JavaScript do site
pra ele escrever no repositório ou disparar o workflow — qualquer
visitante conseguiria ler esse token no código-fonte da página e usá-lo.
Por isso a lista de nicks (e, agora, o token que dispara a importação sob
demanda) ficam num backend intermediário: o Apps Script guarda tudo isso
do lado do Google, e o site só conversa com ele, nunca com o GitHub
diretamente. Mesmo padrão que você já usa na Marcolino Champions League.

**Por que não fazer o site buscar as partidas direto do navegador?** Eu
cheguei a considerar essa opção (seria a forma mais "instantânea"), mas
tanto o Lichess quanto o Chess.com não liberam CORS no endpoint de
exportação de partidas — ou seja, o navegador bloqueia esse tipo de
chamada por segurança, mesmo que a API seja pública. Por isso a
importação em si continua acontecendo no GitHub Actions (que não tem essa
restrição), só que agora pode ser disparada na hora.

## Configurar o backend dos nicks (Apps Script)

1. Crie uma planilha nova no Google Sheets. Renomeie a primeira aba para
   `Nicks` e coloque na linha 1 o cabeçalho: `Plataforma` | `Nick`.
2. Copie o ID da planilha (está na URL, entre `/d/` e `/edit`).
3. Nessa planilha, vá em **Extensões → Apps Script**, apague o conteúdo
   padrão e cole o conteúdo de `apps-script/Code.gs`. Troque `SHEET_ID`
   pelo ID copiado, e `GITHUB_OWNER` / `GITHUB_REPO` pelo seu usuário e
   nome do repositório no GitHub.
4. **Implantar → Nova implantação → tipo "App da Web"**:
   - Executar como: **Eu (você)**
   - Quem pode acessar: **Qualquer pessoa**
5. Copie a URL gerada (termina em `/exec`) — é ela que entra no site e no
   GitHub Actions.

## Configurar o botão "Atualizar agora"

Esse botão precisa de um token do GitHub com permissão só de disparar o
workflow (nada além disso):

1. No GitHub, vá em **Settings (da sua conta) → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token**.
2. Em **Repository access**, escolha **Only select repositories** e
   selecione só o repositório deste projeto.
3. Em **Permissions → Repository permissions**, dê acesso **Read and
   write** só em **Actions**. Não precisa de mais nenhuma permissão.
4. Gere o token e copie (ele só aparece uma vez).
5. Na planilha, vá em **Extensões → Apps Script**, clique no ícone de
   engrenagem (⚙, "Configurações do projeto"), role até **Propriedades
   do script → Adicionar propriedade do script**:
   - Propriedade: `GITHUB_TOKEN`
   - Valor: o token gerado no passo 4
6. Reimplante o Apps Script se já tinha implantado antes (**Implantar →
   Gerenciar implantações → editar → Nova versão**).

Esse token nunca aparece no site nem em nenhum arquivo do repositório —
fica só nas Propriedades do script, que só você (o dono da planilha)
consegue ver.

## Como rodar localmente (primeira vez)

```bash
pip install -r requirements.txt

# busca os nicks cadastrados (ou pule isso e passe os nicks direto pro build_tree.py pra testar)
python scripts/fetch_config.py --apps-script-url "SUA_URL_DO_APPS_SCRIPT"

python scripts/fetch_lichess.py SEU_NICK_LICHESS --output data/raw/lichess_SEU_NICK.pgn
python scripts/fetch_chesscom.py SEU_NICK_CHESSCOM --email seu@email.com --output data/raw/chesscom_SEU_NICK.pgn

python scripts/build_tree.py \
  --lichess-username SEU_NICK_LICHESS OUTRO_NICK_LICHESS \
  --chesscom-username SEU_NICK_CHESSCOM

# depois abra index.html com um servidor local, ex.:
python -m http.server 8000
# e acesse http://localhost:8000
```

(Abrir `index.html` direto com duplo-clique não funciona bem porque o
navegador bloqueia `fetch()` de arquivos locais — por isso o servidor local.
No GitHub Pages isso não é um problema.)

## Publicando no GitHub Pages

1. Suba este projeto para um repositório novo (`git init`, `git remote add
   origin ...`, `git push`), do mesmo jeito que você já faz com os outros
   sites — recomendo `git clone` + `git push` em vez do upload pela
   interface web, para preservar a estrutura de pastas.
2. Em **Settings → Pages**, configure para publicar a partir da branch
   `main`, pasta raiz (`/`).
3. Abra `index.html`, encontre a constante `APPS_SCRIPT_URL` no `<script>`
   e cole ali a URL do seu Apps Script (passo anterior). Faça commit dessa
   mudança.
4. Em **Settings → Secrets and variables → Actions**, crie estes secrets:
   - `APPS_SCRIPT_URL` — a mesma URL usada no `index.html`
   - `CHESSCOM_CONTACT_EMAIL` — um e-mail seu (a Chess.com exige isso no
     cabeçalho das requisições, senão pode bloquear com erro 403)
   - `LICHESS_TOKEN` — opcional; um [token pessoal do
     Lichess](https://lichess.org/account/oauth/token) ajuda a evitar
     limite de requisições, mas não é obrigatório para dados públicos
5. Abra o site publicado, clique no ⚙ e cadastre seus nicks (do Lichess e
   do Chess.com).
6. Clique em **↻ Atualizar agora** (ou rode o workflow manualmente em
   **Actions → Atualizar árvore de aberturas → Run workflow**) para gerar
   os primeiros `tree_white.json` / `tree_black.json` com esses nicks.

Depois disso, os dados se mantêm atualizados de dois jeitos: sozinho toda
segunda-feira às 08:00 UTC, ou na hora sempre que você clicar no botão
(limitado a uma vez a cada 5 minutos, pra evitar disparos acidentais em
sequência). Uma importação sob demanda costuma levar de 1 a 3 minutos —
o site fica de olho e atualiza a árvore na tela sozinho assim que os
dados novos chegam, sem precisar dar F5.

## Filtros

Na barra lateral dá pra filtrar por:

- **Data** (o mais importante — atalhos de "3 meses", "6 meses", "este
  ano" e "tudo", além de um intervalo customizado com data inicial e
  final)
- **Site** (Lichess / Chess.com), dentro de "mais filtros"
- **Nick** (lista construída automaticamente a partir dos dados), dentro
  de "mais filtros"
- **Resultado** (vitórias / empates / derrotas), dentro de "mais filtros"

Tudo isso é recalculado **inteiramente no navegador**, na hora — não
precisa esperar o robô rodar de novo nem recarregar a página. Isso só é
possível porque cada aresta da árvore carrega a lista de partidas
(por índice) que passaram por ali, então filtrar é só cruzar essa lista
com o filtro ativo. Ramos que ficam sem nenhuma partida sob o filtro
atual somem da árvore (por exemplo, uma linha que você só jogou há anos
não aparece quando o filtro é "últimos 3 meses").

Um detalhe: se uma partida não tiver data reconhecível no PGN (raro, mas
acontece com importações antigas ou partidas manuais), ela é **excluída**
sempre que algum filtro de data está ativo, para não distorcer a janela
escolhida — mas continua aparecendo normalmente quando o filtro de data
está em "Tudo".

## Sobre a árvore

- **Posição, não ordem de lances**: as estatísticas são calculadas por
  posição (usando os 4 primeiros campos do FEN — posição das peças, quem
  joga, direitos de roque e alvo de en passant — ignorando os contadores
  de lance, que não fazem parte da posição em si). Quando duas ordens
  diferentes levam à mesma posição (transposição, ex.: `1.d4 d5 2.c4 e6`
  e `1.d4 e6 2.c4 d5`), os dois pontos da árvore mostram exatamente os
  mesmos números — vitórias, empates, derrotas e total de partidas — e
  ficam marcados com o selo ⇄. Por baixo dos panos isso é um grafo de
  posições, não uma árvore; a árvore que você navega é só uma forma de
  percorrer esse grafo a partir da posição inicial.
- Cada nó ainda mostra, entre parênteses, quantas vezes você jogou
  *aquele lance específico a partir daquele ponto* (`(2x aqui)`) — esse
  número pode ser menor que o total da posição, quando ela também foi
  atingida por outras ordens.
- **Nota técnica**: o JSON guarda cada posição **uma única vez** — uma
  lista compacta indexada por número (o índice na lista já é o
  identificador da posição), com as arestas de saída como pares
  `[índice_do_filho, partidas]` em vez de objetos com nomes de campo por
  extenso. O site monta a navegação sob demanda a partir daí, e calcula
  sozinho quais posições são transposição (mais de um pai distinto).
  Uma versão anterior serializava uma árvore aninhada e duplicava a
  subárvore inteira toda vez que uma posição transposta aparecia em mais
  de um lugar, o que causava uma explosão combinatorial em repertórios
  reais (uma abertura com várias transposições, seguida de um meio-jogo
  longo, podia nunca terminar de processar) — e gerava arquivos bem
  maiores do que o necessário mesmo quando terminava. Se algum dia isso
  for reescrito, vale manter o formato de grafo achatado e compacto — é
  o que garante que o custo cresça com o número de posições e partidas,
  nunca com o número de caminhos possíveis entre elas.
- **Profundidade**: partida completa (não só a abertura). Isso significa
  que, depois de ~15-20 lances, a maioria dos nós vai ter só 1 partida —
  o que é esperado e até informativo (mostra o quanto uma linha é
  "familiar" para você ou não).
- **Times separados**: uma árvore para quando você joga de brancas, outra
  para pretas, porque o objetivo de cada lado é diferente.
- **Pontuação**: vitória = 1, empate = 0.5, derrota = 0. `score_pct` é a
  média disso em cada nó.
- **"Linhas a revisar"** (barra lateral): já é uma primeira versão simples
  da parte de "dicas" que você mencionou — sinaliza automaticamente linhas
  com 3+ partidas e aproveitamento abaixo de 45% (cada posição aparece só
  uma vez aqui, mesmo que seja atingida por mais de uma ordem). Essa lista
  também respeita os filtros ativos — filtrando pros últimos 3 meses, por
  exemplo, ela mostra só o que tem sido fraco recentemente.

## Próximos passos (fase 2 — recomendações)

Algumas ideias para quando quiser ir além do "linhas a revisar" atual:

- Comparar seu aproveitamento em cada linha com estatísticas agregadas de
  bases públicas (ex.: [Lichess Opening Explorer
  API](https://lichess.org/api#tag/Opening-Explorer)), pra saber se o
  problema é a linha em si ou a sua execução dela.
- Detectar padrões nas derrotas: mesmo tipo de estrutura de peões, mesmo
  erro posicional recorrente (isso exigiria também importar avaliações de
  engine, não só o resultado da partida).
- Alertar quando uma linha "boa" está sendo abandonada sem necessidade
  (poucas partidas recentes apesar de score alto).

Nenhuma dessas depende de mudar a arquitetura atual — todas dão pra
encaixar em cima do `tree_white.json` / `tree_black.json` que já existem.
