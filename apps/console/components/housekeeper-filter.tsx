"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Label } from "@/components/ui/label";
import type { PilotHousekeeper } from "@/lib/pilot-housekeepers";

const COOKIE = "aol_hk_filter";

export function HousekeeperFilter({
  pilots,
  currentId,
}: {
  pilots: PilotHousekeeper[];
  currentId?: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  if (pilots.length === 0) return null;

  function onChange(value: string) {
    document.cookie = `${COOKIE}=${encodeURIComponent(value)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="hk-filter" className="text-muted-foreground text-xs shrink-0">
        管家收件箱
      </Label>
      <select
        id="hk-filter"
        className="border-input bg-background h-8 rounded-md border px-2 text-sm"
        defaultValue={currentId ?? ""}
        disabled={pending}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">全部试点</option>
        {pilots.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export { COOKIE as HOUSEKEEPER_FILTER_COOKIE };
