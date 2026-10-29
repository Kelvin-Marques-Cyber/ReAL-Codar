"""Referência offline de HTML e CSS para o painel ESTUDO: o que cada elemento, atributo e propriedade faz.

`conceitos_da_linha` reconhece as tags ou a regra CSS da linha do cursor e devolve os conceitos na ordem em que
aparecem. `anotacoes` explica o que está escrito naquela linha (cada atributo e seu valor, o tipo do input, a
especificidade do seletor, as unidades e cores) e aponta problemas comuns, sem executar nada. As explicações são
conteúdo local; os links do MDN e das especificações são leitura complementar.

`linguagem_na_posicao` faz uma linha dentro de <script> ser explicada como JavaScript e dentro de <style> como CSS.
"""

from __future__ import annotations

import re
from difflib import get_close_matches

_MDN_HTML = "https://developer.mozilla.org/docs/Web/HTML/Element/"
_MDN_CSS = "https://developer.mozilla.org/docs/Web/CSS/"
_ESPEC = "https://html.spec.whatwg.org/multipage/"

# tag -> (título, categoria, explicação, exemplo, erro comum, prática, confira, aula relacionada do percurso)
_E = {}


def _el(tags, titulo, categoria, texto, exemplo, erro="", pratique="", confira="", aula="html_estrutura"):
    tags = tags.split()
    for tag in tags:
        _E[tag] = (tags[0], titulo, categoria, texto, exemplo, erro, pratique, confira, aula)


_el("!doctype", "<!doctype html> · tipo do documento", "Documento",
    "Primeira linha de toda página. Não é uma tag: avisa o navegador para usar o modo padrão de renderização. Sem ela, "
    "o navegador entra no modo quirks, que imita navegadores antigos e muda medidas de caixas e tabelas. Em HTML atual "
    "a forma é sempre esta, sem número de versão.",
    "<!doctype html>\n<html lang=\"pt-BR\">\n  <head>\n    <meta charset=\"utf-8\">\n    <title>Minha página</title>\n"
    "  </head>\n  <body>\n    <h1>Olá!</h1>\n  </body>\n</html>",
    "Esquecer o doctype ou escrever algo antes dele.",
    "Apague o doctype de uma página com bordas e padding e compare as larguras no inspetor do navegador.",
    "A primeira linha do arquivo é exatamente <!doctype html>?")
_el("html", "<html> · raiz do documento", "Documento",
    "Elemento raiz: envolve head e body. O atributo lang declara o idioma do conteúdo. Leitores de tela escolhem a "
    "pronúncia por ele; tradutores automáticos, corretores e a hifenização do CSS também o usam. Use códigos como pt-BR, "
    "pt-PT, en ou es.",
    "<html lang=\"pt-BR\">\n  <head>…</head>\n  <body>…</body>\n</html>",
    "Omitir lang ou deixar lang=\"en\" numa página em português: o leitor de tela lê com pronúncia inglesa.",
    "Troque lang para en e ouça um parágrafo com o leitor de tela do sistema (Narrador, VoiceOver ou Orca).",
    "lang corresponde ao idioma da maior parte do texto? Trechos em outra língua têm lang próprio?")
_el("head", "<head> · informações sobre a página", "Documento",
    "Guarda o que descreve a página e não aparece no corpo: codificação (meta charset), título da aba (title), viewport, "
    "descrição, folhas de estilo (link) e scripts. O navegador lê o head antes de desenhar o conteúdo.",
    "<head>\n  <meta charset=\"utf-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "  <title>Padaria do bairro</title>\n  <link rel=\"stylesheet\" href=\"estilo.css\">\n</head>",
    "Colocar conteúdo visível (h1, p, img) no head: o navegador o move para o body e a estrutura fica confusa.",
    "Monte um head com charset, viewport, title e um CSS externo; confira na aba Rede se o CSS carregou.",
    "O head tem charset, viewport e um title específico desta página?", aula="html_metadados")
_el("body", "<body> · conteúdo visível", "Documento",
    "Tudo o que a pessoa vê e com que interage fica no body: regiões (header, nav, main, footer), textos, imagens e "
    "formulários. Há um único body por documento.",
    "<body>\n  <header><h1>Receitas</h1></header>\n  <main><p>Bem-vindo!</p></main>\n  <footer><p>Contato</p></footer>\n</body>",
    "Encher o body de divs sem regiões semânticas: quem usa leitor de tela perde os atalhos de navegação.",
    "Organize a página em header, main e footer e navegue pelas regiões com o atalho de marcos do leitor de tela.",
    "Existe um main com o conteúdo principal?")
_el("meta", "<meta> · metadados", "Metadados",
    "Elemento vazio (sem fechamento) que descreve a página. charset=\"utf-8\" define a codificação e deve vir logo no "
    "início do head, para os acentos aparecerem certos. name=\"viewport\" faz a página usar a largura real do celular; "
    "name=\"description\" resume a página para buscadores, que podem escolher outro trecho.",
    "<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<meta name=\"description\" content=\"Receitas rápidas com ingredientes da estação.\">",
    "Esquecer o viewport (no celular a página aparece minúscula) ou bloquear o zoom com user-scalable=no.",
    "Remova o viewport e abra a página no modo dispositivo do navegador; compare antes e depois.",
    "charset vem antes de qualquer texto do head? A descrição corresponde ao conteúdo real?", aula="html_metadados")
_el("title", "<title> · título da aba", "Metadados",
    "Texto da aba, dos favoritos, do histórico e dos resultados de busca; é também o primeiro anúncio do leitor de tela "
    "ao abrir a página. Deve ser único por página, com o específico antes do geral.",
    "<title>Carrinho (3 itens) — Padaria do bairro</title>",
    "Usar o mesmo título em todas as páginas (\"Home\") ou deixá-lo vazio.",
    "Abra duas páginas do seu site em abas: dá para distingui-las só pelo título?",
    "O título descreve esta página, e não apenas o site?", aula="html_metadados")
_el("link", "<link> · recurso externo", "Metadados",
    "Liga o documento a outro recurso. O uso mais comum é rel=\"stylesheet\" com href para o arquivo CSS; também declara "
    "o ícone da aba (rel=\"icon\") e pré-carregamentos (rel=\"preload\"). É vazio e fica no head.",
    "<link rel=\"stylesheet\" href=\"css/estilo.css\">\n<link rel=\"icon\" href=\"favicon.svg\" type=\"image/svg+xml\">",
    "Caminho relativo errado: href é resolvido a partir da página, não da raiz do projeto.",
    "Ligue um estilo.css; depois renomeie o arquivo e veja o erro 404 na aba Rede do navegador.",
    "O CSS carrega (status 200) abrindo pelo servidor e pelo arquivo local?", aula="html_integracao")
_el("style", "<style> · CSS dentro da página", "Metadados",
    "Contém regras CSS no próprio documento. Serve para protótipos ou estilos críticos; em projetos maiores prefira um "
    "arquivo .css ligado por link, que o navegador guarda em cache e várias páginas reutilizam. As linhas dentro de "
    "style são explicadas como CSS.",
    "<style>\n  body { font-family: system-ui, sans-serif; margin: 0; }\n  .aviso { color: #8b0000; }\n</style>",
    "Copiar o mesmo bloco style em todas as páginas: cada ajuste precisa ser repetido.",
    "Mova as regras para estilo.css e ligue o arquivo com link.",
    "As regras continuam valendo depois de mover para o arquivo externo?", aula="html_integracao")
_el("script", "<script> · JavaScript", "Scripts",
    "Executa JavaScript escrito dentro do elemento ou carregado por src. Um script comum no head interrompe a leitura do "
    "HTML até baixar e executar; defer espera o documento ser analisado e mantém a ordem; type=\"module\" ativa módulos "
    "ES (import/export) e já se comporta como defer. As linhas dentro de script são explicadas como JavaScript.",
    "<script src=\"app.js\" defer></script>\n<script type=\"module\">\n  import { iniciar } from \"./app.js\";\n"
    "  iniciar();\n</script>",
    "Procurar elementos (document.querySelector) num script do head sem defer: eles ainda não existem e o resultado é null.",
    "Ligue app.js no head sem defer, procure um botão e veja o null; depois acrescente defer.",
    "A página continua legível com JavaScript desativado?", aula="html_integracao")
_el("noscript", "<noscript> · alternativa sem JavaScript", "Scripts",
    "Conteúdo mostrado só quando o JavaScript está desativado ou bloqueado. Melhor ainda é a página já apresentar o "
    "conteúdo essencial em HTML e o script apenas melhorar a experiência.",
    "<noscript><p>O simulador precisa de JavaScript. A tabela de preços abaixo funciona sem ele.</p></noscript>",
    aula="html_integracao")
_el("header", "<header> · cabeçalho", "Regiões",
    "Agrupa a introdução de uma página ou seção: logotipo, título, navegação. No topo do body vira o marco \"banner\" "
    "dos leitores de tela; dentro de article ou section é apenas o cabeçalho daquela parte.",
    "<header>\n  <a href=\"/\">Padaria do bairro</a>\n  <nav aria-label=\"Principal\">…</nav>\n</header>",
    "Confundir header (região visível), head (metadados) e h1 (título).",
    "Coloque logotipo e menu num header e encontre-o pela lista de marcos do leitor de tela.")
_el("nav", "<nav> · navegação", "Regiões",
    "Marca um bloco de links de navegação importante: menu, sumário, paginação. Leitores de tela pulam direto até ele. "
    "Com mais de um nav, diferencie com aria-label (\"Principal\", \"Rodapé\"). A lista de links costuma ser ul > li > a.",
    "<nav aria-label=\"Principal\">\n  <ul>\n    <li><a href=\"/\" aria-current=\"page\">Início</a></li>\n"
    "    <li><a href=\"/produtos\">Produtos</a></li>\n  </ul>\n</nav>",
    "Usar nav para qualquer grupo de links ou fazer o menu com div e onclick.",
    "Monte um menu com nav, ul e a; marque a página atual com aria-current=\"page\" e percorra com Tab.",
    "Todos os itens são links com href e alcançáveis por Tab?")
_el("main", "<main> · conteúdo principal", "Regiões",
    "Envolve o conteúdo central e exclusivo da página, sem cabeçalho, menu e rodapé repetidos. Há um main visível por "
    "página; o marco e o link \"pular para o conteúdo\" levam direto a ele.",
    "<a class=\"pular\" href=\"#conteudo\">Pular para o conteúdo</a>\n<main id=\"conteudo\">\n  <h1>Produtos</h1>\n</main>",
    "Ter vários main visíveis ou colocar o menu dentro dele.",
    "Crie um link \"Pular para o conteúdo\" para o id do main e teste com Tab logo ao abrir a página.",
    "Existe exatamente um main visível?")
_el("section", "<section> · seção temática", "Regiões",
    "Agrupa conteúdo de um mesmo tema, normalmente com seu próprio título (h2, h3…). Se o bloco só existe para "
    "estilizar, use div; se faz sentido sozinho fora da página (post, cartão de produto), use article.",
    "<section aria-labelledby=\"sobre\">\n  <h2 id=\"sobre\">Sobre nós</h2>\n  <p>Somos uma padaria de bairro.</p>\n</section>",
    "Usar section como div genérica, sem título.",
    "Divida uma página em três sections com h2 e confira a lista de títulos no leitor de tela.",
    "Cada section tem um título que diz do que ela trata?")
_el("article", "<article> · conteúdo independente", "Regiões",
    "Conteúdo completo em si: notícia, post, comentário, cartão de produto. O teste: faria sentido publicado sozinho "
    "em outro lugar? Pode ter header, footer e títulos próprios.",
    "<article>\n  <h2>Pão de fermentação natural</h2>\n  <p><time datetime=\"2026-10-01\">1º de outubro</time></p>\n"
    "  <p>Receita em três dias…</p>\n</article>",
    "Usar article para qualquer caixa da página.",
    "Transforme uma lista de posts em articles, cada um com h2 e time.",
    "Cada article faria sentido fora desta página?")
