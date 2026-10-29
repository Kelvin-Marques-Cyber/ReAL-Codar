# Segurança

## Como reportar

Não abra uma issue pública para uma vulnerabilidade. Use **Security → Report a vulnerability** neste repositório (aviso privado do GitHub), com a versão (`codar version --verbose`), o sistema e o passo a passo. Você recebe uma resposta assim que o relato for analisado; a correção e o crédito são combinados no próprio aviso.

Somente a versão mais recente recebe correções de segurança. O projeto está em fase alfa.

## O que o CODAR protege

- **Daemon local:** socket Unix com permissão 0600 numa pasta privada, Named Pipe no Windows ou TCP apenas em loopback, com token comparado em tempo constante. Pedidos e snapshots têm limites de tamanho.
- **Arquivos do projeto:** edições, sugestões do consultor e referências recusam caminhos absolutos, `..`, `\`, links simbólicos e alvos fora da pasta do projeto. Credenciais (`.env*`, `id_rsa`, `*.pem`, `*.key`, `*.p12`…) não entram em prompts, listagens nem na prévia de rede.
- **Prévia no celular (`codar servir`, F4):** só leitura, com um código aleatório de 96 bits no endereço; não entrega arquivos ocultos, segredos nem links que saiam da pasta.
- **Plugins:** declarativos (TOML) por padrão; Python só com `allow_python = true`. Instalação por Git exige HTTPS sem credenciais, referência validada e hooks desligados; nomes de slot só podem ser identificadores.
- **Downloads:** SDKs e modelos conferem SHA-256; o instalador de pacotes só instala como root depois de conferir o pacote com o `SHA256SUMS` da Release.
- **Bibliotecas:** a inspeção de APIs lê fontes, tipos e documentação como dados, sem importar nem executar pacotes; documentação de terceiros entra nos prompts com delimitadores neutralizados.

## Limites conhecidos

- Código gerado pela IA é uma sugestão **não testada**: revise antes de executar.
- Exercícios e o F5 executam o código que você escolheu, com limites de tempo e de saída, mas **não são uma sandbox**.
- O repasse de servidores de desenvolvimento para a rede (`codar servir --proxy PORTA`) expõe esse servidor a quem estiver na mesma rede enquanto estiver ativo.
- Plugins com `allow_python = true` rodam no mesmo processo do daemon, sem isolamento.
- Nenhum software pode garantir ausência de vulnerabilidades desconhecidas; relatos são bem-vindos.
