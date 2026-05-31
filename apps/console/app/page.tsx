import Link from "next/link";
import { listSuggestions, computeStats } from "@/lib/suggestions";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  eventTypeLabel,
  statusLabel,
  decisionLabel,
  priorityClasses,
  decisionClasses,
  encodeKey,
} from "@/lib/labels";

export const dynamic = "force-dynamic";

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card className="p-4 gap-1">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {hint ? <div className="text-muted-foreground text-xs">{hint}</div> : null}
    </Card>
  );
}

export default async function Page() {
  const rows = await listSuggestions();
  const stats = computeStats(rows);

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agent Console</h1>
          <p className="text-muted-foreground text-sm">
            Follow-up Agent · 看见并处置今天的跟进建议
          </p>
        </div>
        <Badge variant="outline" className="font-mono text-xs">
          FS-AOL · v1.0 console-mvp
        </Badge>
      </header>

      <section className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="待跟进建议" value={stats.needFollow} hint={`共 ${stats.total} 条记录`} />
        <Stat label="待处置" value={stats.pending} hint="尚未同意/拒绝/修改" />
        <Stat
          label="App 内处置率"
          value={`${stats.handledRate}%`}
          hint={`同意 ${stats.approved} · 修改 ${stats.modified} · 拒绝 ${stats.rejected}`}
        />
        <Stat
          label="高优先级"
          value={stats.byPriority["高"] ?? 0}
          hint={`中 ${stats.byPriority["中"] ?? 0} · 低 ${stats.byPriority["低"] ?? 0}`}
        />
      </section>

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[88px]">优先级</TableHead>
              <TableHead>工单 / 事件</TableHead>
              <TableHead className="hidden md:table-cell">原因摘要</TableHead>
              <TableHead className="w-[96px]">状态</TableHead>
              <TableHead className="w-[96px]">处置</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                  暂无建议。先运行引擎填充数据：
                  <code className="mx-1 font-mono text-xs">
                    FSM_SOURCE=mock LLM_PROVIDER=heuristic AGENT_MODE=steps python run_cron.py
                  </code>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((r) => {
                const s = r.suggestion;
                return (
                  <TableRow key={r.dedupeKey} className="group">
                    <TableCell>
                      <Badge className={priorityClasses(s.优先级)}>
                        {s.优先级 || "—"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/suggestions/${encodeKey(r.dedupeKey)}`}
                        className="block"
                      >
                        <div className="font-mono text-sm group-hover:underline">
                          {r.orderNum || r.workOrderId}
                        </div>
                        <div className="text-muted-foreground text-xs">
                          {eventTypeLabel(r.eventType)} · {r.city || "—"}
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <span className="text-muted-foreground line-clamp-2 text-sm">
                        {s.原因摘要 || "—"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-muted-foreground text-xs">
                        {statusLabel(r.status)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge className={decisionClasses(r.outcome?.decision)}>
                        {decisionLabel(r.outcome?.decision)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </main>
  );
}