_el("aside", "<aside> · conteúdo complementar", "Regiões",
    "Conteúdo relacionado, mas secundário: barra lateral, glossário, links relacionados. Fora de article vira o marco "
    "\"complementar\" dos leitores de tela.",
    "<aside aria-label=\"Relacionados\">\n  <h2>Veja também</h2>\n  <ul><li><a href=\"/bolos\">Bolos</a></li></ul>\n</aside>",
    "Colocar no aside algo essencial para entender a página.",
    "Esconda o aside: o conteúdo principal continua compreensível?")
_el("footer", "<footer> · rodapé", "Regiões",
    "Rodapé da página ou de uma seção: autoria, direitos, contato, links legais. No fim do body vira o marco "
    "\"contentinfo\".",
    "<footer>\n  <p>© 2026 Padaria do bairro</p>\n  <address><a href=\"mailto:contato@exemplo.com\">contato@exemplo.com</a></address>\n</footer>",
    "Usar footer só pela posição visual, para algo que não é rodapé.",
    "Acrescente um footer com contato usando address e um link mailto.")
_el("address", "<address> · contato", "Texto",
    "Informações de contato de quem é responsável pela página ou pelo article: email, telefone, endereço. Não é para "
    "qualquer endereço postal citado no texto.",
    "<address>\n  <a href=\"tel:+5511999990000\">(11) 99999-0000</a><br>\n  Rua das Flores, 10 — São Paulo\n</address>")
_el("h1 h2 h3 h4 h5 h6", "<h1>…<h6> · títulos", "Texto",
    "Títulos formam o sumário da página: h1 nomeia a página e h2…h6 criam subníveis, sem pular níveis (h2 → h4). "
    "Leitores de tela listam e navegam pelos títulos. O tamanho visual se ajusta no CSS, nunca trocando o nível.",
    "<h1>Receitas</h1>\n<h2>Pães</h2>\n<h3>Fermentação natural</h3>\n<h2>Bolos</h2>",
    "Escolher h3 porque \"o tamanho ficou bom\" ou usar negrito no lugar de um título.",
    "Escreva o sumário só com os títulos da página: ele descreve o conteúdo na ordem certa?",
    "Há um h1 e os níveis não pulam?")
_el("p", "<p> · parágrafo", "Texto",
    "Um bloco de texto corrido; o espaço entre parágrafos vem da margin padrão e se ajusta no CSS. Um p não pode conter "
    "blocos como div, ul ou outro p: o navegador fecha o parágrafo automaticamente antes deles.",
    "<p>Abrimos de segunda a sábado, das <time datetime=\"07:00\">7h</time> às <time datetime=\"19:00\">19h</time>.</p>",
    "Criar espaço com <p></p> ou <br> vazios: use margin no CSS.",
    "Escreva dois parágrafos e ajuste a distância entre eles somente com CSS.")
_el("div", "<div> · agrupamento genérico", "Agrupamento",
    "Caixa sem significado, para agrupar e estilizar. Use quando nenhum elemento semântico (section, nav, article, ul, "
    "button…) descreve o conteúdo. O leitor de tela ignora a div; o que conta é o que está dentro.",
    "<div class=\"cartao\">\n  <h2>Plano básico</h2>\n  <p>R$ 19/mês</p>\n</div>",
    "Fazer botões e links com div + onclick: não recebem foco, não respondem a Enter/Espaço e não são anunciados como controles.",
    "Troque uma div clicável por button e teste com Tab, Enter e Espaço.",
    "Existe um elemento semântico que descreveria melhor este bloco?")
_el("span", "<span> · trecho genérico", "Agrupamento",
    "Equivalente em linha da div: marca um pedaço de texto para estilizar ou manipular com JavaScript, sem significado. "
    "Para importância use strong; para código, code; para datas, time.",
    "<p>Total: <span class=\"preco\">R$ 42,00</span></p>",
    "Usar span em negrito para indicar importância: use strong.")
_el("br", "<br> · quebra de linha", "Texto",
    "Quebra a linha dentro do mesmo parágrafo quando a quebra faz parte do conteúdo: endereço, poema, letra de música. "
    "É vazio, sem fechamento.",
    "<address>Rua das Flores, 10<br>Centro<br>São Paulo – SP</address>",
    "Empilhar <br><br> para criar espaço entre blocos: use parágrafos e margin.")
_el("hr", "<hr> · mudança de assunto", "Texto",
    "Separa temas dentro de uma seção (mudança de cena ou de assunto). A linha é só a aparência padrão, ajustável no CSS.",
    "<p>Fim da primeira parte.</p>\n<hr>\n<p>Começa a segunda parte.</p>",
    "Usar hr só como enfeite: para isso use border no CSS.")
_el("strong em b i", "<strong>, <em>, <b> e <i> · importância e ênfase", "Texto",
    "strong indica importância, gravidade ou urgência; em indica ênfase que muda o sentido da frase. b e i destacam "
    "sem dar importância (termos técnicos, nomes de obras, palavras estrangeiras). Negrito e itálico são só a aparência "
    "padrão.",
    "<p><strong>Atenção:</strong> o forno estará quente.</p>\n<p>Eu <em>pedi</em> sem cebola.</p>\n"
    "<p>O fermento <i lang=\"fr\">levain</i> leva dias.</p>",
    "Usar strong só porque quer negrito: para isso use font-weight no CSS.")
_el("small mark", "<small> e <mark> · observações e destaque", "Texto",
    "small marca observações e letras miúdas (direitos, avisos legais). mark destaca um trecho por relevância no "
    "contexto, como o termo buscado nos resultados.",
    "<p>Resultados para <mark>fermento</mark></p>\n<p><small>Preços sujeitos a alteração.</small></p>")
_el("code pre kbd samp", "<code>, <pre> e <kbd> · código e teclas", "Texto",
    "code marca um trecho de código; pre preserva espaços e quebras de linha (blocos de código ficam como pre > code); "
    "kbd representa teclas e samp, a saída de um programa. Dentro deles, escreva < como &lt; e & como &amp;.",
    "<p>Rode <code>npm install</code> e depois aperte <kbd>Ctrl</kbd>+<kbd>C</kbd>.</p>\n"
    "<pre><code>for (let i = 0; i &lt; 3; i++) {\n  console.log(i);\n}</code></pre>",
    "Colar código com < sem escapar: o navegador tenta interpretá-lo como tag.")
_el("blockquote q cite", "<blockquote>, <q> e <cite> · citações", "Texto",
    "blockquote é uma citação longa, em bloco; q, uma citação curta dentro da frase (o navegador põe as aspas). O "
    "atributo cite guarda o endereço da fonte; o elemento cite marca o título de uma obra.",
    "<blockquote cite=\"https://exemplo.com/entrevista\">\n  <p>Pão bom precisa de tempo.</p>\n</blockquote>\n"
    "<p>— entrevista a <cite>Revista do Bairro</cite></p>")
_el("time", "<time> · data e hora", "Texto",
    "Mostra uma data ou hora para pessoas e guarda em datetime o valor no formato padrão (AAAA-MM-DD, HH:MM). Agendas, "
    "buscadores e scripts leem o datetime.",
    "<p>Inscrições até <time datetime=\"2026-11-30\">30 de novembro</time>.</p>",
    "Escrever datetime no formato local, como 30/11/2026.")
_el("abbr", "<abbr> · abreviação", "Texto",
    "Marca uma sigla ou abreviação. Na primeira ocorrência, escreva a forma completa no texto; title é só um complemento, "
    "pois não aparece no celular nem para quem usa teclado.",
    "<p>O <abbr title=\"Cadastro de Pessoas Físicas\">CPF</abbr> (Cadastro de Pessoas Físicas) é obrigatório.</p>")
_el("ul", "<ul> · lista sem ordem", "Listas",
    "Lista em que a ordem não muda o sentido: ingredientes, recursos, links de um menu. Os filhos diretos são sempre li. "
    "Leitores de tela anunciam \"lista, 3 itens\", o que ajuda a navegar.",
    "<ul>\n  <li>Farinha</li>\n  <li>Fermento</li>\n  <li>Água</li>\n</ul>",
    "Colocar texto ou div diretamente dentro de ul, fora de li.",
    "Transforme um menu feito com links soltos em ul > li > a.", "Todos os filhos diretos são li?")
_el("ol", "<ol> · lista ordenada", "Listas",
    "Lista em que a ordem importa: passos de uma receita, ranking. start muda o número inicial e reversed inverte a "
    "contagem. A numeração é gerada pelo navegador; não escreva \"1.\" no texto.",
    "<ol>\n  <li>Misture os ingredientes.</li>\n  <li>Descanse por 1 hora.</li>\n  <li>Asse por 40 minutos.</li>\n</ol>",
    "Numerar à mão dentro dos li, duplicando os números.")
_el("li", "<li> · item de lista", "Listas",
    "Item de ul, ol ou menu. Pode conter texto, links e outra lista aninhada (um submenu, por exemplo).",
    "<ul>\n  <li>Pães\n    <ul><li>Integral</li><li>Francês</li></ul>\n  </li>\n</ul>",
    "Usar li fora de ul ou ol.")
_el("dl dt dd", "<dl>, <dt> e <dd> · lista de descrições", "Listas",
    "Pares termo–descrição: glossário, ficha técnica, perguntas e respostas. dt é o termo; dd, a descrição.",
    "<dl>\n  <dt>Tempo de preparo</dt><dd>40 minutos</dd>\n  <dt>Rendimento</dt><dd>8 porções</dd>\n</dl>")
_el("a", "<a> · link", "Links e mídia",
    "Leva a outro endereço: página (href=\"/contato\"), ponto da mesma página (href=\"#precos\" vai até id=\"precos\"), "
    "email (mailto:), telefone (tel:) ou arquivo (download). Só é um link de verdade com href: aí recebe foco, abre com "
    "Enter e entra na lista de links do leitor de tela. O texto deve dizer o destino.",
    "<a href=\"/contato\">Fale conosco</a>\n<a href=\"#precos\">Ver preços</a>\n"
    "<a href=\"cardapio.pdf\" download>Baixar cardápio (PDF, 1 MB)</a>",
    "Textos como \"clique aqui\", que fora de contexto não dizem nada, ou a sem href para ações (use button).",
    "Leia só os textos dos links da página, fora de ordem: cada um ainda diz para onde leva?",
    "Todo link tem href e um texto que descreve o destino?")
_el("img", "<img> · imagem", "Links e mídia",
    "Insere uma imagem (src). alt é obrigatório: descreve a informação da imagem para quem não a vê e aparece se o "
    "arquivo falhar; alt=\"\" marca imagem decorativa, que o leitor de tela ignora. width e height reservam o espaço e "
    "evitam que a página \"pule\" ao carregar; loading=\"lazy\" adia imagens fora da tela.",
    "<img src=\"img/bolo.jpg\" alt=\"Bolo de cenoura com cobertura de chocolate\" width=\"800\" height=\"600\" loading=\"lazy\">\n"
    "<img src=\"img/divisor.svg\" alt=\"\" width=\"120\" height=\"8\">",
    "Esquecer alt, repetir o nome do arquivo (\"IMG_2031.jpg\") ou começar com \"imagem de\".",
    "Desative as imagens no navegador e leia a página só pelos textos alternativos.",
    "Sem ver a imagem, o alt transmite o que ela acrescenta ao texto?", aula="html_imagens")
_el("picture source", "<picture> e <source> · versões de uma mídia", "Links e mídia",
    "picture oferece versões da mesma imagem: o navegador usa o primeiro source cujo type ou media ele aceita e, se "
    "nenhum servir, o img final — obrigatório, é ele que leva o alt. Em video e audio, source lista formatos alternativos.",
    "<picture>\n  <source srcset=\"bolo.avif\" type=\"image/avif\">\n  <source srcset=\"bolo.webp\" type=\"image/webp\">\n"
    "  <img src=\"bolo.jpg\" alt=\"Bolo de cenoura\" width=\"800\" height=\"600\">\n</picture>",
    "Esquecer o img dentro de picture: sem ele nada aparece.", aula="html_imagens")
