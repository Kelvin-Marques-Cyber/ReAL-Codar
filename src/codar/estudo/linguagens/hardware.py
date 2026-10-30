"""Hardware e contratos: Verilog, VHDL e Solidity. Fontes consultadas em 29/10/2026."""

from codar.estudo.linguagens import Ficha

VERILOG = Ficha(
    fonte="https://steveicarus.github.io/iverilog/",
    guia=("Módulos, portas e atribuições",
          "Um module descreve um circuito com portas de entrada e saída. assign cria lógica combinacional contínua; "
          "always @(posedge clk) descreve registradores atualizados na borda do relógio.",
          "module porta_e(input wire a, input wire b, output wire y);\n  assign y = a & b;\nendmodule"),
    ambiente="Instale um simulador como o Icarus Verilog: iverilog -g2012 -o sim arquivo.v compila e vvp sim executa "
             "o testbench. Ondas gravadas com $dumpfile abrem no GTKWave. Para gravar numa FPGA, use a ferramenta do "
             "fabricante (Vivado, Quartus) ou o fluxo aberto Yosys e nextpnr.",
    aulas=(
        ("testbench", "Testbench e simulação", "intermediario", "Simulação",
         "Um testbench é um módulo sem portas que instancia o circuito, aplica entradas e confere as saídas. initial "
         "roda uma vez no início da simulação; #10 espera 10 unidades de tempo; $display mostra valores e $finish "
         "encerra. Compile com iverilog e rode com vvp.",
         "Teste a porta E com as combinações de entrada, mostrando a tabela-verdade com $display e encerrando com "
         "$finish. Troque & por | e veja quais linhas mudam.",
         "module porta_e(input wire a, input wire b, output wire y);\n  assign y = a & b;\nendmodule\n\nmodule teste;\n"
         "  reg a, b;\n  wire y;\n  porta_e dut(.a(a), .b(b), .y(y));\n\n  initial begin\n"
         "    a = 0; b = 0; #10 $display(\"%b %b -> %b\", a, b, y);\n"
         "    a = 1; b = 0; #10 $display(\"%b %b -> %b\", a, b, y);\n"
         "    a = 1; b = 1; #10 $display(\"%b %b -> %b\", a, b, y);\n    $finish;\n  end\nendmodule",
         "Esquecer o $finish (com um relógio, a simulação não termina) ou ler a saída no mesmo instante em que a "
         "entrada muda, sem esperar com #.",
         "A tabela mostra 1 só quando as duas entradas são 1? A simulação termina sozinha?"),
        ("sequencial", "Registradores e relógio", "intermediario", "Lógica sequencial",
         "always @(posedge clk) executa a cada borda de subida do relógio e descreve flip-flops. Use <= (atribuição "
         "não bloqueante) dentro dele: todos os registradores mudam juntos no fim do passo. Um reset síncrono zera o "
         "contador quando rst vale 1 na borda.",
         "Implemente um contador de 4 bits com reset e habilitação; no testbench, gere o relógio com always #5 "
         "clk = ~clk e confira que ele volta a 0 depois de 15.",
         "module contador(input wire clk, input wire rst, input wire en, output reg [3:0] q);\n"
         "  always @(posedge clk) begin\n    if (rst)\n      q <= 4'd0;\n    else if (en)\n      q <= q + 4'd1;\n"
         "  end\nendmodule\n\nmodule teste;\n  reg clk = 0, rst = 1, en = 1;\n  wire [3:0] q;\n"
         "  contador dut(.clk(clk), .rst(rst), .en(en), .q(q));\n  always #5 clk = ~clk;\n\n  initial begin\n"
         "    #12 rst = 0;\n    #100 $display(\"q = %0d\", q);\n    $finish;\n  end\nendmodule",
         "Usar = (bloqueante) em lógica sequencial: a simulação passa a depender da ordem dos blocos e pode não "
         "corresponder ao hardware.",
         "O contador começa em 0 após o reset e aumenta um por borda? Com en = 0 o valor fica parado?"),
        ("fsm", "Máquina de estados", "avancado", "Lógica sequencial",
         "Uma máquina de estados guarda o estado atual num registrador e calcula o próximo num bloco combinacional "
         "(always @*). localparam dá nomes aos estados e case escolhe a transição. Separar estado e lógica de próximo "
         "estado deixa o circuito previsível e fácil de testar.",
         "Descreva um semáforo com VERDE, AMARELO e VERMELHO trocando a cada pulso de avanço; no testbench, avance seis "
         "vezes e confira a sequência impressa.",
         "module semaforo(input wire clk, input wire rst, input wire avancar, output reg [1:0] estado);\n"
         "  localparam VERDE = 2'd0, AMARELO = 2'd1, VERMELHO = 2'd2;\n  reg [1:0] proximo;\n\n  always @* begin\n"
         "    case (estado)\n      VERDE:   proximo = AMARELO;\n      AMARELO: proximo = VERMELHO;\n"
         "      default: proximo = VERDE;\n    endcase\n  end\n\n  always @(posedge clk) begin\n    if (rst)\n"
         "      estado <= VERDE;\n    else if (avancar)\n      estado <= proximo;\n  end\nendmodule",
         "Esquecer o default no case combinacional: o sintetizador cria um latch para guardar o valor anterior.",
         "A sequência é verde, amarelo, vermelho e volta ao verde? Um reset no meio volta ao verde?"),
        ("projeto", "Projeto: contador com teste automático", "avancado", "Projeto e revisão",
         "O projeto reúne o circuito e um testbench que confere sozinho: compara a saída com o valor esperado a cada "
         "passo e conta os erros, terminando com uma mensagem de aprovação ou falha. $dumpfile e $dumpvars gravam as "
         "ondas para abrir no GTKWave.",
         "Escreva um contador módulo 10 (0 a 9) com saída de transporte e um testbench que verifica 25 bordas, conta "
         "erros e grava as ondas; abra o arquivo .vcd no GTKWave.",
         "module contador_mod10(input wire clk, input wire rst, output reg [3:0] q, output wire vai_um);\n"
         "  assign vai_um = (q == 4'd9);\n  always @(posedge clk)\n    q <= (rst || vai_um) ? 4'd0 : q + 4'd1;\n"
         "endmodule\n\nmodule teste;\n  reg clk = 0, rst = 1;\n  wire [3:0] q;\n  wire vai_um;\n"
         "  integer i, erros = 0;\n  contador_mod10 dut(.clk(clk), .rst(rst), .q(q), .vai_um(vai_um));\n"
         "  always #5 clk = ~clk;\n\n  initial begin\n    $dumpfile(\"ondas.vcd\");\n    $dumpvars(0, teste);\n"
         "    @(negedge clk) rst = 0;\n    for (i = 1; i <= 25; i = i + 1) begin\n      @(negedge clk);\n"
         "      if (q !== i % 10) erros = erros + 1;\n    end\n    if (erros == 0) $display(\"APROVADO\");\n"
         "    else $display(\"FALHOU: %0d erros\", erros);\n    $finish;\n  end\nendmodule",
         "Escrever um testbench que só imprime valores para conferir no olho: sem comparação automática, regressões "
         "passam despercebidas.",
         "O testbench imprime APROVADO e passa a imprimir FALHOU quando você troca 9 por 8 no circuito?"),
    ),
    referencia=(
        ("modulo", (r"^\s*(?:module|endmodule)\b",), "module e endmodule",
         "module nome(portas); ... endmodule descreve um bloco de hardware. Um projeto é uma hierarquia de módulos "
         "instanciados uns dentro dos outros; o de mais alto nível é o topo.",
         "module meio_somador(input wire a, b, output wire soma, vai);\n  assign {vai, soma} = a + b;\nendmodule",
         "Declarar um module dentro de outro: módulos são instanciados, não aninhados."),
        ("portas", (r"\b(?:input|output|inout)\b",), "Portas: input, output e inout",
         "input recebe sinais, output entrega e inout é bidirecional. [7:0] define a largura em bits (do 7 ao 0). "
         "Uma saída atribuída em always é declarada output reg.",
         "module registro(input wire clk, input wire [7:0] d, output reg [7:0] q);\n  always @(posedge clk) q <= d;\n"
         "endmodule", "Atribuir uma saída wire dentro de always."),
        ("sinais", (r"^\s*(?:wire|reg|logic|integer|parameter|localparam|genvar)\b",), "wire, reg e parâmetros",
         "wire liga sinais (recebe assign ou saídas de instâncias); reg guarda valor atribuído em always ou initial; "
         "em SystemVerilog, logic serve para os dois. parameter e localparam são constantes, a primeira ajustável na "
         "instância.",
         "module exemplo;\n  parameter LARGURA = 8;\n  wire [LARGURA-1:0] barramento;\n  reg pronto;\nendmodule",
         "Achar que reg sempre vira um registrador: só vira se for atribuído na borda do relógio."),
        ("assign", (r"^\s*assign\b",), "assign · lógica combinacional",
         "assign y = expressão; mantém y sempre igual à expressão: qualquer mudança nas entradas propaga na hora. & é E, "
         "| é OU, ^ é OU exclusivo, ~ é NÃO e ?: escolhe entre dois valores.",
         "module mux(input wire s, a, b, output wire y);\n  assign y = s ? b : a;\nendmodule",
         "Atribuir o mesmo wire em dois assign: os valores entram em conflito (x)."),
        ("always", (r"^\s*always(?:_ff|_comb|_latch)?\b",), "always · blocos de processo",
         "always @(posedge clk) descreve lógica sequencial; always @* (ou always_comb) descreve lógica combinacional "
         "com tudo que é lido na lista de sensibilidade. Em testbench, always #5 clk = ~clk gera um relógio.",
         "module pisca(input wire clk, output reg led);\n  initial led = 0;\n  always @(posedge clk) led <= ~led;\nendmodule",
         "Esquecer um sinal na lista de sensibilidade manual: a simulação difere do circuito sintetizado."),
        ("naobloqueante", (r"^\s*\w+(?:\[[^\]]*\])?\s*<=",), "<= · atribuição não bloqueante",
         "Em lógica sequencial, a <= b agenda a atualização para o fim do passo: todos os registradores leem os valores "
         "antigos e mudam juntos, como flip-flops reais. Use = em lógica combinacional e em testbenches.",
         "module troca(input wire clk, output reg a, b);\n  initial begin a = 0; b = 1; end\n"
         "  always @(posedge clk) begin\n    a <= b;\n    b <= a;\n  end\nendmodule",
         "Misturar = e <= no mesmo bloco sequencial."),
        ("initial", (r"^\s*initial\b",), "initial · início da simulação",
         "initial executa uma vez a partir do tempo zero; é usado em testbenches para aplicar estímulos e, em algumas "
         "FPGAs, para dar valor inicial a registradores. begin e end agrupam vários comandos.",
         "module t;\n  initial begin\n    $display(\"início\");\n    $finish;\n  end\nendmodule",
         "Esperar que initial funcione em qualquer síntese para ASIC: lá, use reset."),
        ("atraso", (r"^\s*#\d+", r"@\s*\((?:pos|neg)edge\b"), "Atrasos e eventos",
         "#10 espera 10 unidades de tempo antes do próximo comando; @(posedge clk) espera a próxima borda de subida e "
         "@(negedge clk) a de descida. Atrasos só valem na simulação: o sintetizador os ignora.",
         "module t;\n  reg clk = 0;\n  always #5 clk = ~clk;\n  initial begin\n    @(posedge clk);\n    #2 $display(\"%0t\", "
         "$time);\n    $finish;\n  end\nendmodule",
         "Usar # para gerar temporização num circuito que vai para a FPGA."),
        ("sistema", (r"\$(?:display|monitor|write|finish|stop|time|dumpfile|dumpvars|error|fatal|random)\b",),
         "Tarefas do sistema ($)",
         "$display imprime uma linha (%b binário, %d decimal, %h hexadecimal, %0t tempo); $monitor imprime sempre que "
         "um valor muda; $finish encerra; $dumpfile e $dumpvars gravam as ondas num arquivo .vcd.",
         "module t;\n  initial begin\n    $display(\"%b %0d %h\", 4'b1010, 10, 255);\n    $finish;\n  end\nendmodule",
         "Usar $display para verificar sem comparar com o valor esperado."),
        ("condicao", (r"^\s*(?:if|else|case|casez|endcase|default|for|while|repeat|begin)\b",), "if, case e laços",
         "if/else e case escolhem atribuições dentro de always; for e repeat repetem comandos (em síntese, cada "
         "repetição vira hardware). begin e end agrupam comandos como as chaves de outras linguagens.",
         "module decod(input wire [1:0] s, output reg [3:0] y);\n  always @* begin\n    case (s)\n      2'd0: y = 4'b0001;\n"
         "      2'd1: y = 4'b0010;\n      default: y = 4'b0000;\n    endcase\n  end\nendmodule",
         "Deixar caminhos sem atribuição em lógica combinacional e criar latches."),
        ("instancia", (r"^\s*\w+\s+(?:#\(.*\)\s*)?\w+\s*\(\s*\.",), "Instâncias de módulos",
         "tipo nome(.porta(sinal), ...) cria uma cópia de um módulo e liga suas portas pelos nomes. #(.PARAM(valor)) "
         "ajusta parâmetros na instância.",
         "module topo(input wire x, z, output wire w);\n  porta_e u1(.a(x), .b(z), .y(w));\nendmodule\n"
         "module porta_e(input wire a, b, output wire y);\n  assign y = a & b;\nendmodule",
         "Ligar portas pela posição: trocar a ordem no módulo quebra a ligação sem aviso."),
        ("caso", (r"^\s*(?:\d+'[bdhoBDHO][0-9a-fA-FxXzZ_]+|[A-Z][A-Z0-9_]*)\s*(?:,\s*[\w']+\s*)*:",), "Itens do case",
         "Cada item do case tem o valor e, depois dos dois-pontos, o comando. Vários valores podem compartilhar um "
         "comando (2'd1, 2'd2: ...) e default cobre os demais.",
         "module par(input wire [1:0] n, output reg e_par);\n  always @*\n    case (n)\n      2'd0, 2'd2: e_par = 1;\n"
         "      default: e_par = 0;\n    endcase\nendmodule", "Repetir o mesmo valor em dois itens."),
        ("literais", (r"\d+'[bdhoBDHO][0-9a-fA-FxXzZ_]+",), "Literais com tamanho",
         "4'd9 é o número 9 com 4 bits em decimal; 8'hFF é 255 em hexadecimal e 4'b1010 é binário. x é valor "
         "desconhecido e z alta impedância. Dar o tamanho evita truncamentos inesperados.",
         "module t;\n  wire [7:0] cheio = 8'hFF;\n  wire [3:0] nove = 4'd9;\nendmodule",
         "Escrever 9 sem tamanho e ter 32 bits truncados em silêncio."),
    ),
)

