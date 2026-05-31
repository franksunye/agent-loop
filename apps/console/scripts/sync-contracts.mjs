import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const candidates = [
  path.join(here, "../../../contracts"),
  path.join(here, "../contracts"),
  path.join(here, "../../contracts"),
];
let src = candidates.find((c) => fs.existsSync(path.join(c, "tables.json")));
if (!src) {
  console.error("[sync-contracts] missing contracts in:", candidates.join(", "));
  process.exit(1);
}

const dst = path.join(here, "../.contracts");

fs.rmSync(dst, { recursive: true, force: true });
fs.cpSync(src, dst, { recursive: true });
console.log("[sync-contracts] copied contracts → apps/console/.contracts");
