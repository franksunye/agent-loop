"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
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
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  if (pilots.length === 0) return null;

  // URL 优先；无 query 时用服务端传入的 cookie 值
  const selected = searchParams.get("hk") ?? currentId ?? "";

  function persistCookie(value: string) {
    if (value) {
      document.cookie = `${COOKIE}=${encodeURIComponent(value)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    } else {
      document.cookie = `${COOKIE}=; path=/; max-age=0; SameSite=Lax`;
    }
  }

  function onChange(value: string) {
    persistCookie(value);
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set("hk", value);
    else params.delete("hk");
    const qs = params.toString();
    const href = qs ? `${pathname}?${qs}` : pathname;
    startTransition(() => {
      router.replace(href);
    });
  }

  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="hk-filter" className="text-muted-foreground text-xs shrink-0">
        管家收件箱
      </Label>
      <select
        id="hk-filter"
        className="border-input bg-background h-8 rounded-md border px-2 text-sm"
        value={selected}
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