VHDL = Ficha(
    fonte="https://ghdl.github.io/ghdl/",
    guia=("Entidade e arquitetura",
          "entity declara as portas do circuito e architecture descreve o comportamento. <= atribui sinais; um process "
          "com rising_edge(clk) descreve lógica sequencial.",
          "library ieee;\nuse ieee.std_logic_1164.all;\n\nentity porta_e is\n  port (a, b : in std_logic; y : out std_logic);\n"
          "end entity;\n\narchitecture rtl of porta_e is\nbegin\n  y <= a and b;\nend architecture;"),
    ambiente="Instale o GHDL: ghdl -a arquivo.vhd analisa, ghdl -e teste elabora a entidade do testbench e ghdl -r "
             "teste executa; --wave=ondas.ghw grava as ondas para o GTKWave. Use --std=08 para os recursos do "
             "VHDL-2008.",
    aulas=(
        ("processos", "Processos e lógica sequencial", "intermediario", "Lógica sequencial",
         "process (clk) executa quando clk muda; rising_edge(clk) seleciona a borda de subida e descreve flip-flops. "
         "Com numeric_std, unsigned permite somar e to_unsigned converte inteiros. Sinais recebem o novo valor com <= "
         "ao fim do processo.",
         "Implemente um contador de 4 bits com reset síncrono e habilitação usando unsigned; simule e confira que ele "
         "volta a 0 depois de 15.",
         "library ieee;\nuse ieee.std_logic_1164.all;\nuse ieee.numeric_std.all;\n\nentity contador is\n"
         "  port (clk, rst, en : in std_logic;\n        q : out unsigned(3 downto 0));\nend entity;\n\n"
         "architecture rtl of contador is\n  signal valor : unsigned(3 downto 0) := (others => '0');\nbegin\n"
         "  process (clk)\n  begin\n    if rising_edge(clk) then\n      if rst = '1' then\n"
         "        valor <= (others => '0');\n      elsif en = '1' then\n        valor <= valor + 1;\n      end if;\n"
         "    end if;\n  end process;\n  q <= valor;\nend architecture;",
         "Usar std_logic_arith ou std_logic_unsigned, pacotes antigos e não padronizados, em vez de ieee.numeric_std.",
         "O contador aumenta só com en = 1 e volta a 0 após o reset?"),
        ("testbench", "Testbench com assert", "intermediario", "Simulação",
         "O testbench é uma entidade sem portas que instancia o circuito com port map. Um processo gera os estímulos e "
         "espera com wait for 10 ns; assert ... report ... severity error acusa resultados errados. Termine o processo "
         "com wait; para a simulação parar.",
         "Teste a porta E do guia com as combinações de entrada usando assert para cada saída esperada; simule com ghdl "
         "e provoque uma falha trocando and por or.",
         "library ieee;\nuse ieee.std_logic_1164.all;\n\nentity porta_e is\n  port (a, b : in std_logic; y : out std_logic);\n"
         "end entity;\n\narchitecture rtl of porta_e is\nbegin\n  y <= a and b;\nend architecture;\n\nlibrary ieee;\n"
         "use ieee.std_logic_1164.all;\n\nentity teste is\nend entity;\n\narchitecture sim of teste is\n"
         "  signal a, b, y : std_logic;\nbegin\n  dut : entity work.porta_e port map (a => a, b => b, y => y);\n\n"
         "  process\n  begin\n    a <= '0'; b <= '1'; wait for 10 ns;\n"
         "    assert y = '0' report \"0 and 1 deveria ser 0\" severity error;\n    a <= '1'; b <= '1'; wait for 10 ns;\n"
         "    assert y = '1' report \"1 and 1 deveria ser 1\" severity error;\n    report \"teste concluido\";\n    wait;\n"
         "  end process;\nend architecture;",
         "Terminar o processo de estímulos sem wait;: ele recomeça do início e a simulação nunca para.",
         "ghdl -r teste mostra a mensagem final sem erros de assert? Trocar and por or faz o assert acusar?"),
        ("fsm", "Máquina de estados com tipo enumerado", "avancado", "Lógica sequencial",
         "type estado_t is (verde, amarelo, vermelho) cria um tipo com nomes legíveis e um sinal desse tipo guarda o "
         "estado. case estado is ... when ... => escolhe a transição e when others cobre o restante. O sintetizador "
         "escolhe a codificação dos estados.",
         "Descreva o semáforo com três estados e uma entrada de avanço; no testbench, avance seis vezes e confira a "
         "sequência com assert.",
         "library ieee;\nuse ieee.std_logic_1164.all;\n\nentity semaforo is\n  port (clk, rst, avancar : in std_logic;\n"
         "        luz_verde : out std_logic);\nend entity;\n\narchitecture rtl of semaforo is\n"
         "  type estado_t is (verde, amarelo, vermelho);\n  signal estado : estado_t := verde;\nbegin\n  process (clk)\n"
         "  begin\n    if rising_edge(clk) then\n      if rst = '1' then\n        estado <= verde;\n"
         "      elsif avancar = '1' then\n        case estado is\n          when verde => estado <= amarelo;\n"
         "          when amarelo => estado <= vermelho;\n          when others => estado <= verde;\n        end case;\n"
         "      end if;\n    end if;\n  end process;\n  luz_verde <= '1' when estado = verde else '0';\nend architecture;",
         "Esquecer when others: o compilador recusa o case quando nem todos os valores do tipo foram cobertos.",
         "A saída luz_verde volta a 1 a cada três avanços? Um reset no meio volta ao verde?"),
        ("projeto", "Projeto: divisor de frequência verificado", "avancado", "Projeto e revisão",
         "Um divisor de frequência conta bordas do relógio e inverte a saída a cada N contagens; generic permite "
         "escolher N ao instanciar. O testbench gera o relógio, mede o período da saída e confere com assert. Rode com "
         "ghdl e grave as ondas com --wave para o GTKWave.",
         "Implemente o divisor com generic N, instancie com N = 4 num testbench, gere 40 bordas e confirme com assert "
         "que a saída troca a cada 4 bordas; abra as ondas no GTKWave.",
         "library ieee;\nuse ieee.std_logic_1164.all;\n\nentity divisor is\n  generic (N : positive := 4);\n"
         "  port (clk, rst : in std_logic;\n        saida : out std_logic);\nend entity;\n\narchitecture rtl of divisor is\n"
         "  signal contagem : natural range 0 to N - 1 := 0;\n  signal estado : std_logic := '0';\nbegin\n"
         "  process (clk)\n  begin\n    if rising_edge(clk) then\n      if rst = '1' then\n        contagem <= 0;\n"
         "        estado <= '0';\n      elsif contagem = N - 1 then\n        contagem <= 0;\n        estado <= not estado;\n"
         "      else\n        contagem <= contagem + 1;\n      end if;\n    end if;\n  end process;\n  saida <= estado;\n"
         "end architecture;",
         "Contar até N em vez de N - 1 e ter o período errado por uma borda, erro que só aparece comparando com o valor "
         "esperado.",
         "A saída troca a cada N bordas para N = 4 e N = 5? O assert acusa se você trocar N - 1 por N?"),
    ),
    referencia=(
        ("biblioteca", (r"^\s*(?:library|use)\b",), "library e use",
         "library ieee; torna a biblioteca visível e use ieee.std_logic_1164.all; importa std_logic e "
         "std_logic_vector. use ieee.numeric_std.all; traz unsigned e signed para contas.",
         "library ieee;\nuse ieee.std_logic_1164.all;\nuse ieee.numeric_std.all;",
         "Repetir library/use só no início do arquivo: cada entidade precisa das suas cláusulas."),
        ("entidade", (r"^\s*entity\b", r"^\s*end\s+entity\b"), "entity · interface do circuito",
         "entity nome is port (...); end entity; descreve o que o circuito expõe, sem dizer como funciona. Um "
         "testbench é uma entidade sem portas.",
         "entity somador is\n  port (a, b : in integer; s : out integer);\nend entity;",
         "Esquecer o ponto e vírgula depois do port (...)."),
        ("portas", (r"\bport\s*\(", r":\s*(?:in|out|inout|buffer)\s"), "port · entradas e saídas",
         "Cada porta tem nome, direção (in, out, inout) e tipo. std_logic é um bit com valores como '0', '1', 'Z' e "
         "'U'; std_logic_vector(7 downto 0) é um barramento de 8 bits.",
         "entity registro is\n  port (clk : in std_logic;\n        d : in std_logic_vector(7 downto 0);\n"
         "        q : out std_logic_vector(7 downto 0));\nend entity;",
         "Ler uma porta out dentro da arquitetura em VHDL-93: use um sinal interno."),
        ("generic", (r"^\s*generic\b", r"\bgeneric\s+map\b"), "generic · parâmetros",
         "generic (N : positive := 4); declara um parâmetro com valor padrão, ajustado na instância com generic map "
         "(N => 8). Larguras de barramento e contagens costumam ser genéricas.",
         "entity contador_n is\n  generic (LARGURA : positive := 8);\n  port (clk : in bit);\nend entity;",
         "Escrever números fixos espalhados pela arquitetura em vez de usar o generic."),
        ("arquitetura", (r"^\s*architecture\b", r"^\s*end\s+architecture\b", r"^\s*begin\b"),
         "architecture · comportamento",
         "architecture nome of entidade is declara sinais antes do begin e descreve o comportamento depois dele. Os "
         "comandos fora de process são concorrentes: valem todos ao mesmo tempo.",
         "architecture rtl of porta_ou is\nbegin\n  y <= a or b;\nend architecture;",
         "Esperar que linhas fora de process rodem em sequência."),
        ("sinais", (r"^\s*(?:signal|constant|variable|type|subtype)\b",), "signal, variable e type",
         "signal liga partes do circuito e muda ao fim do passo de simulação; variable (dentro de process) muda na "
         "hora com :=. type cria tipos, como enumerações de estados, e constant valores fixos.",
         "architecture rtl of exemplo is\n  type cor_t is (vermelho, verde);\n  signal cor : cor_t := verde;\n"
         "  constant LIMITE : integer := 10;\nbegin\nend architecture;",
         "Usar variable para comunicar entre processos: só sinais fazem isso."),
        ("atribuicao", (r"<=",), "<= · atribuição de sinal",
         "sinal <= expressão; agenda o novo valor. Fora de process é uma atribuição concorrente; com when ... else "
         "escolhe valores; dentro de process vale o último valor atribuído no passo.",
         "architecture rtl of mux is\nbegin\n  y <= a when s = '0' else b;\nend architecture;",
         "Confundir <= (sinal) com := (variável e valor inicial)."),
        ("processo", (r"^\s*(?:\w+\s*:\s*)?process\b", r"^\s*end\s+process\b", r"\b(?:rising|falling)_edge\s*\("),
         "process e rising_edge",
         "process (lista) executa quando algum sinal da lista muda; dentro dele os comandos rodam em sequência. "
         "if rising_edge(clk) then descreve registradores atualizados na borda de subida.",
         "process (clk)\nbegin\n  if rising_edge(clk) then\n    q <= d;\n  end if;\nend process;",
         "Esquecer um sinal lido na lista de sensibilidade de um processo combinacional."),
        ("condicao", (r"^\s*(?:if|elsif|else|end\s+if|case|when|end\s+case|for|loop|end\s+loop)\b",),
         "if, case e laços",
         "if ... then ... elsif ... else ... end if; e case ... is when ... => ... end case; escolhem comandos dentro "
         "de process. for i in 0 to 7 loop repete; em síntese, cada repetição vira hardware.",
         "process (s)\nbegin\n  case s is\n    when \"00\" => y <= '1';\n    when others => y <= '0';\n  end case;\n"
         "end process;",
         "Escrever else if em vez de elsif e precisar de um end if a mais."),
        ("testbench", (r"^\s*wait\b", r"^\s*(?:assert|report)\b"), "wait, assert e report",
         "wait for 10 ns; pausa o processo de estímulos, wait until clk = '1'; espera uma condição e wait; para para "
         "sempre. assert condição report \"mensagem\" severity error; acusa quando a condição é falsa.",
         "process\nbegin\n  wait for 10 ns;\n  assert soma = 4 report \"soma errada\" severity error;\n  wait;\nend process;",
         "Usar wait for em código para síntese: só vale em simulação."),
        ("instancia", (r"\bentity\s+work\.", r"\bport\s+map\b"), "Instâncias: entity work e port map",
         "rotulo : entity work.nome port map (porta => sinal, ...); cria uma instância de outra entidade e liga as "
         "portas pelo nome. generic map ajusta os parâmetros.",
         "u1 : entity work.porta_e port map (a => x, b => z, y => w);",
         "Ligar portas pela posição e trocá-las sem perceber."),
        ("numeric", (r"\b(?:unsigned|signed|to_unsigned|to_signed|to_integer|resize|natural|positive)\b",),
         "numeric_std e inteiros",
         "unsigned e signed são vetores com aritmética; to_unsigned(5, 4) converte o inteiro 5 para 4 bits e "
         "to_integer faz o inverso. natural e positive são inteiros sem sinal e a partir de 1.",
         "signal n : unsigned(3 downto 0) := to_unsigned(5, 4);\nsignal i : natural range 0 to 15 := 0;",
         "Somar std_logic_vector diretamente: converta para unsigned antes."),
    ),
)

