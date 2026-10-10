// O daemon calcula os trechos; o cliente aplica os mesmos intervalos ao snapshot original.
export interface Change { path: string; before: string | null; after: string | null; }
export interface Hunk {
  id: string; path: string; start: number; diff: string;
  opcodes: [string, number, number, number, number][];
}
export function applyHunks(change: Change, hunks: Hunk[], selected: Set<string>): string | null {
  if (change.before === null || change.after === null) {
    return hunks.some(h => selected.has(h.id)) ? change.after : change.before;
  }
  const lines = (text: string): string[] => text.match(/[^\n]*\n|[^\n]+$/g) ?? [];
  const old = lines(change.before), proposed = lines(change.after);
  const operations = hunks.filter(h => selected.has(h.id)).flatMap(h => h.opcodes);
  for (const [, a, b, c, d] of operations.reverse()) old.splice(a, b - a, ...proposed.slice(c, d));
  return old.join("");
}