_el("figure figcaption", "<figure> e <figcaption> · mídia com legenda", "Links e mídia",
    "figure agrupa imagem, gráfico, código ou citação mencionados no texto; figcaption é a legenda visível, associada "
    "ao conteúdo. A legenda não substitui o alt.",
    "<figure>\n  <img src=\"grafico.png\" alt=\"Vendas subiram de 120 para 180 entre julho e setembro\" width=\"640\" height=\"360\">\n"
    "  <figcaption>Vendas mensais do 3º trimestre.</figcaption>\n</figure>", aula="html_imagens")
_el("video", "<video> · vídeo", "Links e mídia",
    "Reproduz vídeo. controls mostra os controles nativos, acessíveis por teclado; source oferece formatos; track "
    "adiciona legendas WebVTT; poster mostra uma imagem antes de tocar. autoplay só funciona com muted na maioria dos "
    "navegadores.",
    "<video controls width=\"640\" poster=\"capa.jpg\" preload=\"metadata\">\n  <source src=\"aula.webm\" type=\"video/webm\">\n"
    "  <source src=\"aula.mp4\" type=\"video/mp4\">\n"
    "  <track kind=\"captions\" src=\"legendas.vtt\" srclang=\"pt-BR\" label=\"Português\" default>\n</video>",
    "Omitir controls (não há como pausar) ou não oferecer legendas.",
    "Adicione legendas.vtt a um vídeo seu e controle a reprodução só pelo teclado.", aula="html_midia")
_el("audio", "<audio> · áudio", "Links e mídia",
    "Reproduz som; use controls. Ofereça transcrição em texto para quem não pode ouvir. Evite autoplay: som que começa "
    "sozinho atrapalha quem usa leitor de tela.",
    "<audio controls src=\"podcast.mp3\"></audio>\n<details><summary>Transcrição</summary><p>Olá! Hoje…</p></details>",
    aula="html_midia")
_el("track", "<track> · legendas e descrições", "Links e mídia",
    "Arquivo WebVTT de legendas (kind=\"captions\"), traduções (subtitles) ou descrições, dentro de video ou audio. "
    "srclang e label identificam o idioma; default ativa a faixa por padrão.",
    "<track kind=\"captions\" src=\"legendas.vtt\" srclang=\"pt-BR\" label=\"Português\" default>", aula="html_midia")
_el("iframe", "<iframe> · página dentro da página", "Links e mídia",
    "Incorpora outro documento: mapa, vídeo, formulário externo. title é necessário para o leitor de tela anunciar o "
    "conteúdo. sandbox restringe o que a página incorporada pode fazer; loading=\"lazy\" adia o carregamento.",
    "<iframe src=\"https://www.openstreetmap.org/export/embed.html\" title=\"Mapa da padaria\" width=\"600\" height=\"400\" "
    "loading=\"lazy\"></iframe>",
    "Incorporar sem title ou dar ao iframe mais permissões que o necessário.", aula="html_midia")
_el("canvas svg", "<canvas> e <svg> · desenho e gráficos", "Links e mídia",
    "svg descreve formas vetoriais no próprio HTML: nítidas em qualquer zoom, estilizáveis com CSS e acessíveis com "
    "title. canvas é uma área de pixels desenhada por JavaScript: o conteúdo não é texto, então ofereça uma alternativa "
    "(tabela, descrição).",
    "<svg width=\"120\" height=\"120\" role=\"img\" aria-labelledby=\"t\">\n  <title id=\"t\">Gráfico: 75% concluído</title>\n"
    "  <circle cx=\"60\" cy=\"60\" r=\"50\" fill=\"none\" stroke=\"teal\" stroke-width=\"10\"/>\n</svg>",
    "Mostrar dados só num canvas, sem alternativa em texto.")
_el("table", "<table> · tabela de dados", "Tabelas",
    "Para dados em linhas e colunas (horários, preços, notas), nunca para posicionar a página. caption dá o título; "
    "thead e tbody agrupam as linhas; th marca cabeçalhos, com scope=\"col\" ou scope=\"row\", para o leitor de tela "
    "anunciar cada célula junto do seu cabeçalho.",
    "<table>\n  <caption>Horário de funcionamento</caption>\n  <thead><tr><th scope=\"col\">Dia</th><th scope=\"col\">Horário</th></tr></thead>\n"
    "  <tbody>\n    <tr><th scope=\"row\">Segunda</th><td>7h–19h</td></tr>\n    <tr><th scope=\"row\">Domingo</th><td>Fechado</td></tr>\n"
    "  </tbody>\n</table>",
    "Montar layout com tabela ou usar td em negrito no lugar de th.",
    "Navegue célula a célula com o leitor de tela: cada valor é anunciado com seu cabeçalho?",
    "A tabela tem caption e os cabeçalhos são th com scope?", aula="html_tabelas")
_el("caption", "<caption> · título da tabela", "Tabelas",
    "Primeiro filho de table: diz o que os dados representam e é anunciado ao entrar na tabela.",
    "<table>\n  <caption>Notas do 1º bimestre</caption>\n  …\n</table>", aula="html_tabelas")
_el("thead tbody tfoot", "<thead>, <tbody> e <tfoot> · grupos de linhas", "Tabelas",
    "Separam cabeçalho, corpo e rodapé (totais) da tabela. Ajudam a leitura, a impressão (o thead se repete em cada "
    "página impressa) e a estilização.",
    "<thead><tr><th scope=\"col\">Item</th><th scope=\"col\">Preço</th></tr></thead>\n"
    "<tbody><tr><td>Pão</td><td>R$ 1,00</td></tr></tbody>\n<tfoot><tr><th scope=\"row\">Total</th><td>R$ 1,00</td></tr></tfoot>",
    aula="html_tabelas")
_el("tr", "<tr> · linha da tabela", "Tabelas",
    "Uma linha de células th ou td. Todas as linhas devem ter o mesmo número de colunas, contando colspan.",
    "<tr><th scope=\"row\">Segunda</th><td>7h–19h</td></tr>", aula="html_tabelas")
_el("th", "<th> · célula de cabeçalho", "Tabelas",
    "Cabeçalho de coluna ou de linha. scope=\"col\" vale para a coluna abaixo; scope=\"row\", para a linha ao lado. Em "
    "tabelas complexas, dê id aos th e liste-os no atributo headers de cada td.",
    "<th scope=\"col\">Horário</th>", aula="html_tabelas")
_el("td", "<td> · célula de dados", "Tabelas",
    "Um dado da tabela. colspan e rowspan mesclam células; mantenha a grade consistente para a leitura linha a linha.",
    "<td colspan=\"2\">Fechado para reforma</td>", aula="html_tabelas")
_el("form", "<form> · formulário", "Formulários",
    "Agrupa campos e envia os dados. action é o endereço que recebe (sem action, a própria página); method=\"post\" envia "
    "no corpo da requisição (dados pessoais, senhas) e method=\"get\" coloca os campos na URL (buscas, filtros). Só "
    "campos com name são enviados. Enter num campo de texto envia o formulário.",
    "<form action=\"/inscricao\" method=\"post\">\n  <label for=\"nome\">Nome</label>\n"
    "  <input id=\"nome\" name=\"nome\" autocomplete=\"name\" required>\n  <button type=\"submit\">Inscrever</button>\n</form>",
    "Esquecer name nos campos ou confiar só na validação do navegador: valide de novo no servidor.",
    "Envie um formulário com method=\"get\" e observe os campos na URL; depois troque para post.",
    "Cada campo tem name e label, e o envio funciona só com o teclado?", aula="html_semantica")
_el("label", "<label> · rótulo do campo", "Formulários",
    "Nome visível de um campo. for=\"id\" liga o label ao campo com aquele id (ou o campo fica dentro do label): clicar "
    "no texto foca o campo, a área de toque aumenta e o leitor de tela anuncia o nome. placeholder não substitui label, "
    "pois some quando a pessoa digita.",
    "<label for=\"email\">Email</label>\n<input id=\"email\" name=\"email\" type=\"email\" autocomplete=\"email\">\n\n"
    "<label><input type=\"checkbox\" name=\"novidades\"> Quero receber novidades</label>",
    "for apontando para um id inexistente ou repetido na página.",
    "Clique no texto de cada label: o campo certo recebe o foco?",
    "Cada campo visível tem um label associado?", aula="html_semantica")
_el("input", "<input> · campo de entrada", "Formulários",
    "Campo de formulário; type define o comportamento e o teclado do celular (email, tel, number, date, checkbox, radio, "
    "file, password…). name é a chave enviada; id liga ao label. required, min, max, maxlength e pattern validam no "
    "navegador antes do envio; autocomplete ajuda a preencher (name, email, tel, street-address).",
    "<label for=\"tel\">Telefone</label>\n<input id=\"tel\" name=\"tel\" type=\"tel\" autocomplete=\"tel\">\n\n"
    "<label for=\"qtd\">Quantidade</label>\n<input id=\"qtd\" name=\"qtd\" type=\"number\" min=\"1\" max=\"10\" value=\"1\">",
    "Usar type=\"text\" para tudo (perde validação e o teclado certo) ou usar placeholder como único rótulo.",
    "Troque o type de um campo entre text, email e tel e observe o teclado no modo dispositivo.",
    "O type corresponde ao dado e existe um label?", aula="html_semantica")
_el("button", "<button> · botão", "Formulários",
    "Controle para ações: enviar (type=\"submit\", o padrão dentro de form), limpar (reset) ou executar JavaScript "
    "(type=\"button\"). Recebe foco e responde a Enter e Espaço sem código extra. O texto — ou aria-label, se for só um "
    "ícone — diz o que acontece.",
    "<button type=\"submit\">Salvar</button>\n<button type=\"button\" id=\"menu\" aria-expanded=\"false\">Menu</button>",
    "Esquecer type=\"button\" num botão de JavaScript dentro de form: ele envia o formulário e recarrega a página.",
    "Ponha um botão sem type dentro de um form, clique e veja o envio; depois use type=\"button\".",
    "O botão funciona com Tab, Enter e Espaço?", aula="html_semantica")
_el("select option optgroup", "<select> e <option> · lista de opções", "Formulários",
    "Escolha entre opções fixas. Cada option tem value (enviado) e texto (mostrado); selected marca a opção inicial; "
    "multiple permite várias; optgroup agrupa. Uma primeira opção com value vazio e required obriga a escolher.",
    "<label for=\"sabor\">Sabor</label>\n<select id=\"sabor\" name=\"sabor\" required>\n  <option value=\"\">Escolha…</option>\n"
    "  <option value=\"chocolate\">Chocolate</option>\n  <option value=\"morango\">Morango</option>\n</select>",
    "Usar select para duas ou três opções (radio mostra todas de uma vez) ou recriar um select com div.",
    aula="html_semantica")
_el("textarea", "<textarea> · texto longo", "Formulários",
    "Campo de várias linhas (comentários, mensagens). O valor inicial é o conteúdo entre as tags, não um atributo value; "
    "rows sugere a altura e maxlength limita os caracteres.",
    "<label for=\"msg\">Mensagem</label>\n<textarea id=\"msg\" name=\"mensagem\" rows=\"4\" maxlength=\"500\"></textarea>",
    "Deixar espaços ou quebras entre <textarea> e </textarea>: eles viram o valor inicial.", aula="html_semantica")
_el("fieldset legend", "<fieldset> e <legend> · grupo de campos", "Formulários",
    "Agrupa campos relacionados; legend é o título do grupo e é anunciado com cada campo. Indispensável em grupos de "
    "radio e checkbox (\"Forma de pagamento\").",
    "<fieldset>\n  <legend>Forma de pagamento</legend>\n"
    "  <label><input type=\"radio\" name=\"pagamento\" value=\"pix\" checked> Pix</label>\n"
    "  <label><input type=\"radio\" name=\"pagamento\" value=\"cartao\"> Cartão</label>\n</fieldset>",
    "Radios do mesmo grupo com name diferente: deixam de ser mutuamente exclusivos.", aula="html_semantica")
