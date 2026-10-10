# Bibliotecas e código do seu projeto — CODAR 0.3.2

O CODAR separa três ações: **importar**, **consultar a API** e **instalar a dependência**. Importar gera somente a declaração pedida. A consulta usa referências locais. Instalação é um comando explícito, no ambiente do projeto.

## Importar suas próprias funções

Suponha que a pasta contenha `app.py` e `util.py`:

```python
# util.py
def somar(a: int, b: int = 1) -> int:
    """Soma dois valores."""
    return a + b
```

Execute na pasta do projeto:

```bash
codar run "importar função somar do arquivo util.py" --file app.py --stages 0
```

Resultado:

```python
from util import somar
```

Também funcionam pedidos como `importe minha função somar`, `importe a classe Cliente de cliente.py` e `importe todas as funções de util.py`. O último importa explicitamente as funções públicas encontradas, sem usar `*` ou copiar suas definições. Arquivos em subpastas e layout `src` são considerados. Dentro de um pacote Python com `__init__.py`, um módulo vizinho usa import relativo, por exemplo `from .util import somar`.

Sem `--file`, o CLI usa a pasta atual. `--root CAMINHO` escolhe outra raiz. Editores enviam o arquivo e/ou a raiz do projeto. Se não houver essa informação, um pedido de código próprio pede que você indique a origem. Funções homônimas, arquivos ausentes e nomes inválidos produzem uma mensagem antes de gerar qualquer código. O scanner respeita exclusões do projeto e `.gitignore`; não acompanha links nem procura fora da raiz.

## Importar uma biblioteca

```bash
codar run "importar bibliotecas numpy e pandas" -l python --stages 0
codar run "importar classe FastAPI de fastapi" -l python --stages 0
codar run "importar função useState de react" -l typescript --stages 0
```

```python
import numpy as np
import pandas as pd
# O segundo pedido gera somente: from fastapi import FastAPI
```

`importar biblioteca requests para consultar uma API` gera somente `import requests`. Para implementar a funcionalidade, faça um pedido explícito separado. Um módulo informado tem prioridade sobre palavras da finalidade: `importar requests para consultar YouTube` mantém Requests. Imports nativos preservam nomes e aliases.

O reconhecimento pelo nome é genérico: um módulo Python particular válido e um pacote npm como `@empresa/meu-pacote` também podem ser importados offline. Nomes de distribuição conhecidos são relacionados ao módulo correspondente. Aliases pedidos com `como`/`as` prevalecem sobre aliases usuais. Símbolos informados explicitamente usam `from ... import ...` no Python ou imports nomeados no JavaScript/TypeScript; não são criados símbolos novos.

| Uso | Exemplos com reconhecimento offline |
|---|---|
| Dados e ciência | NumPy, pandas, SciPy, matplotlib, seaborn, Polars |
| IA e aprendizado de máquina | PyTorch/torch, TensorFlow, scikit-learn/sklearn, transformers |
| Web, APIs e dados | Requests, HTTPX, FastAPI, Flask, Django, Pydantic, SQLAlchemy |
| Imagens e interface Python | Pillow/PIL, OpenCV/cv2, PySide6, PyQt6, Tkinter |
| JavaScript/TypeScript | React, Express, Axios, lodash, three, pacotes com escopo e nomes particulares |
| Dart/Flutter | Dio, HTTP, Provider, BLoC, Riverpod, GoRouter, GetIt |
| Outros ecossistemas | Gin/Go, serde-json/Rust, Gson/Java, Newtonsoft.Json e Dapper/C#, fmt/C++, libcurl/C, Nokogiri/Ruby, Guzzle/PHP, Pester/PowerShell, Alamofire/Swift, ggplot2/R, DataFrames/Julia |

A tabela mostra exemplos, não uma lista fechada nem uma garantia de disponibilidade no seu projeto. Para Dart, C/C++ e bibliotecas com entradas diferentes do nome de instalação, informe uma entrada conhecida ou forneça o import nativo; o CODAR não inventa headers/arquivos de entrada. Java/Kotlin permitem indicar o namespace ou símbolo. JavaScript/TypeScript usa imports ESM nos pedidos em linguagem natural; imports nativos CommonJS são preservados.

