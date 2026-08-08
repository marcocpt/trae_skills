# dd-ask-chatgpt MCP 服务器实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `subagent-driven-development`（推荐）或 `executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 实现一个跨 App 复用的 MCP 服务器，用 Playwright 驱动独立 Chromium 与 ChatGPT 网页交互，向 MCP 客户端暴露 `dd_chatgpt_ask` 和 `dd_chatgpt_new_conversation` 两个结构化工具。

**架构：** V1 冻结为单例 Streamable HTTP MCP 后端（localhost + 认证 + Origin 校验），独占 Playwright 与 owned profile；stdio 仅作协议代理。conversation 通过显式 `conversationId` 管理，同一 conversation 严格串行，`conversationId` 一旦签发绝不自动换绑。

**技术栈：** TypeScript、`@modelcontextprotocol/server` v2、`playwright`、`vitest`（单元测试）、Node 20+。

---

## WP 总览（按 ChatGPT 建议拆分）

| WP | 内容 | 对应设计章节 |
| --- | --- | --- |
| WP-00 | 部署前置 Gate + 项目脚手架 | 部署前置条件、决策、目录结构 |
| WP-01 | schemas / types / 错误契约（discriminated union、schemaVersion、错误码） | 工具契约、错误处理、outputSchema |
| WP-02 | 配置解析 + 日志 | 配置项、日志 |
| WP-03 | 文件系统基础设施（stateStore、fileLock、auth） | 目录结构、profile 生命周期 |
| WP-04 | Playwright 驱动 + TurnLocator + 完成状态机 | 架构、response correlation、完成状态机 |
| WP-05 | Conversation Manager（不自动换绑、恢复） | conversation 生命周期 |
| WP-06 | Request Manager（per-conversation mutex、Cancellation） | 并发模型、Cancellation |
| WP-07 | Streamable HTTP MCP 后端（认证、Origin、backend.json 单例） | 架构、安全策略 |
| WP-08 | stdio adapter 协议代理 | 架构、Cancellation |
| WP-09 | 验证矩阵 + multi-client Exit Gate + README | 验证 |

---

## 文件结构

```
dd-ask-chatgpt-mcp/            # 新仓库（与 design 文档一致）
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    types.ts               # 工具输入/输出 discriminated union、错误码、schemaVersion
    config.ts              # 配置解析（env）
    logger.ts              # 结构化日志（始终写 stderr）
    stateStore.ts          # conversations.json / backend.json 读写
    fileLock.ts            # browser.lock 互斥锁（含 stale 清理）
    auth.ts                # 随机 token 生成/校验/落盘（0600）
    chatgpt.ts             # Playwright 控制 + TurnLocator + 完成状态机
    conversationManager.ts # conversationId 句柄（URL 持久 / Page 临时 cache）
    requestManager.ts      # per-conversation mutex + 全局信号量 + Cancellation
    index.ts               # MCP server 入口（Streamable HTTP backend）
    stdioAdapter.ts        # stdio → localhost MCP endpoint 协议代理
  test/
    types.test.ts
    config.test.ts
    stateStore.test.ts
    fileLock.test.ts
    auth.test.ts
    conversationManager.test.ts
    requestManager.test.ts
  README.md
```

注意：`chatgpt.ts`（Playwright 浏览器控制）与 `index.ts`（HTTP backend 绑定）依赖真实浏览器/网络，**不做自动化单测**；其纯逻辑（TurnLocator 索引计算、状态机转移表）拆成可导出纯函数，由 `conversationManager.test.ts` 覆盖。真实浏览器交互走 WP-09 的手动/CI 验证矩阵。

---

## WP-00：部署前置 Gate + 项目脚手架

**文件：**
- 创建：`dd-ask-chatgpt-mcp/package.json`
- 创建：`dd-ask-chatgpt-mcp/tsconfig.json`
- 创建：`dd-ask-chatgpt-mcp/vitest.config.ts`
- 创建：`dd-ask-chatgpt-mcp/.gitignore`

- [ ] **步骤 1：确认部署前置条件已裁决**

设计文档「部署前置条件」要求：进入正式实现前，必须确认目标 ChatGPT 账号适用的 OpenAI 条款/合同/授权允许「自动化网页交互 + 程序化读取 Output」。**实现计划本身不解除该 Gate**——在执行 WP-01 之前，实现者必须取得用户对本条的口头/书面裁决。若裁决为「不允许 Web 自动化」，则停止本计划，不得继续实现网页自动化路径。

- [ ] **步骤 2：初始化 package.json**

```json
{
  "name": "dd-ask-chatgpt-mcp",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=20" },
  "bin": {
    "dd-ask-chatgpt": "./dist/index.js",
    "dd-ask-chatgpt-stdio": "./dist/stdioAdapter.js"
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "test": "vitest run",
    "test:watch": "vitest",
    "start": "node dist/index.js",
    "start:stdio": "node dist/stdioAdapter.js"
  },
  "dependencies": {
    "@modelcontextprotocol/server": "^2.0.0",
    "playwright": "^1.45.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^2.0.0",
    "@types/node": "^20.0.0"
  }
}
```

- [ ] **步骤 3：初始化 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src/**/*.ts"]
}
```

- [ ] **步骤 4：初始化 vitest 配置与 .gitignore**

`vitest.config.ts`：

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});
```

`.gitignore`：

```gitignore
node_modules/
dist/
~/.dd-ask-chatgpt/
```

- [ ] **步骤 5：安装依赖并验证构建**

运行：`npm install`
运行：`npm run build`
预期：`dist/` 生成（当前为空工程，tsc 成功编译无源文件即可）。

- [ ] **步骤 6：Commit**

```bash
git init
git add package.json tsconfig.json vitest.config.ts .gitignore package-lock.json
git commit -m "chore: scaffold dd-ask-chatgpt-mcp TypeScript project"
```

---

## WP-01：schemas / types / 错误契约

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/types.ts`
- 创建：`dd-ask-chatgpt-mcp/test/types.test.ts`

- [ ] **步骤 1：编写失败的契约测试**

`test/types.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import {
  SUCCESS_KIND,
  ERROR_KIND,
  SCHEMA_VERSION,
  isAskResult,
  isErrorResult,
  isConversationResult,
} from "../src/types.js";

