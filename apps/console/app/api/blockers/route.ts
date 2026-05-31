import { NextResponse } from "next/server";
import { recordBlocker } from "@/lib/suggestions";
import { choiceToBlockerType } from "@/lib/blockers";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: {
    dedupeKey?: string;
    workOrderId?: string;
    choice?: string;
    note?: string;
    operator?: string;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  if (!body.dedupeKey || !body.choice) {
    return NextResponse.json(
      { error: "dedupeKey 与 choice 必填" },
      { status: 400 }
    );
  }

  const blockerType = choiceToBlockerType(body.choice);
  if (!blockerType) {
    return NextResponse.json({ error: "choice 须为 A/B/C/D" }, { status: 400 });
  }

  try {
    await recordBlocker({
      dedupeKey: body.dedupeKey,
      workOrderId: body.workOrderId ?? "",
      blockerType,
      note: body.note,
      operator: body.operator,
    });
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "写入失败" },
      { status: 500 }
    );
  }
}
