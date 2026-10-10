# Desempenho e escolha de modelos

## Memória sem IA (0.3.1)

Medição em 10/10/2026, Linux x86_64, Python 3.12.14 e Textual 8.2.8. Cada cenário foi executado três vezes, em processos novos e configurações temporárias. Nenhum modelo foi carregado ou baixado. RSS e pico VmHWM vieram de `/proc/self/status`; os valores estão em **MiB** (1 MiB = 1.048.576 bytes).

| Cenário | RSS inicial: medianas | RSS após o trabalho: mediana | Faixa após o trabalho | Maior pico |
|---|---|---|---|---|
| Motor no processo local | 25,0 MiB | **25,8 MiB** | 25,80–25,81 MiB | 25,8 MiB |
| Studio headless com motor no mesmo processo | 58,7 MiB | **60,3 MiB** | 60,24–60,31 MiB | 60,3 MiB |

O motor traduziu 20 atribuições pelo compilador e gerou uma calculadora pelo banco de padrões. O Studio abriu três abas Python de 200 linhas em uma tela de 150 × 42 células, executou o mesmo trabalho e aplicou uma intenção no editor.

O Studio usou o driver headless de teste do Textual. Não estão incluídos emulador de terminal, daemon separado, modelo de IA, servidores de linguagem, builds ou programas filhos ativos. Projetos maiores e plugins adicionais podem mudar o consumo. Não houve comparação com outras IDEs. Os números históricos com IA, abaixo, pertencem a outra medição e outro ambiente.

[Resultados completos, por execução](benchmarks/memory-0.3.1.json) · [Script da medição](benchmarks/measure_memory.py)

Para repetir no Linux, na raiz de um checkout com Studio instalado:

```bash
python docs/benchmarks/measure_memory.py --runs 3 --out memory-local.json
```

O script usa somente projetos temporários, sem inicializar um daemon ou instalar dependências.

## Avaliação de edições (0.3.0)

`python -m codar.evals.editbench --out editing-results.json` usa o modelo local configurado para seis tarefas Python de correção/complemento. Verifica resposta completa, sintaxe, novas definições duplicadas e comportamento por testes executáveis: lista vazia, consumo de iterador, ordem de deduplicação, último bloco de um gerador, argumento mutável e arredondamento financeiro com Decimal. O candidato é executado em subprocesso em uma fixture temporária, com timeout e limite de memória quando o sistema o permite; isso não é um sandbox de segurança.

`--reference` verifica os gabaritos das fixtures e não mede um modelo. Testes de regressão exigem que cada gabarito passe e o bug original falhe. Não há um novo percentual de acerto de IA publicado para edição: as medições antigas abaixo são de geração de código e não podem ser extrapoladas para reescrita. A suíte de projeto também testa múltiplos arquivos, aplicação parcial, falhas de disco, conflitos, recuperação, cancelamento e parsers Dart/PowerShell quando seus SDKs estão disponíveis.

Todas as medições abaixo foram feitas numa máquina modesta, de propósito: se funciona aqui, funciona em quase tudo.

| Peça | Modelo |
|---|---|
| CPU | Intel Core i7-7500U (2 núcleos, 4 threads, 2016), sem GPU |
| RAM | 16 GB (o CODAR fica dentro de 3 GB) |
| Disco | SSD SATA WD Green 480 GB, leitura sequencial medida de 527 MB/s |

## Latência por camada

| Camada | Exemplo | Tempo |
|---|---|---|
| Compilador | `x é igual a 10`, `imprimir o tamanho de pedidos`, `ul>li*3` | 0,3 a 1 ms |
| Banco de padrões | `criar uma calculadora`, `validar cnpj` | menos de 5 ms |
| IA literal, linguagem pré-aquecida | `inverter a lista itens` em JavaScript | 1,6 a 2,1 s |
| IA literal, primeira frase numa linguagem fria | `converter preco para inteiro` em Rust | ~10 s |

A diferença entre a linguagem fria e a pré-aquecida é o processamento do prompt (instruções + exemplos da linguagem). O `warm_langs` deixa esse prefixo pronto no cache para as linguagens que você mais usa.

## Modelos: acerto e memória

