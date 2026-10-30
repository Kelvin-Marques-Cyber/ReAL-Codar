"""Documentos, dados, build e contratos de API: LaTeX, Markdown, JSON, TOML, XML, Makefile, GraphQL, Protocol
Buffers e Terraform. Fontes consultadas em 29/10/2026."""

from codar.estudo.linguagens import Ficha

LATEX = Ficha(
    fonte="https://www.latex-project.org/help/documentation/",
    guia=("Preâmbulo, documento e comandos",
          r"O preâmbulo, antes de \begin{document}, escolhe a classe e os pacotes; o corpo tem o texto. Comandos começam "
          r"com \ e recebem argumentos entre chaves; % inicia um comentário. O PDF sai da compilação com pdflatex.",
          r"""\documentclass[12pt]{article}
\usepackage[brazil]{babel}
\usepackage[T1]{fontenc}

\begin{document}
\section{Introdução}
Olá! Este é o meu primeiro documento em \LaTeX.
\end{document}"""),
    ambiente="Confira pdflatex --version (TeX Live, MiKTeX ou MacTeX) e compile com pdflatex arquivo.tex (F5 no Studio). "
             "Rode duas vezes para atualizar sumário e referências; com BibTeX, rode pdflatex, bibtex e pdflatex duas "
             "vezes. Os pacotes usados (babel com português, amsmath, graphicx, booktabs, hyperref) precisam estar "
             "instalados na distribuição local.",
    aulas=(
        ("estrutura", "Documento, título e seções", "iniciante", "Documento e texto",
         r"O preâmbulo guarda a classe (article, report, book), os pacotes e os dados de \title, \author e \date. "
         r"\maketitle imprime o título; \section e \subsection numeram as seções e alimentam o \tableofcontents, "
         r"que só aparece atualizado depois da segunda compilação.",
         "Crie um documento com título, autor, sumário e três seções, uma delas com subseção. Compile duas vezes e "
         "confira se o sumário e a numeração acompanham suas mudanças.",
         r"""\documentclass{article}
\usepackage[brazil]{babel}
\title{Relatório de estudos}
\author{Ana Souza}
\date{\today}

\begin{document}
\maketitle
\tableofcontents

\section{Objetivo}
Registrar o que aprendi nesta semana.

\subsection{Metodologia}
Uma aula por dia, com exercícios.
\end{document}""",
         r"Escrever caracteres especiais sem escape: % começa um comentário e #, $, &, _, {, } e ~ têm significado "
         r"próprio; no texto use \%, \#, \$, \&, \_, \{ e \}.",
         "O sumário mostra as seções na ordem certa depois da segunda compilação? O log está sem avisos de "
         "referências indefinidas?"),
        ("listas", "Listas e destaque", "iniciante", "Documento e texto",
         r"itemize cria listas com marcadores, enumerate numera os itens e description associa um termo a uma "
         r"explicação. Cada item começa com \item e listas podem ser aninhadas. \textbf, \emph e \texttt destacam "
         r"palavras sem mudar a estrutura do texto.",
         r"Monte uma lista numerada de etapas com uma sublista de marcadores e uma lista de definições com três termos. "
         r"Destaque um termo com \emph e outro com \textbf.",
         r"""\begin{enumerate}
  \item Instalar a distribuição \TeX
  \item Escrever o documento
  \begin{itemize}
    \item usar \emph{seções}
    \item revisar o \textbf{sumário}
  \end{itemize}
\end{enumerate}

\begin{description}
  \item[Preâmbulo] classe e pacotes.
  \item[Corpo] o texto do documento.
\end{description}""",
         r'Escrever texto antes do primeiro \item ou esquecer o \end{itemize}: a compilação para com "missing \item" '
         r'ou "ended by \end{document}".',
         "A numeração recomeça em cada lista? As sublistas aparecem recuadas e com outro marcador?"),
        ("matematica", "Fórmulas e equações numeradas", "intermediario", "Matemática",
         r"Fórmulas no meio do texto ficam entre $ e $; equações destacadas e numeradas usam o ambiente equation. "
         r"Com o pacote amsmath, align alinha várias linhas pelo &, \frac monta frações e \sqrt raízes. \label dá "
         r"um nome à equação e \eqref cita o número dela entre parênteses.",
         r"Escreva a fórmula de Bhaskara numerada, cite-a no texto com \eqref e desenvolva um produto notável em duas "
         r"linhas alinhadas pelo sinal de igual com align.",
         r"""A área do círculo é $A = \pi r^2$.
\begin{equation}\label{eq:bhaskara}
  x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
\end{equation}
Pela equação~\eqref{eq:bhaskara}, as raízes dependem de $\Delta = b^2 - 4ac$.
\begin{align}
  (a+b)^2 &= (a+b)(a+b) \\
          &= a^2 + 2ab + b^2
\end{align}""",
         "Usar $$ ... $$ (forma antiga do TeX, com espaçamento inconsistente) ou deixar uma linha em branco dentro de "
         "equation, o que interrompe o modo matemático.",
         r"A equação tem número e o \eqref mostra o mesmo número? As linhas do align ficam alinhadas no sinal de igual?"),
        ("figuras_tabelas", "Figuras, tabelas e legendas", "intermediario", "Figuras e tabelas",
         r"figure e table são flutuantes: o LaTeX escolhe a melhor posição na página. \includegraphics (pacote graphicx) "
         r"insere a imagem; tabular monta a tabela com colunas l, c e r separadas por & e linhas terminadas em \\. "
         r"\caption cria a legenda numerada e \label, logo depois dela, permite citar com \ref.",
         r"Insira uma figura com metade da largura da linha e uma tabela de três colunas com booktabs. Cite as duas no "
         r"texto com \ref e confira os números depois de compilar duas vezes.",
         r"""\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.5\linewidth]{grafico.png}
  \caption{Vendas por mês.}
  \label{fig:vendas}
\end{figure}

\begin{table}[htbp]
  \centering
  \caption{Notas da turma.}
  \label{tab:notas}
  \begin{tabular}{lcr}
    \toprule
    Aluno & Turma & Nota \\
    \midrule
    Ana & A & 9,5 \\
    Bia & B & 8,0 \\
    \bottomrule
  \end{tabular}
\end{table}
A Tabela~\ref{tab:notas} resume a Figura~\ref{fig:vendas}.""",
         r"Colocar \label antes de \caption (a referência aponta para a seção, não para a figura) ou forçar a posição "
         r"de tudo, o que deixa páginas meio vazias.",
         "Os números de figura e tabela no texto batem com as legendas? A imagem existe no caminho indicado?"),
        ("macros", "Comandos próprios e links", "avancado", "Referências e macros",
         r"\newcommand cria um comando seu: o número entre colchetes diz quantos argumentos ele recebe, usados como #1 "
         r"e #2. Macros deixam a notação consistente no texto inteiro. O pacote hyperref transforma \ref, \cite e o "
         r"sumário em links, e \url mostra endereços sem quebrar caracteres especiais.",
         r"Crie \vetor{v} para vetores em negrito e \unidade{10}{m/s} para valores com unidade; depois troque a "
         r"definição de \vetor e veja o documento inteiro mudar de uma vez.",
         r"""\usepackage{hyperref}
\newcommand{\vetor}[1]{\mathbf{#1}}
\newcommand{\unidade}[2]{#1\,\mathrm{#2}}

A velocidade $\vetor{v}$ vale $\unidade{10}{m/s}$.
Veja \url{https://www.latex-project.org}.""",
         r'Definir com \newcommand um nome que já existe (erro "Command already defined") ou usar \renewcommand sem '
         r'saber o que o comando original fazia.',
         r"Ao mudar a definição de \vetor, todas as ocorrências mudam? Os links do PDF levam às seções certas?"),
        ("projeto", "Projeto: relatório completo", "avancado", "Projeto e revisão",
         r"Um relatório completo separa preâmbulo, resumo, capítulos e bibliografia. A classe report tem \chapter; "
         r"thebibliography lista as obras com \bibitem e \cite as cita no texto. Em trabalhos acadêmicos brasileiros, "
         r"o pacote abntex2 aplica as normas da ABNT; o exemplo usa só pacotes básicos.",
         "Escreva um relatório com resumo, dois capítulos, uma equação, uma tabela, uma figura e duas referências "
         "citadas. Compile até sumir o aviso de referências indefinidas e revise o PDF página por página.",
         r"""\documentclass[12pt,a4paper]{report}
\usepackage[brazil]{babel}
\usepackage[T1]{fontenc}
\usepackage{amsmath,graphicx,booktabs}
\usepackage{hyperref}

\title{Consumo de energia em casa}
\author{Ana Souza}

\begin{document}
\maketitle
\begin{abstract}
Medimos o consumo diário e comparamos com a conta de luz.
\end{abstract}
\tableofcontents

\chapter{Introdução}
O consumo segue a relação $E = P \cdot t$~\cite{halliday}.

\chapter{Resultados}
\begin{equation}\label{eq:energia}
  E = \sum_{i=1}^{n} P_i \, t_i
\end{equation}

\begin{thebibliography}{9}
  \bibitem{halliday} D. Halliday, R. Resnick. \emph{Fundamentos de Física}. LTC, 2016.
\end{thebibliography}
\end{document}""",
         r"Revisar só o PDF sem ler o .log: avisos de Overfull \hbox, referências indefinidas e fontes ausentes "
         r"apontam problemas reais.",
         "Sumário, equação citada e bibliografia aparecem sem ?? depois da segunda compilação? O log está sem erros?"),
    ),
    referencia=(
        ("documentclass", (r"\\documentclass\b",), r"\documentclass · classe do documento",
         "A primeira linha escolhe a classe: article para textos curtos, report para relatórios com capítulos, book "
         "para livros e beamer para apresentações. As opções entre colchetes ajustam a fonte (12pt), o papel (a4paper) "
         "e as colunas (twocolumn).",
         r"\documentclass[12pt,a4paper]{report}",
         r"Usar \chapter em article: a classe não tem capítulos."),
        ("pacotes", (r"\\(?:usepackage|RequirePackage)\b",), r"\usepackage · pacotes",
         "Pacotes acrescentam recursos e ficam no preâmbulo: babel adapta hifenização e nomes (Sumário, Figura) ao "
         "português, fontenc com T1 acerta acentos no PDF, amsmath amplia a matemática, graphicx insere imagens e "
         "hyperref cria links. Opções vão entre colchetes.",
         "\\usepackage[brazil]{babel}\n\\usepackage[T1]{fontenc}\n\\usepackage{amsmath,graphicx}",
         "Carregar hyperref antes dos outros pacotes: ele deve vir por último, salvo exceções documentadas."),
        ("secoes", (r"\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?(?:\[[^\]]*\])?\{",),
         "Seções e capítulos",
         r"\section{Título} numera a seção e a inclui no sumário; \subsection e \subsubsection descem um nível e "
         r"\chapter existe em report e book. A versão com asterisco (\section*) não é numerada nem vai para o sumário.",
         "\\section{Introdução}\n\\subsection{Motivação}\n\\section*{Agradecimentos}",
         r"Pular níveis (\subsubsection logo após \section) ou formatar títulos à mão com \textbf."),
        ("titulo", (r"\\(?:title|author|date|maketitle|tableofcontents|listoffigures|listoftables)\b",),
         "Título, autoria e sumário",
         r"\title, \author e \date guardam os dados no preâmbulo e \maketitle os imprime. \tableofcontents, "
         r"\listoffigures e \listoftables montam as listas a partir das seções e legendas; compile duas vezes para "
         r"atualizá-las.",
         "\\title{Relatório}\n\\author{Ana Souza \\and Bia Lima}\n\\date{\\today}\n\\begin{document}\n\\maketitle\n"
         "\\tableofcontents",
         "Esperar o sumário atualizado depois de uma única compilação."),
        ("listas", (r"\\(?:begin|end)\{(?:itemize|enumerate|description)\}", r"^\s*\\item\b"), "Listas e \\item",
         r"itemize usa marcadores, enumerate numera e description destaca o termo entre colchetes: \item[Termo] "
         r"explicação. Cada item começa com \item e uma lista pode conter outra.",
         "\\begin{itemize}\n  \\item Leite\n  \\item Pão\n\\end{itemize}",
         r"Escrever texto antes do primeiro \item."),
        ("equacoes", (r"\\(?:begin|end)\{(?:equation|align|gather|multline|split|cases)\*?\}", r"&\s*="),
         "Equações destacadas e align",
         r"equation destaca e numera uma equação; align (pacote amsmath) alinha várias linhas no ponto marcado com & "
         r"e quebra linhas com \\. Com asterisco (equation*, align*) não há numeração.",
         "\\begin{align}\n  f(x) &= x^2 + 2x + 1 \\\\\n       &= (x + 1)^2\n\\end{align}",
         "Deixar uma linha em branco dentro do ambiente: o LaTeX acusa \"Missing $ inserted\"."),
        ("matematica", (r"\$[^$]+\$", r"\\[\[(]",
                        r"\\(?:frac|sqrt|sum|prod|int|lim|cdot|times|pm|leq|geq|neq|infty|alpha|beta|gamma|delta|Delta|"
                        r"pi|theta|lambda|sigma|mathbf|mathrm|mathbb)\b"),
         "Matemática: $...$ e comandos",
         r"$...$ coloca a fórmula na linha do texto e \[ ... \] a destaca sem número. ^ faz expoente e _ índice; use "
         r"chaves para mais de um caractere (x^{10}). \frac{a}{b}, \sqrt{x}, \sum e letras gregas (\alpha, \pi, "
         r"\Delta) só funcionam no modo matemático.",
         "A média é $\\bar{x} = \\frac{1}{n}\\sum_{i=1}^{n} x_i$.\n\\[ \\int_0^1 x^2\\,dx = \\frac{1}{3} \\]",
         "Escrever x^10 esperando o expoente inteiro: sem chaves, só o 1 sobe."),
        ("rotulos", (r"\\(?:label|ref|eqref|pageref|autoref|cref)\{",), r"\label e \ref · referências cruzadas",
         r"\label{nome} marca a seção, figura, tabela ou equação logo antes dele; \ref{nome} escreve o número e "
         r"\pageref a página. Prefixos como fig:, tab: e eq: ajudam a organizar; use ~ antes de \ref para não "
         r"separar a palavra do número na quebra de linha.",
         "\\section{Método}\\label{sec:metodo}\nComo descrito na Seção~\\ref{sec:metodo}, na página~\\pageref{sec:metodo}.",
         "?? no PDF: o rótulo não existe ou falta compilar de novo."),
        ("figuras", (r"\\(?:begin|end)\{figure\*?\}", r"\\includegraphics\b", r"\\centering\b"),
         r"Figuras e \includegraphics",
         r"figure é um ambiente flutuante para imagens: [htbp] sugere as posições permitidas. \includegraphics "
         r"(pacote graphicx) aceita width=0.5\linewidth para ajustar a largura; PNG, JPG e PDF funcionam com pdflatex.",
         "\\begin{figure}[htbp]\n  \\centering\n  \\includegraphics[width=0.8\\linewidth]{mapa.png}\n"
         "  \\caption{Mapa da região.}\n\\end{figure}",
         "Dar o caminho com acentos ou espaços sem testar, ou usar imagens enormes que deixam o PDF pesado."),
        ("tabelas", (r"\\(?:begin|end)\{(?:table|tabular|tabularx|longtable)\*?\}", r"&.*\\\\\s*$",
                     r"\\(?:hline|toprule|midrule|bottomrule|cline|multicolumn)\b"),
         "Tabelas com tabular",
         r"tabular{lcr} define três colunas alinhadas à esquerda, ao centro e à direita; & separa as células e \\ "
         r"termina a linha. Com booktabs, \toprule, \midrule e \bottomrule desenham linhas com espaçamento correto.",
         "\\begin{tabular}{lr}\n  \\toprule\n  Item & Preço \\\\\n  \\midrule\n  Café & 12,00 \\\\\n  \\bottomrule\n"
         "\\end{tabular}",
         r"Linha com menos & do que colunas, ou esquecer o \\ no fim da linha."),
        ("legenda", (r"\\caption\{",), r"\caption · legendas",
         r"\caption{texto} cria a legenda numerada de figuras e tabelas, que aparece nas listas de figuras e tabelas. "
         r"O \label vem depois do \caption para apontar para o número certo.",
         "\\begin{table}[htbp]\n  \\caption{Resultados por mês.}\n  \\label{tab:resultados}\n\\end{table}",
         r"\label antes de \caption."),
        ("enfase", (r"\\(?:textbf|textit|emph|underline|texttt|textsc|footnote|url|href)\{",), "Ênfase, notas e links",
         r"\emph destaca (itálico, ou normal dentro de itálico), \textbf põe em negrito e \texttt usa fonte de "
         r"máquina. \footnote cria nota de rodapé numerada; \url e \href (hyperref) inserem endereços clicáveis.",
         "Um termo \\emph{importante} e um comando \\texttt{pdflatex}.\\footnote{Distribuído com o TeX Live.}\n"
         "Veja \\href{https://ctan.org}{o CTAN}.",
         "Sublinhar para destacar: em texto corrido, \\emph é a forma tipográfica usual."),
        ("macros", (r"\\(?:newcommand|renewcommand|providecommand|NewDocumentCommand|DeclareMathOperator)\b",),
         r"\newcommand · comandos próprios",
         r"\newcommand{\nome}[n]{definição} cria um comando com n argumentos, usados como #1, #2. "
         r"\renewcommand redefine um existente. Defina macros no preâmbulo para manter a notação igual em todo o texto.",
         "\\newcommand{\\R}{\\mathbb{R}}\n\\newcommand{\\abs}[1]{\\left|#1\\right|}\nSeja $x \\in \\R$ com $\\abs{x} < 1$.",
         "Usar \\newcommand com um nome que já existe."),
        ("bibliografia", (r"\\(?:cite[pt]?|bibitem|bibliography|bibliographystyle|printbibliography|addbibresource)\b",
                          r"\\(?:begin|end)\{thebibliography\}"),
         r"Citações e bibliografia",
         r"\cite{chave} cita uma obra. thebibliography lista as entradas com \bibitem{chave} dentro do documento; com "
         r"BibTeX, as obras ficam num arquivo .bib e \bibliography{arquivo} gera a lista. Para ABNT existe o abntex2cite.",
         "Segundo~\\cite{knuth}, o espaçamento importa.\n\\begin{thebibliography}{9}\n"
         "  \\bibitem{knuth} D. Knuth. \\emph{The \\TeX book}. Addison-Wesley, 1984.\n\\end{thebibliography}",
         r"Citar uma chave que não existe: aparece [?] e um aviso no log."),
        ("ambientes", (r"\\(?:begin|end)\{[\w*]+\}",), r"\begin e \end · ambientes",
         r"Um ambiente começa com \begin{nome} e termina com \end{nome}, e muda o comportamento do trecho: document "
         r"delimita o corpo, abstract o resumo, center centraliza e quote recua citações. Todo \begin precisa do seu \end.",
         "\\begin{center}\n  Texto centralizado.\n\\end{center}\n\\begin{quote}\n  Uma citação recuada.\n\\end{quote}",
         r"Fechar ambientes fora de ordem: o erro aponta \end que não corresponde ao \begin."),
        ("texto", (r"^\s*[^\s\\%$&{}]",), "Texto, parágrafos e caracteres especiais",
         r"Texto comum é escrito direto: uma linha em branco separa parágrafos e vários espaços contam como um. "
         r"Caracteres reservados se escrevem com barra: \%, \$, \&, \#, \_, \{ e \}. ~ é um espaço que não quebra a "
         r"linha; -- faz o traço de intervalo (1--10) e --- o travessão.",
         "Primeiro parágrafo do texto.\n\nSegundo parágrafo: custou R\\$ 10 e rendeu 5\\%.\nPáginas 1--10 --- leitura "
         "obrigatória.",
         "Esperar que Enter quebre a linha: só uma linha em branco cria parágrafo novo."),
    ),
)