_el("output progress meter", "<output>, <progress> e <meter> · resultados e medidas", "Formulários",
    "output mostra o resultado de um cálculo; com aria-live=\"polite\" o leitor de tela anuncia a mudança. progress "
    "indica o andamento de uma tarefa (sem value, fica indeterminado); meter, uma medida dentro de um intervalo, como "
    "o espaço em disco.",
    "<output id=\"total\" aria-live=\"polite\">0</output>\n<progress value=\"3\" max=\"10\">3 de 10</progress>\n"
    "<meter value=\"0.7\" min=\"0\" max=\"1\">70%</meter>", aula="html_integracao")
_el("details summary", "<details> e <summary> · conteúdo expansível", "Interativos",
    "Bloco que abre e fecha sem JavaScript: summary é o título clicável e o restante aparece ao abrir. Funciona com "
    "teclado por padrão; open deixa aberto. Bom para perguntas frequentes e transcrições.",
    "<details>\n  <summary>Vocês entregam?</summary>\n  <p>Sim, no bairro, até as 18h.</p>\n</details>")
_el("dialog", "<dialog> · janela de diálogo", "Interativos",
    "Caixa de diálogo nativa. showModal() abre como modal: bloqueia o resto da página, leva o foco para dentro e fecha "
    "com Esc; close() fecha. Um form com method=\"dialog\" fecha o diálogo ao enviar.",
    "<dialog id=\"confirmar\">\n  <form method=\"dialog\">\n    <p>Remover o item?</p>\n"
    "    <button type=\"submit\" value=\"nao\">Cancelar</button> <button type=\"submit\" value=\"sim\">Remover</button>\n"
    "  </form>\n</dialog>\n"
    "<button type=\"button\" id=\"remover\">Remover</button>\n"
    "<script>\n  remover.addEventListener(\"click\", () => confirmar.showModal());\n</script>",
    "Criar modais com div sem prender o foco nem fechar com Esc.")
_el("template slot", "<template> e <slot> · modelos para JavaScript", "Scripts",
    "template guarda HTML que não é exibido nem executado até um script cloná-lo (template.content.cloneNode(true)). "
    "slot marca onde o conteúdo entra num Web Component.",
    "<template id=\"item\">\n  <li class=\"item\"><span class=\"nome\"></span></li>\n</template>", aula="html_integracao")
_el("center font marquee blink big strike tt frame frameset acronym", "Elemento obsoleto", "Obsoletos",
    "Este elemento foi removido do HTML. Navegadores ainda o exibem por compatibilidade, mas ele não tem significado e "
    "pode deixar de funcionar. Apresentação vai para o CSS: text-align para centralizar, font-family/color para fontes, "
    "animation para movimento.",
    "<p class=\"centro\">Promoção</p>\n<style>.centro { text-align: center; color: #8b0000; }</style>",
    "Copiar trechos de tutoriais antigos com tags dos anos 1990.")

_COMENTARIO_HTML = ("<!-- --> · comentário", "Documento",
                    "Texto ignorado pelo navegador, mas visível a qualquer pessoa em \"Exibir código-fonte\": nunca guarde "
                    "senhas, endereços internos ou dados pessoais em comentários. Não pode conter -- no meio.",
                    "<!-- Menu principal: manter a mesma ordem do rodapé -->\n<nav aria-label=\"Principal\">…</nav>")

# Atributos: explicação curta. Atributos de evento (on*) e data-* são tratados à parte.
_ATRIBUTOS = {
    "lang": "idioma do conteúdo deste elemento e dos filhos; muda a pronúncia do leitor de tela e a tradução automática",
    "charset": "codificação dos caracteres; utf-8 cobre acentos e emojis e deve vir no início do head",
    "content": "valor do metadado declarado em name ou http-equiv",
    "href": "endereço do destino: caminho relativo (pagina.html), absoluto (/contato), âncora (#id), mailto: ou tel:",
    "src": "endereço do arquivo carregado (imagem, script, mídia), relativo à página",
    "alt": "texto alternativo: o que a imagem informa; alt=\"\" marca decoração ignorada pelo leitor de tela",
    "rel": "relação com o recurso: stylesheet, icon, preload; em links, noopener/noreferrer isolam a nova aba",
    "id": "identificador único na página: alvo de âncoras (#id), de label for e de document.getElementById",
    "class": "nomes separados por espaço usados por seletores CSS (.nome) e pelo JavaScript; pode repetir na página",
    "style": "CSS aplicado só a este elemento; vence a maioria das regras e dificulta a manutenção — prefira uma classe",
    "for": "id do campo que este label nomeia; clicar no texto foca o campo",
    "required": "o formulário não é enviado com o campo vazio; valide também no servidor",
    "placeholder": "dica de formato que some ao digitar; não substitui o label",
    "value": "valor inicial do campo, ou o valor enviado por option, radio, checkbox e button",
    "method": "get coloca os campos na URL (buscas); post envia no corpo da requisição (dados pessoais)",
    "action": "endereço que recebe o formulário; sem action, a própria página",
    "disabled": "desativa o controle: não recebe foco e não é enviado",
    "readonly": "o valor não pode ser editado, mas o campo recebe foco e é enviado",
    "autocomplete": "tipo de dado para o preenchimento automático (name, email, tel, street-address, current-password)",
    "target": "onde abrir o link; _blank abre outra aba — avise no texto, pois muda o comportamento esperado",
    "title": "dica que aparece ao passar o mouse; não aparece no toque nem no teclado, então não guarde informação essencial nele",
    "width": "largura em pixels, sem unidade; com height, reserva o espaço antes da imagem carregar",
    "height": "altura em pixels, sem unidade; com width, evita que o conteúdo pule ao carregar",
    "loading": "lazy adia o carregamento até a mídia se aproximar da tela; eager carrega imediatamente",
    "decoding": "async permite decodificar a imagem sem atrasar o resto da página",
    "defer": "baixa o script em paralelo e executa depois de analisar o HTML, na ordem em que aparecem",
    "async": "baixa em paralelo e executa assim que chegar, sem ordem garantida; bom para scripts independentes",
    "controls": "mostra os controles nativos de reprodução, acessíveis por teclado",
    "autoplay": "tenta tocar sozinho; navegadores só permitem com muted",
    "muted": "começa sem som",
    "loop": "recomeça ao terminar",
    "poster": "imagem exibida antes do vídeo tocar",
    "preload": "quanto baixar antes do play: none, metadata (duração e dimensões) ou auto",
    "colspan": "quantas colunas esta célula ocupa",
    "rowspan": "quantas linhas esta célula ocupa",
    "scope": "col: cabeçalho da coluna abaixo; row: cabeçalho da linha ao lado",
    "headers": "ids dos th que descrevem esta célula, para tabelas complexas",
    "aria-label": "nome acessível quando não há texto visível (botão só com ícone); substitui o texto anunciado",
    "aria-labelledby": "usa o texto do elemento com estes ids como nome acessível",
    "aria-describedby": "liga uma descrição extra, como a mensagem de erro de um campo",
    "aria-live": "polite anuncia mudanças deste trecho quando o leitor de tela estiver livre; assertive interrompe",
    "aria-current": "marca o item atual de um conjunto, como a página aberta no menu (aria-current=\"page\")",
    "aria-expanded": "informa se o conteúdo controlado está aberto (true) ou fechado (false); atualize com JavaScript",
    "aria-controls": "id do elemento que este controle abre ou altera",
    "aria-hidden": "true esconde do leitor de tela; nunca use em algo que recebe foco",
    "aria-invalid": "true informa que o valor do campo foi recusado",
    "role": "papel acessível; prefira o elemento nativo (button, nav) a role=\"button\" numa div",
    "tabindex": "0 coloca no Tab em ordem natural; -1 só permite foco por script; evite valores positivos",
    "hidden": "esconde o elemento de todos, como display: none",
    "srcset": "lista de arquivos com largura (800w) ou densidade (2x) para o navegador escolher",
    "sizes": "largura que a imagem ocupará em cada tela, para escolher o arquivo certo do srcset",
    "min": "menor valor aceito", "max": "maior valor aceito", "step": "intervalo entre valores válidos",
    "pattern": "expressão regular que o valor inteiro precisa cumprir; explique o formato no texto do label",
    "maxlength": "número máximo de caracteres", "minlength": "número mínimo de caracteres",
    "checked": "começa marcado (checkbox, radio)", "selected": "opção escolhida inicialmente",
    "multiple": "permite escolher vários valores (select, email, file)",
    "accept": "tipos de arquivo sugeridos no seletor (image/*, .pdf); valide também no servidor",
    "download": "baixa o arquivo em vez de abri-lo; o valor sugere um nome",
    "open": "deixa details ou dialog abertos",
    "datetime": "data ou hora no formato padrão lido por máquinas (2026-11-30, 19:00)",
    "inputmode": "teclado virtual preferido (numeric, decimal, tel, email) sem mudar a validação",
    "novalidate": "desliga a validação do navegador neste formulário",
    "enctype": "codificação do envio; multipart/form-data é necessário para enviar arquivos",
    "sandbox": "restringe o iframe; libere só o necessário (allow-scripts, allow-forms)",
    "integrity": "hash que o navegador confere antes de usar um arquivo de outro domínio",
    "crossorigin": "como pedir recursos de outro domínio (anonymous ou use-credentials)",
    "start": "número inicial da lista ordenada", "reversed": "conta a lista de trás para frente",
    "rows": "altura sugerida em linhas", "cols": "largura sugerida em caracteres",
    "label": "título visível da faixa de legenda ou do grupo de opções",
    "kind": "tipo da faixa: captions (legendas), subtitles (tradução), descriptions, chapters",
    "srclang": "idioma da faixa de legenda", "default": "ativa esta faixa por padrão",
    "media": "condição de mídia para usar este recurso, como (max-width: 600px)",
    "cite": "endereço da fonte da citação",
    "spellcheck": "liga ou desliga a correção ortográfica do campo",
    "contenteditable": "permite editar o texto do elemento; exige cuidado com acessibilidade e com o que for salvo",
    "draggable": "permite arrastar o elemento com a API de arrastar e soltar",
}
_NAME = {"viewport": "ajusta a página à largura do dispositivo; mantenha o zoom liberado",
         "description": "resumo da página para buscadores e prévias de links",
         "theme-color": "cor da interface do navegador no celular",
         "robots": "pede a buscadores para indexar (index) ou não (noindex) a página",
         "author": "autoria do documento"}
_TIPOS = {
    "text": "texto livre de uma linha", "email": "endereço de email; valida o formato e mostra @ no teclado do celular",
    "password": "esconde o que é digitado; use autocomplete=\"current-password\" ou \"new-password\"",
    "number": "número com setas; para CPF, CEP ou cartão use text com inputmode=\"numeric\" (zeros à esquerda importam)",
    "tel": "telefone; abre o teclado numérico, sem validar o formato", "url": "endereço completo com protocolo (https://)",
    "search": "campo de busca; alguns navegadores mostram um botão para limpar",
    "date": "seletor de data; o valor enviado é AAAA-MM-DD", "time": "hora (HH:MM)",
    "datetime-local": "data e hora sem fuso horário", "month": "mês e ano", "week": "semana do ano",
    "color": "seletor de cor; o valor é #rrggbb", "range": "controle deslizante; mostre o valor atual em um output",
    "checkbox": "liga/desliga; só é enviado quando marcado", "radio": "uma opção entre várias com o mesmo name; agrupe com fieldset e legend",
    "file": "escolha de arquivos; o form precisa de method=\"post\" e enctype=\"multipart/form-data\"",
    "hidden": "valor enviado sem aparecer; não é segredo (está no código-fonte)",
    "submit": "botão que envia o formulário; prefira <button type=\"submit\">", "reset": "volta os campos ao valor inicial",
    "button": "botão sem ação padrão; prefira <button type=\"button\">", "image": "botão de envio feito de imagem; exige alt",
}
_ENTIDADES = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": "\"", "&apos;": "'", "&nbsp;": "espaço que não quebra a linha",
              "&copy;": "©", "&mdash;": "travessão —", "&ndash;": "meia-risca –", "&hellip;": "reticências …"}