SOLIDITY = Ficha(
    fonte="https://docs.soliditylang.org/",
    guia=("Contrato, estado e funções",
          "Um contract guarda variáveis de estado na blockchain e expõe funções. pragma fixa a versão do compilador; "
          "funções view leem sem alterar e cada escrita custa gas.",
          "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\ncontract Contador {\n    uint256 public valor;\n\n"
          "    function incrementar() external {\n        valor += 1;\n    }\n}"),
    ambiente="Compile com solc (ou solcjs, do npm) e teste num ambiente local como Foundry (forge test) ou Hardhat; o "
             "Remix roda no navegador. Nunca publique numa rede principal sem testes e auditoria: transações não podem "
             "ser desfeitas.",
    aulas=(
        ("mapeamentos", "Mapeamentos, structs e msg.sender", "intermediario", "Estado",
         "mapping(address => Aluno) associa cada endereço a um valor e devolve o valor zero para chaves nunca escritas. "
         "struct agrupa campos. msg.sender é quem chamou a função: a base de qualquer controle de acesso. Funções view "
         "leem o estado sem custo quando chamadas fora de uma transação.",
         "Crie um cadastro de alunos com struct Aluno (nome e nota), mapping por endereço e funções para registrar a "
         "própria nota e consultar a de alguém; teste com duas contas no Remix ou no Foundry.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\ncontract Notas {\n    struct Aluno {\n"
         "        string nome;\n        uint8 nota;\n    }\n\n    mapping(address => Aluno) private alunos;\n\n"
         "    function registrar(string calldata nome, uint8 nota) external {\n"
         "        alunos[msg.sender] = Aluno(nome, nota);\n    }\n\n"
         "    function notaDe(address conta) external view returns (uint8) {\n        return alunos[conta].nota;\n    }\n}",
         "Confiar que dados private são secretos: tudo o que está na blockchain pode ser lido; private só impede outros "
         "contratos de acessar.",
         "Cada conta só altera a própria nota? notaDe devolve 0 para quem nunca se registrou?"),
        ("eventos_erros", "Validação, erros e eventos", "intermediario", "Transações",
         "require(condição, \"mensagem\") e erros personalizados (error SaldoInsuficiente(...) com revert) desfazem a "
         "transação inteira. event declara um registro que aplicativos acompanham e emit o publica. Desde a versão 0.8, "
         "contas que estouram o limite do tipo revertem automaticamente.",
         "Escreva um cofre com depositar (payable) e sacar, recusando saque acima do saldo com um erro personalizado e "
         "emitindo os eventos Deposito e Saque; confira os eventos no registro da transação.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\ncontract Cofre {\n"
         "    mapping(address => uint256) public saldos;\n\n    event Deposito(address indexed conta, uint256 valor);\n"
         "    event Saque(address indexed conta, uint256 valor);\n"
         "    error SaldoInsuficiente(uint256 disponivel, uint256 pedido);\n\n    function depositar() external payable {\n"
         "        require(msg.value > 0, \"envie algum valor\");\n        saldos[msg.sender] += msg.value;\n"
         "        emit Deposito(msg.sender, msg.value);\n    }\n\n    function sacar(uint256 valor) external {\n"
         "        uint256 saldo = saldos[msg.sender];\n        if (valor > saldo) revert SaldoInsuficiente(saldo, valor);\n"
         "        saldos[msg.sender] = saldo - valor;\n        (bool ok, ) = payable(msg.sender).call{value: valor}(\"\");\n"
         "        require(ok, \"falha ao enviar\");\n        emit Saque(msg.sender, valor);\n    }\n}",
         "Usar transfer ou send, com limite fixo de gas, que falham com carteiras de contrato; prefira call e confira o "
         "retorno.",
         "Um saque acima do saldo reverte com SaldoInsuficiente e os valores certos? Os eventos aparecem no registro?"),
        ("seguranca", "Segurança: reentrância e controle de acesso", "avancado", "Segurança",
         "Um contrato que envia valor antes de atualizar o saldo permite reentrância: o destinatário chama sacar de "
         "novo antes da primeira chamada terminar. Siga verificações, efeitos e interações, nessa ordem, e restrinja "
         "funções administrativas com um modificador que confere msg.sender.",
         "Escreva uma versão vulnerável do saque (envio antes do débito) e um contrato atacante num ambiente local; "
         "mostre o ataque e depois corrija com a ordem certa e um modificador apenasDono.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\ncontract Caixa {\n    address public immutable dono;\n"
         "    mapping(address => uint256) public saldos;\n    bool public pausado;\n    bool private emUso;\n\n"
         "    constructor() {\n        dono = msg.sender;\n    }\n\n    modifier apenasDono() {\n"
         "        require(msg.sender == dono, \"apenas o dono\");\n        _;\n    }\n\n    modifier semReentrada() {\n"
         "        require(!emUso, \"reentrada\");\n        emUso = true;\n        _;\n        emUso = false;\n    }\n\n"
         "    function depositar() external payable {\n        require(!pausado, \"pausado\");\n"
         "        saldos[msg.sender] += msg.value;\n    }\n\n    function sacar(uint256 valor) external semReentrada {\n"
         "        require(saldos[msg.sender] >= valor, \"saldo insuficiente\");\n        saldos[msg.sender] -= valor;\n"
         "        (bool ok, ) = payable(msg.sender).call{value: valor}(\"\");\n        require(ok, \"falha ao enviar\");\n"
         "    }\n\n    function pausar() external apenasDono {\n        pausado = true;\n    }\n}",
         "Enviar valor antes de atualizar o estado, ou autorizar com tx.origin: um contrato intermediário engana essa "
         "verificação.",
         "O ataque de reentrância falha na versão corrigida? Uma conta que não é a dona recebe \"apenas o dono\" ao "
         "pausar?"),
        ("projeto", "Projeto: token com testes", "avancado", "Projeto e revisão",
         "O projeto é um token simples com nome, símbolo, saldos e transferências, seguindo as partes essenciais da "
         "interface ERC-20. Em produção, use implementações auditadas como as da OpenZeppelin; escrever do zero serve "
         "para entender. Teste cada função num ambiente local antes de qualquer rede pública.",
         "Implemente totalSupply, balanceOf, transfer, approve, allowance e transferFrom com eventos; escreva testes "
         "para transferência acima do saldo, aprovação parcial e transferência para o endereço zero.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\ncontract TokenEstudo {\n"
         "    string public constant name = \"Token de Estudo\";\n    string public constant symbol = \"EST\";\n"
         "    uint8 public constant decimals = 18;\n    uint256 public totalSupply;\n"
         "    mapping(address => uint256) public balanceOf;\n"
         "    mapping(address => mapping(address => uint256)) public allowance;\n\n"
         "    event Transfer(address indexed de, address indexed para, uint256 valor);\n"
         "    event Approval(address indexed dono, address indexed gastador, uint256 valor);\n\n"
         "    constructor(uint256 inicial) {\n        totalSupply = inicial;\n        balanceOf[msg.sender] = inicial;\n"
         "        emit Transfer(address(0), msg.sender, inicial);\n    }\n\n"
         "    function transfer(address para, uint256 valor) external returns (bool) {\n"
         "        _mover(msg.sender, para, valor);\n        return true;\n    }\n\n"
         "    function approve(address gastador, uint256 valor) external returns (bool) {\n"
         "        allowance[msg.sender][gastador] = valor;\n        emit Approval(msg.sender, gastador, valor);\n"
         "        return true;\n    }\n\n    function transferFrom(address de, address para, uint256 valor) external returns "
         "(bool) {\n        allowance[de][msg.sender] -= valor;\n        _mover(de, para, valor);\n        return true;\n"
         "    }\n\n    function _mover(address de, address para, uint256 valor) private {\n"
         "        require(para != address(0), \"destino zero\");\n        balanceOf[de] -= valor;\n"
         "        balanceOf[para] += valor;\n        emit Transfer(de, para, valor);\n    }\n}",
         "Publicar um token escrito do zero sem testes nem auditoria, ou esquecer de emitir Transfer, que carteiras usam "
         "para mostrar saldos.",
         "Transferir acima do saldo reverte? transferFrom só funciona dentro do valor aprovado?"),
    ),
    referencia=(
        ("licenca", (r"SPDX-License-Identifier:",), "SPDX-License-Identifier · licença do código",
         "O comentário // SPDX-License-Identifier: MIT na primeira linha declara a licença do código-fonte, que fica "
         "público quando o contrato é verificado num explorador. O compilador avisa quando a linha falta; use "
         "UNLICENSED para código sem licença aberta.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;", "Omitir a linha e publicar sem deixar clara a "
                                                                      "licença."),
        ("pragma", (r"^\s*pragma\b",), "pragma solidity · versão do compilador",
         "pragma solidity ^0.8.24; aceita compiladores 0.8.24 ou mais novos da série 0.8. Fixe uma faixa conhecida: "
         "versões diferentes mudam regras de segurança e otimização. A linha SPDX acima declara a licença.",
         "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;", "Usar uma faixa ampla como >=0.4."),
        ("contrato", (r"^\s*(?:abstract\s+)?(?:contract|interface|library)\b",), "contract, interface e library",
         "contract define estado e funções; interface só declara funções que outro contrato implementa; library reúne "
         "funções reutilizáveis. contract B is A herda de A.",
         "interface IContador {\n    function valor() external view returns (uint256);\n}\n\n"
         "contract Contador is IContador {\n    uint256 public valor;\n}",
         "Herdar de vários contratos sem entender a ordem de resolução (C3)."),
        ("tipos", (r"^\s*(?:uint\d*|int\d*|address|bool|string|bytes\d*|mapping)\b",), "Tipos e variáveis de estado",
         "uint256 é inteiro sem sinal de 256 bits; address guarda contas; bool, string e bytes32 são os demais tipos "
         "comuns. Declaradas no contrato, ficam gravadas na blockchain (storage); dentro de funções, são locais.",
         "contract Tipos {\n    uint256 public total;\n    address public dono;\n    bool public ativo;\n}",
         "Usar string para dados que cabem em bytes32 ou uint e pagar mais gas."),
        ("funcao", (r"^\s*function\b", r"^\s*(?:constructor|receive|fallback|modifier)\b"),
         "Funções, construtor e modificadores",
         "function nome(parâmetros) visibilidade returns (tipos) define uma função. constructor roda uma vez na "
         "publicação; receive recebe valor sem dados; modifier envolve funções com verificações reutilizáveis.",
         "contract Loja {\n    address public dono;\n\n    constructor() {\n        dono = msg.sender;\n    }\n\n"
         "    receive() external payable {}\n}",
         "Esquecer que o construtor não pode ser chamado de novo depois da publicação."),
        ("visibilidade", (r"\b(?:public|external|internal|private)\b", r"\b(?:view|pure|payable|immutable|constant)\b"),
         "Visibilidade e mutabilidade",
         "external pode ser chamada de fora; public de fora e de dentro; internal só no contrato e nos herdeiros; "
         "private só no contrato. view lê o estado, pure não lê nada e payable aceita valor. constant e immutable fixam "
         "valores sem gastar storage.",
         "contract Taxas {\n    uint256 public constant TAXA = 2;\n\n    function calcular(uint256 v) external pure returns "
         "(uint256) {\n        return v * TAXA / 100;\n    }\n}",
         "Deixar uma função administrativa public sem verificação de quem chama."),
        ("erros", (r"\b(?:require|assert)\s*\(", r"^\s*error\b", r"\brevert\b"), "require, revert e erros",
         "require(condição, \"mensagem\") reverte a transação quando a condição é falsa e devolve o gas restante. "
         "error Nome(parametros) com revert Nome(...) é mais barato e informativo. assert é para invariantes que nunca "
         "deveriam falhar.",
         "contract Limite {\n    error AcimaDoLimite(uint256 pedido);\n\n    function checar(uint256 v) external pure {\n"
         "        if (v > 100) revert AcimaDoLimite(v);\n        require(v != 0, \"zero\");\n    }\n}",
         "Usar assert para validar entradas de usuários."),
        ("eventos", (r"^\s*event\b", r"\bemit\b"), "event e emit",
         "event declara um registro e emit o publica no log da transação. Até três parâmetros indexed permitem filtrar "
         "eventos. Contratos não leem eventos: eles servem para aplicativos e exploradores.",
         "contract Registro {\n    event Pago(address indexed de, uint256 valor);\n\n"
         "    function pagar() external payable {\n        emit Pago(msg.sender, msg.value);\n    }\n}",
         "Guardar em storage um histórico que poderia ser só eventos."),
        ("contexto", (r"\bmsg\.(?:sender|value|data)\b", r"\bblock\.(?:timestamp|number)\b", r"\baddress\(this\)"),
         "msg.sender, msg.value e block",
         "msg.sender é a conta ou contrato que chamou; msg.value o valor enviado em wei; block.timestamp a hora do bloco "
         "(pode variar alguns segundos); address(this).balance o saldo do contrato.",
         "contract Info {\n    function quem() external view returns (address, uint256) {\n"
         "        return (msg.sender, block.timestamp);\n    }\n}",
         "Usar block.timestamp como fonte de aleatoriedade."),
        ("struct", (r"^\s*(?:struct|enum)\b",), "struct e enum",
         "struct agrupa campos num tipo próprio; enum lista estados com nomes (o primeiro vale 0). São usados em "
         "mapeamentos e arrays de estado.",
         "contract Pedidos {\n    enum Status { Aberto, Pago }\n    struct Pedido {\n        uint256 valor;\n"
         "        Status status;\n    }\n}", "Acrescentar valores no meio de um enum já publicado."),
        ("atribuicao", (r"^\s*\w+(?:\[[^\]]*\])*(?:\.\w+)*\s*[-+*/]?=(?!=)",), "Alterar o estado",
         "Atribuir a uma variável de estado grava na blockchain e custa gas; ler é barato. Em mapeamentos, saldos[conta] "
         "+= valor soma ao valor guardado. Desde a 0.8, estouros revertem a transação.",
         "contract Pontos {\n    mapping(address => uint256) public pontos;\n\n    function ganhar() external {\n"
         "        pontos[msg.sender] += 10;\n    }\n}", "Fazer laços que escrevem muitas vezes no storage."),
        ("chamada", (r"\.call\{", r"\bpayable\("), "Enviar valor: call e payable",
         "payable(endereco).call{value: v}(\"\") envia v wei e devolve se deu certo; confira sempre o retorno. Envie "
         "valor só depois de atualizar o estado, para evitar reentrância.",
         "contract Pagador {\n    function pagar(address para) external payable {\n"
         "        (bool ok, ) = payable(para).call{value: msg.value}(\"\");\n        require(ok, \"falhou\");\n    }\n}",
         "Ignorar o retorno de call."),
        ("retorno", (r"^\s*return\b", r"\breturns\s*\("), "returns e return",
         "returns (tipo) na assinatura declara o que a função devolve; return valor; devolve. Uma função pode devolver "
         "vários valores: returns (uint256, bool).",
         "contract Soma {\n    function somar(uint256 a, uint256 b) external pure returns (uint256) {\n"
         "        return a + b;\n    }\n}", "Esquecer o return e devolver o valor zero sem aviso."),
        ("chamadas", (r"^\s*\w+\s*\([^;]*\)\s*;",), "Chamar funções do contrato",
         "nome(argumentos); chama outra função do mesmo contrato sem criar transação nova; funções private e internal "
         "costumam começar com _ por convenção. Chamar outro contrato (outro.funcao()) é uma chamada externa e pode "
         "falhar ou reentrar.",
         "contract Caixa {\n    uint256 public total;\n\n    function somar(uint256 v) external {\n        _registrar(v);\n"
         "    }\n\n    function _registrar(uint256 v) private {\n        total += v;\n    }\n}",
         "Expor como public uma função auxiliar que deveria ser private."),
        ("placeholder", (r"^\s*_;\s*$",), "_; · onde entra a função no modificador",
         "Num modifier, _; marca onde o corpo da função entra: o que vem antes roda antes dela e o que vem depois roda "
         "no fim.",
         "contract Dono {\n    address dono = msg.sender;\n\n    modifier apenasDono() {\n"
         "        require(msg.sender == dono, \"negado\");\n        _;\n    }\n}",
         "Esquecer o _; e a função nunca executar."),
        ("condicao", (r"^\s*(?:if|else|for|while|unchecked)\b",), "if, laços e unchecked",
         "if/else e laços funcionam como em C, mas cada repetição custa gas: laços sobre listas que crescem sem limite "
         "podem tornar a função impossível de executar. unchecked { } desliga a verificação de estouro.",
         "contract Laco {\n    function somar(uint256[] calldata v) external pure returns (uint256 t) {\n"
         "        for (uint256 i = 0; i < v.length; i++) {\n            t += v[i];\n        }\n    }\n}",
         "Percorrer todos os usuários num laço dentro de uma transação."),
    ),
)

FICHAS = {"verilog": VERILOG, "vhdl": VHDL, "solidity": SOLIDITY}
