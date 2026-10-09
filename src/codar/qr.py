"""QR code sem dependências, para abrir no celular o endereço da prévia do Studio (`codar servir`).

Implementa o padrão (ISO/IEC 18004) no modo byte, versões 1 a 10 (até ~270 caracteres), com Reed-Solomon, as oito
máscaras e a escolha pela menor penalidade. Segue o algoritmo do gerador de referência de Project Nayuki.
"""

from __future__ import annotations

from collections import deque

# códigos de correção por bloco e número de blocos, por nível (L, M, Q, H) e versão (índice 0 sem uso)
_ECC_POR_BLOCO = {"L": (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18), "M": (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26),
                  "Q": (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24), "H": (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28)}
_BLOCOS = {"L": (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4), "M": (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5),
           "Q": (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8), "H": (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8)}
_BITS_FORMATO = {"L": 1, "M": 0, "Q": 3, "H": 2}
_ORDEM = ("L", "M", "Q", "H")
VERSAO_MAX = 10
_MASCARAS = (
    lambda x, y: (x + y) % 2, lambda x, y: y % 2, lambda x, y: x % 3, lambda x, y: (x + y) % 3,
    lambda x, y: (x // 3 + y // 2) % 2, lambda x, y: x * y % 2 + x * y % 3,
    lambda x, y: (x * y % 2 + x * y % 3) % 2, lambda x, y: ((x + y) % 2 + x * y % 3) % 2,
)


def _modulos_brutos(v: int) -> int:
    n = (16 * v + 128) * v + 64
    if v >= 2:
        alinh = v // 7 + 2
        n -= (25 * alinh - 10) * alinh - 55
        if v >= 7:
            n -= 36
    return n


def _palavras_de_dados(v: int, nivel: str) -> int:
    return _modulos_brutos(v) // 8 - _ECC_POR_BLOCO[nivel][v] * _BLOCOS[nivel][v]


def _mult(x: int, y: int) -> int:
    """Multiplicação em GF(256) com o polinômio 0x11D."""
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _divisor(grau: int) -> list[int]:
    res = [0] * (grau - 1) + [1]
    raiz = 1
    for _ in range(grau):
        for j in range(grau):
            res[j] = _mult(res[j], raiz)
            if j + 1 < grau:
                res[j] ^= res[j + 1]
        raiz = _mult(raiz, 0x02)
    return res


def _resto(dados: list[int], divisor: list[int]) -> list[int]:
    res = [0] * len(divisor)
    for b in dados:
        fator = b ^ res.pop(0)
        res.append(0)
        for i, coef in enumerate(divisor):
            res[i] ^= _mult(coef, fator)
    return res


class QR:
    """Matriz de um QR code: `modulos[y][x]` True = escuro."""

    def __init__(self, texto: str | bytes, nivel: str = "M", mascara: int | None = None) -> None:
        dados = texto.encode("utf-8") if isinstance(texto, str) else bytes(texto)
        for v in range(1, VERSAO_MAX + 1):
            if 4 + (8 if v <= 9 else 16) + 8 * len(dados) <= _palavras_de_dados(v, nivel) * 8:
                break
        else:
            raise ValueError(f"texto grande demais para um QR versão {VERSAO_MAX} ({len(dados)} bytes)")
        bits_usados = 4 + (8 if v <= 9 else 16) + 8 * len(dados)
        for melhor in reversed(_ORDEM[_ORDEM.index(nivel):]):  # sobrou espaço: mais correção de erro, mesmo tamanho
            if bits_usados <= _palavras_de_dados(v, melhor) * 8:
                nivel = melhor
                break
        self.versao, self.nivel, self.tamanho = v, nivel, v * 4 + 17
        n = self.tamanho
        self.modulos = [[False] * n for _ in range(n)]
        self._funcao = [[False] * n for _ in range(n)]
        self._padroes_fixos()
        self._desenhar_palavras(self._com_ecc(self._codificar(dados)))
        if mascara is None:
            mascara = min(range(8), key=self._penalidade_com)
        self.mascara = mascara
        self._aplicar_mascara(mascara)
        self._formato(mascara)

    # ------------------------------------------------------------------ dados
    def _codificar(self, dados: bytes) -> list[int]:
        bits: list[int] = []

        def junta(valor: int, n: int) -> None:
            bits.extend((valor >> i) & 1 for i in reversed(range(n)))

        junta(0b0100, 4)  # modo byte
        junta(len(dados), 8 if self.versao <= 9 else 16)
        for b in dados:
            junta(b, 8)
        capacidade = _palavras_de_dados(self.versao, self.nivel) * 8
        junta(0, min(4, capacidade - len(bits)))
        junta(0, -len(bits) % 8)
        enchimento = 0xEC
        while len(bits) < capacidade:
            junta(enchimento, 8)
            enchimento ^= 0xEC ^ 0x11
        return [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    def _com_ecc(self, dados: list[int]) -> list[int]:
        v, nivel = self.versao, self.nivel
        nblocos, ecc = _BLOCOS[nivel][v], _ECC_POR_BLOCO[nivel][v]
        brutas = _modulos_brutos(v) // 8
        curtos = nblocos - brutas % nblocos
        tam_curto = brutas // nblocos
        divisor = _divisor(ecc)
        blocos, k = [], 0
        for i in range(nblocos):
            bloco = dados[k:k + tam_curto - ecc + (0 if i < curtos else 1)]
            k += len(bloco)
            correcao = _resto(bloco, divisor)
            if i < curtos:
                bloco = bloco + [0]
            blocos.append(bloco + correcao)
        saida = []
        for i in range(len(blocos[0])):  # intercala os blocos (não concatena)
            for j, bloco in enumerate(blocos):
                if i != tam_curto - ecc or j >= curtos:
                    saida.append(bloco[i])
        return saida

    # ------------------------------------------------------------------ matriz
    def _fixo(self, x: int, y: int, escuro: bool) -> None:
        self.modulos[y][x] = escuro
        self._funcao[y][x] = True

    def _alinhamentos(self) -> list[int]:
        if self.versao == 1:
            return []
        n = self.versao // 7 + 2
        passo = (self.versao * 8 + n * 3 + 5) // (n * 4 - 4) * 2
        return list(reversed([self.tamanho - 7 - i * passo for i in range(n - 1)] + [6]))

    def _padroes_fixos(self) -> None:
        n = self.tamanho
        for i in range(n):  # linhas de sincronismo
            self._fixo(6, i, i % 2 == 0)
            self._fixo(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):  # localizadores nos cantos
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self._fixo(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = self._alinhamentos()
        ultimo = len(pos) - 1
        for i, ax in enumerate(pos):
            for j, ay in enumerate(pos):
                if (i, j) not in ((0, 0), (0, ultimo), (ultimo, 0)):
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            self._fixo(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        self._formato(0)  # reserva a área; o valor certo entra depois da máscara
        if self.versao >= 7:
            resto = self.versao
            for _ in range(12):
                resto = (resto << 1) ^ ((resto >> 11) * 0x1F25)
            bits = self.versao << 12 | resto
            for i in range(18):
                bit = (bits >> i) & 1 == 1
                a, b = n - 11 + i % 3, i // 3
                self._fixo(a, b, bit)
                self._fixo(b, a, bit)

    def _formato(self, mascara: int) -> None:
        dados = _BITS_FORMATO[self.nivel] << 3 | mascara
        resto = dados
        for _ in range(10):
            resto = (resto << 1) ^ ((resto >> 9) * 0x537)
        bits = (dados << 10 | resto) ^ 0x5412
        n = self.tamanho

        def bit(i: int) -> bool:
            return (bits >> i) & 1 == 1

        for i in range(6):
            self._fixo(8, i, bit(i))
        self._fixo(8, 7, bit(6))
        self._fixo(8, 8, bit(7))
        self._fixo(7, 8, bit(8))
        for i in range(9, 15):
            self._fixo(14 - i, 8, bit(i))
        for i in range(8):
            self._fixo(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._fixo(8, n - 15 + i, bit(i))
        self._fixo(8, n - 8, True)  # módulo escuro fixo

    def _desenhar_palavras(self, palavras: list[int]) -> None:
        n, i = self.tamanho, 0
        total = len(palavras) * 8
        direita = n - 1
        while direita >= 1:  # zigue-zague em pares de colunas, da direita para a esquerda
            if direita == 6:
                direita = 5
            for vert in range(n):
                for j in range(2):
                    x = direita - j
                    subindo = (direita + 1) & 2 == 0
                    y = n - 1 - vert if subindo else vert
                    if not self._funcao[y][x] and i < total:
                        self.modulos[y][x] = (palavras[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            direita -= 2

    def _aplicar_mascara(self, mascara: int) -> None:
        f = _MASCARAS[mascara]
        for y in range(self.tamanho):
            for x in range(self.tamanho):
                if not self._funcao[y][x] and f(x, y) == 0:
                    self.modulos[y][x] = not self.modulos[y][x]

    def _penalidade_com(self, mascara: int) -> int:
        self._aplicar_mascara(mascara)
        self._formato(mascara)
        p = self._penalidade()
        self._aplicar_mascara(mascara)  # desfaz (a máscara é um XOR)
        return p

    def _penalidade(self) -> int:
        m, n = self.modulos, self.tamanho
        total = 0
        for linhas in (m, [list(col) for col in zip(*m)]):  # linhas e depois colunas
            for linha in linhas:
                cor, corrida = False, 0
                hist: deque[int] = deque([0] * 7, 7)
                for celula in linha:
                    if celula == cor:
                        corrida += 1
                        total += 3 if corrida == 5 else 1 if corrida > 5 else 0
                    else:
                        self._historico(corrida, hist)
                        if not cor:
                            total += self._padroes_localizador(hist) * 40
                        cor, corrida = celula, 1
                if cor:
                    self._historico(corrida, hist)
                    corrida = 0
                self._historico(corrida + n, hist)
                total += self._padroes_localizador(hist) * 40
        for y in range(n - 1):
            for x in range(n - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    total += 3
        escuros = sum(c for linha in m for c in linha)
        k = (abs(escuros * 20 - n * n * 10) + n * n - 1) // (n * n) - 1
        return total + k * 10

    def _historico(self, corrida: int, hist: deque[int]) -> None:
        if hist[0] == 0:
            corrida += self.tamanho  # borda clara antes da primeira corrida
        hist.appendleft(corrida)

    def _padroes_localizador(self, hist: deque[int]) -> int:
        n = hist[1]
        nucleo = n > 0 and hist[2] == hist[4] == hist[5] == n and hist[3] == n * 3
        return int(nucleo and hist[0] >= n * 4 and hist[6] >= n) + int(nucleo and hist[6] >= n * 4 and hist[0] >= n)

    # ------------------------------------------------------------------ desenho
    def linhas(self, borda: int = 2) -> list[list[bool]]:
        """A matriz com a margem clara em volta (o leitor precisa dela)."""
        n = self.tamanho + 2 * borda
        vazia = [False] * n
        return [vazia[:] for _ in range(borda)] + \
            [[False] * borda + linha + [False] * borda for linha in self.modulos] + [vazia[:] for _ in range(borda)]

    def texto(self, borda: int = 2, cores: bool = True) -> str:
        """Para o terminal: dois módulos por caractere (▀ ▄ █). Com cores, preto sobre branco explícito (funciona
        em qualquer tema); sem cores, desenha os módulos claros, como num terminal de fundo escuro."""
        m = self.linhas(borda)
        if len(m) % 2:
            m.append([False] * len(m[0]))
        saida = []
        for y in range(0, len(m), 2):
            if cores:
                linha = "".join(f"\x1b[38;5;{16 if a else 231};48;5;{16 if b else 231}m▀" for a, b in zip(m[y], m[y + 1]))
                saida.append(linha + "\x1b[0m")
            else:
                saida.append("".join(" ▄▀█"[(not a) * 2 + (not b)] for a, b in zip(m[y], m[y + 1])))
        return "\n".join(saida)
