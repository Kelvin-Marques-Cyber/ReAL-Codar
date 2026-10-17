"""Práticas específicas e projetos de revisão para as demais linguagens."""


def outras_aulas(A):
    return {
        'go': [
            A('slices', 'Slices, mapas e cópias', 'intermediario', 'Dados e contratos',
              'Um slice descreve uma região de um array. Slices podem compartilhar armazenamento; append pode realocar. '
              'O acesso a um mapa pode devolver valor e um booleano que indica presença.',
              'Copie um slice com append([]int(nil), original...) e altere a cópia. Teste chave ausente em um mapa.',
              'package main\nimport "fmt"\nfunc main() {\n original := []int{1, 2}; copia := append([]int(nil), original...)\n'
              ' copia[0] = 9; idades := map[string]int{"Ana": 20}; idade, existe := idades["Bia"]\n'
              ' fmt.Println(original, copia, idade, existe)\n}',
              'Confundir a cópia do descritor de um slice com uma cópia dos elementos.',
              'Alterar a cópia preserva o original e a chave ausente é distinguida do valor zero?'),
            A('concorrencia', 'Goroutines, canais e encerramento', 'avancado', 'Concorrência',
              'go inicia uma goroutine. Um canal sem buffer sincroniza envio e recebimento. O produtor fecha o canal quando '
              'não enviará mais; range termina ao consumir os valores e observar o fechamento.',
              'Produza três valores, consuma com range e depois use context para cancelar uma produção longa.',
              'package main\nimport "fmt"\nfunc main() {\n valores := make(chan int)\n'
              ' go func() { defer close(valores); for i := 1; i <= 3; i++ { valores <- i } }()\n'
              ' for n := range valores { fmt.Println(n * 2) }\n}',
              'Fechar um canal pelo consumidor enquanto o produtor ainda envia ou deixar goroutines bloqueadas.',
              'O programa termina após três resultados? Quem é responsável por fechar o canal?'),
            A('projeto', 'Projeto: analisador de registros', 'avancado', 'Projeto e revisão',
              'Separe processamento de linhas da leitura de arquivo. bufio.Scanner fornece linhas e Err informa falhas. '
              'Use funções pequenas para testar regras com go test, sem depender de um servidor externo.',
              'Leia registros de um arquivo, agrupe por nível e grave JSON. Trate arquivo ausente, linha inválida e limite de tamanho. '
              'Acrescente testes tabelados e execute go test ./... no módulo criado com go mod init.',
              'package main\nimport ("bufio"; "fmt"; "strings")\nfunc main() {\n'
              ' s := bufio.NewScanner(strings.NewReader("INFO inicio\\nERRO falha\\n")); contagem := map[string]int{}\n'
              ' for s.Scan() { campos := strings.Fields(s.Text()); if len(campos) > 0 { contagem[campos[0]]++ } }\n'
              ' if err := s.Err(); err != nil { panic(err) }; fmt.Println(contagem)\n}',
              'Ignorar Scanner.Err ou criar um teste que só verifica que o processo terminou.',
              'Os testes detectam contagem incorreta e uma entrada vazia gera um resumo vazio?'),
        ],
        'rust': [
            A('result', 'Result, Option e propagação com ?', 'intermediario', 'Contratos e erros',
              'Result<T,E> representa sucesso ou erro; Option<T> representa presença ou ausência. O operador ? devolve cedo '
              'o erro para o chamador. match obriga a considerar as variantes.',
              'Converta texto em inteiro devolvendo Result. Teste texto vazio, negativo e inválido, sem unwrap na entrada externa.',
              'fn dobro(texto: &str) -> Result<i32, std::num::ParseIntError> { Ok(texto.parse::<i32>()? * 2) }\n'
              'fn main() { for entrada in ["10", "abc"] { match dobro(entrada) { Ok(n) => println!("{n}"), '
              'Err(e) => eprintln!("Entrada inválida: {e}") } } }',
              'Usar unwrap para transformar entradas esperadamente inválidas em panic.',
              'Uma falha é descrita e não impede o tratamento das próximas entradas?'),
            A('iteradores', 'Iteradores e empréstimos', 'intermediario', 'Coleções',
              'iter empresta elementos; into_iter pode consumir a coleção. map e filter são preguiçosos até um consumidor '
              'como collect ou sum solicitar resultados. Escolha referências ou valores conforme o contrato.',
              'Some os pares com iter, filter e sum e depois mostre o vetor original. Compare com consumir um Vec<String>.',
              'fn main() {\n let valores = vec![1, 2, 3, 4];\n'
              ' let soma: i32 = valores.iter().copied().filter(|n| n % 2 == 0).sum();\n'
              ' println!("{soma} {valores:?}");\n}',
              'Tentar usar uma coleção depois de movê-la ou esperar efeitos de um iterador que nunca foi consumido.',
              'O compilador explica o movimento e a versão com empréstimo mantém a coleção disponível?'),
            A('projeto', 'Projeto: catálogo de tarefas com testes', 'avancado', 'Projeto e revisão',
              'Cargo organiza pacote, dependências e testes. Mantenha domínio em funções testáveis e entrada/saída no executável. '
              'O exemplo inclui teste de comportamento: salve em exemplo.rs e execute rustc --test exemplo.rs -o testes.',
              'Crie um projeto Cargo de tarefas com enum para estado, Result para erros e persistência em texto. '
              'Teste id ausente, título vazio e recuperação após arquivo inválido. Use cargo test --offline com dependências já disponíveis.',
              '#[derive(Debug, PartialEq)]\nenum Estado { Pendente, Feita }\n'
              'fn concluir(estado: &mut Estado) { *estado = Estado::Feita; }\n'
              'fn main() { let mut e = Estado::Pendente; concluir(&mut e); println!("{e:?}"); }\n'
              '#[cfg(test)] mod tests { use super::*; #[test] fn conclui() { let mut e = Estado::Pendente; '
              'concluir(&mut e); assert_eq!(e, Estado::Feita); } }',
              'Adicionar crates esperando que o modo offline faça downloads ou ocultar erros de persistência.',
              'O teste falha ao remover a mudança de estado e a aplicação trata dados inválidos sem sobrescrever o arquivo?'),
        ],
        'java': [
            A('colecoes', 'Coleções, interfaces e genéricos', 'intermediario', 'Objetos e dados',
              'List<String> expressa o tipo dos elementos; ArrayList é uma implementação mutável. List.of cria uma lista '
              'não modificável. Programe pela interface quando não precisar de detalhes da implementação.',
              'Copie uma List.of para ArrayList, acrescente um nome e filtre nomes com mais de três letras.',
              'import java.util.*;\nclass Exemplo { public static void main(String[] args) {\n'
              ' List<String> nomes = new ArrayList<>(List.of("Ana", "Beatriz")); nomes.add("Caio");\n'
              ' nomes.stream().filter(n -> n.length() > 3).forEach(System.out::println);\n} }',
              'Supor que toda List aceita add ou usar coleções sem parâmetro de tipo.',
              'Você distingue interface, implementação e mutabilidade pelo contrato?'),
            A('recursos', 'Exceções e try-with-resources', 'intermediario', 'Recursos e erros',
              'try-with-resources fecha objetos AutoCloseable mesmo quando há exceções. Capture a exceção no ponto '
              'em que existe uma decisão útil; não substitua falha por sucesso vazio.',
              'Troque o StringReader por Files.newBufferedReader com UTF-8. Trate arquivo ausente e preserve a causa do erro.',
              'import java.io.*;\nclass Exemplo { public static void main(String[] args) throws IOException {\n'
              ' try (BufferedReader leitor = new BufferedReader(new StringReader("Ana\\nBia"))) {\n'
              '  String linha; while ((linha = leitor.readLine()) != null) System.out.println(linha);\n }\n} }',
              'Deixar um catch vazio ou fechar o recurso só no caminho sem erros.',
              'A leitura funciona e o fechamento ocorre também quando o processamento falha?'),
            A('projeto', 'Projeto: biblioteca com empréstimos', 'avancado', 'Projeto e revisão',
              'Modele livros e empréstimos por composição. Separe regras de disponibilidade de interface e arquivos. '
              'Um método deve comunicar uma operação inválida com um contrato claro.',
              'Crie catálogo com Map por código, empréstimo/devolução e persistência CSV. Escreva testes para livro duplicado, '
              'empréstimo indisponível e devolução sem empréstimo; organize pacotes e documente o comando do seu sistema de build.',
              'class Exemplo {\n static class Livro { private boolean emprestado;\n'
              '  void emprestar() { if (emprestado) throw new IllegalStateException("indisponível"); emprestado = true; }\n'
              '  boolean disponivel() { return !emprestado; }\n }\n'
              ' public static void main(String[] args) { Livro livro = new Livro(); livro.emprestar(); '
              'if (livro.disponivel()) throw new AssertionError("empréstimo não registrado"); System.out.println("ok"); }\n}',
              'Permitir mudanças diretas no estado que contornam a regra do empréstimo.',
              'O segundo empréstimo falha e o estado continua coerente após a falha?'),
        ],
        'c': [
            A('limites', 'Arrays, tamanhos e strings terminadas em zero', 'intermediario', 'Memória e contratos',
              'Um array tem capacidade fixa. Strings C terminam em \\0; reserve espaço para esse terminador. '
              'Funções que recebem ponteiros precisam receber ou conhecer o tamanho disponível.',
              'Leia com fgets em um buffer pequeno, detecte truncamento e trate a ausência da quebra de linha.',
              '#include <stdio.h>\n#include <string.h>\nint main(void) {\n'
              ' char nome[8] = "Ana"; size_t tamanho = strlen(nome);\n'
              ' printf("%zu de %zu bytes\\n", tamanho, sizeof nome); return 0;\n}',
              'Confundir sizeof de um ponteiro com o tamanho do array ou escrever além do terminador.',
              'A capacidade inclui o byte final e entradas maiores que o buffer são tratadas?'),
            A('recursos', 'Alocação e responsabilidade por liberar', 'intermediario', 'Memória e contratos',
              'malloc devolve memória não inicializada ou NULL. Cada recurso precisa de um responsável por liberar; '
              'use free uma única vez e não acesse depois. calloc inicializa bytes com zero e também pode falhar.',
              'Aloque uma sequência cujo tamanho seja validado. Teste zero, falha de alocação simulada e erro antes do processamento.',
              '#include <stdio.h>\n#include <stdlib.h>\nint main(void) {\n'
              ' size_t n = 3; int *valores = calloc(n, sizeof *valores);\n'
              ' if (valores == NULL) { fputs("sem memória\\n", stderr); return 1; }\n'
              ' valores[1] = 7; printf("%d\\n", valores[1]); free(valores); return 0;\n}',
              'Usar memória após free, liberar duas vezes ou ignorar overflow ao calcular o tamanho da alocação.',
              'Todos os caminhos liberam o recurso e nenhum caminho usa um ponteiro após a liberação?'),
            A('projeto', 'Projeto: estatísticas de arquivo', 'avancado', 'Projeto e revisão',
              'Uma ferramenta robusta diferencia EOF de erro de leitura e valida conversões. Compile com avisos como '
              '-Wall -Wextra -pedantic e, quando disponível, use sanitizadores para encontrar acessos inválidos.',
              'Leia inteiros com fgets e strtol, rejeite texto extra e overflow, calcule contagem/mínimo/máximo. '
              'Teste arquivo vazio, número inválido, arquivo inexistente e limites; rode o desafio ordenar.',
              '#include <stdio.h>\n#include <errno.h>\n#include <stdlib.h>\nint main(void) {\n'
              ' char *fim; errno = 0; long n = strtol("42", &fim, 10);\n'
              ' if (errno || *fim != \'\\0\') return 1; printf("%ld\\n", n); return 0;\n}',
              'Usar atoi sem detectar falhas ou assumir que toda falha de leitura é EOF normal.',
              'O processo sinaliza erro em entradas inválidas e os testes detectam estouro e conversão parcial?'),
        ],
        'cpp': [
            A('containers', 'Containers e algoritmos', 'intermediario', 'Valores e recursos',
              'std::vector gerencia armazenamento contíguo; algoritmos operam sobre iteradores. '
              'sort muda a coleção; acessos fora dos limites são defeitos mesmo quando parecem funcionar.',
              'Ordene inteiros preservando repetidos. Compare operator[] com at e trate o erro de índice da segunda forma.',
              '#include <algorithm>\n#include <iostream>\n#include <vector>\nint main() {\n'
              ' std::vector<int> valores{3, 1, 2, 2}; std::sort(valores.begin(), valores.end());\n'
              ' for (int n : valores) std::cout << n << " "; std::cout << "\\n";\n}',
              'Invalidar iteradores com inserções durante a iteração ou guardar referência a elemento realocado.',
              'A ordem é numérica, repetições permanecem e índices inválidos são prevenidos?'),
            A('raii', 'RAII e posse exclusiva', 'avancado', 'Valores e recursos',
              'RAII vincula duração do recurso ao objeto. unique_ptr representa posse exclusiva e libera ao sair do escopo. '
              'Mover transfere posse; a origem perde o recurso e precisa ser tratada antes de acessar.',
              'Crie um unique_ptr, mova para outro e explique por que o ponteiro original não deve ser desreferenciado.',
              '#include <iostream>\n#include <memory>\n#include <utility>\nint main() {\n'
              ' auto origem = std::make_unique<int>(42); auto destino = std::move(origem);\n'
              ' std::cout << *destino << " " << (origem == nullptr) << "\\n";\n}',
              'Misturar delete manual com smart pointer ou acessar o objeto por uma referência que ficou pendente.',
              'A posse é clara e o recurso é liberado mesmo diante de uma exceção?'),
            A('projeto', 'Projeto: índice de palavras', 'avancado', 'Projeto e revisão',
              'Combine streams, containers e funções puras para separar leitura de contagem. '
              'std::map produz ordem por chave; defina como tratar maiúsculas e pontuação antes de implementar.',
              'Conte palavras de arquivo UTF-8 com política explícita para tokens. Trate falha ao abrir e gravar, '
              'teste vazio e repetidos e use avisos do compilador. Evite prometer normalização Unicode que o programa não faz.',
              '#include <iostream>\n#include <sstream>\n#include <map>\n#include <string>\n'
              'int main() { std::istringstream entrada("ana bia ana"); std::map<std::string, int> contagem;\n'
              ' std::string palavra; while (entrada >> palavra) ++contagem[palavra];\n'
              ' for (const auto& item : contagem) std::cout << item.first << ": " << item.second << "\\n"; }',
              'Usar bytes como caracteres Unicode ou anunciar sucesso quando a gravação falhou.',
              'Os testes definem a política de tokens e detectam perda de ocorrências repetidas?'),
        ],
        'csharp': [
            A('linq', 'Coleções, LINQ e execução adiada', 'intermediario', 'Dados e contratos',
              'LINQ descreve transformações em sequências. Muitas operações são adiadas até enumerar; ToList materializa '
              'o resultado naquele momento. Escolha interfaces e mutabilidade conforme a operação.',
              'Filtre os pares, materialize uma lista e altere a origem. Compare a consulta adiada com o resultado já materializado.',
              'using System;\nusing System.Linq;\nusing System.Collections.Generic;\nclass Exemplo {\n'
              ' static void Main() { var valores = new List<int> {1, 2, 3, 4};\n'
              ' var pares = valores.Where(n => n % 2 == 0).ToList(); Console.WriteLine(string.Join(", ", pares)); }\n}',
              'Executar uma consulta várias vezes esperando um snapshot invariável de dados mutáveis.',
              'Você distingue uma consulta adiada de uma lista materializada?'),
            A('async', 'Task, await e descarte de recursos', 'avancado', 'Assincronismo e recursos',
              'Task<T> descreve trabalho assíncrono. await propaga falhas sem bloquear a thread como Result pode bloquear. '
              'using descarta IDisposable; operações canceláveis devem receber CancellationToken quando aplicável.',
              'Faça uma tarefa falhar e capture a exceção em torno do await. Acrescente cancelamento a Task.Delay.',
              'using System;\nusing System.Threading.Tasks;\nclass Exemplo {\n'
              ' static async Task<int> Dobro(int n) { await Task.Delay(1); return n * 2; }\n'
              ' static async Task Main() { try { Console.WriteLine(await Dobro(10)); } '
              'catch (Exception e) { Console.Error.WriteLine(e.Message); } }\n}',
              'Usar async void fora de handlers ou bloquear a interface com .Result.',
              'O chamador consegue aguardar e observar tanto o resultado quanto a falha?'),
            A('projeto', 'Projeto: catálogo em JSON', 'avancado', 'Projeto e revisão',
              '.NET organiza aplicação e dependências em um projeto. System.Text.Json serializa dados, mas regras de domínio '
              'precisam ser validadas. Separe repositório, serviço e interface para testar sem disco ou rede.',
              'Crie um catálogo com id único, busca e persistência JSON. Teste entrada vazia, duplicados e JSON inválido. '
              'Use dotnet test no projeto de testes e documente dependências previamente restauradas para uso offline.',
              'using System;\nusing System.Collections.Generic;\nclass Exemplo {\n'
              ' static void Main() { var catalogo = new Dictionary<int, string>();\n'
              ' if (!catalogo.TryAdd(1, "Caderno")) throw new InvalidOperationException("id duplicado");\n'
              ' Console.WriteLine(catalogo.TryGetValue(1, out var nome) ? nome : "ausente"); }\n}',
              'Confiar que desserializar valida todas as regras ou suprimir erros de escrita.',
              'Uma falha de persistência mantém os dados anteriores e os testes podem usar um repositório em memória?'),
        ],
        'bash': [
            A('aspas', 'Aspas, arrays e argumentos seguros', 'intermediario', 'Argumentos e processos',
              'Aspas duplas preservam espaços e impedem globbing sobre expansões. Arrays mantêm limites entre argumentos. '
              '"${itens[@]}" expande cada item separadamente; não monte comandos em texto para usar eval.',
              'Percorra nomes contendo espaços e asterisco, depois compare com uma expansão sem aspas em uma pasta temporária.',
              '#!/usr/bin/env bash\nitens=("um arquivo.txt" "*.txt")\n'
              'for item in "${itens[@]}"; do printf "<%s>\\n" "$item"; done',
              'Usar for item in $(ls) ou eval com entradas do usuário.',
              'Há exatamente duas linhas e os caracteres especiais permanecem literais?'),
            A('erros', 'Status de saída, pipes e limpeza', 'intermediario', 'Argumentos e processos',
              'O status zero indica sucesso. if comando avalia esse status; pipefail considera falhas anteriores do pipeline. '
              'trap permite limpar temporários na saída. set -e tem exceções e não substitui tratamento explícito.',
              'Crie um temporário com mktemp, registre trap e faça uma operação falhar. Confira que o arquivo é removido.',
              '#!/usr/bin/env bash\nset -o pipefail\n'
              'if printf "%s\\n" "Ana" | wc -l; then printf "%s\\n" "contagem concluída"; '
              'else printf "%s\\n" "falha na contagem" >&2; exit 1; fi',
              'Ignorar o status de comandos ou supor que a última etapa comprova sucesso do pipeline todo.',
              'Substituir a primeira etapa por false faz o pipeline ser detectado como falha?'),
            A('projeto', 'Projeto: inventário de arquivos com prévia', 'avancado', 'Projeto e revisão',
              'Scripts de automação precisam manter limites de argumentos e tratar nomes incomuns. find -print0 e read -d '
              'podem percorrer nomes com quebras de linha no Bash. Restrinja o escopo e separe inventário de alterações.',
              'Produza inventário de uma pasta temporária sem modificar arquivos. Inclua nomes com espaços e quebras, '
              'argumentos ausentes e pasta inexistente. Faça uma opção de prévia antes de qualquer transformação futura.',
              '#!/usr/bin/env bash\npasta=${1:-.}\nif [[ ! -d "$pasta" ]]; then printf "%s\\n" "pasta ausente" >&2; exit 1; fi\n'
              'while IFS= read -r -d \'\' arquivo; do printf "%q\\n" "$arquivo"; done < <(find "$pasta" -type f -print0)',
              'Interpretar nomes como opções de comandos ou dividir nomes por espaços e linhas.',
              'O inventário inclui cada arquivo uma vez e os testes verificam os nomes especiais?'),
        ],
        'powershell': [
            A('contratos', 'Parâmetros, validação e objetos de saída', 'intermediario', 'Funções e contratos',
              'param declara o contrato; atributos podem exigir um valor e validar seu intervalo. Retorne objetos com '
              'propriedades para permitir novos filtros. Mensagens de diagnóstico não devem contaminar a saída de dados.',
              'Crie uma função que recebe quantidade não negativa e devolve um objeto com Quantidade e Dobro. Teste -1.',
              'function Get-Resumo {\n param([Parameter(Mandatory)][ValidateRange(0,1000)][int]$Quantidade)\n'
              ' [pscustomobject]@{ Quantidade = $Quantidade; Dobro = $Quantidade * 2 }\n}\n'
              'Get-Resumo -Quantidade 3 | Select-Object Quantidade, Dobro',
              'Usar Write-Host como se fosse um retorno de dados ou misturar texto decorativo no pipeline.',
              'O chamador consegue acessar .Dobro e um valor fora do intervalo é rejeitado?'),
            A('json', 'JSON e persistência de objetos', 'intermediario', 'Dados e arquivos',
              'ConvertTo-Json serializa objetos; a profundidade deve cobrir a estrutura que você pretende guardar. '
              'ConvertFrom-Json não valida regras do domínio. Use codificação explícita ao escrever arquivos.',
              'Faça ida e volta de um objeto aninhado, confira propriedades obrigatórias e trate JSON inválido com -ErrorAction Stop.',
              '$original = [pscustomobject]@{ Nome = "Ana"; Preferencias = @{ Tema = "escuro" } }\n'
              '$json = $original | ConvertTo-Json -Depth 4\n$restaurado = $json | ConvertFrom-Json\n'
              '$restaurado.Preferencias.Tema',
              'Salvar um objeto profundamente aninhado com profundidade insuficiente ou confiar em dados externos sem validar.',
              'A propriedade aninhada permanece após serializar e restaurar?'),
            A('projeto', 'Projeto: limpeza com ShouldProcess', 'avancado', 'Projeto e revisão',
              'SupportsShouldProcess oferece -WhatIf para visualizar ações e -Confirm conforme a política do comando. '
              'A operação só deve acontecer dentro da verificação de ShouldProcess.',
              'Crie um comando de limpeza restrito a uma pasta escolhida. Use -LiteralPath, -WhatIf e tratamento de erro. '
              'Teste somente em TestDrive do Pester se disponível ou pasta temporária; valide que WhatIf não remove arquivos.',
              'function Remove-Exemplo {\n [CmdletBinding(SupportsShouldProcess)]\n param([Parameter(Mandatory)][string]$LiteralPath)\n'
              ' if ($PSCmdlet.ShouldProcess($LiteralPath, "Remover arquivo")) { Remove-Item -LiteralPath $LiteralPath -ErrorAction Stop }\n'
              '}\nRemove-Exemplo -LiteralPath "exemplo.tmp" -WhatIf',
              'Executar a ação antes da chamada ShouldProcess ou expandir curingas em caminhos fornecidos como literais.',
              'WhatIf descreve a operação e mantém todos os arquivos intactos?'),
        ],
        'lua': [
            A('tabelas', 'Tabelas, sequências e valores ausentes', 'intermediario', 'Dados e módulos',
              'Uma tabela representa mapa ou sequência. nil remove uma chave; ipairs percorre índices consecutivos até '
              'o primeiro ausente. O comprimento # só é previsível para sequências sem lacunas.',
              'Conte palavras em uma tabela e compare pairs com ipairs em uma sequência sem lacunas e outra com lacunas.',
              'local contagem = {}\nfor palavra in string.gmatch("ana bia ana", "%S+") do\n'
              ' contagem[palavra] = (contagem[palavra] or 0) + 1\nend\nprint(contagem.ana, contagem.bia)',
              'Depender da ordem de pairs ou tratar # como contagem de todas as chaves de um mapa.',
              'As repetições são contadas e a ordem das chaves não afeta o resultado?'),
            A('erros', 'Módulos, pcall e contrato de retorno', 'intermediario', 'Dados e módulos',
              'Um arquivo carregado por require pode devolver uma tabela de funções. pcall chama uma função protegida '
              'e retorna um booleano seguido do resultado ou erro; preserve essa distinção no chamador.',
              'Mova dobro para um módulo local que devolve uma tabela. Teste um valor numérico e texto inválido com pcall.',
              'local function dobro(n)\n assert(type(n) == "number", "número esperado")\n return n * 2\nend\n'
              'for _, valor in ipairs({3, "abc"}) do\n local ok, resposta = pcall(dobro, valor)\n print(ok, resposta)\nend',
              'Descartar o booleano de pcall e usar uma mensagem de erro como se fosse um resultado válido.',
              'Você diferencia sucesso e erro sem analisar o texto da mensagem?'),
            A('projeto', 'Projeto: agenda em arquivo de texto', 'avancado', 'Projeto e revisão',
              'Separe tabela de contatos, regras de validação e leitura/escrita. Defina um formato de arquivo e rejeite '
              'separadores em campos ou implemente escape. Não carregue dados com load ou dofile.',
              'Implemente adicionar e buscar contato, arquivo UTF-8 e gravação em temporário. '
              'Use assert para testar nome duplicado, vazio e contato ausente. Leia dados como texto, sem executar o arquivo.',
              'local function adicionar(agenda, nome, telefone)\n assert(nome ~= "" and not agenda[nome], "nome inválido ou duplicado")\n'
              ' agenda[nome] = telefone\nend\nlocal agenda = {}\nadicionar(agenda, "Ana", "1234")\n'
              'assert(agenda.Ana == "1234")\nprint(agenda.Ana)',
              'Executar um arquivo de dados como código ou sobrescrever uma agenda depois de uma leitura incompleta.',
              'O teste detecta duplicatas e um arquivo inválido não destrói a agenda anterior?'),
        ],
        'ruby': [
            A('enumerable', 'Enumerable, blocos e transformação', 'intermediario', 'Coleções e objetos',
              'map transforma cada elemento; select filtra; sum pode agregar. Blocos recebem parâmetros entre barras. '
              'Métodos com ! frequentemente alteram o receptor, mas consulte o contrato de cada método.',
              'Filtre valores positivos, dobre e some. Confira que a sequência original permanece inalterada.',
              'valores = [-2, 1, 3]\npositivos = valores.select { |n| n > 0 }\n'
              'puts positivos.map { |n| n * 2 }.sum\np valores',
              'Usar each esperando o array transformado de map ou depender de convenções sem ler o retorno do método.',
              'O resultado é 8 e o array original ainda contém -2?'),
            A('recursos', 'Arquivos com bloco e tratamento de erros', 'intermediario', 'Arquivos e erros',
              'File.open com bloco fecha o recurso ao terminar. Rescue trata classes de exceção selecionadas; ensure '
              'executa a finalização. StringIO permite exercitar o contrato de leitura sem arquivos prévios.',
              'Crie uma função que recebe um objeto com each_line. Use StringIO nos testes e File.open com UTF-8 no programa.',
              'require "stringio"\ndef contar(io)\n io.each_line.count { |linha| !linha.strip.empty? }\nend\n'
              'puts contar(StringIO.new("Ana\\n\\nBia\\n"))',
              'Capturar Exception indiscriminadamente ou deixar arquivo aberto quando o processamento falha.',
              'Linhas vazias são excluídas e o leitor pode ser trocado sem mudar a regra?'),
            A('projeto', 'Projeto: orçamento com testes Minitest', 'avancado', 'Projeto e revisão',
              'Separe soma de centavos inteiros de conversão e apresentação monetária. Minitest oferece testes de '
              'comportamento quando disponível na instalação Ruby; dependências precisam ser preparadas antes do uso offline.',
              'Crie orçamento por categoria, persistência JSON e uma CLI. Teste negativos, categoria vazia e JSON inválido. '
              'Salve o exemplo como teste.rb e rode ruby teste.rb; faça o teste falhar alterando a soma.',
              'require "minitest/autorun"\ndef total(valores)\n valores.sum\nend\n'
              'class TestOrcamento < Minitest::Test\n def test_centavos\n  assert_equal 30, total([10, 20])\n end\nend',
              'Usar float para representar dinheiro sem uma regra de precisão ou testar só a ausência de exceções.',
              'A soma de centavos é exata e o teste falha se um valor for descartado?'),
        ],
        'php': [
            A('arrays', 'Arrays associativos e contratos', 'intermediario', 'Dados e funções',
              'Arrays PHP associam chaves a valores e também representam sequências. ?? fornece um padrão quando a chave '
              'está ausente ou é null. Declare tipos em funções e valide os dados externos separadamente.',
              'Conte palavras com array associativo e trate uma chave ausente sem emitir aviso.',
              '<?php\ndeclare(strict_types=1);\n$contagem = [];\nforeach (["ana", "bia", "ana"] as $palavra) {\n'
              ' $contagem[$palavra] = ($contagem[$palavra] ?? 0) + 1;\n}\necho $contagem["ana"], PHP_EOL;',
              'Supor que toda chave existe ou confundir null com um valor necessariamente presente.',
              'A repetição é contada e a busca ausente tem um comportamento definido?'),
            A('seguranca', 'Saída HTML e consultas parametrizadas', 'intermediario', 'Aplicações web',
              'Ao apresentar texto em HTML, use escape para aquele contexto. htmlspecialchars com UTF-8 evita interpretar '
              'tags fornecidas como conteúdo. Em SQL, use parâmetros no driver; escape HTML não protege consultas.',
              'Teste texto com <script>, aspas e acentos. Depois escreva uma consulta PDO preparada com parâmetros, sem concatenar a entrada.',
              '<?php\n$nome = \'<script>alert("x")</script>\';\n'
              'echo "<p>", htmlspecialchars($nome, ENT_QUOTES | ENT_SUBSTITUTE, "UTF-8"), "</p>", PHP_EOL;',
              'Usar a mesma função de escape para HTML, JavaScript e SQL ou confiar em validação só no navegador.',
              'O texto aparece literalmente no HTML e a consulta mantém valores separados da instrução SQL?'),
            A('projeto', 'Projeto: cadastro validado', 'avancado', 'Projeto e revisão',
              'Separe validação, persistência e apresentação. Composer gerencia dependências e autoload; a instalação '
              'offline exige dependências já disponíveis. Regras puras podem ser testadas sem um servidor.',
              'Implemente cadastro de contatos com validação de email, PDO parametrizado, escape na exibição e testes de entradas inválidas. '
              'Defina também proteção contra CSRF se houver operações web que alterem dados de uma sessão.',
              '<?php\ndeclare(strict_types=1);\nfunction emailValido(string $email): bool {\n'
              ' return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;\n}\n'
              'if (!emailValido("ana@example.com") || emailValido("invalido")) { throw new RuntimeException("teste falhou"); }\n'
              'echo "ok", PHP_EOL;',
              'Considerar formato de email como prova de posse do endereço ou guardar segredos no código do projeto.',
              'O teste detecta regressão na validação e erros de persistência não são apresentados como cadastro concluído?'),
        ],
        'sql': [
            A('joins', 'Junções e cardinalidade', 'intermediario', 'Consultas relacionais',
              'JOIN combina linhas conforme a condição. LEFT JOIN preserva linhas da esquerda sem correspondência, '
              'preenchendo campos da direita com NULL. Mais de uma correspondência multiplica linhas; isso afeta agregações.',
              'Use o exemplo em SQLite ou PostgreSQL. Adicione duas compras de Ana e explique por que aparecem duas linhas. '
              'Compare COUNT(*) com COUNT(c.valor).',
              "WITH pessoas(id, nome) AS (VALUES (1, 'Ana'), (2, 'Bia')),\n"
              "compras(pessoa_id, valor) AS (VALUES (1, 10), (1, 20))\n"
              'SELECT p.nome, c.valor FROM pessoas p LEFT JOIN compras c ON c.pessoa_id = p.id ORDER BY p.id, c.valor;',
              'Filtrar uma coluna da direita em WHERE e eliminar acidentalmente os registros sem correspondência.',
              'Bia aparece com valor NULL e a quantidade de linhas corresponde à cardinalidade da relação?'),
            A('integridade', 'Restrições, transações e parâmetros', 'intermediario', 'Integridade e alterações',
              'PRIMARY KEY identifica linhas, CHECK protege regras e transações agrupam operações. ROLLBACK desfaz '
              'alterações ainda não confirmadas. Aplicações devem enviar valores por parâmetros do driver, sem concatenar SQL.',
              'Execute em banco temporário. Tente quantidade negativa e chave duplicada. Ative foreign_keys no SQLite quando usar chaves estrangeiras.',
              'CREATE TABLE estoque (id INTEGER PRIMARY KEY, quantidade INTEGER NOT NULL CHECK (quantidade >= 0));\n'
              'INSERT INTO estoque VALUES (1, 5);\nBEGIN;\nUPDATE estoque SET quantidade = quantidade - 2 WHERE id = 1;\n'
              'ROLLBACK;\nSELECT quantidade FROM estoque WHERE id = 1;',
              'Confiar só na validação da interface ou confirmar metade de uma operação que deveria ser atômica.',
              'Após ROLLBACK a quantidade continua 5 e a restrição rejeita quantidade negativa?'),
            A('projeto', 'Projeto: relatórios de vendas', 'avancado', 'Projeto e revisão',
              'Defina tabelas, relacionamentos e casos de consulta antes de otimizar. EXPLAIN mostra o plano; índices '
              'têm custo de escrita e espaço. O desafio sql_totais usa SQLite em memória, sem servidor ou rede.',
              'Modele clientes, pedidos e itens com restrições. Consulte totais por cliente, incluindo quem não comprou, '
              'teste NULL e pedidos múltiplos e compare planos antes/depois de um índice. Rode study exercise sql_totais.',
              "WITH vendas(categoria, valor) AS (VALUES ('A', 10), ('A', 20), ('B', 5))\n"
              'SELECT categoria, SUM(valor) AS total FROM vendas GROUP BY categoria ORDER BY categoria;',
              'Duplicar totais ao juntar tabelas com múltiplas linhas ou assumir ordem sem ORDER BY.',
              'Os testes incluem clientes sem pedidos e confirmam que cada item contribui exatamente uma vez?'),
        ],
        'kotlin': [
            A('null', 'Null safety e coleções', 'intermediario', 'Tipos e dados',
              'Um tipo com ? permite null. ?. chama somente se houver valor; ?: fornece alternativa. '
              'mapNotNull transforma e exclui resultados nulos. Evite !! sem uma garantia verificável.',
              'Converta uma lista de textos com toIntOrNull, calcule soma e preserve os textos rejeitados para feedback.',
              'fun main() {\n val entradas = listOf("1", "x", "3")\n val numeros = entradas.mapNotNull { it.toIntOrNull() }\n'
              ' println(numeros.sum())\n val nome: String? = null\n println(nome?.uppercase() ?: "VISITANTE")\n}',
              'Descartar dados inválidos sem informar ao usuário ou usar !! para esconder um possível null.',
              'A soma é 4 e a aplicação distingue valor inválido de zero?'),
            A('estados', 'Classes seladas e when', 'intermediario', 'Modelagem',
              'Uma classe selada restringe variantes conhecidas de um domínio. when como expressão pode verificar '
              'cobertura exaustiva. Data classes representam valores; composição organiza responsabilidades.',
              'Adicione um estado Carregando e atualize when. Compare com um modelo de vários campos opcionais.',
              'sealed class Resultado {\n data class Ok(val valor: Int): Resultado()\n data class Erro(val mensagem: String): Resultado()\n}\n'
              'fun resumo(r: Resultado): String = when (r) { is Resultado.Ok -> "${r.valor}"; is Resultado.Erro -> r.mensagem }\n'
              'fun main() { println(resumo(Resultado.Ok(42))) }',
              'Usar else para esconder novas variantes que deveriam exigir tratamento explícito.',
              'O compilador sinaliza um when incompleto quando surge uma nova variante?'),
            A('projeto', 'Projeto: agenda de compromissos', 'avancado', 'Projeto e revisão',
              'Separe modelo imutável, validação e repositório. Recursos como coroutines precisam da biblioteca '
              'apropriada; a linguagem não instala dependências ao escrever suspend.',
              'Crie agenda por id com busca e persistência. Teste colisões de horário, ids duplicados e datas inválidas. '
              'Se adicionar carregamento assíncrono, injete o repositório e teste sem rede.',
              'data class Compromisso(val id: Int, val titulo: String)\n'
              'fun adicionar(itens: List<Compromisso>, novo: Compromisso): List<Compromisso> {\n'
              ' require(novo.titulo.isNotBlank() && itens.none { it.id == novo.id })\n return itens + novo\n}\n'
              'fun main() { check(adicionar(emptyList(), Compromisso(1, "Estudar")).size == 1); println("ok") }',
              'Misturar interface e persistência com a regra de conflito ou presumir bibliotecas disponíveis offline.',
              'A regra pode ser testada sem interface e a entrada original permanece inalterada?'),
        ],
        'swift': [
            A('opcionais', 'Optionals, guard e conversões seguras', 'intermediario', 'Tipos e contratos',
              'Int(texto) devolve Int? porque a conversão pode falhar. guard let extrai o valor ou sai cedo do escopo. '
              'Evite forçar com ! quando a ausência faz parte das entradas esperadas.',
              'Converta texto em dobro opcional. Teste string vazia e inválida, devolvendo um erro útil no chamador.',
              'func dobro(_ texto: String) -> Int? {\n guard let numero = Int(texto) else { return nil }\n return numero * 2\n}\n'
              'print(dobro("3") ?? 0)\nif dobro("abc") == nil { print("entrada inválida") }',
              'Usar um padrão zero que torna um erro indistinguível de um resultado válido.',
              'O chamador consegue diferenciar ausência, zero e um inteiro válido?'),
            A('protocolos', 'Structs, protocolos e composição', 'intermediario', 'Modelagem',
              'struct modela valores; protocolos definem capacidades exigidas. Uma função pode depender do protocolo '
              'em vez da implementação concreta. mutating indica um método de valor que altera self.',
              'Crie dois tipos que implementam um protocolo de descrição e teste a função consumidora com ambos.',
              'protocol Descritivel { func descrever() -> String }\n'
              'struct Produto: Descritivel { let nome: String; func descrever() -> String { "Produto: \\(nome)" } }\n'
              'func mostrar(_ valor: Descritivel) { print(valor.descrever()) }\nmostrar(Produto(nome: "Caderno"))',
              'Escolher herança para todo compartilhamento de comportamento ou ignorar semântica de valor e referência.',
              'O consumidor funciona com outro tipo sem alterar seu código?'),
            A('projeto', 'Projeto: leitor de catálogo Codable', 'avancado', 'Projeto e revisão',
              'Codable descreve codificação e decodificação; JSONDecoder pode lançar erros de formato ou tipo. '
              'Valide regras do domínio depois de decodificar. Se usar rede, separe URLSession da transformação e trate cancelamento.',
              'Leia produtos de JSON local, rejeite nomes vazios e ids repetidos e mostre um relatório. '
              'Adicione testes XCTest para JSON inválido, campo ausente e coleção vazia; mantenha os testes offline.',
              'import Foundation\nstruct Produto: Codable { let id: Int; let nome: String }\n'
              'let dados = Data("[{\\"id\\":1,\\"nome\\":\\"Caderno\\"}]".utf8)\n'
              'do { let produtos = try JSONDecoder().decode([Produto].self, from: dados); print(produtos[0].nome) }\n'
              'catch { print("JSON inválido: \\(error)") }',
              'Usar try! em dados externos ou assumir que decodificar garante ids únicos.',
              'Erros de formato e regras de domínio têm testes separados e mensagens úteis?'),
        ],
        'dart': [
            A('colecoes', 'Coleções, funções e transformações', 'intermediario', 'Domínio e dados',
              'List, Set e Map têm contratos diferentes. where e map devolvem Iterable que pode ser preguiçoso; toList '
              'materializa. Uma função pode receber outras funções para separar transformação da origem de dados.',
              'Filtre pares e dobre-os. Compare a lista resultante com o Iterable quando a coleção original é alterada.',
              'void main() {\n final valores = [1, 2, 3, 4];\n'
              ' final pares = valores.where((n) => n.isEven).map((n) => n * 2).toList();\n print(pares);\n}',
              'Confundir final com imutabilidade profunda ou depender de um snapshot sem materializar.',
              'O resultado contém 4 e 8 e você explica quando a transformação é executada?'),
            A('erros', 'Exceções e contratos assíncronos', 'intermediario', 'Domínio e dados',
              'Uma função pode lançar FormatException; try/catch trata falhas esperadas. Em Future, o erro é observado '
              'ao aguardar. Separe conversão, validação e efeito externo para testar sem interface Flutter.',
              'Teste conversão com texto válido e inválido. Converta a operação em Future e confira a propagação pelo await.',
              'int dobro(String texto) => int.parse(texto) * 2;\nvoid main() {\n'
              ' for (final texto in ["3", "abc"]) { try { print(dobro(texto)); } '
              'on FormatException catch (erro) { print("Entrada inválida: ${erro.message}"); } }\n}',
              'Capturar tudo e devolver zero ou deixar uma Future com erro sem observador.',
              'O resultado zero permanece distinguível de erro de conversão?'),
            A('projeto', 'Projeto: tarefas com domínio independente de Flutter', 'avancado', 'Projeto e revisão',
              'Regras de domínio em Dart puro podem ser testadas antes da interface. Em Flutter, widgets representam '
              'a tela; repositórios controlam persistência. Evite efeitos externos em build e libere recursos no ciclo de vida.',
              'Faça tarefas com id, título e conclusão. Crie um repositório em memória e outro JSON. '
              'Teste ids ausentes e duplicados com package:test quando instalado; depois conecte a uma tela Flutter.',
              'class Tarefa {\n final int id; final String titulo; final bool feita;\n'
              ' const Tarefa(this.id, this.titulo, {this.feita = false});\n'
              ' Tarefa concluir() => Tarefa(id, titulo, feita: true);\n}\n'
              'void main() { final tarefa = Tarefa(1, "Estudar").concluir(); '
              'if (!tarefa.feita) throw StateError("teste falhou"); print(tarefa.titulo); }',
              'Acoplar toda regra ao widget ou anunciar salvamento antes de aguardar a persistência.',
              'A lógica funciona sem Flutter e a interface apresenta falhas reais de gravação?'),
        ],
        'r': [
            A('ausentes', 'Dados ausentes, fatores e resumos', 'intermediario', 'Dados e estatística',
              'NA representa ausência; is.na identifica valores ausentes. == NA não é um teste de ausência. '
              'Na média, na.rm=TRUE remove ausentes, mas informe quantas observações ficaram de fora.',
              'Calcule média e quantidade de ausentes por coluna. Teste uma coluna só com NA e defina sua política.',
              'notas <- c(7, NA, 9)\nvalidas <- notas[!is.na(notas)]\n'
              'print(list(media=mean(validas), ausentes=sum(is.na(notas)), observacoes=length(validas)))',
              'Excluir observações sem registrar a exclusão ou comparar NA com ==.',
              'A média é 8, há um ausente e duas observações válidas?'),
            A('funcoes', 'Funções puras e validação', 'intermediario', 'Organização e revisão',
              'Uma função deve tornar explícitos entrada e retorno. stop comunica falha; stopifnot verifica condições. '
              'set.seed torna sorteios reproduzíveis dentro de um ambiente, mas não substitui separar treino e avaliação.',
              'Escreva uma função de média que rejeite entradas não numéricas e uma política para coleção vazia. Teste com stopifnot.',
              'media_segura <- function(x) {\n if (!is.numeric(x) || length(x) == 0) stop("vetor numérico não vazio esperado")\n'
              ' mean(x)\n}\nstopifnot(media_segura(c(2, 4)) == 3)\nprint(media_segura(c(2, 4)))',
              'Depender de objetos globais ou aceitar texto convertido silenciosamente em fator.',
              'A função produz o mesmo resultado sem depender de objetos fora dos parâmetros?'),
            A('projeto', 'Projeto: relatório reprodutível de vendas', 'avancado', 'Projeto e revisão',
              'Uma análise reprodutível declara dados de entrada, política de ausentes e transformações. '
              'Use funções para leitura, validação, resumo e gráfico; bibliotecas externas precisam estar preparadas localmente.',
              'Leia CSV, valide categoria e valor, agregue totais e salve relatório e gráfico. '
              'Teste categorias repetidas, NA, tabela vazia e valores negativos, registrando as exclusões realizadas.',
              'vendas <- data.frame(categoria=c("A", "A", "B"), valor=c(10, 20, 5))\n'
              'resumo <- aggregate(valor ~ categoria, data=vendas, FUN=sum)\n'
              'stopifnot(resumo$valor[resumo$categoria == "A"] == 30)\nprint(resumo)',
              'Publicar um gráfico sem validar os dados ou misturar alteração manual dos dados com a transformação do script.',
              'Uma execução limpa reproduz a tabela e os testes detectam uma soma incorreta?'),
        ],
        'julia': [
            A('despacho', 'Métodos e despacho múltiplo', 'intermediario', 'Tipos e funções',
              'Uma função pode ter métodos conforme os tipos dos argumentos. Despacho múltiplo escolhe o método mais '
              'específico aplicável. Prefira contratos com tipos abstratos quando não precisar de uma representação concreta.',
              'Defina métodos para inteiro e texto e use methods para inspecionar. Teste um tipo sem método aplicável.',
              'dobro(x::Number) = x * 2\ndobro(x::AbstractString) = x * x\n'
              'println(dobro(3))\nprintln(dobro("oi"))\nprintln(methods(dobro))',
              'Restringir tudo a tipos concretos sem necessidade ou criar métodos ambiguamente sobrepostos.',
              'O método escolhido corresponde aos tipos e você consegue explicar a diferença entre os resultados?'),
            A('colecoes', 'Arrays, views e alocação', 'intermediario', 'Dados e desempenho',
              'Uma fatia comum cria cópia; view pode compartilhar os dados originais. Broadcast com .= escreve no destino. '
              'Meça antes de otimizar e coloque trabalho relevante em funções para facilitar especialização e testes.',
              'Altere uma view e uma cópia da mesma região e compare o array original. Evite depender de índices fixos em código genérico.',
              'valores = [1, 2, 3, 4]\ncopia = valores[1:2]\njanela = view(valores, 1:2)\n'
              'copia[1] = 9\njanela[2] = 8\nprintln(valores)\nprintln(copia)',
              'Mudar uma view esperando preservar a origem ou otimizar sem verificar alocações e resultados.',
              'O original vira [1,8,3,4] e a alteração na cópia não muda seu primeiro elemento?'),
            A('projeto', 'Projeto: estatísticas com testes', 'avancado', 'Projeto e revisão',
              'O módulo Test faz parte da biblioteca padrão. Separe tratamento de missing, cálculo e apresentação. '
              'Um ambiente de projeto registra dependências, que precisam estar disponíveis antes da execução offline.',
              'Crie relatório de medições com contagem, média e extremos, leitura de arquivo e validação de dados. '
              'Teste coleção vazia, missing e valores inválidos; documente como ativar o ambiente do projeto.',
              'using Test, Statistics\nmedia_valida(xs) = mean(collect(skipmissing(xs)))\n'
              '@testset "medições" begin\n @test media_valida([2, missing, 4]) == 3\nend\n'
              'println(media_valida([2, missing, 4]))',
              'Excluir missing sem informar a contagem ou chamar mean em uma coleção sem observações válidas.',
              'O teste falha se missing for tratado como zero e a política para ausência total é explícita?'),
        ],
        'yaml': [
            A('escalares', 'Strings, blocos e tipos previsíveis', 'intermediario', 'Dados de configuração',
              'YAML representa dados; o programa consumidor define os tipos e regras aceitos. Aspas preservam strings '
              'ambíguas; | preserva quebras e > dobra linhas comuns. Parsers de versões diferentes podem resolver valores de formas distintas.',
              'Compare | e > em duas mensagens. Coloque códigos com zero inicial e valores que devem ser texto entre aspas.',
              'codigo: "0012"\nativo: true\nmensagem: |\n  Linha um\n  Linha dois\n'
              'resumo: >\n  Um texto longo\n  em duas linhas de origem.\n',
              'Supor que YAML executa comandos ou que todo parser interpreta valores implícitos de forma idêntica.',
              'O consumidor recebe codigo como string e a mensagem preserva as quebras esperadas?'),
            A('validacao', 'Configuração, validação e segredos', 'intermediario', 'Contratos e segurança',
              'Um YAML sintaticamente válido pode ser inválido para a aplicação. Valide chaves, tipos e intervalos com '
              'o schema da ferramenta consumidora. Use carregamento seguro, sem tags que construam objetos arbitrários.',
              'Defina as regras para porta, ambiente e hosts. Crie versões inválidas e confirme que o consumidor rejeita cada uma. '
              'Mantenha segredos fora do arquivo versionado.',
              'servidor:\n  porta: 8080\n  ambiente: "desenvolvimento"\n  hosts:\n    - "localhost"\n'
              'credenciais:\n  origem: "variavel_de_ambiente"\n',
              'Confundir parse com validação de schema ou escrever tokens reais no repositório.',
              'Chave desconhecida, porta negativa e tipo incorreto produzem erro útil no consumidor?'),
            A('projeto', 'Projeto: configuração documentada e validada', 'avancado', 'Projeto e revisão',
              'O projeto YAML inclui dados, contrato e testes no consumidor. A linguagem não tem laços ou funções '
              'de aplicação; essas operações pertencem à ferramenta que lê o arquivo.',
              'Crie configuração de duas instâncias locais, documente cada campo e escreva testes de schema no consumidor '
              'para ausência de campo, tipo incorreto, chaves duplicadas e segredo não configurado. Compare mapas por dados, não por formatação.',
              'versao: 1\ninstancias:\n  - nome: "api"\n    porta: 8080\n    log: "info"\n'
              '  - nome: "painel"\n    porta: 8081\n    log: "warning"\n',
              'Aprovar a configuração apenas porque um editor colore o arquivo ou aceitar chaves duplicadas silenciosamente.',
              'Os testes verificam portas únicas, versão suportada e todos os erros de contrato documentados?'),
        ],
        'dockerfile': [
            A('contexto', 'Contexto de build e cache de camadas', 'intermediario', 'Imagens e builds',
              'COPY lê arquivos do contexto de build, não de qualquer caminho do computador. .dockerignore evita enviar '
              'arquivos desnecessários e segredos ao contexto. Ordene instruções por frequência de mudança para aproveitar cache.',
              'Crie app.py e .dockerignore excluindo .git, .venv e .env. Construa somente com a imagem base já disponível se estiver offline.',
              'FROM python:3.13-slim\nWORKDIR /app\nCOPY app.py ./app.py\nCMD ["python", "app.py"]',
              'Copiar todo o diretório incluindo segredos ou assumir que o build pode ler arquivos fora do contexto.',
              'O contexto contém só o necessário e a imagem não inclui .env ou credenciais?'),
            A('usuario', 'Usuário, sinais e comando em formato exec', 'intermediario', 'Execução e segurança',
              'USER escolhe a identidade do processo. CMD em array evita um shell intermediário; o programa recebe '
              'sinais diretamente. Defina permissões dos arquivos que o usuário precisa ler ou escrever.',
              'Use o exemplo com app.py local. Verifique a identidade dentro do container e teste encerramento com docker stop.',
              'FROM python:3.13-slim\nWORKDIR /app\nCOPY --chown=10001:10001 app.py ./app.py\n'
              'USER 10001:10001\nCMD ["python", "-u", "app.py"]',
              'Executar como root sem necessidade ou usar shell form sem compreender sinais e expansão.',
              'O processo roda sem privilégios e encerra de modo previsível ao receber um sinal?'),
            A('projeto', 'Projeto: aplicação local em imagem verificável', 'avancado', 'Projeto e revisão',
              'O Dockerfile descreve uma imagem; o projeto também precisa de aplicação, contexto e testes de execução. '
              'Build offline exige a base e todas as dependências já locais. Tags podem mudar; registre o digest usado na validação.',
              'Empacote uma aplicação que lê entrada e gera resultado, com .dockerignore, usuário sem privilégios e CMD exec. '
              'Teste build, código de saída, sinais e volumes em pasta temporária. Registre comandos e limite os recursos de execução.',
              'FROM python:3.13-slim\nWORKDIR /app\nCOPY --chown=10001:10001 app.py ./app.py\n'
              'USER 10001:10001\nENTRYPOINT ["python", "-u", "app.py"]\nCMD ["--help"]',
              'Declarar a imagem validada sem construir e executar ou presumir que uma tag fixa torna o conteúdo imutável.',
              'O relatório inclui digest real, resultado dos testes e dependências locais necessárias para reproduzir?'),
        ],
    }
