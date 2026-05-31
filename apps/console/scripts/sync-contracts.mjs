import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, "../../../contracts");
const dst = path.join(here, "../.contracts");

if (!fs.existsSync(src)) {
  console.error("[sync-contracts] missing:", src);
  process.exit(1);
}

fs.rmSync(dst, { recursive: true, force: true });
fs.cpSync(src, dst, { recursive: true });
console.log("[sync-contracts] copied contracts → apps/console/.contracts");
