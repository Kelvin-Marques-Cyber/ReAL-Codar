// Cliente JSON-RPC 2.0 (NDJSON) do daemon codar — sem dependência da API do VS Code (testável com Node puro).
import { execFile } from "node:child_process";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";

export interface Endpoint {
  transport: "unix" | "pipe" | "tcp";
  address: string;
  token?: string;
}

export interface Finding {
  id: string;
  severity: "info" | "warning" | "error" | "critical";
  category: string;
  message: string;
  line: number;
  col: number;
  suggestion?: string;
  body_line?: number;
}

export interface TranslateResult {
  code: string;
  body: string;
  imports: string[];
  lang: string;
  stage: string;
  source: string;
  confidence: number;
  timings: Record<string, number>;
  findings: Finding[];
  annotated: string | null;
  slots: Record<string, string>;
  notes: string[];
  cached: boolean;
  file_suggestion: { path: string; kind: string } | null;
  complete?: boolean;
  annotated_body?: string | null;
}

export class RpcError extends Error {
  constructor(public code: number, message: string, public data?: unknown) {
    super(message);
  }
}

interface Pending {
  resolve: (v: unknown) => void;
  reject: (e: Error) => void;
  onProgress?: (delta: string) => void;
  cleanup?: () => void;
}

/** Diretório onde o daemon publica endpoint.json (mesma regra de codar/paths.py). */
export function runtimeDir(): string {
  if (process.env.CODAR_HOME) return path.join(path.resolve(process.env.CODAR_HOME), "run");
  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA ?? path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "codar", "run");
  }
  const xdg = process.env.XDG_RUNTIME_DIR;
  if (xdg && fs.existsSync(xdg)) return path.join(xdg, "codar");
  return path.join(os.tmpdir(), `codar-${process.getuid?.() ?? 0}`);
}

export function parseEndpoint(spec: string, token = ""): Endpoint {
  if (spec.startsWith("tcp://")) return { transport: "tcp", address: spec.slice(6), token };
  if (spec.startsWith("unix:")) return { transport: "unix", address: spec.slice(5), token };
  if (spec.startsWith("pipe:")) return { transport: "pipe", address: spec.slice(5), token };
  if (spec.startsWith("\\\\.\\pipe\\")) return { transport: "pipe", address: spec, token };
  return { transport: "unix", address: spec, token };
}

export function discoverEndpoint(configured = ""): Endpoint | undefined {
  const spec = configured || process.env.CODAR_ENDPOINT;
  if (spec) return parseEndpoint(spec, process.env.CODAR_TOKEN ?? "");
  try {
    const data = JSON.parse(fs.readFileSync(path.join(runtimeDir(), "endpoint.json"), "utf8"));
    return { transport: data.transport, address: data.address, token: data.token };
  } catch {
    return undefined;
  }
}

export class CodarClient {
  private socket?: net.Socket;
  private buffer = "";
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private connecting?: Promise<void>;

  constructor(
    private readonly options: { endpoint?: string; executable?: string; autoStart?: boolean; log?: (m: string) => void } = {},
  ) {}

  get connected(): boolean {
    return !!this.socket && !this.socket.destroyed;
  }

  async connect(): Promise<void> {
    if (this.connected) return;
    this.connecting ??= this.doConnect().finally(() => (this.connecting = undefined));
    return this.connecting;
  }

  private async doConnect(): Promise<void> {
    let ep = discoverEndpoint(this.options.endpoint);
    try {
      if (!ep) throw new Error("endpoint não encontrado");
      await this.open(ep);
    } catch (err) {
      if (!this.options.autoStart) throw new Error(`daemon do codar indisponível: ${(err as Error).message}`);
      this.options.log?.("subindo o daemon do codar…");
      await this.startDaemon();
      ep = discoverEndpoint(this.options.endpoint);
      if (!ep) throw new Error("o daemon subiu mas não publicou o endpoint");
      await this.open(ep);
    }
  }

