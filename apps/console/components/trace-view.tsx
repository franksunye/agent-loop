import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { TraceRow } from "@/lib/suggestions";

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v));
  return [];
}

export function TraceView({ trace }: { trace: TraceRow | null }) {
  if (!trace) {
    return (
      <p className="text-muted-foreground text-sm">
        暂无推理轨迹。仅 <code className="font-mono">AGENT_MODE=steps</code>{" "}
        运行才会记录查证步骤。
      </p>
    );
  }

  const enrich = trace.enrich ?? {};
  const verdict = String(enrich.business_verdict ?? "");
  const evidence = asStringList(enrich.evidence_lines);
  const hints = asStringList(enrich.business_hints);
  // enrich 会把 business_hints 追加进 evidence_lines；UI 上事实与提示分开展示，避免重复
  const factLines = evidence.filter((line) => !line.startsWith("业务提示"));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="outline" className="font-mono">
          {trace.mode}
        </Badge>
        <Badge variant="outline" className="font-mono">
          {trace.model}
        </Badge>
        <span className="text-muted-foreground font-mono">
          {trace.latencyMs}ms · {trace.totalTokens}tok
        </span>
        <span className="text-muted-foreground font-mono">{trace.createdAt}</span>
        {trace.status !== "ok" ? (
          <Badge className="border-transparent bg-red-500/15 text-red-400">
            {trace.status}
          </Badge>
        ) : null}
      </div>

      {/* 步骤链 */}
      <div>
        <h3 className="mb-2 text-sm font-medium">推理步骤</h3>
        <ol className="space-y-2">
          {trace.steps.length === 0 ? (
            <li className="text-muted-foreground text-sm">（单次推理，无分步）</li>
          ) : (
            trace.steps.map((st, i) => (
              <li
                key={i}
                className="bg-muted/40 flex items-center gap-3 rounded-md px-3 py-2 text-sm"
              >
                <span className="bg-background flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs">
                  {st.step ?? i + 1}
                </span>
                <span className="font-medium">{st.name || st.kind}</span>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {st.kind}
                </Badge>
                <span className="text-muted-foreground ml-auto font-mono text-xs">
                  {st.latency_ms != null ? `${st.latency_ms}ms` : ""} {st.status}
                </span>
              </li>
            ))
          )}
        </ol>
      </div>

      {/* 系统查证（证据） */}
      {(verdict || factLines.length > 0 || hints.length > 0) && (
        <div>
          <Separator className="mb-4" />
          <h3 className="mb-2 text-sm font-medium">系统查证 · 只读事实</h3>
          {verdict ? (
            <p className="mb-2 text-sm font-medium text-amber-400">{verdict}</p>
          ) : null}
          <ul className="space-y-1">
            {factLines.map((line, i) => (
              <li key={i} className="text-muted-foreground text-sm">
                · {line}
              </li>
            ))}
          </ul>
          {hints.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {hints.map((h, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {h}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {/* 原始响应 */}
      <details className="group">
        <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
          原始模型输出 / Prompt（可展开核对）
        </summary>
        <div className="mt-3 space-y-3">
          {trace.error ? (
            <pre className="overflow-x-auto rounded-md bg-red-500/10 p-3 font-mono text-xs text-red-400">
              {trace.error}
            </pre>
          ) : null}
          <div>
            <div className="text-muted-foreground mb-1 text-xs">raw_response</div>
            <pre className="bg-muted/40 max-h-72 overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
              {trace.rawResponse || "—"}
            </pre>
          </div>
          <div>
            <div className="text-muted-foreground mb-1 text-xs">user prompt</div>
            <pre className="bg-muted/40 max-h-60 overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
              {trace.promptUser || "—"}
            </pre>
          </div>
        </div>
      </details>
    </div>
  );
}