_TAG = re.compile(r"<(/?)([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?)*)\s*(/?)(>?)")
_ATTR = re.compile(r"([^\s=>/]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+)))?")
# Elementos válidos sem verbete próprio, inclusive SVG e MathML: nunca são apontados como erro de grafia.
_VALIDOS = set("""a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption cite code
col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2 h3 h4
h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li link main map mark menu meta meter nav noscript
object ol optgroup option output p picture pre progress q rp rt ruby s samp script search section select slot small source
span strong style sub summary sup table tbody td template textarea tfoot th thead time title tr track u ul var video wbr
svg g path rect circle ellipse line polyline polygon text tspan defs use symbol lineargradient radialgradient stop
clippath mask pattern image foreignobject filter marker desc animate animatetransform feblend fecolormatrix
fegaussianblur feoffset femerge femergenode math mi mn mo mrow msup msub mfrac msqrt mroot mtext mtable mtr mtd""".split())


def _tags(linha: str) -> list[tuple[str, dict[str, str], bool]]:
    """(tag, atributos, fechamento) na ordem da linha; o doctype vira a tag "!doctype"."""
    out = []
    if re.search(r"<!doctype\b", linha, re.I):
        out.append(("!doctype", {}, False))
    for match in _TAG.finditer(linha):
        attrs = {}
        for attr in _ATTR.finditer(match[3] or ""):
            value = next((v for v in attr.groups()[1:] if v is not None), None)
            attrs[attr[1].lower()] = value
        out.append((match[2].lower(), attrs, bool(match[1])))
    return out


def _conceito_id(tag: str) -> str:
    return "html_ref_" + _E[tag][0].lstrip("!")


def ampliar_web(C):
    """Conceitos estáticos da referência: aparecem no catálogo, na busca e no painel ESTUDO."""
    out, feitos = [], set()
    for tag, (principal, titulo, categoria, texto, exemplo, erro, pratique, confira, aula) in _E.items():
        if principal in feitos:
            continue
        feitos.add(principal)
        tags = [t for t, v in _E.items() if v[0] == principal]
        # "tag a" casaria com "tag atual": nomes curtos só valem escritos como tag.
        palavras = tuple(p for t in tags if not t.startswith("!")
                         for p in ((f"<{t}>", f"<{t} ") + ((f"tag {t}", f"elemento {t}") if len(t) > 2 else ())))
        out.append(C(_conceito_id(principal), titulo, "referencia", f"{categoria}. {texto}",
                     pratique or "Escreva um exemplo seu com este elemento, abra no navegador e navegue usando só o teclado.",
                     palavras=palavras, exemplos={"html": exemplo}, relacionados=(aula,),
                     fontes=tuple(_MDN_HTML + t for t in tags if not t.startswith("!"))[:2] or (_ESPEC + "syntax.html",),
                     erros_comuns=erro, verifique=confira))
    titulo, categoria, texto, exemplo = _COMENTARIO_HTML
    out.append(C("html_ref_comentario", titulo, "referencia", f"{categoria}. {texto}",
                 "Comente uma decisão de estrutura e confira o comentário em Exibir código-fonte.",
                 palavras=("comentário html",), exemplos={"html": exemplo}, fontes=(_ESPEC + "syntax.html#comments",)))
    for chave, (titulo, texto, exemplo, erro, pratique, aula, fonte) in _CSS.items():
        out.append(C("css_ref_" + chave, titulo, "referencia", texto, pratique, palavras=(titulo.split(" · ")[0].lower(),),
                     exemplos={"css": exemplo}, relacionados=(aula,) if aula else (), fontes=(fonte,), erros_comuns=erro))
    return out


def _alertas(tag: str, attrs: dict[str, str | None], fecha: bool, *, dentro_label=False, controle_depois=False) -> list[str]:
    """Problemas reconhecíveis só pela linha; nada que dependa do resto do documento."""
    if fecha:
        return []
    out = []
    has = attrs.__contains__
    tipo = (attrs.get("type") or "").lower()
    if tag in ("center", "font", "marquee", "blink", "big", "strike", "tt", "frame", "frameset", "acronym"):
        out.append(f"<{tag}> é obsoleto: use CSS para a apresentação.")
    if tag == "html" and not attrs.get("lang"):
        out.append("<html> sem lang: o leitor de tela não sabe em que idioma ler.")
    if tag == "img":
        if not has("alt"):
            out.append("img sem alt: o leitor de tela anuncia o nome do arquivo. Descreva a informação ou use alt=\"\" se for decoração.")
        elif re.search(r"\.(?:jpe?g|png|gif|webp|svg|avif)$", attrs.get("alt") or "", re.I):
            out.append("O alt repete o nome do arquivo; descreva o que a imagem mostra.")
        elif re.match(r"(?:imagem|foto|figura|image|picture|photo) (?:de|do|da|of)\b", attrs.get("alt") or "", re.I):
            out.append("Não comece o alt com \"imagem de\": o leitor de tela já anuncia que é uma imagem.")
        if not (has("width") and has("height")):
            out.append("Sem width e height, a página pula quando a imagem termina de carregar.")
    if tag == "a":
        if not has("href"):
            out.append("a sem href não é focável nem abre com Enter. Para uma ação, use <button type=\"button\">.")
        elif (attrs.get("href") or "").strip().lower().startswith("javascript:"):
            out.append("href=\"javascript:…\" mistura link com ação: use button e addEventListener.")
        if (attrs.get("target") or "").lower() == "_blank" and "noopener" not in (attrs.get("rel") or ""):
            out.append("target=\"_blank\": navegadores atuais já isolam a nova aba; rel=\"noopener\" deixa isso explícito para os antigos.")
    if tag == "button" and not tipo:
        out.append("button sem type: dentro de um form ele é submit e envia o formulário. Use type=\"button\" para ações de script.")
    if tag in ("input", "select", "textarea") and tipo not in ("hidden", "submit", "reset", "button", "image"):
        if not (has("id") or has("aria-label") or has("aria-labelledby") or dentro_label):
            out.append(f"{tag} sem id nem aria-label: nenhum label pode nomeá-lo. Dê um id e um <label for>, ou envolva o "
                       "campo com label" + (" — o placeholder some ao digitar e não serve de rótulo." if has("placeholder") else "."))
        if tag != "select" and not has("name"):
            out.append(f"{tag} sem name: o valor não é enviado com o formulário.")
    if tag == "input" and tipo and tipo not in _TIPOS:
        out.append(f"type=\"{tipo}\" não existe; o navegador usa text.")
    if tag == "input" and tipo == "image" and not has("alt"):
        out.append("input type=\"image\" precisa de alt descrevendo a ação.")
    if tag == "label" and not has("for") and not controle_depois:
        out.append("label sem for: ligue ao id do campo, ou mantenha o campo dentro do label.")
    if tag == "iframe" and not attrs.get("title"):
        out.append("iframe sem title: o leitor de tela não informa o que foi incorporado.")
    if tag in ("video", "audio"):
        if has("autoplay") and not has("muted"):
            out.append("autoplay com som é bloqueado pelos navegadores e atrapalha leitores de tela; acrescente muted ou remova autoplay.")
        if not has("controls"):
            out.append(f"{tag} sem controls: a pessoa não consegue pausar nem ajustar o volume.")
    if tag == "meta" and (attrs.get("name") or "").lower() == "viewport" and re.search(
            r"user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0)?\b", attrs.get("content") or "", re.I):
        out.append("Este viewport bloqueia o zoom; quem precisa ampliar o texto fica impedido. Remova user-scalable/maximum-scale.")
    if tag == "script" and has("src") and not (has("defer") or has("async")) and tipo != "module":
        out.append("script externo sem defer: se estiver no head, a leitura do HTML para até ele baixar e executar.")
    if tag in ("div", "span") and any(a in attrs for a in ("onclick", "onkeydown")):
        out.append(f"{tag} clicável não recebe foco nem responde a Enter/Espaço; use <button type=\"button\">.")
    if any(a.startswith("on") and len(a) > 3 for a in attrs):
        out.append("Atributos de evento (onclick…) misturam HTML e JavaScript; prefira addEventListener num script.")
    if has("style"):
        out.append("style em linha vence quase todas as regras e se repete pelo HTML; mova para uma classe no CSS.")
    if (attrs.get("tabindex") or "").strip().isdigit() and int(attrs["tabindex"]) > 0:
        out.append("tabindex positivo muda a ordem do Tab em relação à leitura; use 0 ou a ordem do HTML.")
    if attrs.get("aria-hidden") == "true" and tag in ("a", "button", "input", "select", "textarea"):
        out.append("aria-hidden=\"true\" num elemento focável cria um controle invisível ao leitor de tela.")
    if tag == "th" and not has("scope") and not has("id"):
        out.append("th sem scope: indique se é cabeçalho da coluna (col) ou da linha (row).")
    if tag == "form" and (attrs.get("method") or "get").lower() == "get" and "senha" in str(attrs).lower():
        out.append("Formulário com senha usando GET coloca dados na URL; use method=\"post\".")
    return out


def anotacoes_html(linha: str) -> list[tuple[str, str]]:
    """O que cada tag, atributo e entidade desta linha faz, e os problemas visíveis nela."""
    out: list[tuple[str, str]] = []
    if "<!--" in linha:
        out.append(("info", "comentário: o navegador ignora, mas qualquer pessoa vê no código-fonte"))
    tags = _tags(linha[:_LIMITE])[:_MAX_TAGS]
    abertas = {t for t, _a, f in tags if not f}
    label_aberto = False  # <label><input …> Texto</label>: o campo está dentro do rótulo
    for indice, (tag, attrs, fecha) in enumerate(tags):
        if tag == "label":
            label_aberto = not fecha
        if tag == "!doctype":
            out.append(("info", "<!doctype html>: ativa o modo padrão de renderização"))
            continue
        if fecha:
            if tag in _E and tag not in abertas:
                out.append(("info", f"</{tag}> fecha o elemento {tag} aberto numa linha anterior"))
            continue
        if tag not in _E and tag not in _VALIDOS and "-" not in tag:
            out.append(("alerta", f"Não reconheço <{tag}>: confira a grafia. Elementos personalizados precisam de hífen."))
        elif "-" in tag:
            out.append(("info", f"<{tag}>: elemento personalizado (Web Component), definido por JavaScript com customElements.define"))
        for name, value in attrs.items():
            shown = name if value is None else f"{name}=\"{value}\""
            if name == "type" and tag == "input":
                text = _TIPOS.get((value or "").lower())
                text = f"campo de {text}" if text else "tipo do campo"
            elif name == "type" and tag == "button":
                text = {"submit": "envia o formulário", "button": "não faz nada sozinho: a ação vem do JavaScript",
                        "reset": "volta os campos ao valor inicial"}.get((value or "").lower(), "comportamento do botão")
            elif name == "type" and tag == "script":
                text = "módulo ES: permite import/export e executa como defer" if value == "module" else \
                    "conteúdo que não é JavaScript; o navegador não executa" if value and "javascript" not in value else "tipo do script"
            elif name == "type":
                text = "tipo MIME do recurso, para o navegador decidir se consegue usá-lo"
            elif name == "name" and tag == "meta":
                text = _NAME.get((value or "").lower(), "nome do metadado")
            elif name == "name":
                text = "chave com que o valor é enviado no formulário" + ("; radios com o mesmo name formam um grupo"
                                                                         if attrs.get("type") == "radio" else "")
            elif name == "rel" and tag == "a":
                text = "relação com o destino; noopener/noreferrer isolam a aba aberta, nofollow pede a buscadores para não seguir"
            elif name.startswith("data-"):
                text = f"dado próprio para o JavaScript, lido como elemento.dataset.{_camel(name[5:])}"
            elif name.startswith("on"):
                text = "código executado no evento; prefira addEventListener"
            elif name.startswith("aria-") and name not in _ATRIBUTOS:
                text = "informação extra para tecnologias assistivas"
            else:
                text = _ATRIBUTOS.get(name)
            if text:
                out.append(("atributo", f"{shown} — {text}"))
        controles = {"input", "select", "textarea", "meter", "progress", "output"}
        out.extend(("alerta", alerta) for alerta in _alertas(
            tag, attrs, fecha, dentro_label=label_aberto and tag != "label",
            controle_depois=any(t in controles and not f for t, _a, f in tags[indice + 1:])))
    for entidade in dict.fromkeys(re.findall(r"&[a-zA-Z]+;|&#\d+;", linha)):
        if entidade in _ENTIDADES:
            out.append(("info", f"{entidade} escreve {_ENTIDADES[entidade]}"))
    return list(dict.fromkeys(out))


