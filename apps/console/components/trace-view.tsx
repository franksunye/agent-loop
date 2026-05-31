import { Check, ChevronRight, Database, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { TraceRow, TraceStep } from "@/lib/suggestions";

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v));
  return [];
}

function stepTitle(st: TraceStep): string {
  const name = st.name || "";
  if (name === "enrich_work_order_context") return "系统查证";
  if (name === "suggest") return "生成跟进建议";
  return name || st.kind || "步骤";
}

function stepSubtitle(st: TraceStep): string {
  if (st.kind === "tool") return "读取 Mongo 报价 / 签约 / 部位与渠道";
  if (st.kind === "llm") return "基于查证事实输出 Action Spec";
  return st.kind || "";
}

function formatVerdict(raw: string): string {
  return raw.replace(/^【结论】\s*/, "").trim();
}

function hintLabel(raw: string): string {
  return raw.replace(/^业务提示：\s*/, "").trim();
}

function StepIcon({ kind }: { kind?: string }) {
  const Icon = kind === "tool" ? Database : Sparkles;
  return (
    <span className="bg-primary/10 text-primary flex h-7 w-7 shrink-0 items-center justify-center rounded-full">
      <Icon className="h-3.5 w-3.5" />
    </span>
  );
}

export function TraceView({ trace }: { trace: TraceRow | null }) {
  if (!trace) {
    return (
      <p className="text-muted-foreground text-sm">
        暂无推理轨迹。仅{" "}
        <code className="font-mono text-xs">AGENT_MODE=steps</code>{" "}
        运行时会记录分步查证。
      </p>
    );
  }

  const enrich = trace.enrich ?? {};
  const verdict = formatVerdict(String(enrich.business_verdict ?? ""));
  const evidence = asStringList(enrich.evidence_lines);
  const hints = asStringList(enrich.business_hints).map(hintLabel);
  const factLines = evidence.filter((line) => !line.startsWith("业务提示"));

  return (
    <div className="space-y-5">
      {/* 结论摘要 — 类似 Copilot / Perplexity 顶部 answer snippet */}
      {verdict ? (
        <div className="border-primary/20 bg-primary/5 rounded-lg border px-4 py-3">
          <p className="text-muted-foreground mb-1 text-xs font-medium">
            查证结论
          </p>
          <p className="text-sm leading-relaxed">{verdict}</p>
        </div>
      ) : null}

      {/* 推理时间线 — 主流 chain-of-thought 竖线 + 完成态 */}
      {trace.steps.length > 0 ? (
        <section>
          <h3 className="text-muted-foreground mb-3 text-xs font-medium">
            推理过程
          </h3>
          <ol className="relative space-y-0">
            {trace.steps.map((st, i) => {
              const done = st.status === "ok" || !st.status;
              const isLast = i === trace.steps.length - 1;
              return (
                <li key={i} className="relative flex gap-3 pb-5 last:pb-0">
                  {!isLast ? (
                    <span
                      className="bg-border absolute top-8 left-3.5 h-[calc(100%-12px)] w-px"
                      aria-hidden
                    />
                  ) : null}
                  <div className="relative z-10 flex flex-col items-center">
                    <StepIcon kind={st.kind} />
                    {done ? (
                      <Check
                        className="text-emerald-600 absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full bg-background"
                        aria-hidden
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                      <span className="text-sm font-medium">{stepTitle(st)}</span>
                      {st.latency_ms != null ? (
                        <span className="text-muted-foreground font-mono text-[11px]">
                          {(st.latency_ms / 1000).toFixed(1)}s
                        </span>
                      ) : null}
                    </div>
                    {stepSubtitle(st) ? (
                      <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
                        {stepSubtitle(st)}
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : (
        <p className="text-muted-foreground text-sm">单次推理，无分步记录。</p>
      )}

      {/* 查证依据 — 事实与运营提示分区 */}
      {(factLines.length > 0 || hints.length > 0) && (
        <section className="space-y-3">
          <h3 className="text-muted-foreground text-xs font-medium">
            查证依据
          </h3>
          {factLines.length > 0 ? (
            <ul className="bg-muted/30 divide-border/60 divide-y rounded-lg border text-sm">
              {factLines.map((line, i) => (
                <li key={i} className="text-muted-foreground px-3 py-2 leading-relaxed">
                  {line}
                </li>
              ))}
            </ul>
          ) : null}
          {hints.length > 0 ? (
            <div>
              <p className="text-muted-foreground mb-1.5 text-xs">运营提示</p>
              <div className="flex flex-wrap gap-1.5">
                {hints.map((h, i) => (
                  <Badge
                    key={i}
                    variant="secondary"
                    className="h-auto max-w-full py-1 text-left text-xs font-normal leading-snug whitespace-normal"
                  >
                    {h}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      )}

      {/* 调试信息 — 技术元数据默认收起 */}
      <details className="group border-border rounded-lg border">
        <summary className="text-muted-foreground hover:text-foreground flex cursor-pointer list-none items-center gap-1 px-3 py-2.5 text-sm select-none [&::-webkit-details-marker]:hidden">
          <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
          调试信息
          <span className="text-muted-foreground/80 ml-1 text-xs font-normal">
            原始输出 · Prompt · 运行参数
          </span>
        </summary>
        <div className="border-border space-y-3 border-t px-3 py-3">
          <dl className="text-muted-foreground grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt>模型</dt>
            <dd className="font-mono">{trace.model}</dd>
            <dt>模式</dt>
            <dd className="font-mono">{trace.mode}</dd>
            <dt>耗时</dt>
            <dd className="font-mono">{trace.latencyMs}ms</dd>
            <dt>Token</dt>
            <dd className="font-mono">{trace.totalTokens}</dd>
            <dt>时间</dt>
            <dd className="font-mono">{trace.createdAt}</dd>
            {trace.status !== "ok" ? (
              <>
                <dt>状态</dt>
                <dd className="text-red-400">{trace.status}</dd>
              </>
            ) : null}
          </dl>
          {trace.error ? (
            <pre className="overflow-x-auto rounded-md bg-red-500/10 p-3 font-mono text-xs text-red-400 whitespace-pre-wrap">
              {trace.error}
            </pre>
          ) : null}
          <div>
            <p className="text-muted-foreground mb-1 text-xs">模型输出</p>
            <pre className="bg-muted/40 max-h-48 overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
              {trace.rawResponse || "—"}
            </pre>
          </div>
          <div>
            <p className="text-muted-foreground mb-1 text-xs">用户 Prompt</p>
            <pre className="bg-muted/40 max-h-40 overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
              {trace.promptUser || "—"}
            </pre>
          </div>
        </div>
      </details>
    </div>
  );
}
