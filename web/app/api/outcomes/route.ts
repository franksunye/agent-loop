import { NextResponse } from "next/server";
import { recordOutcome, type Decision, type SuggestionDoc } from "@/lib/suggestions";

const VALID: Decision[] = ["approved", "rejected", "modified"];

export async function POST(req: Request) {
  let body: {
    dedupeKey?: string;
    workOrderId?: string;
    decision?: Decision;
    note?: string;
    operator?: string;
    modifiedSuggestion?: SuggestionDoc | null;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  if (!body.dedupeKey || !body.decision || !VALID.includes(body.decision)) {
    return NextResponse.json(
      { error: "dedupeKey 与合法 decision 必填" },
      { status: 400 }
    );
  }

  try {
    await recordOutcome({
      dedupeKey: body.dedupeKey,
      workOrderId: body.workOrderId ?? "",
      decision: body.decision,
      note: body.note,
      operator: body.operator,
      modifiedSuggestion: body.modifiedSuggestion ?? null,
    });
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "写入失败" },
      { status: 500 }
    );
  }
}