MARKDOWN = Ficha(
    fonte="https://spec.commonmark.org/current/",
    guia=("Títulos, ênfase e listas",
          "Markdown é texto legível que vira HTML. # cria títulos, *itálico* e **negrito** marcam ênfase, - inicia "
          "itens de lista e uma linha em branco separa parágrafos.",
          "# Diário de estudos\n\nHoje estudei **Markdown** e *listas*.\n\n- Títulos começam com #\n"
          "- Links: [CommonMark](https://commonmark.org)"),
    ambiente="Salve como .md e veja o resultado num visualizador (VS Code, GitHub, GitLab) ou converta com pandoc "
             "arquivo.md -o arquivo.html. CommonMark é o núcleo; tabelas, tarefas e notas de rodapé são extensões do "
             "GitHub Flavored Markdown e podem não funcionar em outros sites.",
    aulas=(
        ("texto", "Parágrafos, ênfase e quebras", "iniciante", "Texto",
         "Parágrafos são separados por uma linha em branco; uma quebra simples de linha vira espaço. Para quebrar a "
         "linha sem novo parágrafo, termine-a com uma barra invertida. *itálico*, **negrito** e `código` marcam "
         "trechos; \\* mostra o asterisco literal.",
         "Escreva três parágrafos sobre um tema, com uma quebra de linha forçada, uma palavra em negrito, um comando "
         "entre crases e um asterisco literal escapado.",
         "Markdown é texto puro que vira HTML.\nEsta linha continua o mesmo parágrafo.\n\n"
         "Novo parágrafo com **negrito**, *itálico* e `código`.\\\nLinha quebrada com barra invertida.\n\n"
         "Use \\* para mostrar um asterisco.",
         "Esperar que Enter crie uma nova linha no resultado ou deixar espaços no fim da linha sem perceber que dois "
         "deles também quebram a linha.",
         "A visualização mostra três parágrafos? O asterisco escapado aparece literalmente?"),
        ("links", "Links e imagens", "intermediario", "Links e mídia",
         "[texto](endereço) cria um link e ![descrição](imagem.png) uma imagem: o texto entre colchetes vira o alt, "
         "lido por leitores de tela. Links de referência ([texto][id] e a definição [id]: url) deixam parágrafos "
         "longos legíveis. Caminhos relativos funcionam dentro do repositório.",
         "Monte um parágrafo com dois links de referência, uma imagem local com descrição útil e um link relativo "
         "para outro arquivo .md do projeto; confira se todos abrem.",
         "Leia o [guia oficial][commonmark] e a [especificação do GitHub][gfm].\n\n"
         "![Gráfico de barras com as vendas de janeiro a março](imagens/vendas.png)\n\n"
         "Veja também [Instalação](docs/instalacao.md) e <https://commonmark.org>.\n\n"
         "[commonmark]: https://commonmark.org/help/\n[gfm]: https://github.github.com/gfm/",
         "Deixar o alt vazio em imagens informativas ou escrever \"clique aqui\" como texto do link: o texto deve "
         "dizer para onde o link leva.",
         "Os links de referência aparecem como links no resultado? A descrição substitui bem a imagem?"),
        ("codigo_tabelas", "Código, tabelas e tarefas", "intermediario", "Links e mídia",
         "Três crases abrem um bloco de código; a palavra depois delas (python, bash) escolhe o realce. Tabelas e "
         "listas de tarefas são extensões do GitHub Flavored Markdown: | separa colunas, a linha com --- separa o "
         "cabeçalho e :---: centraliza, ---: alinha à direita.",
         "Documente um comando de instalação num bloco bash, uma tabela com alinhamentos diferentes e uma lista com "
         "duas tarefas feitas e uma pendente.",
         "```bash\npython -m pip install codar\n```\n\n| Linguagem | Extensão | Aulas |\n|:----------|:--------:|------:|\n"
         "| LaTeX | .tex | 6 |\n| Markdown | .md | 5 |\n\n- [x] Escrever o README\n- [ ] Revisar os links",
         "Esquecer a linha de separação da tabela (|---|) ou fechar o bloco de código com outra quantidade de crases.",
         "O bloco de código mantém os espaços e não interpreta * nem _? A tabela aparece com as colunas alinhadas?"),
        ("estrutura", "Documentos longos, citações e HTML", "avancado", "Organização",
         "Use um único # por documento e desça um nível por vez (##, ###): ferramentas geram sumário e âncoras a "
         "partir dos títulos. > cria citações, --- uma linha horizontal e [^1] uma nota de rodapé (GFM). HTML "
         "embutido funciona, mas muitos sites removem scripts e atributos por segurança.",
         "Organize um documento com três níveis de título sem pular níveis, uma citação, uma nota de rodapé e um "
         "link para uma seção do próprio documento (#nome-da-secao).",
         "# Manual do projeto\n\n## Instalação\n\n> **Atenção:** use Python 3.10 ou mais novo.\n\n"
         "Veja a seção [Uso](#uso) para os primeiros passos.[^versao]\n\n---\n\n## Uso\n\n<details>\n"
         "<summary>Opções avançadas</summary>\n\nTexto escondido até o leitor abrir.\n\n</details>\n\n"
         "[^versao]: Testado no Python 3.13.",
         "Pular de # para ### ou escolher títulos pelo tamanho da fonte: o sumário e a navegação por leitores de tela "
         "ficam confusos.",
         "O link [Uso](#uso) leva à seção? A nota de rodapé aparece no fim, com link de volta ao texto?"),
        ("projeto", "Projeto: README de um projeto real", "avancado", "Projeto e revisão",
         "Um bom README responde o que é, como instalar, como usar, como contribuir e sob qual licença. Comece pelo "
         "título e uma frase de descrição; mostre comandos copiáveis em blocos de código e use links relativos para a "
         "documentação. Confira o resultado num visualizador, como o do GitHub.",
         "Escreva o README de um projeto seu com descrição, requisitos, instalação, exemplo de uso, tabela de "
         "opções, contribuição e licença. Peça para alguém seguir só o README e anote onde a pessoa travou.",
         "# Calculadora de Notas\n\nCalcula a média ponderada de uma turma a partir de um arquivo CSV.\n\n"
         "## Instalação\n\n```bash\npython -m pip install calculadora-notas\n```\n\n## Uso\n\n```bash\n"
         "calcular-notas turma.csv --peso-prova 0.6\n```\n\n| Opção | Padrão | Descrição |\n|-------|-------:|-----------|\n"
         "| `--peso-prova` | 0.5 | Peso da prova na média |\n\n## Licença\n\nMIT, veja [LICENSE](LICENSE).",
         "Documentar comandos que não foram testados ou deixar o README desatualizado em relação ao código.",
         "Alguém que não conhece o projeto consegue instalar e rodar só com o README? Todos os links funcionam?"),
    ),
    referencia=(
        ("titulos", (r"^\s{0,3}#{1,6}(?:\s|$)",), "Títulos com #",
         "# até ###### criam títulos do nível 1 ao 6; o espaço depois de # é obrigatório. Muitos sites geram âncoras "
         "a partir do texto (## Uso vira #uso), permitindo links para a seção.",
         "# Projeto\n\n## Instalação\n\n### No Linux", "Escrever #Título sem espaço: vira texto comum."),
        ("enfase", (r"\*\*[^*\n]+\*\*|__[^_\n]+__", r"(?<![*\w\\])\*[^*\s][^*\n]*\*(?!\*)"), "Ênfase",
         "*texto* ou _texto_ deixam em itálico; **texto** ou __texto__ em negrito; ***texto*** faz os dois. No meio "
         "de palavras, prefira asteriscos: sublinhados dentro de palavras não marcam ênfase.",
         "Um termo *importante* e um aviso **obrigatório**.", "Deixar espaço depois do asterisco de abertura: * texto* "
                                                                  "não vira ênfase."),
        ("codigo", (r"^\s{0,3}(?:```|~~~)", r"`[^`\n]+`"), "Código em linha e blocos",
         "`trecho` marca código no meio do texto. Blocos começam e terminam com três crases (ou ~~~); a palavra após "
         "a abertura indica a linguagem para o realce. Dentro do bloco nada é interpretado como Markdown.",
         "Rode `python app.py` ou veja:\n\n```python\nprint(\"olá\")\n```",
         "Indentar o bloco com quatro espaços sem querer: vira bloco de código."),
        ("tarefas", (r"^\s*[-*+]\s+\[[ xX]\]\s",), "Listas de tarefas (GFM)",
         "- [ ] cria uma tarefa pendente e - [x] uma concluída. É extensão do GitHub Flavored Markdown: em issues e "
         "pull requests do GitHub as caixas podem ser marcadas clicando.",
         "- [x] Criar o repositório\n- [ ] Escrever os testes", "Esquecer o espaço entre os colchetes: [] não vira caixa."),
        ("listas", (r"^\s*(?:[-*+]|\d{1,9}[.)])\s",), "Listas",
         "-, * ou + iniciam itens com marcador; 1. ou 1) numeram. O número do primeiro item define o início e os "
         "seguintes contam a partir dele. Para aninhar, recue o subitem até o texto do item pai.",
         "1. Instale\n2. Configure\n   - edite config.toml\n   - defina a porta", "Recuar pouco o subitem e vê-lo "
                                                                                   "virar item do mesmo nível."),
        ("imagens", (r"!\[[^\]]*\]\([^)]*\)",), "Imagens e texto alternativo",
         "![descrição](caminho \"título opcional\") insere uma imagem. A descrição é o texto alternativo: diga o que a "
         "imagem informa, porque leitores de tela leem esse texto.",
         "![Tela inicial com o menu à esquerda](docs/tela.png)", "Descrever a imagem como \"imagem\" ou deixar vazio."),
        ("links", (r"(?<!!)\[[^\]]+\](?:\([^)]*\)|\[[^\]]*\])", r"^\s{0,3}\[[^\]^]+\]:\s*\S", r"<https?://[^>]+>"),
         "Links",
         "[texto](url) cria um link; [texto][id] com a definição [id]: url em outra linha é a forma de referência. "
         "<https://exemplo.org> mostra o próprio endereço. Caminhos relativos ([Guia](docs/guia.md)) apontam para "
         "arquivos do repositório.",
         "Leia o [manual](docs/manual.md) e o [site][site].\n\n[site]: https://commonmark.org",
         "Espaço entre ] e (: [texto] (url) não vira link."),
        ("tabelas", (r"^\s*\|.*\|\s*$",), "Tabelas (GFM)",
         "Cada linha começa e termina com |, que também separa as colunas. A segunda linha (|---|) separa o "
         "cabeçalho; dois-pontos definem o alinhamento: :--- esquerda, :---: centro e ---: direita.",
         "| Nome | Nota |\n|:-----|-----:|\n| Ana | 9,5 |", "Esquecer a linha de separação: vira texto comum."),
        ("citacoes", (r"^\s{0,3}>",), "Citações com >",
         "> no início da linha cria uma citação; >> aninha. Muitos sites usam citações com **Atenção:** ou com a "
         "sintaxe > [!NOTE] (GitHub) para avisos.",
         "> **Atenção:** faça backup antes de atualizar.", "Esquecer o > em linhas seguintes de um parágrafo longo "
                                                              "com quebras."),
        ("regua", (r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$",), "Linha horizontal",
         "Uma linha só com três ou mais -, * ou _ vira uma linha horizontal (<hr>). Deixe uma linha em branco antes: "
         "--- logo abaixo de um texto transforma esse texto em título.",
         "Fim da primeira parte.\n\n---\n\nSegunda parte.", "Colocar --- logo abaixo de um parágrafo sem linha em branco."),
        ("notas", (r"\[\^[^\]]+\]",), "Notas de rodapé (GFM)",
         "[^nome] marca a nota no texto e [^nome]: texto define o conteúdo, que vai para o fim do documento com um "
         "link de volta. É extensão do GitHub Flavored Markdown.",
         "O Markdown nasceu em 2004.[^gruber]\n\n[^gruber]: Criado por John Gruber.", "Repetir o mesmo nome em notas "
                                                                                     "diferentes."),
        ("html", (r"^\s*</?[a-zA-Z][\w-]*(?:\s[^>]*)?>",), "HTML dentro do Markdown",
         "Tags HTML funcionam onde o Markdown não tem recurso próprio, como <details> e <summary> para trechos "
         "recolhíveis. Deixe linhas em branco em volta do Markdown dentro do bloco HTML. Sites como o GitHub removem "
         "scripts e estilos.",
         "<details>\n<summary>Mostrar detalhes</summary>\n\nConteúdo em **Markdown**.\n\n</details>",
         "Esperar que <script> ou style funcionem em README publicados."),
        ("escape", (r"\\[\\`*_{}\[\]()#+\-.!|]", r"\\$"), "Escapes e quebra de linha",
         "Barra invertida antes de um caractere especial (\\*, \\_, \\#) o mostra literalmente. Uma barra no fim da "
         "linha força uma quebra dentro do mesmo parágrafo.",
         "Custa 5\\* (asterisco literal).\\\nSegunda linha do mesmo parágrafo.", "Esquecer o escape em nomes como "
                                                                                 "arquivo_teste_final."),
        ("paragrafo", (r"^\s*[A-Za-zÀ-ÿ0-9\"'(«]",), "Parágrafos",
         "Texto comum forma parágrafos; uma linha em branco separa um parágrafo do outro e quebras simples viram "
         "espaço. Linhas de comando dentro de blocos de código também são texto, mostrado sem interpretação.",
         "Primeiro parágrafo,\ncontinua aqui.\n\nSegundo parágrafo.", "Esperar que uma quebra simples apareça no "
                                                                       "resultado."),
    ),
)

JSON = Ficha(
    fonte="https://www.rfc-editor.org/rfc/rfc8259",
    guia=("Objetos, arrays e valores",
          "Um objeto JSON tem pares \"chave\": valor entre chaves; arrays ficam entre colchetes. Chaves e textos usam "
          "aspas duplas, e os valores podem ser texto, número, true, false, null, objeto ou array.",
          '{\n  "nome": "Ana",\n  "idade": 20,\n  "cursos": ["LaTeX", "Python"],\n  "ativo": true,\n  "apelido": null\n}'),
    ambiente="Salve como .json e valide com python -m json.tool arquivo.json (ou jq . arquivo.json). Editores mostram "
             "erros de sintaxe, mas só um schema ou o programa consumidor confere se os campos e tipos estão certos.",
    aulas=(
        ("tipos", "Valores, textos e números", "iniciante", "Valores",
         "JSON tem seis tipos de valor: texto entre aspas duplas, número, booleano (true ou false), null, objeto e "
         "array. Textos aceitam escapes como \\\", \\\\, \\n e \\u00e9. Números não têm zeros à esquerda, NaN nem "
         "Infinity; datas não têm tipo próprio e costumam ir como texto no formato ISO 8601.",
         "Descreva um produto com nome contendo aspas, preço decimal, estoque inteiro, data ISO 8601 em texto e um "
         "campo null. Valide com python -m json.tool produto.json.",
         '{\n  "nome": "Caderno \\"Universitário\\"",\n  "preco": 24.9,\n  "estoque": 120,\n  "lancamento": "2026-03-15",\n'
         '  "promocao": false,\n  "desconto": null\n}',
         "Usar aspas simples, vírgula depois do último item ou comentários: o JSON padrão rejeita os três.",
         "python -m json.tool aceita o arquivo? O preço continua número e a data continua texto ao ler o arquivo?"),
        ("aninhamento", "Objetos e arrays aninhados", "intermediario", "Estrutura",
         "Objetos agrupam campos relacionados e arrays guardam listas; os dois podem ser aninhados. Mantenha o mesmo "
         "formato em todos os itens de um array para quem consome o arquivo. A ordem das chaves de um objeto não tem "
         "significado, mas a ordem dos itens de um array tem.",
         "Represente um pedido com cliente (objeto), endereço dentro do cliente e itens (array de objetos com produto, "
         "quantidade e preço). Calcule o total lendo o arquivo com Python.",
         '{\n  "pedido": 1042,\n  "cliente": {\n    "nome": "Bia",\n    "endereco": {"cidade": "Recife", "uf": "PE"}\n'
         '  },\n  "itens": [\n    {"produto": "caneta", "quantidade": 3, "preco": 2.5},\n'
         '    {"produto": "caderno", "quantidade": 1, "preco": 24.9}\n  ]\n}',
         "Misturar formatos no mesmo array (ora objeto, ora texto) ou repetir a mesma chave no objeto: cada leitor "
         "trata isso de um jeito.",
         "Todos os itens têm os mesmos campos? O total calculado confere com a soma manual?"),
        ("schema", "Contratos com JSON Schema", "avancado", "Validação",
         "JSON Schema descreve, em JSON, o formato esperado: type, properties, required, minimum, enum e "
         "additionalProperties. Validar na entrada impede que dados errados avancem pelo sistema. O campo $schema "
         "indica a versão da especificação usada.",
         "Escreva o schema do produto da primeira aula com campos obrigatórios, preço mínimo zero e categorias "
         "permitidas por enum. Teste com um produto válido e três inválidos.",
         '{\n  "$schema": "https://json-schema.org/draft/2020-12/schema",\n  "type": "object",\n'
         '  "required": ["nome", "preco"],\n  "properties": {\n    "nome": {"type": "string", "minLength": 1},\n'
         '    "preco": {"type": "number", "minimum": 0},\n    "categoria": {"enum": ["papelaria", "livros"]}\n  },\n'
         '  "additionalProperties": false\n}',
         "Confiar só no schema para regras que envolvem vários campos ou esquecer additionalProperties e aceitar campos "
         "digitados errado.",
         "Um produto sem preço, com preço negativo e com campo desconhecido é recusado? O produto válido passa?"),
        ("projeto", "Projeto: configuração validada", "avancado", "Projeto e revisão",
         "Arquivos de configuração em JSON precisam de valores padrão, validação e mensagens de erro claras. Guarde "
         "segredos fora do arquivo, em variáveis de ambiente, e versione só um exemplo sem dados sensíveis. O exemplo "
         "configura um serviço com lista de usuários permitidos.",
         "Crie config.exemplo.json e o schema correspondente; escreva um programa que lê a configuração, valida, aplica "
         "padrões e explica cada erro com o caminho do campo (servidor.porta).",
         '{\n  "servidor": {"host": "127.0.0.1", "porta": 8080},\n  "registro": {"nivel": "info", "arquivo": '
         '"logs/app.log"},\n  "usuarios_permitidos": ["ana", "bia"],\n  "recursos": {"exportar_pdf": true, '
         '"limite_upload_mb": 10}\n}',
         "Colocar senhas ou tokens no JSON versionado ou aceitar porta fora de 1 a 65535 sem avisar.",
         "A configuração de exemplo passa no schema? Uma porta 0 ou um nível desconhecido gera mensagem com o campo?"),
    ),
    referencia=(
        ("objeto", (r"^\s*[{}],?\s*$", r'"\s*:\s*\{'), "Objetos { }",
         "Um objeto é uma coleção de pares \"chave\": valor entre chaves, separados por vírgula. As chaves são textos "
         "entre aspas duplas e não deveriam se repetir no mesmo objeto.",
         '{\n  "cidade": "Recife",\n  "uf": "PE"\n}', "Vírgula depois do último par."),
        ("par", (r'(?:^|[{,])\s*"(?:[^"\\]|\\.)*"\s*:',), "Pares \"chave\": valor",
         "Cada campo tem a chave entre aspas duplas, dois-pontos e o valor. O valor pode ser texto, número, true, "
         "false, null, objeto ou array.",
         '{"nome": "Ana", "idade": 20}', "Chave sem aspas ou com aspas simples: {nome: 'Ana'} não é JSON."),
        ("array", (r"^\s*[\[\]],?\s*$", r'"\s*:\s*\[', r"^\s*\{.*\},?\s*$"), "Arrays [ ]",
         "Um array guarda valores em ordem, entre colchetes e separados por vírgula. Itens podem ser objetos; "
         "mantenha o mesmo formato em todos para facilitar o consumo.",
         '{\n  "tags": ["json", "dados"],\n  "itens": [\n    {"id": 1},\n    {"id": 2}\n  ]\n}',
         "Esperar que a ordem das chaves de um objeto seja preservada; só a ordem do array é garantida."),
        ("textos", (r'"(?:[^"\\]|\\.)*\\["\\/bfnrtu]',), "Textos e escapes",
         "Textos ficam entre aspas duplas. \\\" escreve aspas, \\\\ a barra, \\n a quebra de linha, \\t a tabulação e "
         "\\u00e9 um caractere pelo código Unicode. Quebras de linha reais dentro do texto são proibidas.",
         '{"mensagem": "Linha 1\\nLinha 2", "citacao": "Ele disse \\"oi\\""}', "Colocar uma quebra de linha de verdade "
                                                                                "dentro do texto."),
        ("numeros", (r":\s*-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\s*[,}\]]?\s*$",), "Números",
         "Números são decimais, com sinal opcional, ponto como separador e expoente com e (1.5e3). Não há zeros à "
         "esquerda, NaN, Infinity nem tipo separado para inteiros; valores muito grandes podem perder precisão no "
         "JavaScript.",
         '{"preco": 24.9, "estoque": 120, "distancia": 1.2e6}', "Guardar identificadores enormes como número: use texto."),
        ("literais", (r":\s*(?:true|false|null)\b",), "true, false e null",
         "true e false são booleanos e null indica ausência de valor, sempre em minúsculas e sem aspas. \"false\" entre "
         "aspas é texto e conta como verdadeiro em muitas linguagens.",
         '{"ativo": true, "excluido": false, "apelido": null}', "Escrever True, None ou \"false\" entre aspas."),
        ("schema", (r'"\$(?:schema|id|ref|defs|comment)"',
                    r'"(?:type|required|properties|items|minimum|maximum|minLength|maxLength|enum|pattern|'
                    r'additionalProperties|format|const)"\s*:'), "JSON Schema",
         "Num schema, type define o tipo, properties descreve cada campo, required lista os obrigatórios e minimum, "
         "maxLength, pattern e enum restringem valores. additionalProperties: false recusa campos não previstos.",
         '{\n  "type": "object",\n  "required": ["email"],\n  "properties": {"email": {"type": "string", '
         '"format": "email"}}\n}',
         "Esperar que format valide sozinho: muitos validadores só conferem format quando configurados."),
    ),
)

TOML = Ficha(
    fonte="https://toml.io/en/v1.0.0",
    guia=("Chaves, tabelas e tipos",
          "TOML guarda configuração: cada linha chave = valor tem tipo explícito (texto entre aspas, número, booleano, "
          "data). [tabela] agrupa as chaves seguintes e # inicia um comentário.",
          'titulo = "Meu projeto"\nversao = 2\n\n[servidor]\nhost = "127.0.0.1"\nporta = 8080\ndebug = false'),
    ambiente="Salve como .toml e leia com tomllib (Python 3.11+): python -c \"import tomllib; "
             "print(tomllib.load(open('config.toml', 'rb')))\". Cada ferramenta (pip, Cargo, Poetry) confere só os "
             "campos que conhece; o TOML apenas garante a sintaxe.",
    aulas=(
        ("tipos", "Valores e tipos", "iniciante", "Valores",
         "Cada linha chave = valor tem um tipo explícito: texto entre aspas duplas (com escapes) ou simples (literal, "
         "sem escapes), inteiro, decimal, booleano, data e hora no formato ISO 8601 e array entre colchetes. # começa "
         "um comentário até o fim da linha.",
         "Descreva um evento com nome, caminho de pasta do Windows em texto literal, data e hora com fuso, lista de "
         "palestrantes e preço decimal; leia com tomllib e confira os tipos em Python.",
         'nome = "Semana de Tecnologia"\npasta = \'C:\\Eventos\\2026\'\ninicio = 2026-10-29T09:00:00-03:00\n'
         'palestrantes = ["Ana", "Bia", "Caio"]\npreco = 49.90\ngratuito = false',
         "Repetir uma chave ou definir a mesma tabela duas vezes: o TOML recusa o arquivo inteiro.",
         "tomllib devolve datetime com fuso para inicio e str para pasta, sem interpretar as barras?"),
        ("tabelas", "Tabelas e arrays de tabelas", "intermediario", "Estrutura",
         "[tabela] abre um grupo de chaves até a próxima tabela; [a.b] cria uma tabela dentro de outra e chaves com "
         "ponto (endereco.cidade = ...) fazem o mesmo numa linha. [[pratos]] acrescenta um item a um array de tabelas a "
         "cada ocorrência. Tabelas em linha usam { } numa única linha.",
         "Monte o cardápio de um restaurante com [restaurante], [restaurante.contato] e três [[pratos]] com nome, "
         "preço e alergênicos; leia o arquivo e liste os pratos com seus preços.",
         '[restaurante]\nnome = "Sabor da Terra"\nendereco.cidade = "Belém"\n\n[restaurante.contato]\n'
         'telefone = "+55 91 3000-0000"\n\n[[pratos]]\nnome = "Tacacá"\npreco = 28.0\nalergenicos = ["camarão"]\n\n'
         '[[pratos]]\nnome = "Açaí"\npreco = 15.5\nalergenicos = []',
         "Escrever [pratos] em vez de [[pratos]]: a segunda ocorrência da mesma tabela é erro, não um novo item.",
         "O array pratos tem dois itens e cada um mantém os próprios alergênicos?"),
        ("pyproject", "pyproject.toml e Cargo.toml", "avancado", "Ferramentas",
         "Ferramentas leem tabelas com nomes padronizados: em Python, [project] guarda nome, versão e dependências "
         "(PEP 621) e [build-system] diz como empacotar; em Rust, Cargo.toml usa [package] e [dependencies]. O TOML só "
         "valida a sintaxe; cada ferramenta confere os campos que entende.",
         "Escreva o pyproject.toml de um pacote com uma dependência por faixa de versão, um comando de terminal e um "
         "extra de testes; instale com python -m pip install -e . num ambiente virtual.",
         '[build-system]\nrequires = ["setuptools>=68"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\n'
         'name = "calculadora-notas"\nversion = "1.0.0"\nrequires-python = ">=3.10"\ndependencies = ["rich>=13,<15"]\n\n'
         '[project.optional-dependencies]\ntestes = ["pytest>=8"]\n\n[project.scripts]\n'
         'calcular-notas = "calculadora.cli:main"',
         "Colocar dependências numa tabela que a ferramenta ignora em silêncio, como [dependencies] num pyproject.toml.",
         "O pip instala o pacote e o comando calcular-notas fica disponível? O pytest só vem com o extra testes?"),
        ("projeto", "Projeto: configuração com valores padrão", "avancado", "Projeto e revisão",
         "Um programa que usa TOML deve ter padrões razoáveis, aceitar só as chaves conhecidas e explicar erros com o "
         "caminho da chave. tomllib (Python 3.11+) lê o arquivo aberto em modo binário; a escrita fica com outra "
         "biblioteca ou com o próprio programa.",
         "Escreva config.toml com [servidor], [registro] e [[tarefas]]; faça um programa que lê, aplica padrões, recusa "
         "chaves desconhecidas e mostra o caminho do erro (tarefas[1].intervalo_minutos).",
         '[servidor]\nhost = "127.0.0.1"\nporta = 8080\n\n[registro]\nnivel = "info"\n\n[[tarefas]]\nnome = "backup"\n'
         'intervalo_minutos = 60\n\n[[tarefas]]\nnome = "relatorio"\nintervalo_minutos = 1440',
         "Abrir o arquivo em modo texto (tomllib exige \"rb\") ou ignorar chaves desconhecidas, deixando passar erros "
         "de digitação.",
         "Uma chave escrita errado (prota em vez de porta) gera erro com o caminho completo da chave?"),
    ),
    referencia=(
        ("par", (r"^\s*[A-Za-z0-9_\"'-][\w\"'.-]*\s*=(?!=)",), "chave = valor",
         "Cada linha define uma chave e seu valor. Chaves simples usam letras, números, _ e -; outras vão entre aspas "
         "(\"nome completo\" = ...). O valor precisa ter um tipo: texto sem aspas é erro.",
         'nome = "Ana"\nidade = 20', "Escrever nome = Ana sem aspas."),
        ("tabela", (r"^\s*\[[^\[\]]+\]\s*(?:#.*)?$",), "[tabela]",
         "[nome] abre uma tabela: as chaves seguintes pertencem a ela até a próxima tabela. [a.b] é a tabela b dentro "
         "de a. Cada tabela só pode ser definida uma vez.",
         '[servidor]\nporta = 8080\n\n[servidor.tls]\nativo = true', "Definir [servidor] duas vezes no mesmo arquivo."),
        ("array_tabelas", (r"^\s*\[\[[^\[\]]+\]\]",), "[[array de tabelas]]",
         "[[nome]] acrescenta uma nova tabela a um array a cada ocorrência: é a forma de escrever uma lista de "
         "objetos, como produtos ou tarefas.",
         '[[produtos]]\nnome = "Caneta"\n\n[[produtos]]\nnome = "Lápis"', "Usar [produtos] e ter erro de tabela repetida."),
        ("chave_pontuada", (r"^\s*[\w-]+(?:\.[\w-]+)+\s*=",), "Chaves com ponto",
         "endereco.cidade = \"Belém\" cria a tabela endereco com a chave cidade, sem precisar de [endereco]. Útil para "
         "poucos campos; para muitos, uma tabela fica mais legível.",
         'endereco.cidade = "Belém"\nendereco.uf = "PA"', "Misturar chave com ponto e [tabela] para a mesma tabela."),
        ("textos", (r"=\s*(?:\"\"\"|'''|\"|')",), "Textos básicos e literais",
         "\"texto\" aceita escapes (\\n, \\t, \\\"); 'texto' é literal e mostra barras como estão, ideal para caminhos "
         "do Windows e expressões regulares. Três aspas permitem várias linhas.",
         "caminho = 'C:\\Users\\ana'\nsaudacao = \"Olá\\nmundo\"", "Usar aspas duplas num caminho com barras: \\U vira "
                                                                  "escape inválido."),
        ("datas", (r"=\s*\d{4}-\d{2}-\d{2}",), "Data e hora",
         "Datas e horas seguem o ISO 8601 sem aspas: 2026-10-29 é data, 09:30:00 hora e 2026-10-29T09:30:00-03:00 "
         "data e hora com fuso. tomllib devolve objetos date, time e datetime.",
         "entrega = 2026-11-30\nreuniao = 2026-10-29T14:00:00-03:00", "Colocar a data entre aspas e receber texto."),
        ("arrays", (r"=\s*\[",), "Arrays",
         "[1, 2, 3] guarda uma lista de valores; pode ocupar várias linhas e terminar com vírgula. Itens de tipos "
         "diferentes são permitidos no TOML 1.0, mas confundem quem lê.",
         'portas = [8080, 8081]\nnomes = [\n  "ana",\n  "bia",\n]', "Esperar que [tabela] dentro do array funcione: "
                                                                    "use [[array]]."),
        ("tabela_linha", (r"=\s*\{",), "Tabelas em linha",
         "{ chave = valor, outra = valor } escreve uma tabela pequena numa linha só. Ela não pode ser continuada em "
         "outras linhas nem receber chaves depois.",
         'ponto = { x = 1, y = 2 }', "Quebrar uma tabela em linha em várias linhas."),
        ("numeros_bool", (r"=\s*(?:[+-]?\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|[+-]?inf|[+-]?nan)\s*(?:#.*)?$",),
         "Números e booleanos",
         "Inteiros aceitam _ para separar milhares (1_000_000) e prefixos 0x, 0o e 0b; decimais usam ponto. true e "
         "false são minúsculos. inf e nan existem para decimais.",
         "porta = 8080\nlimite = 1_000_000\ntaxa = 0.15\nativo = true", "Escrever True ou números com vírgula decimal."),
    ),
)

XML = Ficha(
    fonte="https://www.w3.org/TR/xml/",
    guia=("Elementos, atributos e declaração",
          "Um documento XML tem um único elemento raiz. Toda tag aberta é fechada (ou autofechada com />), atributos "
          "ficam entre aspas e maiúsculas e minúsculas são diferentes.",
          '<?xml version="1.0" encoding="UTF-8"?>\n<biblioteca>\n  <livro id="1" idioma="pt">\n'
          '    <titulo>Dom Casmurro</titulo>\n    <autor>Machado de Assis</autor>\n  </livro>\n</biblioteca>'),
    ambiente="Salve como .xml e confira com xmllint --noout arquivo.xml (pacote libxml2-utils); com schema, "
             "xmllint --noout --schema regras.xsd arquivo.xml. Navegadores mostram a árvore e desenham arquivos .svg.",
    aulas=(
        ("bem_formado", "Documento bem formado", "iniciante", "Sintaxe",
         "Um XML bem formado tem um único elemento raiz, toda tag aberta é fechada na ordem inversa, atributos ficam "
         "entre aspas e nomes diferenciam maiúsculas. < e & no texto viram &lt; e &amp;; uma seção CDATA guarda um "
         "trecho sem interpretar marcação.",
         "Escreva uma receita com ingredientes, uma observação contendo < e & escapados e um trecho em CDATA; valide "
         "com xmllint --noout receita.xml.",
         '<?xml version="1.0" encoding="UTF-8"?>\n<receita nome="Bolo de fubá" porcoes="8">\n'
         '  <ingrediente quantidade="2" unidade="xícara">fubá</ingrediente>\n'
         '  <ingrediente quantidade="3" unidade="unidade">ovo</ingrediente>\n'
         '  <nota>Forno &lt; 200 °C &amp; 40 minutos</nota>\n'
         '  <codigo><![CDATA[if (temperatura < 200) { assar(); }]]></codigo>\n  <foto arquivo="bolo.jpg"/>\n</receita>',
         "Escrever & ou < soltos no texto, fechar tags fora de ordem (<b><i></b></i>) ou ter dois elementos na raiz.",
         "xmllint --noout não mostra erros? A nota aparece com < e & quando um parser lê o documento?"),
        ("namespaces", "Namespaces e SVG", "intermediario", "Vocabulários",
         "Namespaces evitam conflito entre vocabulários: xmlns=\"...\" define o padrão do elemento e de seus filhos, e "
         "xmlns:prefixo associa um prefixo a uma URI. SVG é XML com o namespace http://www.w3.org/2000/svg, e o "
         "navegador desenha os elementos.",
         "Desenhe um selo em SVG com um retângulo, um círculo e um texto; abra no navegador e depois mude cores e "
         "posições pelos atributos.",
         '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80">\n'
         '  <title>Selo de aprovado</title>\n'
         '  <rect x="5" y="5" width="110" height="70" rx="8" fill="#e8f5e9" stroke="#2e7d32"/>\n'
         '  <circle cx="30" cy="40" r="15" fill="#2e7d32"/>\n'
         '  <text x="55" y="45" font-size="14" fill="#1b5e20">OK</text>\n</svg>',
         "Esquecer o xmlns do SVG ao salvar como .svg: o navegador mostra o código em vez do desenho.",
         "O arquivo abre como imagem no navegador? O title aparece ao passar o mouse e ajuda leitores de tela?"),
        ("validacao", "Validação com XSD", "avancado", "Validação",
         "Um XML Schema (XSD) descreve elementos, atributos, tipos e quantidades permitidas: xs:element, "
         "xs:complexType, xs:sequence, minOccurs e maxOccurs. Validar recusa documentos bem formados mas incorretos, "
         "como um preço escrito com letras.",
         "Escreva o XSD do catálogo de livros com título, ano inteiro e preço decimal; valide um documento correto e "
         "dois incorretos com xmllint --noout --schema catalogo.xsd catalogo.xml.",
         '<?xml version="1.0" encoding="UTF-8"?>\n<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">\n'
         '  <xs:element name="catalogo">\n    <xs:complexType>\n      <xs:sequence>\n'
         '        <xs:element name="livro" maxOccurs="unbounded">\n          <xs:complexType>\n'
         '            <xs:sequence>\n              <xs:element name="titulo" type="xs:string"/>\n'
         '              <xs:element name="ano" type="xs:integer"/>\n              <xs:element name="preco" type="xs:decimal"/>\n'
         '            </xs:sequence>\n            <xs:attribute name="codigo" type="xs:string" use="required"/>\n'
         '          </xs:complexType>\n        </xs:element>\n      </xs:sequence>\n    </xs:complexType>\n'
         '  </xs:element>\n</xs:schema>',
         "Achar que bem formado significa válido: sem schema, um preço \"dez reais\" passa sem erro.",
         "O documento correto valida e os incorretos mostram o elemento e a linha do problema?"),
        ("projeto", "Projeto: catálogo validado e consultado", "avancado", "Projeto e revisão",
         "O projeto junta documento, schema e consultas. XPath seleciona partes do documento por caminho "
         "(//livro[ano>2000]/titulo). Ao ler XML de fora, use um parser que não resolva entidades externas, evitando o "
         "ataque XXE; em Python, a biblioteca defusedxml faz isso.",
         "Monte catalogo.xml com cinco livros e o XSD da aula anterior; valide e use xmllint --xpath para listar os "
         "títulos depois de 2000. Escreva um leitor em Python com defusedxml.",
         '<?xml version="1.0" encoding="UTF-8"?>\n<catalogo>\n  <livro codigo="L1">\n    <titulo>Dom Casmurro</titulo>\n'
         '    <ano>1899</ano>\n    <preco>39.90</preco>\n  </livro>\n  <livro codigo="L2">\n'
         '    <titulo>Torto Arado</titulo>\n    <ano>2019</ano>\n    <preco>59.90</preco>\n  </livro>\n</catalogo>',
         "Ler XML recebido da internet com um parser que expande entidades externas, expondo arquivos do servidor (XXE).",
         "xmllint --xpath \"//livro[ano>2000]/titulo/text()\" catalogo.xml mostra só Torto Arado? O documento valida "
         "contra o XSD?"),
    ),
    referencia=(
        ("declaracao", (r"^\s*<\?xml\b",), "<?xml ...?> · declaração",
         "A declaração opcional na primeira linha indica a versão do XML e a codificação do arquivo. Sem ela, vale "
         "UTF-8. Nada pode vir antes dela, nem espaços.",
         '<?xml version="1.0" encoding="UTF-8"?>\n<raiz/>', "Salvar em outra codificação do que a declarada."),
        ("xsd", (r"<xs:\w+",), "XML Schema (xs:)",
         "No XSD, xs:element declara um elemento, xs:complexType um conteúdo com filhos ou atributos, xs:sequence a "
         "ordem dos filhos e xs:attribute os atributos; type usa tipos prontos como xs:string, xs:integer e xs:date.",
         '<xs:element name="ano" type="xs:integer"/>', "Esquecer minOccurs=\"0\" em elementos opcionais."),
        ("namespace", (r"\bxmlns(?::[\w.-]+)?\s*=",), "Namespaces (xmlns)",
         "xmlns=\"uri\" define o namespace padrão do elemento e dos filhos; xmlns:p=\"uri\" associa o prefixo p, usado "
         "como <p:elemento>. A URI identifica o vocabulário e não precisa abrir no navegador.",
         '<lista xmlns="https://exemplo.org/lista" xmlns:x="https://exemplo.org/extra">\n  <x:item/>\n</lista>',
         "Usar um prefixo sem declará-lo."),
        ("svg", (r"<(?:svg|rect|circle|ellipse|line|polyline|polygon|path|text|g)\b",), "Elementos SVG",
         "svg define a área de desenho (width, height e viewBox); rect, circle, line e path desenham formas, text "
         "escreve e g agrupa. fill é o preenchimento e stroke o contorno.",
         '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">\n  <circle cx="5" cy="5" r="4" fill="teal"/>\n</svg>',
         "Esquecer viewBox e ver o desenho cortado ao mudar o tamanho."),
        ("elemento_texto", (r"<([\w:.-]+)(?:\s[^>]*)?>[^<]*</\1>",), "Elemento com texto",
         "<nome>conteúdo</nome> é um elemento com texto. O nome de fechamento repete o de abertura com /. Espaços "
         "dentro do texto fazem parte do conteúdo.",
         "<titulo>Dom Casmurro</titulo>", "Fechar com outro nome ou com maiúsculas diferentes: <Titulo></titulo>."),
        ("abertura", (r"^\s*<[\w:.-]+(?:\s[^>]*)?(?<!/)>\s*$",), "Abertura de elemento",
         "Uma tag de abertura sozinha na linha inicia um elemento com filhos; tudo até a tag de fechamento "
         "correspondente pertence a ele. A indentação é só para leitura.",
         "<livro>\n  <titulo>Iracema</titulo>\n</livro>", "Fechar os filhos fora de ordem."),
        ("fechamento", (r"^\s*</[\w:.-]+>\s*$",), "Fechamento de elemento",
         "</nome> fecha o elemento aberto mais recente com esse nome. Em XML não há fechamento opcional como em HTML.",
         "<lista>\n  <item>A</item>\n</lista>", "Esquecer um fechamento: o parser aponta a linha do elemento seguinte."),
        ("vazio", (r"<[\w:.-]+(?:\s[^>]*)?/>",), "Elemento vazio />",
         "<nome atributo=\"valor\"/> é um elemento sem conteúdo, equivalente a <nome></nome>. É comum para dados que "
         "cabem em atributos.",
         '<foto arquivo="bolo.jpg" largura="800"/>', "Escrever <foto> sem barra e sem fechamento."),
        ("atributos", (r"\s[\w:.-]+\s*=\s*\"[^\"]*\"",), "Atributos",
         "Atributos ficam na tag de abertura como nome=\"valor\", com aspas duplas ou simples. Cada nome aparece uma "
         "vez por elemento; dados com estrutura ou repetição ficam melhor como elementos filhos.",
         '<produto codigo="P1" moeda="BRL">', "Valor sem aspas: <produto codigo=P1>."),
        ("entidades", (r"&(?:lt|gt|amp|quot|apos|#\d+|#x[0-9a-fA-F]+);", r"<!\[CDATA\["), "Entidades e CDATA",
         "&lt; &gt; &amp; &quot; e &apos; escrevem < > & \" e '; &#233; escreve um caractere pelo código. "
         "<![CDATA[ ... ]]> guarda texto com < e & sem precisar escapar.",
         "<nota>A &amp; B &lt; C</nota>\n<script><![CDATA[if (a < b) {}]]></script>",
         "Usar &nbsp; ou &eacute;: essas entidades são do HTML e não existem em XML sem DTD."),
        ("doctype", (r"<!DOCTYPE\b",), "DOCTYPE e DTD",
         "<!DOCTYPE> associa uma DTD, forma antiga de validação que também pode definir entidades. Em documentos "
         "recebidos de fora, DTDs com entidades externas são o vetor do ataque XXE.",
         '<?xml version="1.0"?>\n<!DOCTYPE nota SYSTEM "nota.dtd">\n<nota/>',
         "Ler XML externo com entidades externas habilitadas."),
    ),
)

MAKEFILE = Ficha(
    fonte="https://www.gnu.org/software/make/manual/make.html",
    guia=("Alvos, dependências e receitas",
          "Uma regra diz como gerar um alvo a partir de dependências. As linhas da receita começam com TAB, e o make só "
          "refaz o alvo quando alguma dependência é mais nova que ele.",
          "programa: main.c\n\tgcc -Wall -o programa main.c\n\nlimpar:\n\trm -f programa\n\n.PHONY: limpar"),
    ambiente="Confira make --version (GNU Make). Rode make para o primeiro alvo, make alvo para um específico e "
             "make -n para ver os comandos sem executá-los. No Windows, use o make do MSYS2 ou do WSL.",
    aulas=(
        ("variaveis", "Variáveis e variáveis automáticas", "intermediario", "Regras",
         "Variáveis evitam repetir comandos: CC := gcc define na hora (:=), = expande só quando usada e ?= define "
         "apenas se ainda não existir. $(CC) usa o valor. Nas receitas, $@ é o alvo, $< a primeira dependência e $^ "
         "todas as dependências.",
         "Reescreva o Makefile do guia com CC, CFLAGS e as variáveis automáticas; rode make CFLAGS=-O0 e confira, com "
         "make -n, o comando que seria executado.",
         "CC := gcc\nCFLAGS ?= -Wall -Wextra -O2\nOBJETOS := main.o util.o\n\nprograma: $(OBJETOS)\n"
         "\t$(CC) $(CFLAGS) -o $@ $^\n\nmain.o: main.c util.h\n\t$(CC) $(CFLAGS) -c -o $@ $<",
         "Indentar a receita com espaços: o make acusa \"missing separator\". Receitas exigem TAB.",
         "make -n mostra o gcc com -O0 quando você passa CFLAGS na linha de comando? Alterar util.h recompila main.o?"),
        ("padroes", "Regras de padrão e funções", "intermediario", "Regras",
         "Uma regra de padrão como build/%.o: src/%.c vale para qualquer arquivo: % é o mesmo nome dos dois lados. "
         "$(wildcard src/*.c) lista arquivos e $(patsubst ...) troca prefixos e extensões. -include $(DEPS) lê as "
         "dependências de cabeçalhos geradas pelo gcc -MMD sem falhar na primeira vez.",
         "Monte um Makefile que compila todos os .c de src/ em build/, gera dependências com -MMD -MP e cria a pasta "
         "build/ quando precisar. Altere um .h e confira o que é recompilado.",
         "FONTES := $(wildcard src/*.c)\nOBJETOS := $(patsubst src/%.c,build/%.o,$(FONTES))\nDEPS := $(OBJETOS:.o=.d)\n\n"
         "build/programa: $(OBJETOS)\n\t$(CC) -o $@ $^\n\n"
         "build/%.o: src/%.c\n\t@mkdir -p $(dir $@)\n\t$(CC) -MMD -MP -c -o $@ $<\n\n-include $(DEPS)",
         "Listar arquivos à mão e esquecer um novo, ou não declarar a dependência dos cabeçalhos: o programa fica "
         "desatualizado sem aviso.",
         "Criar src/novo.c faz o make compilá-lo sem editar o Makefile? Alterar um .h recompila só quem o inclui?"),
        ("condicionais", "Alvos falsos, condicionais e paralelismo", "avancado", "Organização",
         ".PHONY marca alvos que não são arquivos (test, clean), para que rodem mesmo se existir um arquivo com o mesmo "
         "nome. ifeq e ifdef escolhem trechos conforme variáveis, como o sistema operacional. make -j4 executa receitas "
         "independentes em paralelo; dependências corretas garantem a ordem.",
         "Acrescente os alvos test e clean; use ifeq para trocar o nome do executável no Windows (.exe) e rode make -j4 "
         "conferindo que o resultado é igual ao de make sem -j.",
         "ifeq ($(OS),Windows_NT)\n  EXE := programa.exe\nelse\n  EXE := programa\nendif\n\n.PHONY: all test clean\n"
         "all: $(EXE)\n\n$(EXE): main.c\n\t$(CC) -o $@ $<\n\ntest: $(EXE)\n\t./$(EXE) --teste\n\nclean:\n\t$(RM) $(EXE)",
         "Esquecer .PHONY e ver \"'clean' is up to date\" porque existe um arquivo chamado clean na pasta.",
         "make -j4 e make sem -j produzem o mesmo resultado? make clean funciona mesmo com um arquivo chamado clean?"),
        ("projeto", "Projeto: build de um programa em C com testes", "avancado", "Projeto e revisão",
         "O Makefile do projeto descreve compilar, testar, instalar e limpar, com variáveis que o usuário pode "
         "sobrescrever (PREFIX, CFLAGS, DESTDIR). Um alvo help documenta os comandos. Rode make, make test e make "
         "install DESTDIR=/tmp/teste para conferir cada caminho.",
         "Monte o build de uma calculadora em C com src/ e build/; inclua all, test, install, clean e help. Peça a "
         "alguém para compilar só lendo a saída de make help.",
         "CC ?= cc\nCFLAGS ?= -Wall -Wextra -O2\nPREFIX ?= /usr/local\nFONTES := $(wildcard src/*.c)\n"
         "OBJETOS := $(FONTES:src/%.c=build/%.o)\n\n.PHONY: all test install clean help\nall: build/calc\n\n"
         "build/calc: $(OBJETOS)\n\t$(CC) $(CFLAGS) -o $@ $^\n\nbuild/%.o: src/%.c\n\t@mkdir -p build\n"
         "\t$(CC) $(CFLAGS) -c -o $@ $<\n\ntest: build/calc\n\t./build/calc 2 + 3 | grep -qx 5\n\n"
         "install: build/calc\n\tinstall -D -m 755 build/calc $(DESTDIR)$(PREFIX)/bin/calc\n\nclean:\n"
         "\t$(RM) -r build\n\nhelp:\n\t@echo \"make | make test | make install PREFIX=... | make clean\"",
         "Escrever caminhos absolutos fixos (/home/ana/...) ou instalar sem PREFIX e DESTDIR, o que impede empacotar o "
         "programa.",
         "make install DESTDIR=/tmp/teste instala dentro da pasta temporária? make test falha se a soma der errado?"),
    ),
    referencia=(
        ("phony", (r"^\.PHONY\s*:",), ".PHONY · alvos que não são arquivos",
         ".PHONY: test clean diz que esses alvos são nomes de tarefas, não arquivos: rodam sempre que chamados, mesmo "
         "que exista um arquivo com o mesmo nome, e não são verificados por data.",
         ".PHONY: test clean\ntest:\n\tpython -m pytest", "Deixar de declarar e ver o alvo ser ignorado."),
        ("padrao", (r"^[\w./$()-]*%[\w./-]*\s*:(?!=)",), "Regras de padrão (%)",
         "%.o: %.c é uma regra para qualquer par de arquivos com o mesmo nome base. Dentro da receita, $< é o .c e $@ "
         "o .o correspondentes. Prefira regras de padrão a repetir uma regra por arquivo.",
         "%.o: %.c\n\t$(CC) $(CFLAGS) -c -o $@ $<", "Usar * no lugar de %: * só funciona em listas de arquivos."),
        ("regra", (r"^[\w./$()-]+(?:\s+[\w./$()-]+)*\s*::?(?!=)",), "Regra: alvo, dependências e receita",
         "alvo: dependências declara o que o alvo precisa. O make compara datas: se uma dependência é mais nova que "
         "o alvo (ou o alvo não existe), executa a receita. O primeiro alvo do arquivo é o padrão do comando make.",
         "relatorio.pdf: relatorio.tex figuras.tex\n\tpdflatex relatorio.tex", "Esquecer uma dependência e ter um "
                                                                              "alvo desatualizado."),
        ("receita", (r"^\t",), "Receita (linhas com TAB)",
         "Cada linha da receita começa com TAB e roda num shell separado; para manter cd entre comandos, junte-os com "
         "&& na mesma linha. @ no início esconde o comando e - ignora falhas daquela linha.",
         "publicar:\n\t@echo publicando\n\tcd site && ./gerar.sh", "Indentar com espaços: missing separator."),
        ("variaveis", (r"^\s*[\w.-]+\s*(?::=|::=|\?=|\+=|!=|=)",), "Variáveis: =, :=, ?= e +=",
         "NOME := valor expande na hora; NOME = valor expande sempre que usada; ?= define só se ainda não existir "
         "(permite make CFLAGS=...); += acrescenta. Variáveis do ambiente também ficam disponíveis.",
         "CC := gcc\nCFLAGS ?= -O2\nCFLAGS += -Wall", "Usar = com $(shell ...) e executar o comando várias vezes."),
        ("automaticas", (r"\$[@<^?*|]", r"\$\([@<^*][DF]\)"), "Variáveis automáticas",
         "Dentro da receita, $@ é o alvo, $< a primeira dependência, $^ todas sem repetição e $? as mais novas que o "
         "alvo. $(@D) é a pasta do alvo.",
         "build/app: main.o util.o\n\t$(CC) -o $@ $^", "Usar $^ quando só a primeira dependência deve ir ao compilador."),
        ("funcoes", (r"\$\((?:wildcard|patsubst|subst|shell|foreach|notdir|dir|basename|addprefix|addsuffix|filter|"
                     r"filter-out|sort|word|if|call|eval)\s",), "Funções do make",
         "$(wildcard padrão) lista arquivos, $(patsubst de,para,lista) troca padrões, $(dir x) e $(notdir x) separam "
         "pasta e nome, $(shell comando) usa a saída de um comando e $(foreach v,lista,texto) repete.",
         "FONTES := $(wildcard src/*.c)\nNOMES := $(notdir $(FONTES))", "Esquecer que wildcard não procura em subpastas."),
        ("include", (r"^\s*-?include\b",), "include",
         "include arquivo lê outro Makefile no ponto em que aparece; -include ignora arquivos inexistentes, o que é "
         "útil para as dependências geradas pelo compilador (.d).",
         "-include $(OBJETOS:.o=.d)", "Usar include sem - para arquivos que só existem depois da primeira compilação."),
        ("condicionais", (r"^\s*(?:ifeq|ifneq|ifdef|ifndef|else|endif)\b",), "Condicionais",
         "ifeq (a,b) compara textos e ifdef VAR testa se a variável tem valor; else e endif fecham o bloco. São "
         "avaliados ao ler o Makefile, antes de qualquer receita.",
         "ifdef DEBUG\n  CFLAGS += -g\nendif", "Indentar ifeq com TAB: vira linha de receita."),
        ("uso_variavel", (r"\$\(\w+\)", r"\$\{\w+\}"), "Usar variáveis: $(NOME)",
         "$(NOME) ou ${NOME} inserem o valor da variável. Para um $ literal na receita (variável do shell), escreva "
         "$$NOME.",
         "saudacao:\n\techo \"Compilando com $(CC) para $$USER\"", "Escrever $NOME: o make lê só $N seguido de OME."),
    ),
)

GRAPHQL = Ficha(
    fonte="https://graphql.org/learn/",
    guia=("Tipos, campos e consultas",
          "O schema descreve tipos e campos; uma consulta pede exatamente os campos desejados e a resposta tem o mesmo "
          "formato. ! marca um campo obrigatório e [Tipo] uma lista.",
          "type Livro {\n  id: ID!\n  titulo: String!\n  autores: [String!]!\n}\n\ntype Query {\n  livro(id: ID!): Livro\n}"),
    ambiente="Salve o schema em .graphql. Valide e experimente com a biblioteca GraphQL da sua linguagem (graphql-js, "
             "graphql-core, gqlgen) ou com o GraphiQL do servidor. Instale as dependências antes de estudar offline.",
    aulas=(
        ("consultas", "Consultas, argumentos e variáveis", "intermediario", "Consultas",
         "Uma query pede campos de forma aninhada e a resposta tem o mesmo formato. Argumentos filtram "
         "(livro(id: \"1\")); variáveis como $id: ID! chegam separadas da consulta, em JSON. Um alias (recentes: "
         "livros(...)) renomeia o resultado.",
         "Escreva uma consulta que busca um livro por id usando variável, com título e autores, e outra parte com alias "
         "para os três livros mais recentes.",
         "query LivroPorId($id: ID!) {\n  livro(id: $id) {\n    titulo\n    autores\n  }\n"
         "  recentes: livros(ordem: RECENTES, limite: 3) {\n    titulo\n  }\n}",
         "Montar a consulta concatenando texto do usuário em vez de usar variáveis.",
         "A resposta tem exatamente os campos pedidos? A consulta funciona trocando só o valor da variável?"),
        ("mutacoes", "Mutações e tipos de entrada", "intermediario", "Escrita",
         "mutation altera dados e devolve o resultado da alteração. Tipos input agrupam os argumentos (input "
         "NovoLivro) e campos com ! são obrigatórios. Devolva o objeto criado para o cliente atualizar a tela sem nova "
         "consulta.",
         "Defina input NovoLivro e a mutation criarLivro; escreva a operação que cria um livro e pede de volta id e "
         "título. Envie um título vazio e confira a mensagem de erro.",
         "input NovoLivro {\n  titulo: String!\n  autores: [String!]!\n  ano: Int\n}\n\ntype Mutation {\n"
         "  criarLivro(dados: NovoLivro!): Livro!\n}\n\nmutation Criar($dados: NovoLivro!) {\n"
         "  criarLivro(dados: $dados) {\n    id\n    titulo\n  }\n}",
         "Usar query para alterar dados ou aceitar argumentos soltos em vez de um tipo input, o que dificulta evoluir "
         "a API.",
         "A mutation devolve o livro criado com id? Um título vazio é recusado com uma mensagem clara?"),
        ("schema", "Interfaces, enums, fragmentos e evolução", "avancado", "Schema",
         "enum limita valores; interface define campos comuns e implements obriga os tipos a tê-los; union reúne tipos "
         "sem campos em comum. Fragmentos (fragment ... on Tipo) reutilizam seleções e ... on separa campos por tipo. "
         "@deprecated avisa os clientes antes de remover um campo.",
         "Crie interface Midia com titulo, o tipo Filme, um enum Ordem e uma busca que devolve [Midia!]!. Escreva uma "
         "consulta com fragmento e ... on Filme para pedir a duração.",
         "enum Ordem {\n  RECENTES\n  TITULO\n}\n\ninterface Midia {\n  titulo: String!\n}\n\n"
         "type Filme implements Midia {\n  titulo: String!\n  duracaoMinutos: Int!\n"
         "  diretor: String @deprecated(reason: \"Use direcao.\")\n}\n\nfragment Basico on Midia {\n  titulo\n}\n\n"
         "query Busca {\n  busca(texto: \"mar\") {\n    ...Basico\n    ... on Filme {\n      duracaoMinutos\n    }\n  }\n}",
         "Remover ou mudar o tipo de um campo usado por clientes sem aviso: acrescente o novo e marque o antigo com "
         "@deprecated.",
         "A consulta traz a duração só para filmes? Ferramentas mostram o aviso de @deprecated ao usar diretor?"),
        ("projeto", "Projeto: API de biblioteca", "avancado", "Projeto e revisão",
         "O projeto define o schema completo de uma biblioteca: tipos, consultas, mutações e paginação por limite e "
         "cursor. Descrições entre aspas viram a documentação navegável da API. No servidor, limite a profundidade e o "
         "tamanho das consultas.",
         "Escreva o schema com Livro, Autor, consultas paginadas e a mutation emprestar; implemente um servidor de teste "
         "com uma biblioteca da sua linguagem e consultas que cubram sucesso e erro.",
         "\"\"\"Um livro do acervo.\"\"\"\ntype Livro {\n  id: ID!\n  titulo: String!\n  autor: Autor!\n"
         "  disponivel: Boolean!\n}\n\ntype Autor {\n  id: ID!\n  nome: String!\n"
         "  livros(limite: Int = 10, depois: String): [Livro!]!\n}\n\ntype Query {\n"
         "  livros(limite: Int = 10, depois: String): [Livro!]!\n  autor(id: ID!): Autor\n}\n\ntype Mutation {\n"
         "  emprestar(livroId: ID!, leitorId: ID!): Livro!\n}",
         "Permitir consultas aninhadas sem limite (autor, livros, autor...): uma única requisição sobrecarrega o "
         "servidor.",
         "Todas as consultas do cliente validam contra o schema? O servidor recusa uma consulta profunda demais?"),
    ),
    referencia=(
        ("tipos", (r"^\s*(?:type|input|interface|enum|union|scalar|schema|extend\s+type)\b",), "Definições de tipo",
         "type define um objeto com campos; input um objeto de entrada para argumentos; enum um conjunto de valores; "
         "interface campos comuns; union uma escolha entre tipos e scalar um tipo simples próprio (como Data).",
         "scalar Data\nunion Resultado = Livro | Filme\ntype Query {\n  hoje: Data!\n}",
         "Usar type como argumento de mutation: argumentos aceitam input, não type."),
        ("implements", (r"\bimplements\b",), "implements · interfaces",
         "type Filme implements Midia obriga Filme a ter todos os campos de Midia, com tipos compatíveis. Consultas "
         "sobre Midia podem pedir os campos comuns e usar ... on Filme para os específicos.",
         "interface Midia {\n  titulo: String!\n}\ntype Livro implements Midia {\n  titulo: String!\n  paginas: Int\n}",
         "Esquecer um campo da interface no tipo."),
        ("campo", (r"^\s*\w+\s*(?:\([^)]*\))?\s*:\s*\[?\w+",), "Campos, listas e !",
         "nome: Tipo declara um campo. ! torna obrigatório (nunca null); [Tipo] é uma lista. [String!]! é uma lista "
         "obrigatória de textos não nulos. Campos podem ter argumentos com valor padrão.",
         "type Autor {\n  nome: String!\n  apelidos: [String!]!\n  livros(limite: Int = 5): [Livro!]!\n}",
         "Marcar tudo com !: quando um dado faltar, o erro se espalha e anula o objeto pai inteiro."),
        ("operacao", (r"^\s*(?:query|mutation|subscription)\b",), "query, mutation e subscription",
         "query lê dados, mutation altera e subscription recebe atualizações em tempo real. Dar um nome à operação "
         "(query LivroPorId) ajuda a depurar e a medir no servidor.",
         "query Inicio {\n  livros(limite: 3) {\n    titulo\n  }\n}", "Escrever consultas anônimas em produção."),
        ("variaveis", (r"\$\w+",), "Variáveis $",
         "Variáveis são declaradas na operação ($id: ID!) e usadas nos argumentos ($id). Os valores chegam em JSON "
         "separado, o que evita montar consultas com texto do usuário.",
         "query ($id: ID!) {\n  livro(id: $id) {\n    titulo\n  }\n}", "Usar a variável sem declará-la na operação."),
        ("selecao", (r"^\s*\w+\s*(?:\([^)]*\))?\s*\{\s*$", r"^\s*\w+\s*$"), "Seleção de campos",
         "Numa consulta, cada linha pede um campo; campos que são objetos abrem chaves com a seleção dos subcampos. "
         "Campos não pedidos não vêm na resposta.",
         "{\n  livro(id: \"1\") {\n    titulo\n    autor {\n      nome\n    }\n  }\n}",
         "Pedir um campo objeto sem selecionar subcampos."),
        ("alias", (r"^\s*\w+\s*:\s*\w+\s*(?:\(|\{)",), "Aliases",
         "apelido: campo(...) renomeia o resultado, permitindo pedir o mesmo campo duas vezes com argumentos "
         "diferentes na mesma consulta.",
         "{\n  antigos: livros(ordem: TITULO) {\n    titulo\n  }\n  novos: livros(ordem: RECENTES) {\n    titulo\n  }\n}",
         "Pedir o mesmo campo duas vezes com argumentos diferentes sem alias: a consulta é recusada."),
        ("fragmentos", (r"^\s*fragment\b", r"^\s*\.\.\."), "Fragmentos",
         "fragment Nome on Tipo { campos } define uma seleção reutilizável, usada com ...Nome. ... on Tipo { } escolhe "
         "campos conforme o tipo real do resultado de uma interface ou union.",
         "fragment Resumo on Livro {\n  titulo\n}\nquery {\n  livros {\n    ...Resumo\n  }\n}",
         "Repetir a mesma seleção em vários lugares em vez de um fragmento."),
        ("diretivas", (r"@\w+",), "Diretivas @",
         "Diretivas ajustam a execução ou o schema: @include(if: $x) e @skip(if: $x) controlam campos na consulta; "
         "@deprecated(reason: \"...\") marca campos que serão removidos.",
         "query ($detalhes: Boolean!) {\n  livro(id: \"1\") {\n    titulo\n    resumo @include(if: $detalhes)\n  }\n}",
         "Remover um campo sem antes marcá-lo com @deprecated."),
        ("descricao", (r'^\s*"""', r'^\s*"[^"]*"\s*$'), "Descrições",
         "Textos entre aspas (ou três aspas, para várias linhas) logo antes de um tipo ou campo viram a documentação "
         "exibida por ferramentas como o GraphiQL.",
         "\"\"\"Livro disponível para empréstimo.\"\"\"\ntype Livro {\n  \"Título como na capa.\"\n  titulo: String!\n}",
         "Documentar com comentários #, que não aparecem na introspecção."),
    ),
)

PROTOBUF = Ficha(
    fonte="https://protobuf.dev/programming-guides/proto3/",
    guia=("Mensagens e números de campo",
          "Uma message define campos com tipo, nome e número. O número identifica o campo no formato binário: depois "
          "de publicado, não o reutilize nem o altere.",
          'syntax = "proto3";\n\npackage loja.v1;\n\nmessage Produto {\n  string nome = 1;\n  int64 preco_centavos = 2;\n'
          '  repeated string tags = 3;\n}'),
    ambiente="Confira protoc --version e gere código com protoc --python_out=. arquivo.proto (ou --java_out, "
             "--cpp_out; Go e gRPC usam plugins próprios). A biblioteca de runtime da linguagem precisa estar "
             "instalada para usar o código gerado.",
    aulas=(
        ("tipos", "Tipos, enums, mapas e oneof", "intermediario", "Mensagens",
         "Campos escalares têm tipos fixos (string, int32, int64, bool, double, bytes). Todo enum começa pelo valor 0, "
         "que deve significar não informado. map<string, string> cria um dicionário e oneof garante que só um dos "
         "campos esteja preenchido.",
         "Modele um Pagamento com enum de status iniciando em STATUS_UNSPECIFIED, um map de metadados e um oneof entre "
         "cartão e pix; gere o código com protoc --python_out=. e preencha os dois casos.",
         'syntax = "proto3";\n\nenum Status {\n  STATUS_UNSPECIFIED = 0;\n  STATUS_PAGO = 1;\n  STATUS_RECUSADO = 2;\n}\n\n'
         'message Pagamento {\n  string id = 1;\n  Status status = 2;\n  map<string, string> metadados = 3;\n'
         '  oneof meio {\n    string cartao_final = 4;\n    string chave_pix = 5;\n  }\n}',
         "Usar o valor 0 do enum para um estado real: em proto3, um campo não preenchido lê como 0 e fica impossível "
         "distinguir.",
         "Ao preencher chave_pix, cartao_final fica vazio? Um Pagamento sem status lê como STATUS_UNSPECIFIED?"),
        ("servicos", "Serviços gRPC", "intermediario", "Serviços",
         "service agrupa chamadas remotas: rpc Nome(Requisicao) returns (Resposta). Use uma mensagem própria para cada "
         "requisição e resposta, mesmo pequena, para poder acrescentar campos depois. stream na resposta permite "
         "receber vários itens na mesma chamada.",
         "Defina um serviço de pedidos com Criar, Obter e Acompanhar (resposta em stream); gere o código numa linguagem "
         "com plugin gRPC e escreva um cliente que chama Obter.",
         'syntax = "proto3";\n\npackage loja.v1;\n\nservice Pedidos {\n  rpc Criar(CriarRequest) returns (Pedido);\n'
         '  rpc Obter(ObterRequest) returns (Pedido);\n  rpc Acompanhar(ObterRequest) returns (stream Evento);\n}\n\n'
         'message CriarRequest { repeated string produtos = 1; }\nmessage ObterRequest { string id = 1; }\n'
         'message Pedido { string id = 1; repeated string produtos = 2; }\nmessage Evento { string descricao = 1; }',
         "Reaproveitar a mesma mensagem como entrada de várias rpcs: quando uma precisar de um campo novo, todas mudam.",
         "protoc gera o código sem erros? O cliente recebe vários eventos de Acompanhar até o servidor encerrar?"),
        ("evolucao", "Evolução compatível", "avancado", "Compatibilidade",
         "Mensagens antigas e novas precisam conviver. Acrescente campos com números novos; ao remover, reserve número e "
         "nome com reserved para ninguém reutilizar. optional permite saber se um escalar foi preenchido. Nunca troque o "
         "tipo nem o número de um campo publicado.",
         "Remova o campo telefone do Cliente reservando número e nome, acrescente email como campo novo e leia, com o "
         "código novo, uma mensagem gravada pela versão antiga.",
         'syntax = "proto3";\n\nmessage Cliente {\n  reserved 3;\n  reserved "telefone";\n  string nome = 1;\n'
         '  optional int32 idade = 2;\n  string email = 4;\n  string apelido = 5 [deprecated = true];\n}',
         "Reutilizar o número de um campo removido: dados antigos passam a ser lidos como outro campo, sem erro.",
         "O código gerado avisa ao usar apelido? Uma mensagem gravada pela versão antiga ainda é lida pela nova?"),
        ("projeto", "Projeto: contrato de uma API de pedidos", "avancado", "Projeto e revisão",
         "O contrato reúne pacote versionado (loja.v1), mensagens, enums e serviço, e é a fonte única para servidor e "
         "clientes. Gere o código no build, não à mão, e revise os .proto como qualquer código. Ferramentas como buf "
         "verificam estilo e mudanças incompatíveis.",
         "Escreva loja/v1/pedidos.proto completo, gere código Python com protoc, serialize um pedido em arquivo e leia "
         "de volta; depois faça uma mudança incompatível e veja a ferramenta acusar.",
         'syntax = "proto3";\n\npackage loja.v1;\n\nimport "google/protobuf/timestamp.proto";\n\n'
         'option java_package = "br.exemplo.loja.v1";\n\nmessage Item {\n  string produto_id = 1;\n  int32 quantidade = 2;\n'
         '  int64 preco_centavos = 3;\n}\n\nmessage Pedido {\n  string id = 1;\n  repeated Item itens = 2;\n'
         '  google.protobuf.Timestamp criado_em = 3;\n}\n\nservice Pedidos {\n  rpc Obter(ObterPedidoRequest) returns '
         '(Pedido);\n}\n\nmessage ObterPedidoRequest {\n  string id = 1;\n}',
         "Guardar dinheiro em double (arredondamentos) ou mudar o pacote de v1 para v2 sem manter a versão antiga para "
         "os clientes existentes.",
         "O pedido lido do arquivo é igual ao gravado? O total em centavos confere?"),
    ),
    referencia=(
        ("syntax", (r"^\s*(?:syntax|edition)\s*=",), "syntax · versão da linguagem",
         "syntax = \"proto3\"; na primeira linha escolhe as regras do proto3. Arquivos mais novos podem usar "
         "edition = \"2023\". Sem a linha, o protoc assume proto2 e avisa.",
         'syntax = "proto3";', "Omitir a linha e misturar regras de proto2 e proto3."),
        ("pacote", (r"^\s*(?:package|import|option)\b",), "package, import e option",
         "package evita conflito de nomes e costuma incluir a versão (loja.v1). import traz tipos de outro arquivo, "
         "como google/protobuf/timestamp.proto. option ajusta o código gerado (java_package, go_package).",
         'package loja.v1;\nimport "google/protobuf/timestamp.proto";\noption go_package = "exemplo.com/loja/v1";',
         "Mudar o package de um contrato publicado: os nomes completos mudam para os clientes."),
        ("message", (r"^\s*message\b",), "message",
         "message agrupa campos como uma estrutura. Mensagens podem ser aninhadas e usadas como tipo de outros campos. "
         "Nomes de mensagens usam CamelCase e de campos snake_case.",
         "message Endereco {\n  string cidade = 1;\n}\nmessage Cliente {\n  Endereco endereco = 1;\n}",
         "Criar uma mensagem gigante para tudo em vez de mensagens menores e reutilizáveis."),
        ("campo", (r"^\s*(?:repeated\s+|optional\s+)?[\w.]+\s+\w+\s*=\s*\d+",), "Campos e números",
         "tipo nome = número; declara um campo. Números de 1 a 15 ocupam um byte no formato binário: reserve-os para "
         "campos frequentes. repeated cria uma lista e optional registra se o valor foi preenchido.",
         "message Produto {\n  string nome = 1;\n  repeated string tags = 2;\n  optional int32 estoque = 3;\n}",
         "Renumerar campos para deixá-los em ordem: isso quebra a compatibilidade."),
        ("map", (r"\bmap\s*<",), "map<chave, valor>",
         "map<string, int32> estoque = 4; cria um dicionário. A ordem das entradas não é garantida e map não pode ser "
         "repeated.",
         "message Inventario {\n  map<string, int32> estoque = 1;\n}", "Depender da ordem das entradas do map."),
        ("enum", (r"^\s*enum\b", r"^\s*[A-Z][A-Z0-9_]*\s*=\s*\d+"), "enum",
         "enum lista valores nomeados; o primeiro deve ser 0 e representar não informado (TIPO_UNSPECIFIED). Prefixe os "
         "valores com o nome do enum para evitar conflitos no mesmo pacote.",
         "enum Cor {\n  COR_UNSPECIFIED = 0;\n  COR_AZUL = 1;\n}", "Começar o enum por um valor com significado real."),
        ("oneof", (r"^\s*oneof\b",), "oneof",
         "oneof agrupa campos dos quais só um pode estar preenchido: preencher um limpa os outros. O código gerado "
         "informa qual campo está ativo.",
         "message Contato {\n  oneof meio {\n    string email = 1;\n    string telefone = 2;\n  }\n}",
         "Usar repeated dentro de oneof: não é permitido."),
        ("service", (r"^\s*(?:service|rpc)\b",), "service e rpc",
         "service define chamadas remotas para gRPC: rpc Nome(Requisicao) returns (Resposta). stream antes do tipo "
         "permite enviar ou receber vários itens na mesma chamada.",
         "service Catalogo {\n  rpc Listar(ListarRequest) returns (stream Produto);\n}\n"
         "message ListarRequest { int32 limite = 1; }\nmessage Produto { string nome = 1; }",
         "Usar tipos escalares como parâmetro de rpc: entradas e saídas são sempre mensagens."),
        ("reserved", (r"^\s*reserved\b", r"\[deprecated\s*="), "reserved e deprecated",
         "reserved 3, 7 to 9; e reserved \"nome\"; impedem reutilizar números e nomes de campos removidos. "
         "[deprecated = true] marca um campo que ainda existe mas não deve mais ser usado.",
         "message Usuario {\n  reserved 2;\n  reserved \"senha\";\n  string login = 1;\n}",
         "Remover um campo sem reservar o número."),
    ),
)

TERRAFORM = Ficha(
    fonte="https://developer.hashicorp.com/terraform/language",
    guia=("Blocos, argumentos e saídas",
          "Arquivos .tf declaram o estado desejado em blocos: resource cria infraestrutura, variable recebe entradas e "
          "output expõe valores. terraform plan mostra as mudanças antes do apply.",
          'terraform {\n  required_version = ">= 1.5"\n}\n\nvariable "nome" {\n  type    = string\n  default = "estudos"\n}\n\n'
          'output "saudacao" {\n  value = "Olá, ${var.nome}"\n}'),
    ambiente="Confira terraform version (ou tofu version, do OpenTofu). Rode terraform init, fmt, validate, plan e "
             "apply numa pasta de teste. Providers são baixados no init: para estudar offline, prepare antes o cache "
             "de plugins (plugin_cache_dir) ou um espelho local.",
    aulas=(
        ("variaveis", "Variáveis, validação e locals", "intermediario", "Configuração",
         "variable declara uma entrada com type, default, description e validation; o valor vem de -var, de arquivos "
         ".tfvars ou da variável de ambiente TF_VAR_nome. locals calcula valores internos reutilizados. "
         "sensitive = true esconde o valor na saída do plan.",
         "Declare ambiente (dev ou prod, com validation), uma senha sensitive e um local com prefixo; crie dev.tfvars e "
         "prod.tfvars e compare terraform plan -var-file com cada um.",
         'variable "ambiente" {\n  type        = string\n  description = "dev ou prod"\n\n  validation {\n'
         '    condition     = contains(["dev", "prod"], var.ambiente)\n    error_message = "Use dev ou prod."\n  }\n}\n\n'
         'variable "senha_banco" {\n  type      = string\n  sensitive = true\n}\n\nlocals {\n'
         '  prefixo = "loja-${var.ambiente}"\n}',
         "Versionar .tfvars com senhas ou usar default em variáveis que deveriam ser informadas para cada ambiente.",
         "terraform plan recusa ambiente = \"teste\" com a mensagem da validação? A senha aparece como (sensitive)?"),
        ("recursos", "Providers, recursos e referências", "intermediario", "Recursos",
         "provider configura com quem o Terraform conversa (nuvem, Kubernetes, arquivos locais) e required_providers "
         "fixa origem e versão. resource \"tipo\" \"nome\" descreve um objeto; referências como local_file.equipe "
         "definem a ordem de criação. for_each cria um recurso por item.",
         "Use o provider hashicorp/local para criar um arquivo por equipe com for_each e um output com os caminhos; rode "
         "init, plan, apply e destroy numa pasta de teste.",
         'terraform {\n  required_providers {\n    local = {\n      source  = "hashicorp/local"\n      version = "~> 2.5"\n'
         '    }\n  }\n}\n\nresource "local_file" "equipe" {\n  for_each = toset(["ana", "bia"])\n'
         '  filename = "${path.module}/equipes/${each.key}.txt"\n  content  = "Equipe de ${each.key}"\n}\n\n'
         'output "arquivos" {\n  value = [for f in local_file.equipe : f.filename]\n}',
         "Usar count com uma lista que muda de ordem: remover o primeiro item recria os seguintes. Prefira for_each com "
         "chaves estáveis.",
         "terraform plan mostra dois arquivos a criar? Remover \"ana\" da lista destrói só o arquivo dela?"),
        ("modulos", "Módulos e estado", "avancado", "Organização",
         "O arquivo de estado liga o código aos recursos reais e pode conter segredos: guarde-o num backend remoto com "
         "trava e criptografia, nunca no Git. Módulos empacotam recursos reutilizáveis com variables e outputs. "
         "terraform fmt e validate conferem estilo e consistência antes do plan.",
         "Transforme os arquivos de equipe num módulo em modules/equipe com a variável nomes e o output arquivos; chame "
         "o módulo duas vezes e rode fmt, validate e plan.",
         'module "equipes_dev" {\n  source = "./modules/equipe"\n  nomes  = ["ana", "bia"]\n}\n\n'
         'module "equipes_prod" {\n  source = "./modules/equipe"\n  nomes  = ["caio"]\n}\n\n'
         'output "todos_os_arquivos" {\n  value = concat(module.equipes_dev.arquivos, module.equipes_prod.arquivos)\n}',
         "Versionar terraform.tfstate ou mudar recursos à mão no console: o estado deixa de refletir a realidade e o "
         "próximo apply desfaz a mudança.",
         "terraform validate passa? O plan mostra três arquivos, separados pelos dois módulos?"),
        ("projeto", "Projeto: infraestrutura local reproduzível", "avancado", "Projeto e revisão",
         "O projeto organiza versions.tf, variables.tf, main.tf e outputs.tf, fixa versões do Terraform e dos "
         "providers e versiona o .terraform.lock.hcl. O fluxo é fmt, validate, plan salvo em arquivo (-out) e apply "
         "desse plano depois de revisado por outra pessoa.",
         "Monte um projeto que gera a configuração de uma aplicação para dev e prod a partir de variáveis, com "
         "validação e outputs. Revise o plano salvo antes de aplicar e documente o fluxo no README.",
         'terraform {\n  required_version = ">= 1.5"\n  required_providers {\n    local = {\n'
         '      source  = "hashicorp/local"\n      version = "~> 2.5"\n    }\n  }\n}\n\nvariable "porta" {\n'
         '  type    = number\n  default = 8080\n  validation {\n    condition     = var.porta > 0 && var.porta < 65536\n'
         '    error_message = "A porta deve estar entre 1 e 65535."\n  }\n}\n\nresource "local_file" "config" {\n'
         '  filename = "${path.module}/saida/app.json"\n  content  = jsonencode({ porta = var.porta })\n}\n\n'
         'output "config" {\n  value = local_file.config.filename\n}',
         "Aplicar sem revisar o plano ou sem fixar versões: uma atualização do provider muda o comportamento sem aviso.",
         "plan -out=plano.tfplan seguido de apply plano.tfplan cria exatamente o que o plano mostrou? Porta 0 é recusada?"),
    ),
    referencia=(
        ("blocos", (r"^\s*(?:terraform|provider|resource|data|variable|output|locals|module|moved|import|check|"
                    r"backend)\b",), "Blocos do Terraform",
         "terraform configura versões e backend; provider conecta a uma plataforma; resource cria um objeto; data lê "
         "algo que já existe; variable recebe entradas; locals calcula valores; output expõe resultados e module "
         "reutiliza um conjunto de recursos.",
         'data "local_file" "versao" {\n  filename = "VERSION"\n}\n\noutput "versao" {\n  value = data.local_file.versao.content\n}',
         "Confundir data com resource: data só lê e nunca cria."),
        ("argumento", (r"^\s*[\w-]+\s*=(?!=)",), "Argumentos nome = valor",
         "Dentro de um bloco, nome = valor define um argumento. Os valores podem ser textos, números, booleanos, "
         "listas, mapas ou expressões com referências e funções. terraform fmt alinha os sinais de igual.",
         'resource "local_file" "nota" {\n  filename = "nota.txt"\n  content  = "Olá"\n}', "Usar aspas simples: o HCL só "
                                                                                          "aceita aspas duplas."),
        ("interpolacao", (r"\$\{",), "Interpolação ${...}",
         "\"texto ${expressão}\" insere um valor no texto, como \"loja-${var.ambiente}\". Para usar só a referência, "
         "escreva sem aspas: value = var.nome.",
         'locals {\n  nome = "app-${var.ambiente}-${terraform.workspace}"\n}', "Escrever \"${var.nome}\" quando "
                                                                               "var.nome basta."),
        ("referencias", (r"\b(?:var|local|module|data|path|each|count|terraform)\.\w+", r"\b[a-z]+_[a-z_]+\.\w+\.\w+"),
         "Referências",
         "var.x lê uma variável, local.x um local, module.m.saida o output de um módulo e tipo.nome.atributo um recurso. "
         "Cada referência cria uma dependência: o Terraform cria primeiro o que é referenciado.",
         'output "arquivo" {\n  value = local_file.nota.filename\n}', "Usar depends_on quando uma referência já cria a "
                                                                         "dependência."),
        ("meta", (r"^\s*(?:count|for_each|depends_on|lifecycle|provisioner)\b",), "Meta-argumentos",
         "count cria N cópias (count.index), for_each uma por chave (each.key, each.value), depends_on força uma ordem e "
         "lifecycle controla recriação (prevent_destroy, create_before_destroy).",
         'resource "local_file" "copia" {\n  count    = 2\n  filename = "copia-${count.index}.txt"\n  content  = "x"\n}',
         "Trocar count por for_each depois de aplicado sem planejar a migração com moved."),
        ("validacao", (r"^\s*(?:validation|condition|error_message|sensitive|nullable)\b",), "Validação e sensitive",
         "validation { condition = ...; error_message = \"...\" } recusa valores inválidos de uma variável no plan. "
         "sensitive = true esconde o valor na saída, mas ele continua gravado no estado.",
         'variable "regiao" {\n  type = string\n  validation {\n    condition     = startswith(var.regiao, "sa-")\n'
         '    error_message = "Use uma região da América do Sul."\n  }\n}',
         "Achar que sensitive criptografa o valor no estado."),
        ("funcoes", (r"\b(?:toset|tolist|tomap|contains|concat|jsonencode|jsondecode|yamlencode|lookup|merge|length|"
                     r"format|join|split|file|templatefile|startswith|try|coalesce)\(",), "Funções",
         "O Terraform tem funções prontas: toset e tolist convertem coleções, concat junta listas, merge junta mapas, "
         "jsonencode gera JSON, file lê um arquivo e templatefile preenche um modelo. Não é possível criar funções "
         "próprias em HCL.",
         'locals {\n  config = jsonencode(merge({ porta = 80 }, { debug = false }))\n}', "Montar JSON concatenando texto "
                                                                                       "em vez de jsonencode."),
        ("aninhado", (r"^\s*[\w-]+\s*\{\s*$", r"^\s*[\w-]+\s*=\s*\{\s*$"), "Blocos aninhados e mapas",
         "Dentro de um bloco, nome { ... } abre um bloco aninhado (validation, lifecycle, required_providers) e "
         "nome = { ... } define um mapa ou objeto como valor.",
         'terraform {\n  required_providers {\n    local = {\n      source = "hashicorp/local"\n    }\n  }\n}',
         "Confundir bloco aninhado com mapa: alguns provedores exigem um, outros o outro."),
        ("for", (r"\[\s*for\s+\w+", r"\{\s*for\s+\w+"), "Expressões for",
         "[for x in lista : transformação] cria uma lista e {for k, v in mapa : k => v} um mapa. Um if no final "
         "filtra os itens.",
         'locals {\n  maiusculas = [for n in ["ana", "bia"] : upper(n)]\n}', "Usar for para criar recursos: isso é "
                                                                             "trabalho do for_each."),
    ),
)

FICHAS = {"latex": LATEX, "markdown": MARKDOWN, "json": JSON, "toml": TOML, "xml": XML, "makefile": MAKEFILE,
          "graphql": GRAPHQL, "protobuf": PROTOBUF, "terraform": TERRAFORM}