  private open(ep: Endpoint): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock =
        ep.transport === "tcp"
          ? net.connect({ host: ep.address.split(":")[0], port: Number(ep.address.split(":").pop()) })
          : net.connect({ path: ep.address });
      sock.setEncoding("utf8");
      sock.once("error", reject);
      sock.once("connect", async () => {
        sock.off("error", reject);
        this.socket = sock;
        sock.on("data", (chunk: string) => this.onData(chunk));
        sock.on("close", () => this.onClose());
        sock.on("error", () => sock.destroy());
        try {
          if (ep.transport === "tcp" && ep.token) await this.call("auth", { token: ep.token });
          resolve();
        } catch (e) {
          reject(e as Error);
        }
      });
    });
  }

  private startDaemon(): Promise<void> {
    const exe = this.options.executable || "codar";
    return new Promise((resolve, reject) => {
      execFile(exe, ["start"], { timeout: 60_000, windowsHide: true }, (err, _stdout, stderr) =>
        err ? reject(new Error(`falha ao executar '${exe} start': ${stderr || err.message}`)) : resolve(),
      );
    });
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, nl).trim();
      this.buffer = this.buffer.slice(nl + 1);
      if (!line) continue;
      let msg: { id?: number; result?: unknown; error?: { code: number; message: string; data?: unknown }; method?: string; params?: { id?: number; delta?: string } };
      try {
        msg = JSON.parse(line);
      } catch {
        continue;
      }
      if (msg.method === "$/progress" && msg.params?.id !== undefined) {
        this.pending.get(msg.params.id)?.onProgress?.(msg.params.delta ?? "");
        continue;
      }
      if (msg.id === undefined) continue;
      const p = this.pending.get(msg.id);
      if (!p) continue;
      this.pending.delete(msg.id);
      p.cleanup?.();
      if (msg.error) p.reject(new RpcError(msg.error.code, msg.error.message, msg.error.data));
      else p.resolve(msg.result);
    }
  }

  private onClose(): void {
    this.socket = undefined;
    for (const p of this.pending.values()) {
      p.cleanup?.();
      p.reject(new Error("conexão com o daemon encerrada"));
    }
    this.pending.clear();
  }

  /** Envia uma requisição; `signal` cancela no daemon via $/cancelRequest. */
  async call<T = unknown>(method: string, params: object = {}, opts: { onProgress?: (d: string) => void; signal?: AbortSignal } = {}): Promise<T> {
    if (opts.signal?.aborted) throw new RpcError(-32800, "requisição cancelada");
    if (!this.connected && method !== "auth") await this.connect();
    if (opts.signal?.aborted) throw new RpcError(-32800, "requisição cancelada");
    const id = this.nextId++;
    const sock = this.socket!;
    return new Promise<T>((resolve, reject) => {
      const abort = () => {
        this.notify("$/cancelRequest", { id });
        this.pending.delete(id);
        opts.signal?.removeEventListener("abort", abort);
        reject(new RpcError(-32800, "requisição cancelada"));
      };
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, onProgress: opts.onProgress,
        cleanup: () => opts.signal?.removeEventListener("abort", abort) });
      opts.signal?.addEventListener("abort", abort, { once: true });
      sock.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
    });
  }

  notify(method: string, params: object): void {
    this.socket?.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
  }

  translate(
    params: {
      intent: string;
      lang?: string;
      context?: { file?: string; before?: string; after?: string; selected?: string; indent?: string; indent_unit?: string };
      options?: { stages?: number[]; audit?: boolean; hints?: boolean; mode?: string; stream?: boolean };
    },
    opts: { onProgress?: (d: string) => void; signal?: AbortSignal } = {},
  ): Promise<TranslateResult> {
    return this.call<TranslateResult>("translate", params, opts);
  }

  dispose(): void {
    this.socket?.destroy();
    this.socket = undefined;
  }
}
