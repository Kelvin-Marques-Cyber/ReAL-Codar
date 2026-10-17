"""Percursos offline: aulas nativas, ordem explícita e projetos de revisão.

Um percurso organiza o material disponível; não certifica domínio da linguagem.
As referências são complementares: explicações, código e práticas estão no pacote.
Exemplos de navegador indicam seu ambiente no próprio texto.
"""

from dataclasses import dataclass
import unicodedata

from codar.estudo.ampliado import FONTES


@dataclass(frozen=True)
class Aula:
    chave: str
    titulo: str
    nivel: str
    modulo: str
    texto: str
    pratique: str
    codigo: str
    erro: str
    confira: str


# Cada aula tem um objetivo e uma verificação próprios. Não geramos traduções
# do mesmo texto para simular uma cobertura que a linguagem não tem.
AULAS = {
    'html': [
        Aula('estrutura', 'Documento, regiões e hierarquia', 'iniciante', 'Documento e navegação',
             'Abra o arquivo .html no navegador. O doctype ativa o modo padrão; lang informa a língua. '
             'header, nav, main e footer dão significado às regiões. Um h1 nomeia a página e h2 inicia uma seção.',
             'Crie uma página de estudos com navegação por âncoras, um h1 e duas seções com h2. Percorra os links com Tab.',
             '<!doctype html>\n<html lang="pt-BR">\n<head><meta charset="utf-8"><title>Estudos</title></head>\n'
             '<body><header><nav><a href="#aulas">Aulas</a></nav></header>\n'
             '<main><h1>Meus estudos</h1><section id="aulas"><h2>Aulas</h2><p>Uma por dia.</p></section></main>\n'
             '<footer><p>Projeto pessoal</p></footer></body></html>',
             'Escolher títulos apenas pelo tamanho visual ou criar vários main visíveis.',
             'Os títulos descrevem a hierarquia? O link muda o fragmento da URL e alcança a seção?'),
        Aula('metadados', 'Metadados, idioma e descoberta', 'iniciante', 'Documento e navegação',
             'title identifica a aba e deve descrever a página. A descrição resume o conteúdo para ferramentas de busca, '
             'que podem escolher outro resumo. viewport permite usar a largura do dispositivo; não bloqueie o zoom.',
             'Dê a duas páginas títulos e descrições diferentes. Teste largura estreita e zoom de 200%.',
             '<!doctype html>\n<html lang="pt-BR"><head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
             '<meta name="description" content="Exercícios locais de HTML com exemplos de formulários.">\n'
             '<title>Formulários acessíveis — Caderno de estudos</title>\n</head>\n'
             '<body><main><h1>Formulários acessíveis</h1><p>Aprenda com exemplos.</p></main></body></html>',
             'Repetir palavras-chave sem conteúdo correspondente ou impedir o zoom com user-scalable=no.',
             'A aba tem um título específico? A descrição corresponde ao texto realmente apresentado?'),
        Aula('imagens', 'Imagens, alternativas e dimensões', 'iniciante', 'Conteúdo acessível',
             'img precisa de uma alternativa adequada ao propósito: alt descreve informação; alt="" marca decoração. '
             'width e height reservam espaço. figure e figcaption associam uma legenda à mídia. Use uma imagem local sua.',
             'Coloque uma foto informativa e uma decoração. Desative imagens e confira se a informação permanece.',
             '<figure>\n  <img src="horta.jpg" alt="Três vasos de manjericão junto à janela" width="640" height="480">\n'
             '  <figcaption>Horta no primeiro mês.</figcaption>\n</figure>\n'
             '<img src="divisor.svg" alt="" width="120" height="8">',
             'Repetir o nome do arquivo no alt ou descrever decoração que não transmite informação.',
             'Sem a foto, é possível entender o que ela acrescenta? Os caminhos apontam a arquivos existentes?'),
        Aula('tabelas', 'Tabelas de dados com cabeçalhos', 'intermediario', 'Conteúdo acessível',
             'Use table para dados tabulares. caption dá contexto; th com scope associa cabeçalhos à linha ou coluna. '
             'thead e tbody organizam grupos. Layout visual deve ficar no CSS.',
             'Monte uma tabela de aulas com assunto e duração. Leia cada célula junto de seu cabeçalho.',
             '<table><caption>Plano semanal</caption>\n<thead><tr><th scope="col">Assunto</th>'
             '<th scope="col">Minutos</th></tr></thead>\n<tbody><tr><th scope="row">HTML</th><td>30</td></tr>'
             '<tr><th scope="row">CSS</th><td>40</td></tr></tbody></table>',
             'Usar tabela para posicionar a página ou usar td onde há um cabeçalho.',
             'Cada coluna tem nome e a legenda explica o conjunto de dados?'),
        Aula('midia', 'Áudio, vídeo e alternativas textuais', 'intermediario', 'Conteúdo acessível',
             'controls expõe os controles nativos. source oferece um arquivo de mídia; track fornece legendas WebVTT. '
             'Inclua transcrição para áudio e descrição das informações visuais relevantes. Forneça os arquivos locais indicados.',
             'Adicione um vídeo curto seu, crie legendas.vtt e uma transcrição em HTML. Teste pausa e volume pelo teclado.',
             '<video controls width="640" preload="metadata">\n  <source src="aula.mp4" type="video/mp4">\n'
             '  <track kind="captions" src="legendas.vtt" srclang="pt-BR" label="Português" default>\n'
             '  <a href="aula.mp4">Baixar vídeo</a>\n</video>\n'
             '<details><summary>Transcrição</summary><p>Olá! Hoje vamos criar uma página.</p></details>',
             'Reproduzir áudio automaticamente ou fornecer legendas que não acompanham a fala.',
             'As legendas são selecionáveis? Todo o conteúdo pode ser compreendido pela transcrição?'),
        Aula('integracao', 'Integrar CSS e JavaScript com melhoria progressiva', 'intermediario', 'Integração e comportamento',
             'O HTML deve apresentar conteúdo útil antes do JavaScript. style altera aparência; um script no fim do body '
             'encontra os elementos já analisados. Em projetos maiores use link para CSS e script defer para arquivos externos.',
             'Separe o estilo em estilo.css e o script em app.js usando link e defer. Teste a página também com JavaScript desativado.',
             '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>Contador</title>\n'
             '<style>button { padding: .5rem; } output { font-weight: bold; }</style></head>\n'
             '<body><main><h1>Contador</h1><button id="somar" type="button">Somar</button> '
             '<output id="total" aria-live="polite">0</output><p>Pratique eventos de clique.</p></main>\n'
             '<script>let n = 0; document.querySelector("#somar").addEventListener("click", () => { '
             'document.querySelector("#total").textContent = String(++n); });</script></body></html>',
             'Usar um div clicável sem teclado ou depender de JavaScript para apresentar todo o texto básico.',
             'O botão funciona com Enter e Espaço e o número aumenta uma vez por ativação?'),
        Aula('projeto', 'Projeto: caderno de estudos acessível', 'avancado', 'Projeto e revisão',
             'Combine documento, metadados, navegação, conteúdo e formulário. O projeto é uma avaliação manual: '
             'testes estruturais não demonstram acessibilidade ou qualidade visual por si sós.',
             'Construa duas páginas locais ligadas por nav: plano e cadastro. Inclua tabela com caption, imagem com alternativa, '
             'formulário com labels, CSS externo e botão com evento. Revise teclado, zoom, caminhos e conteúdo sem script. '
             'Execute study check html_formulario no cadastro para verificar os critérios estruturais do desafio.',
             '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>Cadastro de estudos</title></head>\n'
             '<body><nav><a href="plano.html">Plano de estudos</a></nav><main><h1>Cadastro</h1>\n'
             '<form><label for="email">Email</label><input id="email" name="email" type="email" required>\n'
             '<button type="submit">Cadastrar</button></form></main></body></html>',
             'Marcar o projeto como validado apenas porque o HTML abre ou um teste estrutural passou.',
             'Liste três defeitos encontrados pela revisão manual e como os corrigiu. Explique cada escolha semântica.'),
    ],
    'css': [
        Aula('cascata', 'Seletores, cascata e especificidade', 'iniciante', 'Fundamentos visuais',
             'Um seletor escolhe os elementos. A cascata resolve regras concorrentes considerando origem, importância, '
             'camadas e especificidade; a ordem decide empates. Inspecione estilos computados nas ferramentas do navegador.',
             'Aplique as regras a <p class="aviso">Olá</p>. Troque a ordem, depois use p.aviso, e explique a cor calculada.',
             'p { color: #222; }\n.aviso { color: #8b0000; }\np.aviso { border-left: 3px solid currentColor; padding-left: .5rem; }',
             'Usar !important para cada conflito sem entender a regra que está vencendo.',
             'Você identifica o seletor vencedor e o motivo no painel de estilos computados?'),
        Aula('caixa', 'Box model e tamanhos previsíveis', 'iniciante', 'Fundamentos visuais',
             'No modelo content-box, padding e borda somam-se à largura declarada. border-box inclui ambos. '
             'max-width limita a largura e margin-inline: auto centraliza quando há espaço.',
             'Crie uma div.cartao com conteúdo. Compare a largura total antes e depois de border-box em uma janela estreita.',
             '* { box-sizing: border-box; }\n.cartao { width: 100%; max-width: 30rem; padding: 1rem; '
             'border: 2px solid #555; margin-inline: auto; }',
             'Somar width:100% e padding sem verificar estouro horizontal.',
             'Em 320px de largura, o cartão cabe sem esconder texto ou criar rolagem horizontal?'),
        Aula('grid', 'Grid para linhas e colunas', 'intermediario', 'Layouts responsivos',
             'Grid organiza duas dimensões. repeat e minmax definem faixas; auto-fit ocupa o espaço com as colunas que cabem. '
             'min(100%, 14rem) evita que uma coluna mínima ultrapasse um contêiner pequeno.',
             'Coloque seis articles em section.galeria. Varie a largura e compare Grid com o Flexbox da aula anterior.',
             '.galeria { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr)); }\n'
             '.galeria > article { padding: 1rem; border: 1px solid #777; }',
             'Escolher larguras fixas que só funcionam na tela do autor.',
             'Os cartões passam de uma para várias colunas sem perder a ordem de leitura?'),
        Aula('responsivo', 'Responsividade, unidades e foco', 'intermediario', 'Layouts responsivos',
             'Comece com um layout estreito e acrescente regras quando o conteúdo precisar de espaço. rem acompanha o tamanho '
             'de fonte da raiz. :focus-visible torna a navegação por teclado visível sem remover o foco nativo sem substituto.',
             'Aplique a um main com nav e article. Teste Tab, zoom de 200% e larguras de 320px e 1000px.',
             'main { display: grid; gap: 1rem; padding: 1rem; }\n'
             'a:focus-visible, button:focus-visible { outline: 3px solid #075cad; outline-offset: 3px; }\n'
             '@media (min-width: 50rem) { main { grid-template-columns: 14rem minmax(0, 1fr); } }',
             'Remover outline ou criar pontos de quebra só por modelos específicos de telefone.',
             'O conteúdo mantém legibilidade e cada elemento interativo tem foco visível?'),
        Aula('movimento', 'Transições e preferência por movimento reduzido', 'intermediario', 'Interação e organização',
             'transition interpola uma mudança; animation usa quadros-chave. Anime transform ou opacity quando adequado. '
             'prefers-reduced-motion permite respeitar a preferência do usuário por menos movimento.',
             'Aplique .entrada a um cartão e .botao a um botão. Ative movimento reduzido nas ferramentas do navegador.',
             '.entrada { animation: surgir .3s ease-out; }\n@keyframes surgir { from { opacity: 0; transform: translateY(.5rem); } '
             'to { opacity: 1; transform: translateY(0); } }\n'
             '.botao { transition: transform .15s; }\n.botao:hover { transform: translateY(-2px); }\n'
             '@media (prefers-reduced-motion: reduce) { .entrada { animation: none; } .botao { transition: none; } }',
             'Usar movimento incessante ou esconder informações quando animações são desativadas.',
             'Com movimento reduzido, o conteúdo fica visível e todas as ações continuam disponíveis?'),
        Aula('arquitetura', 'Tokens, camadas e componentes', 'avancado', 'Interação e organização',
             'Custom properties centralizam escolhas como cor e espaço. @layer estabelece a ordem de camadas para declarações '
             'normais; organize base, componentes e ajustes. Classes de componente reduzem dependência da estrutura da página.',
             'Crie dois botões com .botao e altere o tema mudando somente as variáveis de :root. Acrescente uma camada de ajustes.',
             '@layer base, componentes, ajustes;\n@layer base { :root { --acao: #174ea6; --espaco: .75rem; } }\n'
             '@layer componentes { .botao { color: white; background: var(--acao); padding: var(--espaco); border: 0; } }\n'
             '@layer ajustes { .botao.grande { padding: calc(var(--espaco) * 2); } }',
             'Misturar regras sem camada e com camada sem conferir a precedência resultante.',
             'Você consegue mudar o tema sem editar cada seletor? A ordem das camadas é explícita?'),
        Aula('projeto', 'Projeto: painel adaptável', 'avancado', 'Projeto e revisão',
             'Um painel combina composição, legibilidade e interação. Verificações estáticas conferem declarações; '
             'o navegador é necessário para verificar aparência, contraste, foco e adaptação do conteúdo real.',
             'Faça um painel com cabeçalho Flexbox, cartões Grid, formulário e tema por variáveis. '
             'Teste 320px, 768px, 1280px, zoom de 200%, teclado e movimento reduzido. Rode o desafio css_grade.',
             ':root { --espaco: 1rem; }\n* { box-sizing: border-box; }\n'
             '.painel { display: grid; gap: var(--espaco); grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); }\n'
             '.cabecalho { display: flex; flex-wrap: wrap; gap: var(--espaco); align-items: center; }',
             'Aprovar o layout após olhar somente uma captura em largura grande.',
             'Registre quais larguras causaram quebra e mostre como o conteúdo se reorganiza sem sumir.'),
    ],
    'javascript': [
        Aula('dom', 'DOM e atualização segura de texto', 'intermediario', 'Navegador e eventos',
             'No console do navegador, document representa a página. querySelector pode devolver null. '
             'textContent insere texto sem interpretá-lo como HTML, apropriado para valores fornecidos pelo usuário.',
             'Execute no navegador, altere o nome para <img src=x> e confira que aparece como texto. Remova o elemento e trate sua ausência.',
             'const saida = document.createElement("p");\ndocument.body.append(saida);\n'
             'const nome = "<img src=x>";\nsaida.textContent = `Olá, ${nome}`;',
             'Interpolar dados externos em innerHTML ou chamar métodos em um querySelector que devolveu null.',
             'A entrada é exibida literalmente e nenhum elemento img é criado?'),
        Aula('eventos', 'Eventos, formulário e estado', 'intermediario', 'Navegador e eventos',
             'addEventListener registra uma função chamada depois da interação. preventDefault impede a ação padrão de um evento '
             'cancelável. Guarde estado fora do handler para preservá-lo entre cliques. Execute no navegador.',
             'Conte envios de um formulário sem recarregar a página. Adicione um botão para zerar e teste Enter dentro do formulário.',
             'const form = document.createElement("form");\nconst botao = document.createElement("button");\n'
             'botao.textContent = "Contar"; form.append(botao); document.body.append(form);\n'
             'let total = 0;\nform.addEventListener("submit", (event) => { event.preventDefault(); '
             'botao.textContent = `Envios: ${++total}`; });',
             'Executar a função ao registrar o listener ou registrar novamente a cada atualização de tela.',
             'Cada envio aumenta exatamente uma unidade e a página não recarrega?'),
        Aula('promessas', 'Promessas, erros e cancelamento', 'intermediario', 'Assincronismo e dados',
             'await obtém o resultado de uma Promise e propaga rejeições. try/catch deve envolver o await para tratar falhas. '
             'Promise.all reúne tarefas independentes e rejeita se uma delas rejeitar. O exemplo roda em Node ou navegador.',
             'Faça uma tarefa rejeitar com Error e trate sem perder a mensagem. Compare execução sequencial com Promise.all.',
             'async function carregar(id) { if (id < 0) throw new Error("id inválido"); return { id }; }\n'
             'async function main() {\n  try { const itens = await Promise.all([carregar(1), carregar(2)]); console.log(itens); }\n'
             '  catch (erro) { console.error(erro.message); }\n}\nmain();',
             'Esquecer await dentro do try ou assumir que Promise.all cancela automaticamente as tarefas restantes.',
             'Uma rejeição é tratada sem ser confundida com uma lista vazia bem-sucedida?'),
        Aula('api', 'Contrato de API e respostas HTTP', 'intermediario', 'Assincronismo e dados',
             'fetch pode resolver mesmo em status HTTP de erro: confira ok antes de ler JSON. Valide o formato recebido; '
             'JSON.parse não valida o domínio. Injete a função de busca para testar offline. A versão de exemplo usa uma resposta local.',
             'Substitua o mock por respostas com ok:false e um objeto sem nome. Confira que ambos causam erro identificável.',
             'async function nomeDaApi(buscar) {\n  const resposta = await buscar("/pessoa");\n'
             '  if (!resposta.ok) throw new Error("HTTP " + resposta.status);\n'
             '  const dado = await resposta.json();\n  if (typeof dado.nome !== "string") throw new Error("nome ausente");\n'
             '  return dado.nome;\n}\nnomeDaApi(async () => ({ ok: true, status: 200, json: async () => ({ nome: "Ana" }) }))'
             '.then(console.log).catch(console.error);',
             'Tratar todo retorno JSON como válido ou fazer testes dependerem de uma API pública ao vivo.',
             'Você consegue testar sucesso, falha HTTP e resposta inválida sem conexão?'),
        Aula('modulos', 'Módulos e fronteiras de aplicação', 'avancado', 'Organização e testes',
             'Um módulo exporta um contrato explícito. No navegador use script type="module" e um servidor local para os arquivos; '
             'em Node use extensão .mjs. O exemplo é um módulo completo que exporta e também demonstra a função.',
             'Salve como valores.mjs. Em main.mjs use import { total } from "./valores.mjs". '
             'Separe a demonstração para que importar o módulo não imprima nada.',
             'export function total(valores) {\n  if (!valores.every(Number.isFinite)) throw new TypeError("Somente números");\n'
             '  return valores.reduce((soma, valor) => soma + valor, 0);\n}\nconsole.log(total([2, 3]));',
             'Confundir nomes de pacote com caminhos relativos ou executar efeitos de aplicação durante toda importação.',
             'O consumidor recebe a função exportada e entradas inválidas são rejeitadas?'),
        Aula('testes', 'Testes de comportamento com Node', 'avancado', 'Organização e testes',
             'O módulo node:test executa testes sem pacotes externos em versões de Node que o incluem. '
             'assert verifica o contrato; um teste deve falhar quando o comportamento está errado. Salve como teste.cjs e rode node --test teste.cjs.',
             'Inclua zero, negativos e uma entrada inválida. Troque o cálculo por x+2 e confirme a falha.',
             'const test = require("node:test");\nconst assert = require("node:assert/strict");\n'
             'function dobro(x) { if (!Number.isFinite(x)) throw new TypeError("número esperado"); return x * 2; }\n'
             'test("dobro aceita negativos", () => assert.equal(dobro(-3), -6));\n'
             'test("dobro rejeita texto", () => assert.throws(() => dobro("3"), TypeError));',
             'Testar só um valor que também passa com uma implementação errada.',
             'Os testes detectam tanto o erro de cálculo quanto a ausência de validação?'),
        Aula('projeto', 'Projeto: lista de tarefas com armazenamento', 'avancado', 'Projeto e revisão',
             'Uma aplicação pequena separa estado, persistência e renderização. localStorage guarda texto por origem e pode falhar '
             'por restrições do ambiente. O exemplo roda no navegador; não guarde segredos nesse armazenamento.',
             'Crie lista com adicionar, concluir e remover, eventos delegados e JSON em localStorage. '
             'Trate dados corrompidos e erro de gravação; renderize com textContent e teste a lógica com node:test.',
             'function lerTarefas(storage) {\n  try { const dados = JSON.parse(storage.getItem("tarefas") ?? "[]");\n'
             '    return Array.isArray(dados) ? dados.filter(x => typeof x === "string") : [];\n'
             '  } catch { return []; }\n}\nconsole.log(lerTarefas({ getItem: () => \'["Estudar"]\' }));',
             'Persistir HTML de entrada do usuário ou ignorar erro de armazenamento e anunciar salvamento.',
             'Reabrir a página mantém os dados? JSON corrompido e armazenamento indisponível geram feedback coerente?'),
    ],
    'typescript': [
        Aula('unknown', 'unknown e validação nas fronteiras', 'intermediario', 'Tipos e contratos',
             'unknown exige verificar o valor antes de usá-lo. Uma anotação ou as não transforma nem valida dados externos. '
             'Use typeof, comparação com null e in para estreitar tipos de objetos recebidos como desconhecidos.',
             'Teste a função com null, {}, {nome:3} e um nome válido. Compile com tsc --strict antes de executar.',
             'function nomeDoUsuario(valor: unknown): string {\n  if (typeof valor !== "object" || valor === null || '
             '!("nome" in valor) || typeof valor.nome !== "string") throw new Error("usuário inválido");\n'
             '  return valor.nome;\n}\nconsole.log(nomeDoUsuario({ nome: "Ana" }));',
             'Usar as Usuario ou any para silenciar uma falha de validação real.',
             'O compilador exige as verificações e o programa rejeita todos os formatos inválidos?'),
        Aula('unioes', 'Uniões discriminadas e estados possíveis', 'intermediario', 'Tipos e contratos',
             'Uma propriedade literal comum distingue variantes. Depois de testar status, TypeScript conhece os campos '
             'daquela variante. Isso evita estados impossíveis como sucesso sem dados.',
             'Adicione o estado carregando e ajuste a renderização. Faça um switch com verificação de never para detectar variantes esquecidas.',
             'type Resultado = { status: "ok"; dados: string[] } | { status: "erro"; mensagem: string };\n'
             'function resumo(r: Resultado): string {\n  return r.status === "ok" ? r.dados.join(", ") : r.mensagem;\n}\n'
             'console.log(resumo({ status: "ok", dados: ["HTML", "CSS"] }));',
             'Declarar vários campos opcionais independentes e precisar de ! em todo acesso.',
             'O compilador rejeita um objeto de sucesso sem dados?'),
        Aula('genericos', 'Genéricos que preservam relações', 'intermediario', 'Tipos e contratos',
             'Um parâmetro de tipo relaciona entrada e saída sem perder informação. keyof restringe a chave às propriedades '
             'existentes; T[K] descreve o tipo do valor daquela chave. readonly impede alterações pela referência recebida.',
             'Extraia id e nome com a mesma função. Tente uma chave inexistente e explique o erro de compilação.',
             'function campo<T, K extends keyof T>(objeto: T, chave: K): T[K] { return objeto[chave]; }\n'
             'const pessoa = { id: 1, nome: "Ana" };\nconsole.log(campo(pessoa, "nome"));\n'
             'function primeiro<T>(valores: readonly T[]): T | undefined { return valores[0]; }\nconsole.log(primeiro([1, 2]));',
             'Criar um genérico usado só uma vez sem estabelecer relação ou fingir que um array nunca estará vazio.',
             'O retorno mantém o tipo específico e a lista vazia produz undefined tratado pelo chamador?'),
        Aula('dom', 'DOM tipado e ausência de elementos', 'intermediario', 'Navegador e aplicações',
             'No navegador, querySelector pode retornar null e Element pode não ter value. instanceof HTMLInputElement '
             'verifica o elemento real e estreita o tipo. Compile com bibliotecas DOM e strict; carregue o JavaScript na página.',
             'Adicione um input#nome ao HTML, depois teste o código sem o input e com um div de mesmo id.',
             'const campo = document.querySelector("#nome");\nif (campo instanceof HTMLInputElement) {\n'
             '  campo.addEventListener("input", () => console.log(campo.value.trim()));\n'
             '} else { console.warn("Campo de nome indisponível"); }',
             'Afirmar as HTMLInputElement sem garantir que o elemento existe ou tem esse tipo.',
             'Os três formatos de página são tratados sem TypeError?'),
        Aula('assincrono', 'Retornos assíncronos e contratos de serviços', 'avancado', 'Navegador e aplicações',
             'Uma função async devolve Promise<T>. Uma interface permite trocar o serviço real por um fake offline sem '
             'alterar o consumidor. Tipagem descreve o contrato; a implementação de rede ainda deve validar a resposta.',
             'Crie um fake que rejeita e um consumidor com try/catch. Depois implemente a interface usando fetch com verificação de status e formato.',
             'interface Repositorio { nomes(): Promise<readonly string[]>; }\n'
             'async function listar(repo: Repositorio): Promise<string> { return (await repo.nomes()).join(", "); }\n'
             'const local: Repositorio = { nomes: async () => ["Ana", "Bia"] };\nlistar(local).then(console.log).catch(console.error);',
             'Anotar uma resposta como um tipo esperado sem validar os bytes recebidos.',
             'O consumidor funciona com serviço offline e propaga erros identificáveis?'),
        Aula('configuracao', 'strict, módulos e verificação de projeto', 'avancado', 'Organização e testes',
             'tsconfig.json reúne as escolhas de compilação. strict aumenta verificações. Use tsc --noEmit --strict arquivo.ts '
             'para verificar um arquivo; em um projeto com tsconfig use tsc --noEmit. Instalação e execução dependem do runtime local.',
             'Crie tsconfig.json com compilerOptions contendo strict:true e noEmit:true. Crie src/index.ts com o exemplo '
             'e use tsc --noEmit. Remova a verificação de null, observe o diagnóstico e corrija-o.',
             'function tamanho(texto: string | null): number {\n  if (texto === null) return 0;\n'
             '  return texto.length;\n}\nconsole.log(tamanho(null), tamanho("Estudo"));',
             'Passar arquivos na linha de comando esperando que as opções de tsconfig sejam aplicadas automaticamente.',
             'A verificação falha diante do acesso nulo e passa após tratar a ausência?'),
        Aula('projeto', 'Projeto: tarefas com domínio e adaptadores', 'avancado', 'Projeto e revisão',
             'Separe o domínio puro da interface de navegador e armazenamento. Uma interface de framework pode chamar as mesmas '
             'funções; esse limite reduz a dependência de bibliotecas específicas. O exemplo executa sem framework.',
             'Implemente criar, concluir e remover tarefas por id. Faça adaptadores DOM e armazenamento, valide JSON como unknown, '
             'adicione testes de comportamento e compile com strict. Registre que partes dependem do navegador.',
             'type Tarefa = Readonly<{ id: number; titulo: string; concluida: boolean }>;\n'
             'function concluir(tarefas: readonly Tarefa[], id: number): Tarefa[] {\n'
             '  return tarefas.map(t => t.id === id ? { ...t, concluida: true } : t);\n}\n'
             'console.log(concluir([{ id: 1, titulo: "Estudar", concluida: false }], 1));',
             'Misturar acesso ao DOM nas regras de domínio e tornar os testes dependentes da página inteira.',
             'Os testes cobrem id ausente, lista vazia e preservação das tarefas não alteradas?'),
    ],
    'python': [
        Aula('dataclass', 'Modelos com dataclass e invariantes', 'intermediario', 'Domínio e arquivos',
             'dataclass gera inicialização e representação a partir de campos anotados. frozen impede atribuições normais '
             'aos campos; validações de domínio continuam sendo sua responsabilidade. __post_init__ verifica invariantes após criar o objeto.',
             'Crie um Produto imutável e rejeite preço negativo. Teste preço zero e nome vazio.',
             'from dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass Produto:\n    nome: str\n    preco: float\n'
             '    def __post_init__(self):\n        if not self.nome.strip() or self.preco < 0:\n'
             '            raise ValueError("produto inválido")\n\nprint(Produto("Caderno", 12.5))',
             'Esperar que uma anotação de tipo valide entrada ou que frozen torne objetos internos mutáveis imutáveis.',
             'Construções inválidas falham e dois produtos preservam seus próprios dados?'),
        Aula('csv', 'CSV, caminhos e contextos', 'intermediario', 'Domínio e arquivos',
             'pathlib compõe caminhos; csv trata separadores, aspas e quebras dentro de campos. Use newline="" ao abrir CSV '
             'para que o módulo controle quebras de linha. O exemplo usa StringIO e roda sem arquivos prévios.',
             'Grave e leia um CSV real usando with, encoding="utf-8" e newline="". Inclua um nome com vírgula e um acento.',
             'import csv\nimport io\n\nmemoria = io.StringIO(newline="")\n'
             'gravador = csv.DictWriter(memoria, fieldnames=["nome", "nota"])\ngravador.writeheader()\n'
             'gravador.writerow({"nome": "Ana, Silva", "nota": 8})\nmemoria.seek(0)\n'
             'for linha in csv.DictReader(memoria):\n    print(linha["nome"], float(linha["nota"]))',
             'Separar CSV com split(",") ou esquecer que dados lidos de CSV são texto.',
             'O nome com vírgula continua em uma única coluna e a nota é convertida antes de calcular?'),
        Aula('api', 'APIs, JSON e validação sem rede', 'intermediario', 'Integrações e automação',
             'json.loads converte JSON em estruturas Python; o domínio precisa de validação separada. '
             'Separe buscar bytes de interpretar dados para testar offline. Em uma chamada HTTP real configure tempo limite e trate status e decodificação.',
             'Teste JSON inválido, lista no lugar de objeto e nome ausente. Faça a função de busca real separada, usando urllib.request.urlopen com timeout.',
             'import json\n\ndef ler_usuario(corpo):\n    dado = json.loads(corpo)\n'
             '    if not isinstance(dado, dict) or not isinstance(dado.get("nome"), str):\n'
             '        raise ValueError("nome ausente ou inválido")\n    return dado["nome"]\n\n'
             'print(ler_usuario(\'{"nome": "Ana"}\'))',
             'Usar eval para ler dados ou confundir falha HTTP com usuário sem nome.',
             'Os testes distinguem JSON malformado de um objeto válido que viola o contrato?'),
        Aula('asyncio', 'Concorrência com asyncio e limites', 'avancado', 'Integrações e automação',
             'asyncio alterna tarefas quando elas aguardam. asyncio.sleep não bloqueia a thread; time.sleep dentro de uma coroutine bloqueia. '
             'gather reúne resultados na ordem das entradas, que pode diferir da ordem de término.',
             'Execute três tarefas com atrasos diferentes. Use wait_for para limitar o tempo total e trate TimeoutError.',
             'import asyncio\n\nasync def tarefa(nome, atraso):\n    await asyncio.sleep(atraso)\n    return nome\n\n'
             'async def main():\n    resultados = await asyncio.gather(tarefa("A", .02), tarefa("B", .01))\n'
             '    print(resultados)\n\nif __name__ == "__main__":\n    asyncio.run(main())',
             'Achar que async acelera automaticamente processamento de CPU ou chamar uma coroutine sem await.',
             'O resultado mantém a ordem A, B e o limite de tempo cancela uma tarefa lenta?'),
        Aula('automacao', 'Automação com prévia e arquivos temporários', 'avancado', 'Integrações e automação',
             'Antes de modificar arquivos em lote, calcule um plano, detecte conflitos e apresente uma prévia. '
             'TemporaryDirectory permite ensaiar sem tocar nos dados reais. Prefira subprocess com lista de argumentos e sem shell para comandos externos.',
             'Planeje renomear .txt para .md; rejeite destinos existentes. Só aplique quando uma opção explícita estiver ativa e teste em pasta temporária.',
             'from pathlib import Path\nfrom tempfile import TemporaryDirectory\n\ndef plano(pasta):\n'
             '    return [(p, p.with_suffix(".md")) for p in sorted(pasta.glob("*.txt"))]\n\n'
             'with TemporaryDirectory() as pasta:\n    raiz = Path(pasta)\n    (raiz / "a.txt").write_text("Estudo", encoding="utf-8")\n'
             '    for origem, destino in plano(raiz):\n        print(origem.name, "->", destino.name)',
             'Executar renomeações durante a descoberta ou sobrescrever um destino já existente.',
             'A prévia não altera arquivos e um conflito impede qualquer sobrescrita?'),
        Aula('projeto', 'Projeto: relatório de despesas testável', 'avancado', 'Projeto e revisão',
             'Uma ferramenta de linha de comando pode separar leitura, regras, formatação e escrita. Use Decimal para valores '
             'monetários decimais; conversões de texto e arredondamento devem ter regras explícitas.',
             'Leia despesas de CSV, valide categoria/valor, totalize por categoria e gere JSON. Use argparse, erros legíveis, '
             'gravação atômica e unittest com pastas temporárias. Cubra arquivo ausente, CSV malformado, valor inválido e totais. '
             'Execute também o desafio soma para exercitar entrada e saída.',
             'from decimal import Decimal\n\ndef totais(linhas):\n    resultado = {}\n    for categoria, texto in linhas:\n'
             '        valor = Decimal(texto)\n        if not valor.is_finite() or valor < 0:\n'
             '            raise ValueError("valor inválido")\n        resultado[categoria] = resultado.get(categoria, Decimal(0)) + valor\n'
             '    return resultado\n\nprint(totais([("estudo", "0.10"), ("estudo", "0.20")]))',
             'Somar dinheiro em float sem definir a precisão ou aceitar NaN e infinito como despesas.',
             'O total de 0.10 e 0.20 é exatamente 0.30 e falhas de entrada preservam o relatório anterior?'),
    ],
}

