# Qualidade, CI e critérios de liberação

Etapa 0 do roteiro de melhorias: diagnosticar o CI, registrar uma linha de base verificável e definir o que precisa
estar verde antes de uma versão estável. Os números abaixo são medições locais; não substituem o CI remoto.

## Diagnóstico do GitHub Actions (29/10/2026)

As execuções do workflow `CI` em `main` (execuções 73 a 82, de 17/10/2026) falharam em todos os 10 jobs, com duração
de 2 a 8 segundos. Nenhum job recebeu um runner (`runner_id: 0`, sem nome de runner), nenhum passo foi executado e os
logs não existem (a API devolve 404). Um teste que falha produz passos e logs; aqui o job termina antes de começar.

**Conclusão:** a falha é de infraestrutura do Actions na conta ou no repositório, não do código. As causas típicas
desse sintoma são limite de gastos ou de minutos do Actions atingido, pendência de pagamento na conta, ou Actions
desativado/restrito nas configurações do repositório. Quem administra o repositório deve conferir:

1. **Settings → Billing and plans** da conta: uso de minutos do Actions, limite de gastos (*spending limit*) e
   pendências de pagamento.
2. **Settings → Actions → General** do repositório: Actions habilitado e as ações usadas (`actions/checkout`,
   `actions/setup-python`, `actions/setup-node`, `rhysd/action-setup-vim`, `actions/upload-artifact`) permitidas.
3. Depois de corrigir, executar de novo o workflow mais recente (*Re-run all jobs*) ou usar `workflow_dispatch`.

Enquanto os runners não executarem, o CI não comprova nada — nem falha, nem sucesso. A inspeção local encontrou um
defeito real que teria aparecido assim que os runners voltassem: `tests/test_estudo_multilingue.py` importava
`tests.test_estudo`, que só existe com `python -m pytest`; o `pytest` do CI falharia sempre. Foi corrigido, junto de
um teste do Studio que dependia de tempo (`tests/test_studio_review.py`).

## Linha de base local

Linux, Python 3.13, Node.js 22, Rust e Go instalados; sem Dart, PowerShell, Kotlin, Docker nem modelo GGUF.

| Verificação | Resultado |
|---|---|
| `pytest` (suíte completa) | **1569 aprovados, 52 ignorados, 0 falhas** (1621 coletados, cerca de 2,5 min) |
| `python -m codar.evals.patternlint` | 132 padrões, 352 variantes validadas, 56 sem validador, **0 erros de sintaxe, 158 execuções, 0 falhas** |
| `python packaging/check_versions.py` | versões e changelog consistentes |

A primeira execução desta linha de base encontrou dois defeitos, corrigidos antes de registrar os números:

- **patternlint em Go:** as variantes Go eram executadas com `go run`, que sai com 1 sempre que o programa falha;
  as três execuções de `cli.subcommands` que esperam o código 2 falhavam. Os runners do GitHub têm Go instalado, então
  o job *Banco de padrões* teria falhado. Agora o programa é compilado e o binário executado, preservando o código de
  saída (`tests/test_patternlint_sessao.py`).
- **Studio ao fechar:** uma troca de aba do painel enfileirada podia chegar depois de a tela ser desmontada e lançar
  `NoMatches`. O handler usa o painel que vem no próprio evento. O teste de prévia aciona o botão sem depender da
  posição na tela.

Os testes ignorados não são aprovações: dependem de SDKs ausentes (Dart, PowerShell, Kotlin), de contêineres, de um
modelo GGUF (`CODAR_TEST_MODEL`) ou de Xvfb, ou documentam construções sem equivalente na linguagem (classes em Bash,
listas dinâmicas em C).

## Critérios de liberação de uma versão estável

Uma versão só é publicada como estável quando:

1. **CI remoto:** 100% dos jobs obrigatórios de `.github/workflows/ci.yml` aprovados no commit da versão — testes em
   Python 3.10, 3.12 e 3.13, banco de padrões, edição e recuperação em Windows e macOS, plugins de Neovim e Vim,
   cliente VS Code em Ubuntu e Windows e instalação dos pacotes em contêineres. Um job que não executou conta como
   **não aprovado**.
2. **Suíte local:** `pytest` sem falhas; cada teste ignorado tem motivo registrado.
3. **Banco de padrões:** `patternlint` com 0 erros e 0 falhas.
4. **Cenários mínimos:** os oito cenários abaixo aprovados (`pytest tests/test_regressao_minima.py` confere que a
   tabela aponta para testes existentes).
5. **Versões:** `python packaging/check_versions.py` sem divergências.
6. **Documentação:** CHANGELOG e documentos refletem o que foi validado; limitações conhecidas declaradas; nada
   anunciado como concluído sem verificação.
7. **Arquivos do usuário:** nenhuma alteração inesperada — edições passam por prévia/histórico e exercícios
   preservam a solução.

Alfas e prévias podem ser publicadas sem o item 1, desde que as notas digam explicitamente que o CI remoto não
executou e quais verificações foram locais.

## Cenários mínimos de regressão

| Cenário do roteiro | Teste |
|---|---|
| Importação isolada produz somente import | `tests/test_import_scope.py::test_importacao_nativa_nao_vira_programa`, `tests/test_import_scope.py::test_bloco_so_de_importacoes_nao_vira_funcoes` |
| Importar símbolo próprio do projeto, inclusive em subpastas | `tests/test_library_context.py::test_modulo_proprio_em_subpasta` |
| Modificar uma função sem afetar trechos vizinhos | `tests/test_continuity.py::test_studio_edita_somente_a_funcao_sob_o_cursor`, `tests/test_import_scope.py::test_substitui_so_a_linha_de_intencao_e_preserva_as_vizinhas` |
| Abrir Estudo em Rust, Python e demais linguagens | `tests/test_estudo_multilingue.py::test_painel_nativo_ao_trocar_entre_todas_linguagens`, `tests/test_estudo_construcoes.py::test_linhas_das_proprias_aulas_tem_explicacao_especifica` |
| Confirmar instalação no ambiente escolhido, sem tocar o runtime do Codar | `tests/test_library_packages.py::test_python_cria_ambiente_do_projeto_sem_alterar_codar`, `tests/test_library_packages.py::test_cli_instalacao_exige_confirmacao_sem_terminal` |
| Operar os recursos determinísticos com IA desativada | `tests/test_regressao_minima.py::test_recursos_deterministicos_funcionam_com_a_ia_desativada` |
| Trocar locale e manter os comandos semanticamente equivalentes | `tests/test_i18n.py::test_intencoes_equivalentes_usam_mesmo_compilador`, `tests/test_i18n.py::test_classe_da_intencao_equivalente_nos_quatro_idiomas` |
| Cancelar geração sem perder alterações anteriores | `tests/test_cancellation.py::test_cancelar_no_studio_descarta_resposta_tardia_sem_perder_codigo` |

## Metas de qualidade

- 100% dos jobs obrigatórios aprovados antes de uma versão estável.
- Testes de ponta a ponta para os fluxos essenciais: importar, editar com prévia, estudar, instalar com confirmação e
  cancelar.
- Cobertura crescente nos módulos críticos (roteador, edição, importação, estudo). Cobertura alta, sozinha, não
  demonstra correção: cada teste novo deve falhar quando o comportamento que ele protege for quebrado.