# O painel mostra poucas notas: linhas minificadas não podem custar tempo proporcional ao arquivo inteiro.
_LIMITE = 4000
_MAX_TAGS = 60


def _camel(nome: str) -> str:
    partes = nome.split("-")
    return partes[0] + "".join(p.title() for p in partes[1:])


def html_da_linha(linha: str, por_id: dict) -> list:
    """Conceitos da referência HTML na ordem das tags da linha."""
    out = []
    linha = linha[:_LIMITE]
    if "<!--" in linha and "html_ref_comentario" in por_id:
        out.append(por_id["html_ref_comentario"])
    for tag, _attrs, _fecha in _tags(linha)[:_MAX_TAGS]:
        if tag in _E and (c := por_id.get(_conceito_id(tag))) and c not in out:
            out.append(c)
    return out


# ------------------------------------------------------------------------------------------------- CSS
# chave -> (título, explicação, exemplo, erro comum, prática, aula do percurso, fonte)
_CSS = {
    "seletores": ("Seletores e especificidade · CSS",
                  "O seletor escolhe os elementos que recebem as declarações entre chaves. Quando duas regras disputam a "
                  "mesma propriedade, vence a de maior especificidade — contada como (ids, classes/atributos/pseudo-classes, "
                  "elementos) — e, no empate, a que aparece depois. style no HTML e !important passam por cima disso.",
                  "nav a { color: #222; }             /* (0,0,2) */\n.menu a { color: #0645ad; }        /* (0,1,1) vence */\n"
                  "nav > a:hover { text-decoration: underline; }\n.cartao, .aviso { padding: 1rem; }",
                  "Usar ids ou !important para ganhar disputas: cada nova regra precisa ser ainda mais forte.",
                  "Escreva duas regras para o mesmo link e preveja a cor; confira em Estilos computados no inspetor.",
                  "css_cascata", _MDN_CSS + "Specificity"),
    "caixa": ("Modelo de caixa · CSS",
              "Todo elemento é uma caixa: conteúdo, padding (espaço interno), border e margin (espaço externo). Com o "
              "padrão content-box, padding e borda somam-se ao width; box-sizing: border-box inclui os dois no width, o "
              "que torna os tamanhos previsíveis. max-width limita a largura e margin-inline: auto centraliza.",
              "*, *::before, *::after { box-sizing: border-box; }\n.cartao {\n  max-width: 30rem;\n  padding: 1rem;\n"
              "  border: 1px solid #ccc;\n  border-radius: .5rem;\n  margin: 0 auto;\n}",
              "Somar width: 100% com padding sem border-box e ganhar rolagem horizontal.",
              "Compare a largura total de um cartão com e sem border-box no inspetor.", "css_caixa", _MDN_CSS + "CSS_box_model"),
    "display": ("display e visibilidade · CSS",
                "display decide como a caixa participa do layout: block ocupa a linha inteira; inline flui com o texto e "
                "ignora width/height; inline-block flui mas aceita tamanho; flex e grid organizam os filhos; none remove "
                "a caixa e também a esconde do leitor de tela. visibility: hidden esconde mantendo o espaço.",
                ".menu { display: flex; }\n.icone { display: inline-block; width: 1rem; }\n.fechado { display: none; }",
                "Esconder com display: none um texto que deveria ser lido apenas pelo leitor de tela.",
                "Troque o display de um link entre inline, inline-block e block e observe width e margin.",
                "css_caixa", _MDN_CSS + "display"),
    "flex": ("Flexbox · CSS",
             "display: flex organiza os filhos numa linha (ou coluna, com flex-direction: column). justify-content "
             "distribui no eixo principal; align-items alinha no eixo cruzado; gap separa os itens; flex-wrap deixa "
             "passar para a linha seguinte. flex: 1 faz um item ocupar o espaço que sobra.",
             ".barra {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  gap: 1rem;\n"
             "  flex-wrap: wrap;\n}\n.barra .busca { flex: 1; }",
             "Usar margin em cada item no lugar de gap, ou order para mudar só a ordem visual (a do teclado continua a do HTML).",
             "Monte uma barra com logotipo, busca e botão; faça a busca crescer com flex: 1.", "css_flex", _MDN_CSS + "CSS_flexible_box_layout"),
    "grid": ("Grid · CSS",
             "display: grid cria linhas e colunas. grid-template-columns define as faixas: fr divide o espaço livre, "
             "repeat repete e minmax limita; auto-fit cria quantas colunas couberem. grid-column e grid-row posicionam "
             "itens; grid-template-areas nomeia regiões.",
             ".galeria {\n  display: grid;\n  gap: 1rem;\n  grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));\n}",
             "Larguras fixas em px que só funcionam na tela de quem escreveu.",
             "Coloque seis cartões numa galeria e estreite a janela: as colunas se reorganizam sozinhas?", "css_grid", _MDN_CSS + "CSS_grid_layout"),
    "posicao": ("Posicionamento e camadas · CSS",
                "position: relative desloca a caixa sem tirá-la do fluxo e serve de referência para filhos absolute; "
                "absolute sai do fluxo e se posiciona pelo ancestral posicionado mais próximo; fixed fica preso à janela; "
                "sticky gruda ao rolar até um limite. top/right/bottom/left (ou inset) definem a posição; z-index, a "
                "ordem das camadas entre elementos posicionados.",
                ".cartao { position: relative; }\n.selo { position: absolute; top: .5rem; right: .5rem; }\n"
                "header { position: sticky; top: 0; z-index: 10; }",
                "Usar absolute para montar o layout inteiro, que quebra com textos maiores ou zoom.",
                "Coloque um selo \"Novo\" no canto de um cartão com relative + absolute.", "css_caixa", _MDN_CSS + "position"),
    "cores": ("Cores, fundos e sombras · CSS",
              "color muda o texto; background-color, o fundo; background-image aceita imagens e gradientes. Cores podem "
              "ser nomes, #rrggbb, rgb() ou hsl(); currentColor reaproveita a cor do texto. O contraste entre texto e "
              "fundo precisa ser de pelo menos 4,5:1 para texto comum (WCAG).",
              ".aviso {\n  color: #5c0000;\n  background-color: #fff3f3;\n  border-left: 4px solid currentColor;\n"
              "  box-shadow: 0 1px 3px rgb(0 0 0 / .2);\n}",
              "Texto cinza-claro sobre branco: bonito no monitor do autor, ilegível no sol.",
              "Meça o contraste das cores do seu site no inspetor do navegador.", "css_cascata", _MDN_CSS + "color_value"),
    "texto": ("Fontes e texto · CSS",
              "font-family lista fontes em ordem de preferência, terminando numa família genérica (sans-serif, serif, "
              "monospace); font-size em rem respeita o tamanho escolhido pela pessoa; line-height sem unidade (1.5) "
              "escala com a fonte. text-align, text-decoration e text-transform ajustam a apresentação.",
              "body {\n  font-family: system-ui, sans-serif;\n  font-size: 1rem;\n  line-height: 1.5;\n}\n"
              "h1 { font-size: clamp(1.75rem, 4vw, 2.5rem); }",
              "Fixar font-size em px no html: quem aumenta a fonte do navegador não vê diferença.",
              "Aumente a fonte padrão do navegador e confira se o texto acompanha.", "css_responsivo", _MDN_CSS + "font"),
    "medidas": ("Unidades e valores · CSS",
                "px é fixo; rem é relativo à fonte da raiz (1rem = 16px por padrão) e acompanha a preferência da pessoa; "
                "em é relativo à fonte do próprio elemento; % é relativo ao contêiner; vw/vh, à janela; fr, ao espaço "
                "livre do grid; ch, à largura do caractere 0. min(), max() e clamp() combinam limites.",
                ".texto { max-width: 65ch; }\n.titulo { font-size: clamp(1.5rem, 3vw + 1rem, 3rem); }\n"
                ".lateral { width: min(100%, 20rem); }",
                "Usar 100vh no celular, onde a barra do navegador muda a altura; prefira 100dvh.",
                "Troque as medidas de um cartão de px para rem e aumente a fonte do navegador.", "css_responsivo", _MDN_CSS + "length"),
    "movimento": ("Transições e animações · CSS",
                  "transition anima a mudança de uma propriedade (cor, transform) entre dois estados, como no :hover. "
                  "@keyframes descreve etapas e animation as executa. transform e opacity animam sem refazer o layout. "
                  "Respeite prefers-reduced-motion para quem sente desconforto com movimento.",
                  ".botao { transition: background-color .2s ease, transform .2s ease; }\n.botao:hover { transform: translateY(-2px); }\n"
                  "@media (prefers-reduced-motion: reduce) {\n  * { animation: none !important; transition: none !important; }\n}",
                  "Animar width, top ou margin, que forçam recálculo do layout a cada quadro.",
                  "Anime um botão com transform no :hover e desligue com prefers-reduced-motion.", "css_movimento", _MDN_CSS + "transition"),
    "variaveis": ("Variáveis CSS (custom properties) · CSS",
                  "--nome: valor declara uma propriedade personalizada, normalmente em :root para valer na página toda; "
                  "var(--nome, reserva) usa o valor. Elas seguem a cascata: uma regra mais específica pode mudar o valor "
                  "só dentro de um componente, e o JavaScript pode alterá-las em tempo real.",
                  ":root {\n  --cor-marca: #0b6e4f;\n  --espaco: 1rem;\n}\n.botao {\n  background: var(--cor-marca);\n"
                  "  padding: calc(var(--espaco) / 2) var(--espaco);\n}",
                  "Escrever var(cor-marca) sem os dois hífens, ou esquecer que o valor é herdado pelos filhos.",
                  "Crie um tema escuro mudando só as variáveis dentro de @media (prefers-color-scheme: dark).",
                  "css_arquitetura", _MDN_CSS + "Using_CSS_custom_properties"),
    "media": ("@media e responsividade · CSS",
              "@media aplica regras só quando a condição vale: largura (min-width), orientação, preferência de cor "
              "(prefers-color-scheme) ou de movimento. Escreva primeiro para telas estreitas e acrescente regras com "
              "min-width quando o conteúdo pedir mais espaço.",
              ".layout { display: grid; gap: 1rem; }\n@media (min-width: 48rem) {\n  .layout { grid-template-columns: 1fr 3fr; }\n}",
              "Criar um breakpoint para cada aparelho em vez de seguir o conteúdo.",
              "Estreite a janela até o layout quebrar e acrescente um @media nesse ponto.", "css_responsivo", _MDN_CSS + "@media"),
    "regras": ("At-rules (@import, @font-face, @supports, @layer) · CSS",
               "@import inclui outro CSS (deve vir no início; atrasa o carregamento — prefira link no HTML). @font-face "
               "declara uma fonte própria; @supports aplica regras só se o navegador entende uma propriedade; @layer "
               "organiza camadas da cascata; @container reage ao tamanho do contêiner.",
               "@font-face {\n  font-family: \"Título\";\n  src: url(\"fontes/titulo.woff2\") format(\"woff2\");\n  font-display: swap;\n}\n"
               "@supports (display: grid) {\n  .galeria { display: grid; }\n}",
               "Encadear vários @import, que baixam um depois do outro.",
               "Declare uma fonte com @font-face e use font-display: swap.", "css_arquitetura", _MDN_CSS + "At-rule"),
    "interacao": ("Estados e interação · CSS",
                  ":hover reage ao mouse; :focus-visible mostra o foco do teclado; :active, o clique; :disabled, controles "
                  "desligados; :checked, opções marcadas. cursor indica o tipo de ação. Nunca remova o contorno de foco "
                  "sem oferecer outro bem visível.",
                  "a:hover { text-decoration-thickness: 2px; }\nbutton:focus-visible { outline: 3px solid #0b6e4f; outline-offset: 2px; }\n"
                  "input:invalid { border-color: #b00020; }",
                  "outline: none no foco: quem navega pelo teclado não sabe onde está.",
                  "Navegue pela página com Tab: o foco aparece em todos os controles?", "css_responsivo", _MDN_CSS + ":focus-visible"),
}
_PROPS = {
    "caixa": "width height min-width max-width min-height max-height padding margin border box-sizing border-radius "
             "outline aspect-ratio overflow overflow-x overflow-y inline-size block-size margin-inline margin-block "
             "padding-inline padding-block border-top border-right border-bottom border-left border-width border-style "
             "border-color outline-offset object-fit",
    "display": "display visibility",
    "flex": "flex flex-direction flex-wrap flex-flow flex-grow flex-shrink flex-basis justify-content align-items "
            "align-self align-content gap row-gap column-gap order",
    "grid": "grid grid-template-columns grid-template-rows grid-template-areas grid-area grid-column grid-row "
            "grid-auto-flow grid-auto-rows grid-auto-columns place-items place-content place-self justify-items",
    "posicao": "position top right bottom left inset z-index float clear",
    "cores": "color background background-color background-image background-size background-position background-repeat "
             "opacity box-shadow filter accent-color",
    "texto": "font font-family font-size font-weight font-style line-height letter-spacing text-align text-decoration "
             "text-transform white-space word-break overflow-wrap text-overflow list-style text-indent font-display",
    "movimento": "transition transition-property transition-duration transition-timing-function animation "
                 "animation-name animation-duration transform translate rotate scale will-change",
    "interacao": "cursor pointer-events user-select touch-action resize scroll-behavior",
}
_PROP_GRUPO = {prop: grupo for grupo, props in _PROPS.items() for prop in props.split()}
# Propriedades válidas sem verbete próprio: reconhecidas para não serem apontadas como erro de grafia.
_CONHECIDAS = set(_PROP_GRUPO) | set("""content columns column-count column-width fill stroke stroke-width quotes hyphens
isolation mix-blend-mode clip-path backdrop-filter counter-reset counter-increment container container-type
container-name table-layout vertical-align text-shadow src unicode-range font-variant font-feature-settings
font-stretch writing-mode direction caret-color appearance content-visibility contain scroll-snap-type
scroll-snap-align scroll-margin scroll-padding overscroll-behavior justify-self perspective transform-origin
backface-visibility border-collapse border-spacing caption-side empty-cells text-wrap tab-size word-spacing
image-rendering mask object-position border-image zoom all color-scheme print-color-adjust line-clamp field-sizing
anchor-name position-anchor view-transition-name text-underline-offset hanging-punctuation orphans widows
page-break-before page-break-after break-before break-after break-inside user-select""".split())
_PROP_TEXTO = {
    "display": "como a caixa entra no layout e organiza os filhos", "visibility": "esconde mantendo o espaço ocupado",
    "width": "largura do conteúdo (ou da caixa inteira com border-box)", "height": "altura; prefira deixar o conteúdo definir",
    "max-width": "largura máxima: a caixa encolhe em telas menores", "min-width": "largura mínima",
    "min-height": "altura mínima; cresce se o conteúdo precisar", "max-height": "altura máxima",
    "padding": "espaço interno, entre o conteúdo e a borda", "margin": "espaço externo, entre esta caixa e as vizinhas",
    "border": "borda: espessura, estilo e cor", "box-sizing": "se width inclui padding e borda (border-box) ou não (content-box)",
    "border-radius": "arredonda os cantos", "outline": "contorno fora da borda, usado para o foco; não ocupa espaço",
    "overflow": "o que fazer com o conteúdo que não cabe: visible, hidden, scroll ou auto",
    "aspect-ratio": "proporção largura/altura, como 16 / 9", "object-fit": "como imagem/vídeo preenche a caixa: cover recorta, contain encaixa",
    "flex": "atalho de flex-grow, flex-shrink e flex-basis; flex: 1 ocupa o espaço que sobra",
    "flex-direction": "eixo principal: row (linha) ou column (coluna)", "flex-wrap": "wrap deixa os itens passarem para a próxima linha",
    "justify-content": "distribui os itens no eixo principal", "align-items": "alinha os itens no eixo cruzado",
    "align-self": "alinhamento de um item só", "gap": "espaço entre itens de flex ou grid, sem margin nas pontas",
    "order": "muda a ordem visual; a ordem de leitura e do Tab continua a do HTML",
    "grid-template-columns": "define as colunas do grid", "grid-template-rows": "define as linhas do grid",
    "grid-template-areas": "nomeia regiões do grid com texto", "grid-column": "colunas que o item ocupa (início / fim)",
    "grid-row": "linhas que o item ocupa", "grid-area": "região nomeada ou posição do item no grid",
    "place-items": "atalho de align-items e justify-items",
    "position": "esquema de posicionamento da caixa", "top": "distância do topo do contêiner de referência",
    "inset": "atalho de top, right, bottom e left", "z-index": "ordem de empilhamento entre elementos posicionados",
    "float": "flutua à esquerda/direita com o texto ao redor; para layout use flex ou grid",
    "color": "cor do texto (e de currentColor)", "background": "atalho para cor, imagem, posição e repetição do fundo",
    "background-color": "cor de fundo", "background-image": "imagem ou gradiente de fundo",
    "background-size": "tamanho da imagem de fundo: cover cobre, contain encaixa", "opacity": "transparência do elemento inteiro (0 a 1)",
    "box-shadow": "sombra: deslocamento x, y, desfoque, expansão e cor", "accent-color": "cor de checkbox, radio e range nativos",
    "font-family": "fontes em ordem de preferência; termine com uma família genérica", "font-size": "tamanho da fonte",
    "font-weight": "espessura: 400 normal, 700 negrito", "line-height": "altura da linha; sem unidade escala com a fonte",
    "text-align": "alinhamento horizontal do texto", "text-decoration": "sublinhado e outras linhas no texto",
    "text-transform": "maiúsculas/minúsculas só na apresentação", "white-space": "como espaços e quebras de linha são tratados",
    "letter-spacing": "espaço entre letras", "list-style": "marcador das listas",
    "transition": "anima a mudança das propriedades indicadas", "animation": "executa uma animação de @keyframes",
    "transform": "move, gira ou escala sem afetar o layout ao redor", "cursor": "formato do ponteiro sobre o elemento",
    "pointer-events": "none deixa cliques passarem através do elemento", "scroll-behavior": "smooth anima a rolagem para âncoras",
    "user-select": "se o texto pode ser selecionado; none atrapalha quem quer copiar", "content": "texto gerado por ::before e ::after",
    "vertical-align": "alinhamento vertical de elementos inline e células de tabela", "text-shadow": "sombra do texto",
    "font": "atalho para estilo, peso, tamanho, altura de linha e família",
}
_VALORES = {
    "display": {"block": "ocupa a linha inteira e aceita largura e altura", "inline": "flui com o texto; width e height não se aplicam",
                "inline-block": "flui com o texto e aceita largura, altura e margin vertical",
                "flex": "os filhos diretos viram itens flex alinhados numa linha",
                "inline-flex": "contêiner flex que flui com o texto", "grid": "os filhos diretos são posicionados em linhas e colunas",
                "none": "remove a caixa do layout e da árvore de acessibilidade", "contents": "a caixa some e os filhos sobem um nível"},
    "position": {"static": "padrão: segue o fluxo normal; top/left não têm efeito", "relative": "segue o fluxo e serve de referência para filhos absolute",
                 "absolute": "sai do fluxo e se posiciona pelo ancestral posicionado mais próximo",
                 "fixed": "presa à janela, continua visível ao rolar", "sticky": "rola normalmente e gruda ao atingir top/left"},
    "box-sizing": {"border-box": "width inclui padding e borda", "content-box": "padding e borda somam-se ao width"},
    "flex-direction": {"row": "itens lado a lado", "column": "itens um abaixo do outro", "row-reverse": "lado a lado, ordem invertida",
                       "column-reverse": "em coluna, ordem invertida"},
    "justify-content": {"center": "centraliza no eixo principal", "space-between": "primeiro e último nas pontas, espaço igual entre eles",
                        "space-around": "espaço igual ao redor de cada item", "space-evenly": "espaços idênticos, inclusive nas pontas",
                        "flex-start": "agrupa no início", "flex-end": "agrupa no fim", "start": "agrupa no início", "end": "agrupa no fim"},
    "align-items": {"center": "centraliza no eixo cruzado", "stretch": "estica os itens para a altura da linha",
                    "flex-start": "alinha pelo início", "start": "alinha pelo início", "baseline": "alinha pela linha de base do texto"},
    "overflow": {"hidden": "corta o que não cabe (e impede rolagem)", "auto": "mostra barra de rolagem só quando precisa",
                 "scroll": "sempre reserva barra de rolagem", "visible": "o conteúdo extra transborda a caixa"},
    "flex-wrap": {"wrap": "itens passam para a próxima linha quando faltar espaço", "nowrap": "todos numa linha só"},
    "text-align": {"center": "centraliza o texto", "left": "alinha à esquerda", "right": "alinha à direita",
                   "justify": "justifica (pode criar buracos no texto)", "start": "alinha no início do sentido da escrita"},
    "cursor": {"pointer": "mãozinha: algo clicável", "not-allowed": "ação indisponível", "text": "seleção de texto", "move": "arrastável"},
}
_UNIDADES = {"px": "pixels (fixo)", "rem": "relativo à fonte da raiz (16px por padrão)", "em": "relativo à fonte do próprio elemento",
             "%": "porcentagem do contêiner", "vw": "% da largura da janela", "vh": "% da altura da janela",
             "dvh": "% da altura visível da janela (considera a barra do navegador)", "fr": "fração do espaço livre do grid",
             "ch": "largura do caractere 0 da fonte", "s": "segundos", "ms": "milissegundos", "deg": "graus"}