Sem um nome/entrada resolvível, a IA local opcional pode sugerir somente o import. A saída é validada antes de ser exibida ou aplicada. Funções, downloads e comandos concatenados não passam como imports. SQL, YAML e Dockerfile não recebem imports de bibliotecas de outra linguagem.

## Consultar APIs reais

Quando há imports no contexto, o CODAR procura assinaturas, docstrings, tipos e documentação local. Essas referências também participam da tradução literal e da edição de código existente. Imports no topo do arquivo salvo podem ser consultados mesmo quando estão fora da janela do cursor; imports do buffer enviado pelo editor têm prioridade.

| Ecossistema | Fontes procuradas automaticamente |
|---|---|
| Python | Módulos do projeto e layout `src`; `.py`/`.pyi` nos venvs e no runtime escolhido; metadados da distribuição, docstrings, reexportações aninhadas e tabelas literais de exports sob demanda, sem executar `__getattr__` |
| JavaScript/TypeScript | `node_modules`, pacotes com escopo, versão no `package.json`, entradas `types`/`typings`/`main`/`module`, declarações e README; tipos externos `@types` quando não há tipos embutidos; módulos relativos |
| Dart/Flutter | Mapeamento `.dart_tool/package_config.json`, `pubspec.yaml`, fontes e documentação do pacote |
| Rust | Versão do `Cargo.lock` e fontes disponíveis no cache do Cargo |
| Go | Versão do `go.mod` e fontes disponíveis no cache de módulos |
| C# | Pacotes resolvidos em `obj/project.assets.json` e documentação XML/fontes disponíveis no cache NuGet |
| Outros | Fontes/documentação nas pastas `vendor`, `lib`, `libs`, `packages` e `docs`, ou referência fornecida com `--source` |

O catálogo fica separado por **projeto, linguagem, origem, versão e hash do conteúdo**. Uma mudança nas fontes invalida a referência anterior. A versão resolvida pelo projeto é usada quando seus metadados estão disponíveis; o CODAR não escolhe uma versão do cache por ser a mais nova. Referências manuais usam a versão informada e a última referência fornecida para aquele módulo.

**Consultar não executa a biblioteca.** O CODAR não usa imports, reflection ou scripts do pacote para descobrir a API. Há limites de arquivos, tamanho e contexto; nem toda API de um pacote grande cabe em uma geração. Um pacote somente binário, sem fontes/tipos/documentação acessíveis, informa a falta de referências. Isso é contexto para a IA local, não treinamento de pesos e nem garantia de que toda chamada gerada seja correta.

O pedido orienta a seleção: `ler CSV com pandas.read_csv` prioriza `read_csv`; `usar BaseModel.model_dump` prioriza esse método. A referência identifica o arquivo de origem, para distinguir funções homônimas. A leitura usa até 24 arquivos, até 512 KB por arquivo e até 600 declarações, com referências limitadas ao contexto do modelo. Assinaturas muito longas são identificadas como abreviadas. Os tipos externos mostram tanto a versão do pacote quanto a versão de `@types`.

## Gerenciar o catálogo

```bash
codar libraries learn minha_biblioteca --root .
codar libraries list --root .
codar libraries show minha_biblioteca --root .
codar libraries verify minha_biblioteca --root .
codar libraries forget minha_biblioteca --root .
```

`verify` relê a origem e atualiza a referência se ela mudou. `forget` remove somente referências do catálogo; o pacote e o código do projeto continuam instalados. Um import posterior pode consultá-los novamente. `bibliotecas` é um alias em português. `--json` oferece saída estruturada para consultas e prévias.

Para uma biblioteca fora dos resolvedores automáticos, forneça a documentação ou o código:

```bash
codar libraries learn videos -l powershell --source ./documentacao/API.md --library-version 2.1.0
codar libraries learn meu_sdk -l java --source ./documentacao/meu-sdk --library-version 4.0.0
```

