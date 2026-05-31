import { Suspense } from "react";
import { cookies } from "next/headers";
import { listSuggestions, computeStats } from "@/lib/suggestions";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { isAuthEnabled } from "@/lib/auth";
import { loadPilotHousekeepers, housekeeperName } from "@/lib/pilot-housekeepers";
import { LogoutButton } from "@/components/logout-button";
import { HousekeeperFilter, HOUSEKEEPER_FILTER_COOKIE } from "@/components/housekeeper-filter";
import { SuggestionInboxTable } from "@/components/suggestion-inbox-table";
import { SuggestionSort } from "@/components/suggestion-sort";
import {
  parseSuggestionSortKey,
  sortSuggestions,
} from "@/lib/suggestion-sorting";

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

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ hk?: string; sort?: string }>;
}) {
  const sp = await searchParams;
  const cookieStore = await cookies();
  const hkFromCookie = cookieStore.get(HOUSEKEEPER_FILTER_COOKIE)?.value?.trim();
  // URL ?hk= 优先，其次 cookie（便于深链与刷新）
  const hkFilter = sp.hk?.trim() || hkFromCookie || undefined;
  const pilots = loadPilotHousekeepers();
  const rawRows = await listSuggestions(
    hkFilter ? { housekeeperId: hkFilter } : undefined
  );
  const sortKey = parseSuggestionSortKey(sp.sort);
  const rows = sortSuggestions(rawRows, sortKey, pilots);
  const stats = computeStats(rows);
  const filteredLabel = hkFilter
    ? housekeeperName(pilots, hkFilter)
    : null;

  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agent Console</h1>
          <p className="text-muted-foreground text-sm">
            Follow-up Agent · 看见并处置今天的跟进建议
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Suspense fallback={null}>
            <HousekeeperFilter pilots={pilots} currentId={hkFilter} />
          </Suspense>
          {isAuthEnabled() ? <LogoutButton /> : null}
          <Badge variant="outline" className="font-mono text-xs">
            FS-AOL · v0.2.4
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

      <div className="mb-3">
        <Suspense fallback={null}>
          <SuggestionSort current={sortKey} />
        </Suspense>
      </div>

      <Card className="overflow-hidden p-0">
        <SuggestionInboxTable
          rows={rows}
          pilots={pilots}
          emptyMessage={
            filteredLabel ? (
              `${filteredLabel} 暂无跟进建议（Turso 中无匹配 housekeeper_id 的记录）`
            ) : (
              <>
                暂无建议。先运行引擎填充数据：
                <code className="mx-1 font-mono text-xs">
                  FSM_SOURCE=mock LLM_PROVIDER=heuristic AGENT_MODE=steps python run_cron.py
                </code>
              </>
            )
          }
        />
      </Card>
    </main>
  );
}