from codar.estudo.curriculo_outros import outras_aulas

AULAS.update(outras_aulas(Aula))

AMBIENTES = {
    'python': 'Salve em .py. Confira python --version (ou python3) e crie um venv por projeto; execute python arquivo.py. Bibliotecas externas precisam estar instaladas nesse ambiente.',
    'javascript': 'No terminal, confira node --version e execute node arquivo.js. Exemplos DOM exigem uma página no navegador. Para módulos Node use .mjs; no navegador use script type="module".',
    'typescript': 'Prepare TypeScript localmente e confira tsc --version. Verifique com tsc --noEmit --strict arquivo.ts; compile antes de executar com Node quando o runtime não aceita TypeScript. Exemplos DOM exigem navegador.',
    'go': 'Confira go version. Execute go run arquivo.go. Projetos usam go mod init; modo offline exige módulos já locais. Valide com go test ./....',
    'rust': 'Confira rustc --version e cargo --version. Compile rustc arquivo.rs; projetos usam cargo init e cargo test --offline com dependências já locais.',
    'java': 'Prepare um JDK e confira java --version e javac --version. Salve o exemplo como Exemplo.java e execute java Exemplo.java com JDK que suporte arquivos-fonte; ou compile com javac Exemplo.java e use java Exemplo.',
    'c': 'Confira gcc --version ou um compilador C equivalente. Compile gcc -std=c11 -Wall -Wextra arquivo.c -o programa e execute o binário no sistema local.',
    'cpp': 'Confira g++ --version ou compilador C++ equivalente. Compile g++ -std=c++17 -Wall -Wextra arquivo.cpp -o programa e execute o binário.',
    'csharp': 'Prepare o SDK .NET e confira dotnet --info. Crie um projeto console com dotnet new console, salve o código em Program.cs e use dotnet run. Restauração offline exige pacotes locais.',
    'bash': 'Confira bash --version. Valide bash -n arquivo.sh e execute bash arquivo.sh. Extensão .sh não garante que outro shell aceite recursos específicos do Bash.',
    'powershell': 'Confira pwsh --version. Execute pwsh -NoProfile -File arquivo.ps1. Cmdlets dependentes do sistema operacional e módulos externos exigem ambiente compatível.',
    'lua': 'Confira lua -v e execute lua arquivo.lua. Módulos locais usados por require devem estar em um caminho configurado em package.path.',
    'ruby': 'Confira ruby --version e execute ruby arquivo.rb. Use ruby -c arquivo.rb para sintaxe; gems e Minitest devem estar disponíveis antes de estudar offline.',
    'php': 'Confira php --version. Valide php -l arquivo.php e execute php arquivo.php. Recursos web exigem servidor; PDO requer o driver do banco utilizado.',
    'sql': 'Identifique o dialeto e a versão do banco antes de executar. Os desafios deste percurso usam o sqlite3 embutido no Python, em memória, sem servidor e sem rede.',
    'kotlin': 'Prepare kotlinc e Java. Compile kotlinc arquivo.kt -include-runtime -d programa.jar e execute java -jar programa.jar. Coroutines externas precisam de dependência própria.',
    'swift': 'Confira swift --version e execute swift arquivo.swift. Projetos e testes podem usar Swift Package Manager; pacotes externos precisam estar locais para uso offline.',
    'dart': 'Confira dart --version e execute dart run arquivo.dart. Valide dart analyze; Flutter e package:test exigem seus SDKs/pacotes preparados localmente.',
    'r': 'Confira Rscript --version e execute Rscript arquivo.R. Pacotes adicionais devem estar instalados; exemplos base do percurso não exigem download.',
    'julia': 'Confira julia --version e execute julia arquivo.jl. Use ambiente por projeto e prepare dependências locais antes de desconectar a rede.',
    'html': 'Salve como .html e abra no navegador. Mantenha imagens, CSS, scripts e legendas indicados em caminhos locais. Inspecione elementos e teste teclado e zoom.',
    'css': 'Salve como .css e carregue por link rel="stylesheet" em uma página HTML com os elementos das práticas. Use estilos computados e simulação de larguras no navegador.',
    'yaml': 'Salve como .yaml e identifique a ferramenta consumidora e seu schema. Um parser só verifica estrutura; o consumidor precisa validar tipos, campos e regras.',
    'dockerfile': 'Confira docker version e o acesso ao daemon. Crie Dockerfile e os arquivos COPY na mesma pasta de contexto. docker build -t estudo . exige imagem base e dependências locais no uso offline.',
}


