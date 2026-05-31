/** 试点管家列表（v0.2.2 收件箱过滤） */

export interface PilotHousekeeper {
  id: string;
  name: string;
}

export function loadPilotHousekeepers(): PilotHousekeeper[] {
  const raw = process.env.CONSOLE_PILOT_MAP?.trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const id = String((item as { id?: string }).id ?? "").trim();
        const name = String((item as { name?: string }).name ?? "").trim();
        if (!id) return null;
        return { id, name: name || id };
      })
      .filter((x): x is PilotHousekeeper => x !== null);
  } catch {
    return [];
  }
}

export function housekeeperName(
  pilots: PilotHousekeeper[],
  housekeeperId: string
): string {
  if (!housekeeperId) return "—";
  const hit = pilots.find((p) => p.id === housekeeperId);
  return hit?.name ?? housekeeperId;
}