24 tarefas em português, cada resposta executada contra testes (pass@1). RAM é o pico do processo com `use_mmap = false`.

| Modelo | Acerto | RAM | Observação |
|---|---|---|---|
| `qwen2.5-coder-0.5b` | 83% | 668 MB | o mais rápido |
| `qwen3.5-0.8b` | 42% | | generalista, fraco em código |
| `qwen3.5-2b` | 75% | | generalista |
| **`qwen2.5-coder-1.5b`** (padrão) | **88%** | 1212 MB | melhor relação acerto/memória |
| `qwen2.5-coder-3b` Q3_K_M | 88% | | |
| `qwen2.5-coder-3b` Q4_K_M | 88% | 2166 MB | 31,6 s por tarefa; licença qwen-research (uso não comercial) |

O 3B não acerta mais que o 1.5B nessas tarefas porque o trabalho pesado não fica com a IA: o compilador resolve as frases comuns e o banco resolve os pedidos de funcionalidade. A IA só traduz literalmente o que sobra, e para isso um modelo pequeno basta.

### Por que `use_mmap = false`

Com mmap, o llama.cpp reorganiza os pesos para AVX2 numa cópia, e os pesos aparecem duas vezes no RSS. Medido com o 3B Q4: **3423 MB com mmap, 2166 MB sem**.

### Memória ao longo do uso

Com o modelo padrão carregado, o daemon fica entre 1,27 e 1,41 GB depois de pedidos em seis linguagens. Sem o cache compacto de prefixos (`CompactRAMCache`), o mesmo uso chegava a 2078 MB, porque o cache original guardava os logits de todas as posições do prompt (~78 MB por estado) sem contá-los no limite. Sem o modelo carregado, o daemon usa ~55 a 100 MB.

## Um modelo de 8B compensaria?

Não dentro de 3 GB, e não sem forçar o hardware.

**Modelo denso de 8B (ex.: Qwen3-8B em Q4_K_M, ~4,9 GB).** Cada token usa todos os pesos. Com um teto de ~2,8 GB, no mínimo ~2,4 GB de pesos ficariam fora da RAM e teriam de ser relidos do disco a cada token. A 527 MB/s, isso dá cerca de **5 s por token no melhor caso**. É uma estimativa, não uma medição: o mmap lê em blocos espalhados, então na prática seria mais lento. Uma linha de 30 tokens levaria minutos, com CPU e SSD a plena carga o tempo todo. Ler do SSD não desgasta a memória flash, mas o calor constante da CPU desgasta o notebook, e o ganho seria pequeno: o 3B já empata com o 1.5B nestas tarefas.

**colibri** ([JustVugg/colibri](https://github.com/JustVugg/colibri)). É um motor em C para modelos *mixture-of-experts* (MoE) muito grandes. Ele mantém na RAM a parte densa e lê do disco só os especialistas que cada token usa. Segundo o próprio README:
- pede **"8 GB of RAM at the very least"** e 22 GB livres no disco para o menor modelo;
- o menor modelo listado é o OLMoE de 7B, que precisa de 8 GB de RAM;
- não roda modelos densos de 8B;
- grava o arquivo `.coli_usage` a cada turno.

Ele resolve outro problema (rodar modelos de centenas de bilhões de parâmetros em máquinas com 16 a 128 GB) e não cabe no orçamento de 3 GB.

**O que compensa:** ensinar ao compilador as frases que você mais usa (respostas em menos de 1 ms, sem modelo) e acrescentar padrões testados ao banco. Ver [EXTENDING.md](EXTENDING.md).

## Roteador semântico (Cactus Needle)

Avaliado como alternativa ao roteamento por regras: levou de 26 a 121 s por consulta nesta CPU e errou o roteamento em casos simples. Ficou só como adaptador opcional (`[needle] enabled = false` por padrão, com telemetria sempre desligada).

## Como reproduzir

```bash
codar bench -n 200 --soak 200            # latência por camada, pico de RAM e vazamento
python -m codar.evals.runner --model qwen2.5-coder-1.5b   # acerto nas 24 tarefas
```

O teste de modelos usa a CPU a pleno por vários minutos. Num notebook, rode na tomada e com boa ventilação.
