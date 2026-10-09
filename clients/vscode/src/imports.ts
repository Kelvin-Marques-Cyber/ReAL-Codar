/** Inserção de imports em texto puro: testável sem carregar a API do VS Code. */
export function hoistImports(text: string, imports: string[], language: string, eol = "\n"):
  { text: string; at: number; added: number } {
  const lines = text.split(/\r?\n/);
  const missing = [...new Set(imports)].filter((imp) => !lines.some((line) => line.trim() === imp.trim()));
  if (!missing.length) return { text, at: 0, added: 0 };
  if (language === "powershell") {
    const directives = missing.filter((imp) => /^(using |#requires)/i.test(imp));
    const modules = missing.filter((imp) => !directives.includes(imp));
    const first = directives.length ? insert(text, directives, 0, eol) : { text, at: 0, added: 0 };
    const last = modules.length ? insert(first.text, modules, paramEnd(first.text), eol) : { ...first, added: 0 };
    return { ...last, added: first.added + last.added };
  }
  let at = 0;
  if (language === "python") {
    const doc = text.match(/^(?:(?:\s*#.*)?\r?\n)*[ruRU]?("""|''')[\s\S]*?\1[^\r\n]*(?:\r?\n|$)/);
    if (doc) at = (doc[0].match(/\n/g) ?? []).length;
  }
  for (; at < lines.length; at++) {
    const line = lines[at] ?? "";
    if (!line.trim() || /^(#!|# |\/\/|package |library |<\?php|"use strict"|'use strict')/.test(line)) continue;
    if (/^(import\s|from\s+\S+\s+import\s|using\s|#include\s|use\s|require[\s(])/.test(line)) continue;
    break; // não procura imports dentro de funções
  }
  return insert(text, missing, at, eol);
}

function insert(text: string, imports: string[], at: number, eol: string) {
  const lines = text.split(/\r?\n/);
  const block = [...imports];
  if (lines[at]?.trim() && !/^(import|from|using|use|#include|require)/.test(lines[at] ?? "")) block.push("");
  lines.splice(at, 0, ...block);
  return { text: lines.join(eol), at, added: block.length };
}

function paramEnd(text: string): number {
  const masked = text.replace(/'(?:''|[^'])*'|"(?:`.|[^"])*"|#[^\n]*/g, (s) => s.replace(/[^\n]/g, " "));
  const match = /^\s*param\s*\(/im.exec(masked);
  if (!match) return 0;
  const prefix = masked.slice(0, match.index).replace(/^\s*using[^\n]*/gim, "").replace(/\[[\s\S]*?\]/g, "");
  if (prefix.trim()) return 0;
  let depth = 1;
  for (let i = match.index + match[0].length; i < masked.length; i++) {
    if (masked[i] === "(") depth++;
    else if (masked[i] === ")") depth--;
    if (depth === 0) return (text.slice(0, i + 1).match(/\n/g) ?? []).length + 1;
  }
  return 0;
}
