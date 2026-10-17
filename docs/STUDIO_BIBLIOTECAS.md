# Bibliotecas e aprendizagem no Studio

Abra **BIBLIOTECAS** na barra de ferramentas ou use **Ctrl+Shift+L**. A paleta de comandos também encontra “Bibliotecas do projeto”.

1. Escolha a linguagem e filtre por nome ou estado.
2. Selecione uma dependência para ver versão, requisito, módulo, estados e origens.
3. **Consultar API** lê assinaturas, docstrings e documentação da versão encontrada. Não executa imports.
4. **Abrir trilha** apresenta origem, ambiente, importação, API, prática e revisão. Cada etapa tem prática e, quando pertinente, dicas progressivas. O progresso é manual e separado de resultados de teste.
5. **Aprender fonte** associa uma biblioteca a código, tipos ou documentação local que você escolheu. Nenhuma chamada de API é inventada quando as fontes estão ausentes.
6. **Instalar…** prepara o plano. Só **Executar instalação** o envia ao terminal do projeto; cancelar preserva o ambiente.

Consulta e aprendizagem nunca substituem o buffer do editor. Fontes locais mudadas atualizam as referências por hash.

## Progresso pelo terminal

```sh
codar study mark funcao --root . --lang python
codar study progress --root . --lang python --json
codar study export --root . --file progresso.json
codar study import --root outro-projeto --file progresso.json
codar libraries tutorial requests --root . --lang python
```

A importação mescla registros no projeto escolhido, conservando a data mais recente e sem adotar caminhos vindos do JSON. Exportação não substitui arquivos existentes.

## Referências e decisões de interface

A implementação preserva o sistema visual existente: `studio/review.py` (modal de revisão e lista pesquisável), `studio/screens.py` (texto copiável e confirmação) e a paleta de papéis de `studio/widgets.py`. Foram consultadas também as orientações de foco, listas e estados do guia de craft da skill Refero. A pesquisa ao vivo ficou indisponível por assinatura; o alvo adotado foi o próprio produto, sem alterar sua identidade.

| Decisão | Referência | Motivo |
|---|---|---|
| Modal com lista à esquerda e detalhe à direita | ChoiceScreen e ReviewScreen existentes | Preservar navegação por teclado e contexto do editor |
| Fundo, texto, borda e foco com tokens codar | Paleta ativa do Studio | Funcionar também em outros temas |
| Busca e linguagem sempre visíveis | Guia de foco/formulários e catálogo existente | Tornar o inventário encontrável |
| Seis ações em duas linhas | Terminais de 80 colunas | Manter botões acessíveis sem corte horizontal |
| Plano separado com cancelar como foco inicial | AdviceScreen e revisão existentes | Revisar ambiente e comandos antes de instalar |
| Fontes e assinaturas como texto sem markup | Contrato de referências locais | Conteúdo externo permanece dado |

A validação usa o piloto headless do Textual em 150×42 e 80×24, além de inspeção dos SVGs renderizados. Não depende de modelo de IA.

## Exercícios com testes de comportamento

O botão **Exercícios** do painel Estudo e a paleta abrem problemas de entrada/saída. Salve a solução antes de executar. O arquivo é copiado para um snapshot temporário e testado com entradas normais, zero, negativos e outros limites pertinentes. Uma implementação diferente também passa quando produz os resultados esperados.

```sh
codar study exercises
codar study exercise dobro
codar study check dobro --file solucao.py --root . --json
```

O comando `check` executa o código que você forneceu em subprocessos; não é uma sandbox de segurança. Usa runtimes já instalados, limita tempo e saída e encerra o grupo de processos ao exceder os limites. Não baixa SDKs nem instala pacotes. Há adaptadores de execução/compilação para os runtimes do registro de linguagens e para C, C++, Rust, Go e Kotlin. Formatos sem executor e SDKs ausentes não recebem aprovação fictícia. O resultado inclui hash do snapshot e casos individuais, separados do progresso manual. A conclusão vale para os casos executados, não para qualquer entrada possível.

## Consultas e cancelamento

Pedidos como `explique esta função`, `consulte API de util` e `instale requests` usam respostas informativas: explicação, referência local ou plano, sem trocar o código por texto. A execução/instalação efetiva continua nos controles próprios. A resposta JSON identifica essa distinção no campo `action`; clientes que aplicam edições devem tratar `query`, `install`, `execute` e `study` como informativos.

**F2** e **Cancelar geração** na paleta interrompem o pedido atual. O SDK aceita `cancel=threading.Event()` tanto com daemon quanto com motor local. O Studio preserva o editor e ignora tokens/respostas que cheguem depois do cancelamento ou de um novo pedido.

## Completar símbolos

O autocompletar prioriza palavras do arquivo, depois símbolos estáticos do projeto e APIs das bibliotecas disponíveis, antes do vocabulário geral. **F10** abre a seleção com assinatura e origem; Enter insere somente o identificador e Ctrl+Z desfaz. Se o documento ou cursor mudar durante a escolha, a inserção é recusada.

O índice é atualizado ao abrir e ao salvar explicitamente o arquivo, em segundo plano. A digitação não varre o disco. A varredura respeita exclusões e links, até 300 arquivos, 2 MB de fontes do projeto e 1.200 símbolos. É um complemento estático, sem inferência de tipos ou resolução completa de escopo de um servidor LSP. LSP/DAP continuam integrações futuras, sem funcionalidade simulada nesta versão.