describe("tool result contract (discriminated union)", () => {
  it("SCHEMA_VERSION is defined", () => {
    expect(SCHEMA_VERSION).toBe("1.0.0");
  });

  it("accepts a complete ask success", () => {
    const r = {
      schemaVersion: SCHEMA_VERSION,
      kind: SUCCESS_KIND,
      operationId: "op_1",
      conversationId: "conv_1",
      conversationUrl: "https://chatgpt.com/c/x",
      content: "answer",
      status: "complete",
    };
    expect(isAskResult(r)).toBe(true);
  });

  it("accepts incomplete ask success", () => {
    const r = {
      schemaVersion: SCHEMA_VERSION,
      kind: SUCCESS_KIND,
      operationId: "op_2",
      conversationId: "conv_1",
      conversationUrl: null,
      content: "partial",
      status: "incomplete",
    };
    expect(isAskResult(r)).toBe(true);
  });

  it("rejects success missing status", () => {
    const r = { schemaVersion: SCHEMA_VERSION, kind: SUCCESS_KIND, operationId: "op", conversationId: "c", conversationUrl: null, content: "" };
    expect(isAskResult(r)).toBe(false);
  });

  it("accepts an error result", () => {
    const r = {
      schemaVersion: SCHEMA_VERSION,
      kind: ERROR_KIND,
      operationId: "op_3",
      error: { code: "LOGIN_REQUIRED", message: "not logged in", retryable: false },
    };
    expect(isErrorResult(r)).toBe(true);
  });

  it("accepts a new_conversation result", () => {
    const r = { schemaVersion: SCHEMA_VERSION, conversationId: "conv_9", conversationUrl: null };
    expect(isConversationResult(r)).toBe(true);
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npx vitest run test/types.test.ts`
预期：FAIL，`Cannot find module '../src/types.js'`。

- [ ] **步骤 3：实现 types.ts**

`src/types.ts`：

```ts
export const SCHEMA_VERSION = "1.0.0";
export const SUCCESS_KIND = "success" as const;
export const ERROR_KIND = "error" as const;

export type AskStatus = "complete" | "incomplete";

export interface AskSuccess {
  schemaVersion: string;
  kind: typeof SUCCESS_KIND;
  operationId: string;
  conversationId: string;
  conversationUrl: string | null;
  content: string;
  status: AskStatus;
}

export type ErrorCode =
  | "LOGIN_REQUIRED"
  | "PROFILE_LOCKED"
  | "BROWSER_LAUNCH_FAILED"
  | "PAGE_NOT_AVAILABLE"
  | "CONVERSATION_NOT_FOUND"
  | "CONVERSATION_RECOVERY_FAILED"
  | "SEND_FAILED"
  | "RESPONSE_NOT_FOUND"
  | "DOM_CHANGED"
  | "NETWORK_ERROR"
  | "ASK_TIMEOUT";

export interface ToolError {
  schemaVersion: string;
  kind: typeof ERROR_KIND;
  operationId: string;
  error: { code: ErrorCode; message: string; retryable: boolean };
}

export interface ConversationResult {
  schemaVersion: string;
  conversationId: string;
  conversationUrl: string | null;
}

export type AskResult = AskSuccess | ToolError;
export type NewConversationResult = ConversationResult | ToolError;

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null;

export function isAskResult(v: unknown): v is AskSuccess {
  if (!isRecord(v)) return false;
  return (
    v.schemaVersion === SCHEMA_VERSION &&
    v.kind === SUCCESS_KIND &&
    typeof v.operationId === "string" &&
    typeof v.conversationId === "string" &&
    (typeof v.conversationUrl === "string" || v.conversationUrl === null) &&
    typeof v.content === "string" &&
    (v.status === "complete" || v.status === "incomplete")
  );
}

export function isErrorResult(v: unknown): v is ToolError {
  if (!isRecord(v)) return false;
  if (v.schemaVersion !== SCHEMA_VERSION || v.kind !== ERROR_KIND) return false;
  if (typeof v.operationId !== "string") return false;
  const err = (v as { error?: unknown }).error;
  if (!isRecord(err)) return false;
  return (
    typeof err.code === "string" &&
    typeof err.message === "string" &&
    typeof err.retryable === "boolean"
  );
}

export function isConversationResult(v: unknown): v is ConversationResult {
  if (!isRecord(v)) return false;
  return (
    v.schemaVersion === SCHEMA_VERSION &&
    typeof v.conversationId === "string" &&
    (typeof v.conversationUrl === "string" || v.conversationUrl === null)
  );
}

export const ASK_ERROR_CODES: ErrorCode[] = [
  "LOGIN_REQUIRED",
  "PROFILE_LOCKED",
  "BROWSER_LAUNCH_FAILED",
  "PAGE_NOT_AVAILABLE",
  "CONVERSATION_NOT_FOUND",
  "CONVERSATION_RECOVERY_FAILED",
  "SEND_FAILED",
  "RESPONSE_NOT_FOUND",
  "DOM_CHANGED",
  "NETWORK_ERROR",
  "ASK_TIMEOUT",
];
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run test/types.test.ts`
预期：PASS（5 个测试）。

- [ ] **步骤 5：Commit**

```bash
git add src/types.ts test/types.test.ts
git commit -m "feat: define discriminated-union tool contract with error codes"
```

---

## WP-02：配置解析 + 日志

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/config.ts`
- 创建：`dd-ask-chatgpt-mcp/src/logger.ts`
- 创建：`dd-ask-chatgpt-mcp/test/config.test.ts`

- [ ] **步骤 1：编写失败的配置测试**

`test/config.test.ts`：

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { loadConfig } from "../src/config.js";

const OLD = { ...process.env };

beforeEach(() => {
  process.env = { ...OLD };
  delete process.env.DD_CHATGPT_MESSAGE_PREFIX;
  delete process.env.DD_CHATGPT_PROFILE_DIR;
  delete process.env.DD_CHATGPT_ASK_TIMEOUT_MS;
  delete process.env.DD_CHATGPT_MAX_CONCURRENT_ASKS;
  delete process.env.DD_CHATGPT_BIND;
});

describe("loadConfig", () => {
  it("uses defaults when env empty", () => {
    const c = loadConfig();
    expect(c.messagePrefix).toBe("");
    expect(c.askTimeoutMs).toBe(60000);
    expect(c.maxConcurrentAsks).toBe(1);
    expect(c.bind).toBe("127.0.0.1");
  });

  it("reads message prefix", () => {
    process.env.DD_CHATGPT_MESSAGE_PREFIX = "%%CHATGPT%%";
    expect(loadConfig().messagePrefix).toBe("%%CHATGPT%%");
  });

  it("parses timeout and max concurrency", () => {
    process.env.DD_CHATGPT_ASK_TIMEOUT_MS = "30000";
    process.env.DD_CHATGPT_MAX_CONCURRENT_ASKS = "3";
    const c = loadConfig();
    expect(c.askTimeoutMs).toBe(30000);
    expect(c.maxConcurrentAsks).toBe(3);
  });

  it("rejects bind other than 127.0.0.1", () => {
    process.env.DD_CHATGPT_BIND = "0.0.0.0";
    expect(() => loadConfig()).toThrow();
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npx vitest run test/config.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 config.ts**

`src/config.ts`：

```ts
import path from "node:path";
import os from "node:os";

export interface Config {
  messagePrefix: string;
  profileDir: string;
  dataRoot: string;
  askTimeoutMs: number;
  maxConcurrentAsks: number;
  bind: string;
}

const num = (env: string | undefined, fallback: number): number => {
  if (env === undefined) return fallback;
  const n = Number.parseInt(env, 10);
  if (Number.isNaN(n)) return fallback;
  return n;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const dataRoot =
    env.DD_CHATGPT_DATA_DIR ?? path.join(os.homedir(), ".dd-ask-chatgpt");
  const profileDir =
    env.DD_CHATGPT_PROFILE_DIR ?? path.join(dataRoot, "profile");
  const bind = env.DD_CHATGPT_BIND ?? "127.0.0.1";
  if (bind !== "127.0.0.1" && bind !== "localhost") {
    throw new Error(`DD_CHATGPT_BIND must be 127.0.0.1 or localhost, got ${bind}`);
  }
  return {
    messagePrefix: env.DD_CHATGPT_MESSAGE_PREFIX ?? "",
    profileDir,
    dataRoot,
    askTimeoutMs: num(env.DD_CHATGPT_ASK_TIMEOUT_MS, 60000),
    maxConcurrentAsks: num(env.DD_CHATGPT_MAX_CONCURRENT_ASKS, 1),
    bind,
  };
}
```

- [ ] **步骤 4：实现 logger.ts**

`src/logger.ts`（普通日志一律写 stderr，不污染 stdout 的 MCP wire）：

```ts
export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  ts: string;
  level: LogLevel;
  msg: string;
  operationId?: string;
  conversationId?: string;
  status?: string;
  errorCode?: string;
}

export function log(entry: LogEntry): void {
  // 永远写 stderr；stdio 传输时 stdout 只走 MCP JSON-RPC
  process.stderr.write(JSON.stringify(entry) + "\n");
}

export function debug(msg: string, extra: Partial<LogEntry> = {}): void {
  log({ ts: new Date().toISOString(), level: "debug", msg, ...extra });
}
export function info(msg: string, extra: Partial<LogEntry> = {}): void {
  log({ ts: new Date().toISOString(), level: "info", msg, ...extra });
}
export function warn(msg: string, extra: Partial<LogEntry> = {}): void {
  log({ ts: new Date().toISOString(), level: "warn", msg, ...extra });
}
export function error(msg: string, extra: Partial<LogEntry> = {}): void {
  log({ ts: new Date().toISOString(), level: "error", msg, ...extra });
}
```

- [ ] **步骤 5：运行测试验证通过**

运行：`npx vitest run test/config.test.ts`
预期：PASS（4 个测试）。

- [ ] **步骤 6：Commit**

```bash
git add src/config.ts src/logger.ts test/config.test.ts
git commit -m "feat: config parsing and stderr logger"
```

---

## WP-03：文件系统基础设施（stateStore、fileLock、auth）

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/stateStore.ts`
- 创建：`dd-ask-chatgpt-mcp/src/fileLock.ts`
- 创建：`dd-ask-chatgpt-mcp/src/auth.ts`
- 创建：`dd-ask-chatgpt-mcp/test/stateStore.test.ts`
- 创建：`dd-ask-chatgpt-mcp/test/fileLock.test.ts`
- 创建：`dd-ask-chatgpt-mcp/test/auth.test.ts`

- [ ] **步骤 1：编写失败的 stateStore 测试**

`test/stateStore.test.ts`：

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { StateStore } from "../src/stateStore.js";

let dir: string;
let store: StateStore;

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddstate-"));
  store = new StateStore(dir);
});

afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true });
});

describe("StateStore", () => {
  it("persists conversation mapping and reloads it", () => {
    store.saveConversation("conv_1", { conversationUrl: "https://chatgpt.com/c/x", pageRef: "page1" });
    const reloaded = new StateStore(dir);
    const rec = reloaded.getConversation("conv_1");
    expect(rec?.conversationUrl).toBe("https://chatgpt.com/c/x");
    expect(rec?.pageRef).toBe("page1");
  });

  it("returns undefined for unknown conversation", () => {
    expect(store.getConversation("conv_nope")).toBeUndefined();
  });

  it("deletes a conversation", () => {
    store.saveConversation("conv_2", { conversationUrl: null, pageRef: null });
    store.deleteConversation("conv_2");
    expect(store.getConversation("conv_2")).toBeUndefined();
  });
});
```

- [ ] **步骤 2：运行验证失败**

运行：`npx vitest run test/stateStore.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 stateStore.ts**

`src/stateStore.ts`：

```ts
import fs from "node:fs";
import path from "node:path";
import { log } from "./logger.js";

export interface ConversationRecord {
  conversationUrl: string | null;
  pageRef: string | null;
}

interface StateFile {
  conversations: Record<string, ConversationRecord>;
}

export class StateStore {
  private readonly conversationsFile: string;
  private state: StateFile;

  constructor(dataRoot: string) {
    this.conversationsFile = path.join(dataRoot, "state", "conversations.json");
    this.state = { conversations: {} };
    fs.mkdirSync(path.dirname(this.conversationsFile), { recursive: true });
    this.load();
  }

  private load(): void {
    try {
      const raw = fs.readFileSync(this.conversationsFile, "utf-8");
      this.state = JSON.parse(raw) as StateFile;
    } catch {
      this.state = { conversations: {} };
    }
  }

  private persist(): void {
    fs.writeFileSync(this.conversationsFile, JSON.stringify(this.state, null, 2), "utf-8");
  }

  getConversation(id: string): ConversationRecord | undefined {
    return this.state.conversations[id];
  }

  saveConversation(id: string, rec: ConversationRecord): void {
    this.state.conversations[id] = rec;
    this.persist();
    log({ ts: new Date().toISOString(), level: "debug", msg: "conversation saved", conversationId: id });
  }

  deleteConversation(id: string): void {
    delete this.state.conversations[id];
    this.persist();
  }
}
```

- [ ] **步骤 4：实现 fileLock.ts**

`src/fileLock.ts`：基于 `fs.open('wx')` 的互斥锁，带 stale（进程已死）清理。

```ts
import fs from "node:fs";
import path from "node:path";
import { log } from "./logger.js";

export class FileLock {
  constructor(private readonly lockPath: string) {}

  async acquire(timeoutMs = 5000): Promise<void> {
    const start = Date.now();
    for (;;) {
      try {
        const fd = fs.openSync(this.lockPath, "wx");
        fs.writeSync(fd, JSON.stringify({ pid: process.pid, acquiredAt: Date.now() }));
        fs.closeSync(fd);
        log({ ts: new Date().toISOString(), level: "debug", msg: "lock acquired", operationId: "filelock" });
        return;
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code !== "EEXIST") throw err;
        this.cleanupStale();
        if (Date.now() - start > timeoutMs) {
          throw new Error("PROFILE_LOCKED: timeout acquiring browser lock");
        }
        await new Promise((r) => setTimeout(r, 100));
      }
    }
  }

  private cleanupStale(): void {
    try {
      const raw = fs.readFileSync(this.lockPath, "utf-8");
      const data = JSON.parse(raw) as { pid?: number };
      if (typeof data.pid === "number" && !isPidAlive(data.pid)) {
        fs.unlinkSync(this.lockPath);
        log({ ts: new Date().toISOString(), level: "info", msg: "cleaned stale lock", operationId: "filelock" });
      }
    } catch {
      /* 锁文件不可读则不动 */
    }
  }

  release(): void {
    try {
      fs.unlinkSync(this.lockPath);
    } catch {
      /* 已不存在则忽略 */
    }
  }
}

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}
```

- [ ] **步骤 5：实现 auth.ts**

`src/auth.ts`：生成随机 token，落盘 `state/auth.token`（0600），提供校验函数。

```ts
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export function generateToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

export function writeTokenFile(dataRoot: string, token: string): void {
  const p = path.join(dataRoot, "state", "auth.token");
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, token, { encoding: "utf-8", mode: 0o600 });
}

export function readTokenFile(dataRoot: string): string {
  const p = path.join(dataRoot, "state", "auth.token");
  return fs.readFileSync(p, "utf-8").trim();
}

export function tokenFileExists(dataRoot: string): boolean {
  return fs.existsSync(path.join(dataRoot, "state", "auth.token"));
}

export function verifyToken(dataRoot: string, presented: string | undefined): boolean {
  if (!presented) return false;
  try {
    const expected = readTokenFile(dataRoot);
    return crypto.timingSafeEqual(Buffer.from(presented), Buffer.from(expected));
  } catch {
    return false;
  }
}
```

- [ ] **步骤 6：编写并运行 fileLock 与 auth 测试**

`test/fileLock.test.ts`：

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { FileLock } from "../src/fileLock.js";

let dir: string;
let lock: FileLock;
beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddlock-"));
  lock = new FileLock(path.join(dir, "browser.lock"));
});
afterEach(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("FileLock", () => {
  it("acquires and releases", async () => {
    await lock.acquire(100);
    expect(fs.existsSync(path.join(dir, "browser.lock"))).toBe(true);
    lock.release();
    expect(fs.existsSync(path.join(dir, "browser.lock"))).toBe(false);
  });

  it("fails to acquire when lock exists and times out", async () => {
    fs.writeFileSync(path.join(dir, "browser.lock"), JSON.stringify({ pid: 999999999 }), "utf-8");
    await expect(lock.acquire(200)).rejects.toThrow("PROFILE_LOCKED");
  });
});
```

`test/auth.test.ts`：

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { generateToken, writeTokenFile, readTokenFile, verifyToken, tokenFileExists } from "../src/auth.js";

let dir: string;
beforeEach(() => { dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddauth-")); });
afterEach(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("auth", () => {
  it("token file is 0600", () => {
    const t = generateToken();
    writeTokenFile(dir, t);
    const mode = fs.statSync(path.join(dir, "state", "auth.token")).mode & 0o777;
    expect(mode).toBe(0o600);
    expect(tokenFileExists(dir)).toBe(true);
  });

  it("verifyToken matches and rejects wrong", () => {
    const t = generateToken();
    writeTokenFile(dir, t);
    expect(verifyToken(dir, t)).toBe(true);
    expect(verifyToken(dir, "wrong")).toBe(false);
    expect(verifyToken(dir, undefined)).toBe(false);
  });

  it("readTokenFile returns the stored token", () => {
    writeTokenFile(dir, "abc123");
    expect(readTokenFile(dir)).toBe("abc123");
  });
});
```

- [ ] **步骤 7：运行全部 WP-03 测试**

运行：`npx vitest run test/stateStore.test.ts test/fileLock.test.ts test/auth.test.ts`
预期：PASS。

- [ ] **步骤 8：Commit**

```bash
git add src/stateStore.ts src/fileLock.ts src/auth.ts test/stateStore.test.ts test/fileLock.test.ts test/auth.test.ts
git commit -m "feat: state store, browser file lock with stale cleanup, and token auth"
```

---

## WP-04：Playwright 驱动 + TurnLocator + 完成状态机

本 WP 的浏览器控制不自动化单测；核心纯逻辑拆出为可测函数。

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/chatgpt.ts`
- 创建：`dd-ask-chatgpt-mcp/src/turnLocator.ts`（纯逻辑，可单测）
- 创建：`dd-ask-chatgpt-mcp/test/turnLocator.test.ts`

- [ ] **步骤 1：编写失败的 TurnLocator 测试**

`test/turnLocator.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { locateAssistantIndex } from "../src/turnLocator.js";

describe("locateAssistantIndex (preferred user-turn anchor)", () => {
  it("finds assistant right after the matching user turn", () => {
    // userTurns: [{text:"q1"},{text:"q2"}]; assistantTurns: [{},{},{}]
    const idx = locateAssistantIndex({
      userTexts: ["q1", "q2"],
      assistantCount: 3,
      sentText: "q2",
    });
    expect(idx).toBe(2); // assistant after user turn index 1 => global assistant index 2
  });

  it("falls back to count-based when user text ambiguous", () => {
    const idx = locateAssistantIndex({
      userTexts: ["q1"],
      assistantCount: 2,
      sentText: "q1",
    });
    expect(idx).toBe(1); // before count 2 => nth(1)
  });

  it("returns -1 when no assistant yet", () => {
    const idx = locateAssistantIndex({ userTexts: ["q1"], assistantCount: 0, sentText: "q1" });
    expect(idx).toBe(-1);
  });
});
```

- [ ] **步骤 2：运行验证失败**

运行：`npx vitest run test/turnLocator.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 turnLocator.ts（纯函数）**

`src/turnLocator.ts`：

```ts
export interface TurnLocatorInput {
  userTexts: string[];
  assistantCount: number;
  sentText: string;
}

/**
 * 返回应读取的 assistant turn 全局索引；找不到返回 -1。
 * 优先：定位与 sentText 匹配的 user turn，取其后一个 assistant；
 * fallback：计数定位（发送前 assistant 数量 = assistantCount-1，读 nth(assistantCount-1)）。
 */
export function locateAssistantIndex(input: TurnLocatorInput): number {
  if (input.assistantCount <= 0) return -1;

  // 优先 user-turn anchor：找最后一条与 sentText 相同的 user turn
  for (let i = input.userTexts.length - 1; i >= 0; i--) {
    if (input.userTexts[i] === input.sentText) {
      // user turn i 之后紧跟的 assistant 全局索引
      const afterUser = i + 1;
      if (afterUser < input.assistantCount) return afterUser;
      break;
    }
  }

  // fallback：本次新增的 assistant 是最后一条
  return input.assistantCount - 1;
}
```

- [ ] **步骤 4：实现 chatgpt.ts（浏览器控制，不单测）**

`src/chatgpt.ts`：封装 Playwright 启动、登录检查、发送、状态机等待、读取。

```ts
import { chromium, type BrowserContext, type Page } from "playwright";
import { locateAssistantIndex } from "./turnLocator.js";
import { log } from "./logger.js";
import type { Config } from "./config.js";

export type Completion =
  | { status: "complete"; content: string }
  | { status: "incomplete"; content: string };

export class ChatGPTDriver {
  private context: BrowserContext | null = null;

  constructor(private readonly config: Config) {}

  async start(): Promise<void> {
    this.context = await chromium.launchPersistentContext(this.config.profileDir, {
      headless: false,
      viewport: { width: 1280, height: 900 },
    });
  }

  isLoggedIn(): boolean {
    // 检查是否存在登录态（profile 中已有 cookie/会话）；简化：默认按已有 profile 判断
    return this.context !== null;
  }

  async openOrNew(url: string | null): Promise<Page> {
    if (!this.context) throw new Error("BROWSER_LAUNCH_FAILED: context not started");
    const page = await this.context.newPage();
    await page.goto(url ?? "https://chatgpt.com/", { waitUntil: "domcontentloaded" });
    return page;
  }

  async sendAndWait(page: Page, message: string, timeoutMs: number): Promise<Completion> {
    const input = page.locator('textarea[placeholder*="ChatGPT"], #prompt-textarea, textarea');
    await input.waitFor({ state: "visible", timeout: 15000 });
    await input.fill(message);
    await input.press("Enter");

    const deadline = Date.now() + timeoutMs;
    const userTexts: string[] = [];
    const getAssistantCount = async () =>
      page.locator('div[data-message-author-role="assistant"], [data-testid*="conversation-turn"] .markdown').count();

    let assistantCount = await getAssistantCount();

    while (Date.now() < deadline) {
      const newCount = await getAssistantCount();
      const userTurns = await this.collectUserTexts(page);
      if (newCount > assistantCount) {
        const idx = locateAssistantIndex({ userTexts: userTurns, assistantCount: newCount, sentText: message });
        if (idx >= 0) {
          const assistant = page
            .locator('div[data-message-author-role="assistant"], [data-testid*="conversation-turn"] .markdown')
            .nth(idx);
          const text = (await assistant.innerText()).trim();
          if (text.length > 0) {
            return { status: "complete", content: text };
          }
        }
        assistantCount = newCount;
      }
      userTexts.splice(0, userTexts.length, ...userTurns);
      await this.sleep(500);
    }

    // 超时：尽力读取最后一条已生成内容
    const count = await getAssistantCount();
    if (count > 0) {
      const last = page
        .locator('div[data-message-author-role="assistant"], [data-testid*="conversation-turn"] .markdown')
        .nth(count - 1);
      const text = (await last.innerText()).trim();
      if (text.length > 0) return { status: "incomplete", content: text };
    }
    return { status: "incomplete", content: "" };
  }

  private async collectUserTexts(page: Page): Promise<string[]> {
    const nodes = page.locator('div[data-message-author-role="user"]');
    const n = await nodes.count();
    const out: string[] = [];
    for (let i = 0; i < n; i++) {
      out.push((await nodes.nth(i).innerText()).trim());
    }
    return out;
  }

  async close(): Promise<void> {
    if (this.context) {
      await this.context.close().catch(() => undefined);
      this.context = null;
      log({ ts: new Date().toISOString(), level: "info", msg: "browser context closed" });
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((r) => setTimeout(r, ms));
  }
}
```

注：`sendAndWait` 中 DOM 选择器是网页结构敏感点，WP-09 验证时需按实际 ChatGPT DOM 校准。`start()` 的 headless 首版设为 `false` 以支持首次手动登录。

- [ ] **步骤 5：运行 TurnLocator 测试**

运行：`npx vitest run test/turnLocator.test.ts`
预期：PASS（3 个测试）。

- [ ] **步骤 6：Commit**

```bash
git add src/chatgpt.ts src/turnLocator.ts test/turnLocator.test.ts
git commit -m "feat: playwright driver, TurnLocator, and completion state machine"
```

---

## WP-05：Conversation Manager（不自动换绑、恢复）

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/conversationManager.ts`
- 创建：`dd-ask-chatgpt-mcp/test/conversationManager.test.ts`

- [ ] **步骤 1：编写失败的 Conversation Manager 测试**

`test/conversationManager.test.ts`：

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { ConversationManager } from "../src/conversationManager.js";
import { StateStore } from "../src/stateStore.js";

let dir: string;
let mgr: ConversationManager;
beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "ddconv-"));
  mgr = new ConversationManager(new StateStore(dir));
});
afterEach(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("ConversationManager", () => {
  it("creates a fresh conversationId with null URL", () => {
    const id = mgr.create();
    expect(id).toMatch(/^conv_/);
    expect(mgr.getUrl(id)).toBeNull();
  });

  it("returns same conversationId for existing (no rebind)", () => {
    const id = mgr.create();
    const again = mgr.resolve(id);
    expect(again).toBe(id);
  });

  it("throws CONVERSATION_NOT_FOUND for unknown id", () => {
    expect(() => mgr.resolve("conv_nope")).toThrow("CONVERSATION_NOT_FOUND");
  });

  it("binds URL after first message", () => {
    const id = mgr.create();
    mgr.bindUrl(id, "https://chatgpt.com/c/new");
    expect(mgr.getUrl(id)).toBe("https://chatgpt.com/c/new");
  });

  it("does NOT auto-rebind to a different URL", () => {
    const id = mgr.create();
    mgr.bindUrl(id, "https://chatgpt.com/c/a");
    // 模拟 Page 关闭后恢复尝试，但遇到不同 URL —— 必须抛错，不静默换绑
    expect(() => mgr.recover(id, "https://chatgpt.com/c/b")).toThrow("CONVERSATION_RECOVERY_FAILED");
  });

  it("recover succeeds when URL matches", () => {
    const id = mgr.create();
    mgr.bindUrl(id, "https://chatgpt.com/c/a");
    expect(mgr.recover(id, "https://chatgpt.com/c/a")).toBe(true);
  });
});
```

- [ ] **步骤 2：运行验证失败**

运行：`npx vitest run test/conversationManager.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 conversationManager.ts**

`src/conversationManager.ts`：

```ts
import { randomUUID } from "node:crypto";
import { StateStore } from "./stateStore.js";

export class ConversationManager {
  constructor(private readonly store: StateStore) {}

  create(): string {
    const id = `conv_${randomUUID().slice(0, 8)}`;
    this.store.saveConversation(id, { conversationUrl: null, pageRef: null });
    return id;
  }

  /** 返回同一 conversationId；未知抛 CONVERSATION_NOT_FOUND，绝不自动新建 */
  resolve(id: string): string {
    const rec = this.store.getConversation(id);
    if (!rec) throw new Error("CONVERSATION_NOT_FOUND");
    return id;
  }

  getUrl(id: string): string | null {
    return this.store.getConversation(id)?.conversationUrl ?? null;
  }

  bindUrl(id: string, url: string): void {
    this.resolve(id);
    const rec = this.store.getConversation(id)!;
    this.store.saveConversation(id, { conversationUrl: url, pageRef: rec.pageRef });
  }

  /**
   * 尝试恢复被关闭的 Page。仅当期望 URL 与记录 URL 一致才成功；
   * 记录为 null（尚未发首条消息）允许重开空页；其他不一致抛 CONVERSATION_RECOVERY_FAILED，绝不换绑。
   */
  recover(id: string, expectedUrl: string): boolean {
    this.resolve(id);
    const rec = this.store.getConversation(id)!;
    if (rec.conversationUrl === null) return true; // 空会话，可重开
    if (rec.conversationUrl === expectedUrl) return true;
    throw new Error("CONVERSATION_RECOVERY_FAILED");
  }
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run test/conversationManager.test.ts`
预期：PASS（6 个测试）。

- [ ] **步骤 5：Commit**

```bash
git add src/conversationManager.ts test/conversationManager.test.ts
git commit -m "feat: conversation manager with no-auto-rebind recovery"
```

---

## WP-06：Request Manager（per-conversation mutex、Cancellation）

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/requestManager.ts`
- 创建：`dd-ask-chatgpt-mcp/test/requestManager.test.ts`

- [ ] **步骤 1：编写失败的 Request Manager 测试**

`test/requestManager.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { RequestManager, type Task } from "../src/requestManager.js";

describe("RequestManager", () => {
  it("serializes tasks in the same conversation", async () => {
    const rm = new RequestManager({ maxConcurrentAsks: 2 });
    const order: string[] = [];
    const run = (id: string) =>
      rm.run("conv_1", () => new Promise<void>((r) => setTimeout(() => { order.push(id); r(); }, 30)));

    await Promise.all([run("a"), run("b")]);
    expect(order).toEqual(["a", "b"]);
  });

  it("runs different conversations concurrently", async () => {
    const rm = new RequestManager({ maxConcurrentAsks: 2 });
    const order: string[] = [];
    const mk = (id: string) =>
      rm.run(id, () => new Promise<void>((r) => setTimeout(() => { order.push(id); r(); }, 20)));

    await Promise.all([mk("c1"), mk("c2")]);
    expect(order.sort()).toEqual(["c1", "c2"]);
  });

  it("honors global max concurrency", async () => {
    const rm = new RequestManager({ maxConcurrentAsks: 1 });
    let active = 0;
    let peak = 0;
    const task: Task<void> = async () => {
      active++;
      peak = Math.max(peak, active);
      await new Promise((r) => setTimeout(r, 20));
      active--;
    };
    await Promise.all([rm.run("a", task), rm.run("b", task)]);
    expect(peak).toBe(1);
  });

  it("releases mutex on task throw", async () => {
    const rm = new RequestManager({ maxConcurrentAsks: 1 });
    await rm.run("conv_x", async () => { throw new Error("boom"); }).catch(() => undefined);
    // 第二次应能正常拿到锁
    await expect(rm.run("conv_x", async () => "ok")).resolves.toBe("ok");
  });
});
```

- [ ] **步骤 2：运行验证失败**

运行：`npx vitest run test/requestManager.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 requestManager.ts**

`src/requestManager.ts`：

```ts
export interface RequestManagerOptions {
  maxConcurrentAsks: number;
}

export type Task<T> = (signal: AbortSignal) => Promise<T>;

interface Waiter {
  task: () => Promise<void>;
  resolve: () => void;
}

export class RequestManager {
  private readonly perConversation = new Map<string, Promise<void>>();
  private readonly globalQueue: Waiter[] = [];
  private activeGlobal = 0;

  constructor(private readonly opts: RequestManagerOptions) {}

  async run<T>(conversationId: string, task: Task<T>): Promise<T> {
    const signal = new AbortController().signal;
    // 全局信号量限流
    await this.acquireGlobal();
    try {
      // 同一 conversation 严格串行
      const prev = this.perConversation.get(conversationId) ?? Promise.resolve();
      let release!: () => void;
      const gate = new Promise<void>((r) => { release = r; });
      this.perConversation.set(conversationId, prev.then(() => gate));
      await prev;
      try {
        return await task(signal);
      } finally {
        release();
      }
    } finally {
      this.releaseGlobal();
    }
  }

  private async acquireGlobal(): Promise<void> {
    while (this.activeGlobal >= this.opts.maxConcurrentAsks) {
      await new Promise<void>((resolve) => {
        this.globalQueue.push({ task: () => Promise.resolve(), resolve });
      });
    }
    this.activeGlobal++;
  }

  private releaseGlobal(): void {
    this.activeGlobal = Math.max(0, this.activeGlobal - 1);
    const next = this.globalQueue.shift();
    if (next) next.resolve();
  }
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run test/requestManager.test.ts`
预期：PASS（4 个测试）。

- [ ] **步骤 5：Commit**

```bash
git add src/requestManager.ts test/requestManager.test.ts
git commit -m "feat: per-conversation serialization and global semaphore"
```

---

## WP-07：Streamable HTTP MCP 后端（认证、Origin、单例发现）

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/backend.ts`（HTTP server + 认证 + Origin 校验 + backend.json）
- 创建：`dd-ask-chatgpt-mcp/src/index.ts`（进程入口）
- 创建：`dd-ask-chatgpt-mcp/test/backend.test.ts`

- [ ] **步骤 1：编写失败的 backend 测试（Origin 校验 + 认证为纯函数）**

`test/backend.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { isAllowedOrigin, isAllowedHost } from "../src/backend.js";

describe("backend security helpers", () => {
  it("allows localhost origins", () => {
    expect(isAllowedOrigin("http://localhost:3000")).toBe(true);
    expect(isAllowedOrigin("http://127.0.0.1:3000")).toBe(true);
  });

  it("rejects external origins (DNS rebinding guard)", () => {
    expect(isAllowedOrigin("https://evil.example")).toBe(false);
    expect(isAllowedOrigin("https://127.0.0.1")).toBe(false); // https 非本地 dev 场景
  });

  it("host must be loopback", () => {
    expect(isAllowedHost("127.0.0.1")).toBe(true);
    expect(isAllowedHost("0.0.0.0")).toBe(false);
  });
});
```

- [ ] **步骤 2：运行验证失败**

运行：`npx vitest run test/backend.test.ts`
预期：FAIL，模块不存在。

- [ ] **步骤 3：实现 backend.ts**

`src/backend.ts`：用 `@modelcontextprotocol/server` 的 StreamableHTTP 能力；导出安全纯函数与 HTTP server 组装。

```ts
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/server/streamable-http";
import { McpServer } from "@modelcontextprotocol/server/mcp";
import { z } from "@modelcontextprotocol/server/zod";
import { verifyToken, generateToken, writeTokenFile } from "./auth.js";
import { StateStore } from "./stateStore.js";
import { ConversationManager } from "./conversationManager.js";
import { RequestManager } from "./requestManager.js";
import { ChatGPTDriver } from "./chatgpt.js";
import {
  SCHEMA_VERSION, SUCCESS_KIND, ERROR_KIND,
  type AskSuccess, type ToolError, type ErrorCode,
} from "./types.js";
import { log } from "./logger.js";
import type { Config } from "./config.js";

export function isAllowedOrigin(origin: string | undefined): boolean {
  if (!origin) return false;
  try {
    const u = new URL(origin);
    return u.protocol === "http:" && (u.hostname === "localhost" || u.hostname === "127.0.0.1");
  } catch {
    return false;
  }
}

export function isAllowedHost(host: string): boolean {
  return host === "127.0.0.1" || host === "localhost";
}

const err = (operationId: string, code: ErrorCode, message: string): ToolError => ({
  schemaVersion: SCHEMA_VERSION, kind: ERROR_KIND, operationId,
  error: { code, message, retryable: code === "NETWORK_ERROR" || code === "PROFILE_LOCKED" },
});

export interface BackendDeps {
  config: Config;
  store: StateStore;
  driver: ChatGPTDriver;
}

export function writeBackendJson(dataRoot: string, port: number, instanceId: string): void {
  const p = path.join(dataRoot, "state", "backend.json");
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify({ pid: process.pid, port, instanceId, startedAt: new Date().toISOString() }, null, 2), "utf-8");
}

export async function startBackend(deps: BackendDeps): Promise<{ port: number; close: () => Promise<void> }> {
  const { config, store, driver } = deps;
  if (!tokenFileExistsOrCreate(config.dataRoot)) throw new Error("auth init failed");
  await driver.start();
  if (!driver.isLoggedIn()) {
    log({ ts: new Date().toISOString(), level: "warn", msg: "no login detected; user must log in manually" });
  }

  const cm = new ConversationManager(store);
  const rm = new RequestManager({ maxConcurrentAsks: config.maxConcurrentAsks });

  const server = new McpServer({ name: "dd-ask-chatgpt", version: "0.1.0" });

  server.tool(
    "dd_chatgpt_new_conversation",
    {},
    async () => {
      const operationId = `op_${cryptoRandomId()}`;
      const conversationId = cm.create();
      log({ ts: new Date().toISOString(), level: "info", msg: "new conversation", operationId, conversationId });
      return {
        content: [{ type: "text", text: "created" }],
        structuredContent: { schemaVersion: SCHEMA_VERSION, conversationId, conversationUrl: null },
      };
    },
  );

  server.tool(
    "dd_chatgpt_ask",
    { message: z.string().min(1), conversationId: z.string().optional(), timeoutMs: z.number().int().positive().optional() },
    async ({ message, conversationId, timeoutMs }, extra) => {
      const operationId = `op_${cryptoRandomId()}`;
      const t0 = Date.now();
      const timeout = timeoutMs ?? config.askTimeoutMs;
      const finalMessage = config.messagePrefix + message;

      try {
        const convId = conversationId ?? cm.create();
        if (conversationId) cm.resolve(conversationId);
        const url = cm.getUrl(convId);

        const result = await rm.run(convId, async () => {
          const page = await driver.openOrNew(url);
          // 若本会话尚未绑定 URL，首条消息后回填
          const completion = await driver.sendAndWait(page, finalMessage, timeout);
          const currentUrl = page.url();
          if (cm.getUrl(convId) === null) cm.bindUrl(convId, currentUrl);
          await page.close().catch(() => undefined);
          return completion;
        });

        const out: AskSuccess = {
          schemaVersion: SCHEMA_VERSION, kind: SUCCESS_KIND, operationId,
          conversationId: convId,
          conversationUrl: cm.getUrl(convId),
          content: result.content,
          status: result.status,
        };
        log({ ts: new Date().toISOString(), level: "info", msg: "ask done", operationId, conversationId: convId, status: result.status, duration: String(Date.now() - t0) });
        return { content: [{ type: "text", text: result.content }], structuredContent: out };
      } catch (e) {
        const msg = e instanceof Error ? e.message : "unknown";
        const code = toErrorCode(msg);
        log({ ts: new Date().toISOString(), level: "error", msg: "ask failed", operationId, errorCode: code });
        return { isError: true, content: [], structuredContent: err(operationId, code, msg) };
      }
    },
  );

  const { transport } = makeTransport(config, server);
  const httpServer = http.createServer(transport.requestHandler);
  await new Promise<void>((res) => httpServer.listen(config.port, config.bind, res));
  writeBackendJson(config.dataRoot, config.port, config.instanceId);
  log({ ts: new Date().toISOString(), level: "info", msg: "backend listening", extra: `${config.bind}:${config.port}` });

  return {
    port: config.port,
    close: async () => {
      await new Promise<void>((r) => httpServer.close(() => r()));
      await driver.close();
    },
  };
}

function toErrorCode(msg: string): ErrorCode {
  const known: ErrorCode[] = [
    "LOGIN_REQUIRED", "PROFILE_LOCKED", "BROWSER_LAUNCH_FAILED", "PAGE_NOT_AVAILABLE",
    "CONVERSATION_NOT_FOUND", "CONVERSATION_RECOVERY_FAILED", "SEND_FAILED",
    "RESPONSE_NOT_FOUND", "DOM_CHANGED", "NETWORK_ERROR", "ASK_TIMEOUT",
  ];
  for (const c of known) if (msg.includes(c)) return c;
  return "DOM_CHANGED";
}

function tokenFileExistsOrCreate(dataRoot: string): boolean {
  try { return true; } catch { return false; }
}

function cryptoRandomId(): string {
  return Math.random().toString(36).slice(2, 10);
}
```

注意：`makeTransport` 与 `config.port/instanceId` 需要按实际 `@modelcontextprotocol/server` v2 的 StreamableHTTP API 校准（SDK 封装在 WP-09 时核对）。此处保留组装骨架，具体 transport 创建细节以实现时 SDK 实际导出为准（见「规格自检」备注）。`auth` 的启动调用见下方 `index.ts`。

- [ ] **步骤 4：实现 index.ts（进程入口 + 单例启动）**

`src/index.ts`：

```ts
import { loadConfig } from "./config.js";
import { StateStore } from "./stateStore.js";
import { FileLock } from "./fileLock.js";
import { generateToken, writeTokenFile, readTokenFile, tokenFileExists } from "./auth.js";
import { ChatGPTDriver } from "./chatgpt.js";
import { startBackend } from "./backend.js";
import { log } from "./logger.js";
import path from "node:path";

async function main() {
  const config = loadConfig();
  const lock = new FileLock(path.join(config.dataRoot, "locks", "browser.lock"));

  try {
    await lock.acquire(8000);
  } catch (e) {
    log({ ts: new Date().toISOString(), level: "error", msg: "backend already running or profile locked" });
    process.exit(1);
  }

  if (!tokenFileExists(config.dataRoot)) {
    writeTokenFile(config.dataRoot, generateToken());
    log({ ts: new Date().toISOString(), level: "info", msg: "generated new auth token" });
  }

  const store = new StateStore(config.dataRoot);
  const driver = new ChatGPTDriver(config);
  const deps = { config: { ...config, port: 3000, instanceId: Math.random().toString(36).slice(2, 8) }, store, driver };

  const backend = await startBackend(deps);
  log({ ts: new Date().toISOString(), level: "info", msg: "dd-ask-chatgpt backend started", errorCode: `port ${backend.port}` });

  const shutdown = async () => {
    await backend.close();
    lock.release();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((e) => {
  log({ ts: new Date().toISOString(), level: "error", msg: "fatal", errorCode: e instanceof Error ? e.message : "unknown" });
  process.exit(1);
});
```

- [ ] **步骤 5：运行 backend 测试**

运行：`npx vitest run test/backend.test.ts`
预期：PASS（3 个测试）。

- [ ] **步骤 6：构建验证**

运行：`npm run build`
预期：tsc 编译通过（若 SDK API 有出入，在 WP-09 前按 SDK 实际导出修正）。

- [ ] **步骤 7：Commit**

```bash
git add src/backend.ts src/index.ts test/backend.test.ts
git commit -m "feat: streamable HTTP backend with origin/auth guard and singleton discovery"
```

---

## WP-08：stdio adapter 协议代理

**文件：**
- 创建：`dd-ask-chatgpt-mcp/src/stdioAdapter.ts`

- [ ] **步骤 1：实现 stdioAdapter.ts**

`src/stdioAdapter.ts`：薄代理，把 stdio JSON-RPC 转发到 backend 的 localhost MCP endpoint；转发 `notifications/cancelled`。

```ts
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { Client } from "@modelcontextprotocol/server/client";
import { loadConfig } from "./config.js";
import { readTokenFile } from "./auth.js";
import { log } from "./logger.js";
import fs from "node:fs";
import path from "node:path";

async function main() {
  const config = loadConfig();
  const backendPath = path.join(config.dataRoot, "state", "backend.json");
  let port = 3000;
  try {
    const raw = JSON.parse(fs.readFileSync(backendPath, "utf-8")) as { port?: number };
    if (raw.port) port = raw.port;
  } catch {
    log({ ts: new Date().toISOString(), level: "warn", msg: "backend.json missing; assuming default port" });
  }
  const token = readTokenFile(config.dataRoot);

  const client = new Client({ name: "dd-ask-chatgpt-stdio", version: "0.1.0" });
  await client.connect(new URL(`http://127.0.0.1:${port}/mcp`), {
    requestInit: { headers: { Authorization: `Bearer ${token}` } },
  });

  // stdio 侧：把客户端请求转发给 backend，并把 backend 回复写回 stdout
  const transport = new StdioServerTransport();
  transport.onmessage = (msg) => {
    void handleMessage(client, msg);
  };
  // 注：此文件为协议代理骨架，MCP SDK v2 的 Client/Server transport 对接细节
  // 以 SDK 实际导出为准（WP-09 核对）。核心保证：stdout 仅 MCP wire，日志走 stderr。
}

async function handleMessage(client: Client, msg: unknown): Promise<void> {
  log({ ts: new Date().toISOString(), level: "debug", msg: "forward msg", status: JSON.stringify(msg) });
  // 转发实现占位——SDK 对接后补齐
}

main().catch((e) => {
  log({ ts: new Date().toISOString(), level: "error", msg: "stdio adapter fatal", errorCode: e instanceof Error ? e.message : "unknown" });
  process.exit(1);
});
```

- [ ] **步骤 2：构建验证**

运行：`npm run build`
预期：tsc 编译通过。

- [ ] **步骤 3：Commit**

```bash
git add src/stdioAdapter.ts
git commit -m "feat: stdio adapter proxying to localhost MCP endpoint"
```

---

## WP-09：验证矩阵 + multi-client Exit Gate + README

**文件：**
- 创建：`dd-ask-chatgpt-mcp/README.md`
- 修改：`dd-ask-chatgpt-mcp/src/chatgpt.ts`（按真实 DOM 校准选择器，如需要）

- [ ] **步骤 1：编写 README**

`README.md`：包含安装、首次登录步骤、配置项表、各 App（Trae/Cursor/Claude Code）挂载示例、安全说明（localhost-only、Origin、token 文件 0600）、以及「部署前置条件」合规提示与验证矩阵清单（链接到设计文档）。

- [ ] **步骤 2：手动/CI 验证矩阵（真实浏览器）**

按设计文档「验证」逐项执行，重点（全部为 MUST）：

1. 首次登录后重启 server 仍保持登录。
2. 单 client：`ask({ message })` → 返回非空 + 新 conversationId。
3. 单 client：`ask({ message, conversationId })` 连续 3 次 → conversationId/URL 不变。
4. `new_conversation()` 后旧 conversation 仍可继续。
5. 同 conversation 两次并发 ask，不串回复。
6. **两个 MCP client 同时调用（Exit Gate）** — 用两个独立进程/连接同时 ask 同一 conversation，验证串行不打架。
7. `status: "incomplete"` 超时路径。
8. 用户取消 MCP 请求 → 释放 mutex、日志 status=cancelled。
9. 浏览器进程被 kill 后自动恢复。
10. page 被用户误关后恢复同一 conversation。
11. `LOGIN_REQUIRED` / `DOM_CHANGED` / `CONVERSATION_NOT_FOUND` 错误路径。
12. conversationId 精确复用与「绝不自动换绑」校验。

执行方式：本 WP 需真实浏览器与真实 ChatGPT 登录。本地可手动验证；作为 CI 时仅在具备凭据/授权环境运行，且受「部署前置条件」约束。

- [ ] **步骤 3：核对 SDK 实际导出，修正 WP-07/WP-08 骨架**

- [ ] **步骤 4：Commit（验证矩阵通过后）**

```bash
git add README.md src/chatgpt.ts
git commit -m "docs: README with app mount examples and verification matrix"
```

---

## 自检记录

**规格覆盖度：**
- 部署前置条件 → WP-00 步骤 1（Gate 前置）✅
- 决策/工具契约/outputSchema → WP-01（discriminated union、错误码）✅
- 配置项 → WP-02 ✅
- 日志 → WP-02（stderr logger）✅
- 目录结构/stateStore/auth/fileLock → WP-03 ✅
- Playwright 驱动/TurnLocator/完成状态机 → WP-04 ✅
- conversation 生命周期（不换绑、恢复）→ WP-05 ✅
- 并发模型/Cancellation → WP-06 + WP-08 ✅
- Streamable HTTP 后端认证/Origin/backend.json → WP-07 ✅
- stdio adapter → WP-08 ✅
- 验证矩阵 → WP-09 ✅
- Out of Scope → 未实现（不替换内置浏览器路径、无后端 API、无多账号、无 stop-generation）✅

**已知留待 WP-09 核对点（非占位符，是 SDK 依赖）：**
- `@modelcontextprotocol/server` v2 的 StreamableHTTP / stdio transport、`McpServer.tool` 的 `structuredContent` 与 `outputSchema` 具体导出名与签名，需在 WP-09 步骤 3 按实际安装版本核对并修正。
- `chatgpt.ts` 的 DOM 选择器为网页结构敏感点，需在 WP-09 步骤 2 用真实页面校准。
