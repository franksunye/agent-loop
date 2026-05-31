"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Check, X, Pencil } from "lucide-react";
import type { Decision, SuggestionDoc } from "@/lib/suggestions";

export function DecisionActions({
  dedupeKey,
  workOrderId,
  suggestion,
  currentDecision,
}: {
  dedupeKey: string;
  workOrderId: string;
  suggestion: SuggestionDoc;
  currentDecision?: Decision | null;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [busy, setBusy] = useState<Decision | null>(null);

  async function submit(
    decision: Decision,
    extra?: { note?: string; modifiedSuggestion?: SuggestionDoc }
  ) {
    setBusy(decision);
    try {
      const res = await fetch("/api/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dedupeKey, workOrderId, decision, ...extra }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "提交失败");
      }
      toast.success(
        decision === "approved"
          ? "已同意，建议进入执行队列"
          : decision === "rejected"
            ? "已拒绝"
            : "已保存修改"
      );
      startTransition(() => router.refresh());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "提交失败");
    } finally {
      setBusy(null);
    }
  }

  const disabled = pending || busy !== null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {currentDecision ? (
        <span className="text-muted-foreground mr-1 text-xs">
          已处置（可覆盖）：
        </span>
      ) : null}
      <Button
        size="sm"
        onClick={() => submit("approved")}
        disabled={disabled}
        className="bg-emerald-600 text-white hover:bg-emerald-700"
      >
        <Check className="h-4 w-4" /> 同意
      </Button>

      <ModifyDialog
        suggestion={suggestion}
        disabled={disabled}
        onSave={(modified, note) =>
          submit("modified", { modifiedSuggestion: modified, note })
        }
      />

      <Button
        size="sm"
        variant="outline"
        onClick={() => submit("rejected")}
        disabled={disabled}
      >
        <X className="h-4 w-4" /> 拒绝
      </Button>
    </div>
  );
}

function ModifyDialog({
  suggestion,
  disabled,
  onSave,
}: {
  suggestion: SuggestionDoc;
  disabled: boolean;
  onSave: (modified: SuggestionDoc, note: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [primary, setPrimary] = useState(suggestion.跟进方案?.主行动 ?? "");
  const [talk, setTalk] = useState(
    (suggestion.跟进方案?.沟通要点 ?? []).join("\n")
  );
  const [note, setNote] = useState("");

  function handleSave() {
    const modified: SuggestionDoc = {
      ...suggestion,
      跟进方案: {
        ...suggestion.跟进方案,
        主行动: primary.trim(),
        沟通要点: talk
          .split("\n")
          .map((t) => t.trim())
          .filter(Boolean),
      },
    };
    onSave(modified, note.trim());
    setOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" disabled={disabled} />
        }
      >
        <Pencil className="h-4 w-4" /> 修改
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>修改跟进方案</DialogTitle>
          <DialogDescription>
            调整主行动与沟通要点后保存，记为「已修改」处置。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="primary">主行动</Label>
            <Textarea
              id="primary"
              value={primary}
              onChange={(e) => setPrimary(e.target.value)}
              rows={2}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="talk">沟通要点（每行一条）</Label>
            <Textarea
              id="talk"
              value={talk}
              onChange={(e) => setTalk(e.target.value)}
              rows={4}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="note">修改说明（可选）</Label>
            <Textarea
              id="note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="为什么这样改，便于沉淀 SOP"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" size="sm" />}>
            取消
          </DialogClose>
          <Button size="sm" onClick={handleSave}>
            保存修改
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