Referências fornecidas funcionam nas **24 linguagens/formatos registrados**. Use como nome o módulo/pacote que aparece no import. Quando ele aparecer no contexto de código de uma linguagem com imports, o CODAR poderá incluir a referência na geração. HTML/CSS e formatos de configuração também permitem consultar o catálogo pelo CLI; isso não acrescenta uma sintaxe de importação ao formato.

Prefira documentação da versão usada no projeto. Não há download automático de páginas ao importar. A consulta funciona offline com as fontes locais disponíveis. Dados das bibliotecas são tratados como referência, com neutralização de delimitadores de prompt; não viram instruções do sistema.

## Instalar no ambiente do projeto

Veja o plano antes de instalar:

```bash
codar libraries install scikit-learn -l python --dry-run
codar libraries install scikit-learn -l python
codar libraries install Pillow -l python
codar libraries install axios -l typescript --dry-run
```

No Python, o comando usa o venv escolhido para o projeto ou um venv existente. Se nenhum estiver disponível, cria `.venv` com o runtime escolhido; não sobrescreve uma pasta existente inválida. A instalação não usa o ambiente do CODAR como destino. Relações conhecidas como `scikit-learn`/`sklearn`, `Pillow`/`PIL` e `beautifulsoup4`/`bs4` são automáticas. `--module` permite informar outras relações. Para fixar uma versão, acrescente `--library-version NUMERO`.

| Linguagem | Gerenciador de instalação |
|---|---|
| Python | `python -m pip` no ambiente do projeto |
| JavaScript/TypeScript | npm, pnpm, Yarn ou Bun, conforme o lockfile/configuração do projeto |
| Dart/Flutter | `dart pub add` ou `flutter pub add` |
| Rust | `cargo add` e `cargo fetch` |
| Go | `go get` |
| C# | `dotnet add ... package` |
| PHP | `composer require` |
| Ruby | `bundle add` |

Os projetos devem ter seus manifestos, como `package.json`, `pubspec.yaml` ou `Cargo.toml`. Falta de SDK, falha do gerenciador ou múltiplos `.csproj` produz uma mensagem; uma instalação malsucedida não é marcada como pronta. Os comandos usam argumentos separados, sem transformar nomes de pacotes em comandos de shell. Instalação usa rede e o gerenciador pode executar os procedimentos normais do pacote; inspeção de API continua estática.

Para uma linguagem sem adaptador de instalação, use seu gerenciador habitual e depois `libraries learn --source`. Tkinter é parte do Tcl/Tk da distribuição Python: não existe instalação válida por `pip install tkinter`; siga o cartão do consultor para o sistema e runtime selecionados.

## Fontes dos gerenciadores

Imports e tipos: [NumPy](https://numpy.org/doc/stable/user/absolute_beginners.html), [pandas](https://pandas.pydata.org/docs/user_guide/10min.html), [scikit-learn](https://scikit-learn.org/stable/install.html), [React](https://react.dev/reference/react), [Express](https://expressjs.com/en/starter/hello-world.html), [Axios](https://axios-http.com/docs/intro), [Dio](https://pub.dev/documentation/dio/latest/) e [TypeScript: declarações de tipos](https://www.typescriptlang.org/docs/handbook/declaration-files/consumption.html).

- [pip: instalação](https://pip.pypa.io/en/stable/cli/pip_install/)
- [npm: instalação](https://docs.npmjs.com/cli/v11/commands/npm-install/)
- [Dart: pub add](https://dart.dev/tools/pub/cmd/pub-add)
- [Cargo: add](https://doc.rust-lang.org/cargo/commands/cargo-add.html)
- [Go: gerenciamento de dependências](https://go.dev/doc/modules/managing-dependencies)
- [.NET: adicionar pacote](https://learn.microsoft.com/dotnet/core/tools/dotnet-package-add)
- [Composer: require](https://getcomposer.org/doc/03-cli.md#require)
- [Bundler: add](https://bundler.io/man/bundle-add.1.html)
