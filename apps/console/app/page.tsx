import Link from "next/link";
import { cookies } from "next/headers";
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
import { blockerDisplay } from "@/lib/blockers";
import { isAuthEnabled } from "@/lib/auth";
import { loadPilotHousekeepers, housekeeperName } from "@/lib/pilot-housekeepers";
import { LogoutButton } from "@/components/logout-button";
import { HousekeeperFilter, HOUSEKEEPER_FILTER_COOKIE } from "@/components/housekeeper-filter";

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
  const cookieStore = await cookies();
  const hkFilter = cookieStore.get(HOUSEKEEPER_FILTER_COOKIE)?.value?.trim();
  const pilots = loadPilotHousekeepers();
  const rows = await listSuggestions(
    hkFilter ? { housekeeperId: hkFilter } : undefined
  );
  const stats = computeStats(rows);

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agent Console</h1>
          <p className="text-muted-foreground text-sm">
            Follow-up Agent · 看见并处置今天的跟进建议
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <HousekeeperFilter pilots={pilots} currentId={hkFilter} />
          {isAuthEnabled() ? <LogoutButton /> : null}
          <Badge variant="outline" className="font-mono text-xs">
            FS-AOL · v0.2.x
          </Badge>
        </div>
      </header>

      <section className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="待跟进建议" value={stats.needFollow} hint={`共 ${stats.total} 条记录`} />
        <Stat label="待处置" value={stats.pending} hint="尚未同意/拒绝/修改/已跟进" />
        <Stat
          label="App 内处置率"
          value={`${stats.handledRate}%`}
          hint={`同意 ${stats.approved} · 已跟进 ${stats.followedUp} · 修改 ${stats.modified}`}
        />
        <Stat
          label="高优先级"
          value={stats.byPriority["高"] ?? 0}
          hint={`中 ${stats.byPriority["中"] ?? 0} · 低 ${stats.byPriority["低"] ?? 0}`}
        />
      </section>

      <section className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="曝光" value={stats.exposureCount} hint="需跟进建议条数" />
        <Stat label="采纳率" value={`${stats.adoptionRate}%`} hint="同意/修改/已跟进" />
        <Stat
          label="阻塞采集率"
          value={`${stats.blockerCaptureRate}%`}
          hint="已回填 A/B/C/D"
        />
        <Stat
          label="UNKNOWN 占比"
          value={`${stats.unknownBlockerRate}%`}
          hint="尚未采集阻塞"
        />
      </section>

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[88px]">优先级</TableHead>
              <TableHead>工单 / 事件</TableHead>
              <TableHead className="hidden md:table-cell">原因摘要</TableHead>
              <TableHead className="hidden lg:table-cell w-[120px]">阻塞</TableHead>
              <TableHead className="w-[96px]">状态</TableHead>
              <TableHead className="w-[96px]">处置</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
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
                          {pilots.length ? ` · ${housekeeperName(pilots, r.housekeeperId)}` : ""}
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <span className="text-muted-foreground line-clamp-2 text-sm">
                        {s.原因摘要 || "—"}
                      </span>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <span className="text-muted-foreground text-xs">
                        {blockerDisplay(r.blocker?.blockerType, r.blocker?.note)}
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