def ampliar_curriculo(C):
    return [C(f'{lang}_{a.chave}', a.titulo, 'praticas', a.texto, a.pratique,
              exemplos={lang: a.codigo}, fontes=(FONTES[lang],), erros_comuns=a.erro, verifique=a.confira)
            for lang, aulas in AULAS.items() for a in aulas]


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.casefold()) if unicodedata.category(c) != 'Mn')


def percurso(lang, project=None):
    """Sequência navegável de material real, com distinção entre prática e teste."""
    from codar import estudo
    from codar.estudo.progresso import ler

    detalhes = {f'{lang}_{a.chave}': a for a in AULAS[lang]}
    existentes = [c for c in estudo.catalogo(lang) if c.id not in detalhes]
    existentes.sort(key=lambda c: (not c.id.startswith('guia_'), c.trilha != 'fundamentos'))
    conceitos = existentes + [estudo.POR_ID[identity] for identity in detalhes]
    def nivel(c):
        return detalhes[c.id].nivel if c.id in detalhes else ('iniciante' if c.trilha in ('fundamentos', 'linguagens') else 'intermediario')

    conceitos.sort(key=lambda c: {'iniciante': 0, 'intermediario': 1, 'avancado': 2}[nivel(c)])
    progress = ler(project, lang) if project is not None else {}
    lessons = []
    for indice, c in enumerate(conceitos):
        aula = detalhes.get(c.id)
        level = nivel(c)
        module = aula.modulo if aula else estudo.TRILHAS[c.trilha]
        related = [i for i in c.relacionados if any(x.id == i for x in conceitos)]
        if aula:
            related.extend(i for i, other in detalhes.items() if other.modulo == module and i != c.id and i not in related)
        lessons.append({'id': c.id, 'title': c.titulo, 'level': level,
                        'module': module,
                        'previous': conceitos[indice - 1].id if indice else None,
                        'next': conceitos[indice + 1].id if indice + 1 < len(conceitos) else None,
                        'related': related[:4],
                        'practiced': c.id in progress, 'practiced_at': progress.get(c.id)})
    return {'language': lang, 'environment': AMBIENTES[lang], 'lessons': lessons, 'total': len(lessons),
            'practiced': sum(x['practiced'] for x in lessons),
            'next': next((x['id'] for x in lessons if not x['practiced']), None),
            'assessment': 'Prática registrada pelo aluno; não é certificação nem aprovação automática do projeto.',
            'validated_exercises': [{'id': k.removeprefix('exercise.'), 'checked_at': v} for k, v in progress.items() if k.startswith('exercise.')],
            'scope': 'Material disponível em expansão. Projetos têm revisão manual; APIs, frameworks e runtimes externos exigem preparação local.',
            'project': f'{lang}_projeto'}


def buscar(lang, query):
    from codar import estudo

    termos = _normalizar(query or '').split()
    if not termos:
        raise ValueError('Informe o assunto: codar study search "formulários" --lang html.')
    return [c for c in estudo.catalogo(lang)
            if all(t in _normalizar(' '.join((c.id, c.titulo, c.texto, c.pratique))) for t in termos)]