_DECLARACAO = re.compile(r"(?<![\w-])(--[\w-]+|-?[a-z][\w-]*)\s*:\s*([^;{}]+?)\s*(?:;|$|(?=}))")
_SELETOR = re.compile(r"^\s*([^{}@]+?)\s*\{")


def especificidade(seletor: str) -> tuple[int, int, int]:
    """(ids, classes/atributos/pseudo-classes, elementos/pseudo-elementos) de um seletor simples."""
    s = re.sub(r":where\([^()]*\)", "", seletor)
    s = re.sub(r":(?:is|not|has)\(([^(),]*)[^()]*\)", r" \1", s)
    s = re.sub(r"\[[^\]]*\]", " .attr", s)
    s = re.sub(r"\"[^\"]*\"|'[^']*'", "", s)
    ids = len(re.findall(r"#[\w-]+", s))
    pseudo_el = len(re.findall(r"::[\w-]+", s)) + len(re.findall(r"(?<!:):(?:before|after|first-line|first-letter)\b", s))
    s = re.sub(r"::?[\w-]+(?:\([^()]*\))?", lambda m: " .x" if not m[0].startswith("::") and
               m[0][1:].split("(")[0] not in ("before", "after", "first-line", "first-letter") else " ", s)
    classes = len(re.findall(r"\.[\w-]+", s))
    elementos = len(re.findall(r"(?:^|[\s>+~(])([a-zA-Z][\w-]*)", s)) + pseudo_el
    return ids, classes, elementos


