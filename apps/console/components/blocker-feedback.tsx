"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BLOCKER_CHOICES, blockerDisplay } from "@/lib/blockers";
import type { BlockerType } from "@/lib/blockers";

export function BlockerFeedbackForm({
  dedupeKey,
  workOrderId,
  currentType,
  currentNote,
}: {
  dedupeKey: string;
  workOrderId: string;
  currentType?: BlockerType | null;
  currentNote?: string | null;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [choice, setChoice] = useState<string>("");
  const [note, setNote] = useState(currentNote ?? "");

  async function submit(selectedChoice: string) {
    try {
      const res = await fetch("/api/blockers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dedupeKey,
          workOrderId,
          choice: selectedChoice,
          note: note.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "提交失败");
      }
      toast.success("阻塞信息已保存");
      startTransition(() => router.refresh());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "提交失败");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <div className="text-sm font-medium">阻塞信息</div>
        <p className="text-muted-foreground text-xs">
          当前：{blockerDisplay(currentType, currentNote)}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {BLOCKER_CHOICES.map((c) => (
          <Button
            key={c.choice}
            type="button"
            size="sm"
            variant={choice === c.choice ? "default" : "outline"}
            disabled={pending}
            onClick={() => {
              setChoice(c.choice);
              void submit(c.choice);
            }}
          >
            {c.label}
          </Button>
        ))}
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="blocker-note">一句话（可选）</Label>
        <Textarea
          id="blocker-note"
          rows={2}
          placeholder="例如：客户说报价偏高，想再对比一下"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={pending}
        />
      </div>
    </div>
  );
}
