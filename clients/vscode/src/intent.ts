// Heurística do gatilho espaço + Enter / Ctrl+Enter, sem dependência do VS Code (testável no Node).
// Mesma regra de codar.textutil.looks_like_intent (Python), do Neovim e do Vim: mude as quatro juntas.
const CODE_KEYWORDS = new Set(
  ("return import from print const let var function def class if else elif for while in not and or pass break " +
    "continue echo local then do end fi done new public private static void int string fn func package use using " +
    "include require try catch except finally throw raise yield await async self this null none true false nil " +
    "match case switch default struct enum interface type val mut").split(" "),
);

/** A linha é uma frase (pseudocódigo) e não código? "x é igual a 10" sim, "for i in range(3):" não. */
export function looksLikeIntent(line: string): boolean {
  let text = line.trim();
  for (const prefix of ["//", "#", "--", ";"]) {
    if (text.startsWith(prefix)) {
      text = text.slice(prefix.length).trim();
      break;
    }
  }
  if (text.length < 5 || /[{}:;()[\],=\\+\-*/<>]$/.test(text)) return false;
  if ((text.match(/\(/g) ?? []).length !== (text.match(/\)/g) ?? []).length) return false;
  const tokens = text.split(/\s+/);
  const words = tokens.map((t) => t.replace(/^['".,!?]+|['".,!?]+$/g, "")).filter((w) => /^\p{L}+$/u.test(w));
  if (tokens.length < 2 || words.length * 2 < tokens.length) return false;
  return words.some((w) => [...w].length >= 3 && !CODE_KEYWORDS.has(w.toLowerCase()));
}