def _partes_seletor(seletor: str) -> list[str]:
    out = []
    if "," in seletor:
        out.append("vírgula: lista de seletores; a regra vale para cada um")
    if re.search(r"\s>\s|>", seletor):
        out.append("A > B: B filho direto de A")
    if "+" in seletor:
        out.append("A + B: B logo depois de A, com o mesmo pai")
    if "~" in seletor:
        out.append("A ~ B: todos os B depois de A, com o mesmo pai")
    if re.search(r"[\w\])]\s+[\w.#:\[*]", seletor.replace(" > ", ">").replace(" + ", "+").replace(" ~ ", "~")):
        out.append("A B (espaço): B em qualquer nível dentro de A")
    if "#" in seletor:
        out.append("#id: um elemento único; especificidade alta, difícil de sobrescrever")
    if re.search(r"\.[\w-]", seletor):
        out.append(".classe: todos os elementos com essa classe")
    if "*" in seletor:
        out.append("*: qualquer elemento")
    for pseudo in dict.fromkeys(re.findall(r"(?<!:):([\w-]+)", seletor)):
        texto = {"hover": "com o ponteiro do mouse em cima", "focus": "com foco", "focus-visible": "com foco pelo teclado",
                 "active": "enquanto é clicado", "first-child": "primeiro filho do pai", "last-child": "último filho do pai",
                 "nth-child": "posição entre os irmãos (2n = pares)", "not": "exceto os que casam com o argumento",
                 "checked": "marcado", "disabled": "desativado", "root": "a raiz do documento (html)",
                 "is": "qualquer um da lista", "where": "qualquer um da lista, sem somar especificidade",
                 "has": "que contém algo que casa com o argumento", "visited": "link já visitado", "invalid": "campo com valor inválido",
                 "empty": "sem filhos"}.get(pseudo)
        if texto:
            out.append(f":{pseudo}: {texto}")
    for pseudo in dict.fromkeys(re.findall(r"::([\w-]+)", seletor)):
        texto = {"before": "conteúdo gerado antes (precisa de content)", "after": "conteúdo gerado depois (precisa de content)",
                 "placeholder": "o texto do placeholder", "selection": "o trecho selecionado", "marker": "o marcador da lista"}.get(pseudo)
        if texto:
            out.append(f"::{pseudo}: {texto}")
    if re.search(r"\[[^\]]+\]", seletor):
        out.append("[atributo]: elementos com esse atributo (ou valor)")
    return out


def _resumo_valor(prop: str, valor: str) -> list[str]:
    notas = []
    puro = valor.replace("!important", "").strip()
    if prop in _VALORES and puro.lower() in _VALORES[prop]:
        notas.append(f"{puro}: {_VALORES[prop][puro.lower()]}")
    if prop in ("margin", "padding", "inset") and len(puro.split()) in (2, 3, 4) and "(" not in puro:
        lados = puro.split()
        ordem = {2: ("cima/baixo", "esquerda/direita"), 3: ("cima", "esquerda/direita", "baixo"),
                 4: ("cima", "direita", "baixo", "esquerda")}[len(lados)]
        notas.append(", ".join(f"{lado} {v}" for lado, v in zip(ordem, lados)))
        if prop == "margin" and len(lados) == 2 and lados[1] == "auto":
            notas.append("auto nas laterais centraliza um bloco com largura definida")
    unidades = sorted({u for u in re.findall(r"\d(?:\.\d+)?(px|rem|em|%|vw|vh|dvh|fr|ch|ms|s|deg)\b", puro)})
    if unidades:
        notas.append("unidades: " + "; ".join(f"{u} = {_UNIDADES[u]}" for u in unidades))
    for funcao, texto in (("repeat(", "repeat repete faixas"), ("minmax(", "minmax(mínimo, máximo) limita uma faixa"),
                          ("auto-fit", "auto-fit cria quantas colunas couberem"), ("clamp(", "clamp(mínimo, ideal, máximo)"),
                          ("calc(", "calc faz contas misturando unidades"), ("var(", "var(--nome) usa uma variável CSS"),
                          ("rgb(", "rgb(vermelho verde azul / opacidade)"), ("hsl(", "hsl(matiz saturação luminosidade)"),
                          ("linear-gradient(", "gradiente linear entre cores"), ("url(", "url() aponta para um arquivo, relativo ao CSS")):
        if funcao in puro:
            notas.append(texto)
    if re.search(r"#[0-9a-fA-F]{3,8}\b", puro):
        notas.append("#rrggbb: cor em hexadecimal (vermelho, verde, azul)")
    if prop in ("width", "min-width") and re.fullmatch(r"\d{3,}px", puro):
        notas.append("largura fixa grande pode criar rolagem horizontal no celular; considere max-width")
    return notas


def anotacoes_css(linha: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    linha = linha[:_LIMITE]
    texto = re.sub(r"/\*.*?\*/", "", linha)
    if texto.strip() == "}":
        return [("info", "} fecha o bloco de declarações aberto acima")]
    if "/*" in linha:
        out.append(("info", "/* … */ é comentário: ignorado pelo navegador"))
    at = re.match(r"\s*@([\w-]+)\s*([^{;]*)", texto)
    if at:
        nome, resto = at[1].lower(), at[2].strip()
        explic = {"media": "regras aplicadas só quando a condição vale", "import": "inclui outro CSS; deve vir antes das demais regras",
                  "font-face": "declara uma fonte própria", "keyframes": f"etapas da animação {resto}".strip(),
                  "supports": "aplica as regras se o navegador entende a condição", "layer": "camada da cascata",
                  "container": "regras pelo tamanho do contêiner (container-type no pai)"}.get(nome, "regra especial do CSS")
        out.append(("info", f"@{nome}: {explic}"))
        for cond, txt in (("min-width", "min-width: a partir desta largura"), ("max-width", "max-width: até esta largura"),
                          ("prefers-color-scheme", "prefers-color-scheme: tema claro/escuro do sistema"),
                          ("prefers-reduced-motion", "prefers-reduced-motion: pessoa pediu menos movimento"),
                          ("orientation", "orientation: retrato ou paisagem")):
            if cond in resto:
                out.append(("valor", txt))
        return out
    seletor = _SELETOR.match(texto)
    if seletor:
        alvo = seletor[1].strip()
        for parte in alvo.split(","):
            a, b, c = especificidade(parte.strip())
            out.append(("seletor", f"{parte.strip()} — especificidade ({a},{b},{c})"))
        out.extend(("seletor", p) for p in _partes_seletor(alvo))
        texto = texto[seletor.end():]
    for prop, valor in _DECLARACAO.findall(texto):
        prop = prop.lower()
        if prop.startswith("--"):
            out.append(("atributo", f"{prop}: {valor} — variável CSS; use com var({prop})"))
            continue
        base = re.sub(r"^-(?:webkit|moz|ms)-", "", prop)
        descr = _descricao(base)
        if descr:
            out.append(("atributo", f"{prop}: {valor} — {descr}"))
        elif not _conhecida(base) and (parecida := get_close_matches(base, sorted(_CONHECIDAS), n=1, cutoff=.8)):
            out.append(("alerta", f"{prop} não existe; você quis dizer {parecida[0]}?"))
        out.extend(("valor", nota) for nota in _resumo_valor(base, valor))
        if base != prop:
            out.append(("info", f"{prop}: prefixo de navegador antigo; confira se a forma sem prefixo ({base}) já basta"))
        if "!important" in valor:
            out.append(("info", "!important passa por cima da especificidade: reserve para casos como prefers-reduced-motion; "
                                "no resto, dificulta ajustes futuros."))
        if base == "outline" and valor.strip() in ("none", "0"):
            out.append(("alerta", "outline: none tira o indicador de foco do teclado; ofereça outro estilo de :focus-visible."))
        if base == "font-size" and re.fullmatch(r"\d+px", valor.strip()):
            out.append(("info", "font-size em px ignora o tamanho de fonte escolhido pela pessoa; rem acompanha a preferência."))
    return list(dict.fromkeys(out))


def _familia(prop: str) -> str | None:
    """margin-top -> margin, border-top-left-radius -> border: a propriedade de origem do nome longo."""
    partes = prop.split("-")
    for fim in range(len(partes) - 1, 0, -1):
        if "-".join(partes[:fim]) in _PROP_TEXTO or "-".join(partes[:fim]) in _PROP_GRUPO:
            return "-".join(partes[:fim])
    return None


def _conhecida(prop: str) -> bool:
    return prop in _CONHECIDAS or _familia(prop) is not None


_LADOS = {"top": "em cima", "right": "à direita", "bottom": "embaixo", "left": "à esquerda", "inline": "no eixo horizontal",
          "block": "no eixo vertical", "start": "no início", "end": "no fim", "width": "espessura", "style": "estilo",
          "color": "cor", "x": "no eixo x", "y": "no eixo y"}


def _descricao(prop: str) -> str | None:
    if prop.endswith("-radius"):
        prop_texto = _PROP_TEXTO["border-radius"]
        cantos = prop.removeprefix("border-").removesuffix("-radius").split("-")
        return prop_texto + (" (canto " + " ".join(_LADOS.get(c, c) for c in cantos) + ")" if cantos != ["border"] else "")
    if prop in _PROP_TEXTO:
        return _PROP_TEXTO[prop]
    partes = prop.split("-")
    for fim in range(len(partes) - 1, 0, -1):
        familia = "-".join(partes[:fim])
        if familia in _PROP_TEXTO:
            return f"{_PROP_TEXTO[familia]} ({', '.join(_LADOS.get(x, x) for x in partes[fim:])})"
    grupo = _PROP_GRUPO.get(prop) or _PROP_GRUPO.get(_familia(prop) or "")
    return _CSS[grupo][0].split(" · ")[0] if grupo else None


def css_da_linha(linha: str, por_id: dict) -> list:
    texto = re.sub(r"/\*.*?\*/", "", linha[:_LIMITE])
    chaves = []
    at = re.match(r"\s*@([\w-]+)", texto)
    if at:
        chaves.append({"media": "media", "keyframes": "movimento"}.get(at[1].lower(), "regras"))
    elif _SELETOR.match(texto):
        chaves.append("seletores")
    for prop, _valor in _DECLARACAO.findall(_SELETOR.sub("", texto, count=1) if _SELETOR.match(texto) else texto):
        prop = re.sub(r"^-(?:webkit|moz|ms)-", "", prop.lower())
        chave = "variaveis" if prop.startswith("--") else _PROP_GRUPO.get(prop) or _PROP_GRUPO.get(_familia(prop) or "")
        if prop in ("gap", "row-gap", "column-gap") and "grid" in texto:
            chave = "grid"  # gap vale para flex e grid; a linha diz qual
        if chave:
            chaves.append(chave)
    if "var(" in texto:
        chaves.append("variaveis")
    if re.search(r"(?<!:):(?:hover|focus|focus-visible|active|disabled|checked|invalid)\b", texto):
        chaves.append("interacao")
    if re.search(r"\d(?:rem|em|vw|vh|dvh|ch)\b|clamp\(|min\(|max\(", texto) and "medidas" not in chaves:
        chaves.append("medidas")
    return [por_id["css_ref_" + c] for c in dict.fromkeys(chaves) if "css_ref_" + c in por_id]


def linguagem_na_posicao(texto: str, linha: int, lang: str | None) -> str | None:
    """Num .html, linhas dentro de <script> são JavaScript e dentro de <style> são CSS; a linha da tag continua HTML."""
    if lang != "html":
        return lang
    linhas = texto.split("\n")
    antes = "\n".join(linhas[:linha])
    atual = linhas[linha] if linha < len(linhas) else ""
    for tag, destino in (("script", "javascript"), ("style", "css")):
        aberturas = list(re.finditer(rf"<{tag}\b([^>]*)>", antes, re.I))
        if not aberturas or antes.lower().rfind(f"</{tag}") > aberturas[-1].start():
            continue
        tipo = re.search(r"type\s*=\s*[\"']?([^\"'\s>]+)", aberturas[-1][1], re.I)
        if tag == "script" and tipo and tipo[1].lower() not in ("module", "text/javascript", "application/javascript"):
            return lang  # JSON, modelos e outros tipos não são JavaScript executável
        if re.match(rf"\s*</{tag}\b", atual, re.I):
            return lang
        return destino
    return lang
