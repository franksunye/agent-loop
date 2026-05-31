import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { getSuggestion, getTrace, type SuggestionDoc } from "@/lib/suggestions";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DecisionActions } from "@/components/decision-actions";
import { BlockerFeedbackForm } from "@/components/blocker-feedback";
import { TraceView } from "@/components/trace-view";
import {
  eventTypeLabel,
  statusLabel,
  decisionLabel,
  priorityClasses,
  decisionClasses,
} from "@/lib/labels";

export const dynamic = "force-dynamic";

function Field({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-sm">{value}</div>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-muted-foreground font-mono text-xs">
              {i + 1}
            </span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlanView({ s, title }: { s: SuggestionDoc; title?: string }) {
  const sit = s.情况判断 ?? {};
  const plan = s.跟进方案 ?? {};
  return (
    <div className="space-y-6">
      {title ? (
        <Badge variant="secondary" className="text-xs">
          {title}
        </Badge>
      ) : null}
      {s.原因摘要 ? (
        <p className="text-base leading-relaxed">{s.原因摘要}</p>
      ) : null}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Field label="商机阶段" value={sit.商机阶段} />
        <Field label="报价状态" value={sit.报价状态} />
        <Field label="金额与方案" value={sit.金额与方案} />
        <Field label="渠道与部位" value={sit.渠道与部位} />
      </div>

      <Separator />

      {plan.主行动 ? (
        <div>
          <h3 className="mb-1 text-sm font-medium">主行动</h3>
          <p className="text-sm">{plan.主行动}</p>
        </div>
      ) : null}

      <ListBlock title="优先级依据" items={s.优先级依据} />
      <ListBlock title="沟通要点" items={plan.沟通要点} />
      <ListBlock title="避免事项" items={plan.避免事项} />
      <ListBlock title="引用查证" items={s.引用查证} />
    </div>
  );
}

export default async function SuggestionDetail({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = await params;
  const dedupeKey = decodeURIComponent(key);
  const row = await getSuggestion(dedupeKey);
  if (!row) notFound();

  const trace = await getTrace(row.workOrderId);
  const s = row.suggestion;
  const modified = row.outcome?.modifiedSuggestion ?? null;

  return (
    <main className="mx-auto w-full max-w-4xl px-6 py-8">
      <Link
        href="/"
        className="text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 text-sm"
      >
        <ArrowLeft className="h-4 w-4" /> 返回列表
      </Link>

      <Card className="mb-6 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="font-mono text-lg font-semibold">
              {row.orderNum || row.workOrderId}
            </div>
            <div className="text-muted-foreground text-sm">
              {eventTypeLabel(row.eventType)} · {row.city || "—"} ·{" "}
              {statusLabel(row.status)}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={priorityClasses(s.优先级)}>
              优先级 {s.优先级 || "—"}
            </Badge>
            {s.客户情绪 ? (
              <Badge variant="outline">情绪 {s.客户情绪}</Badge>
            ) : null}
            <Badge className={decisionClasses(row.outcome?.decision)}>
              {decisionLabel(row.outcome?.decision)}
            </Badge>
          </div>
        </div>

        <Separator className="my-4" />

        <DecisionActions
          dedupeKey={row.dedupeKey}
          workOrderId={row.workOrderId}
          suggestion={s}
          currentDecision={row.outcome?.decision ?? null}
        />

        <div className="mt-4">
          <BlockerFeedbackForm
            dedupeKey={row.dedupeKey}
            workOrderId={row.workOrderId}
            currentType={row.blocker?.blockerType ?? null}
            currentNote={row.blocker?.note ?? null}
          />
        </div>
      </Card>

      <Tabs defaultValue="plan">
        <TabsList>
          <TabsTrigger value="plan">跟进方案</TabsTrigger>
          <TabsTrigger value="trace">推理与查证</TabsTrigger>
        </TabsList>
        <TabsContent value="plan" className="pt-2">
          <Card className="p-5">
            <PlanView s={s} />
            {modified ? (
              <>
                <Separator className="my-6" />
                <PlanView s={modified} title="人工修改后的方案" />
              </>
            ) : null}
          </Card>
        </TabsContent>
        <TabsContent value="trace" className="pt-2">
          <Card className="p-5">
            <TraceView trace={trace} />
          </Card>
        </TabsContent>
      </Tabs>
    </main>
  );
}
