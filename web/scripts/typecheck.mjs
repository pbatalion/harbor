import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const tsconfigPath = join(root, "tsconfig.json");
const config = JSON.parse(readFileSync(tsconfigPath, "utf8"));
const include = Array.isArray(config.include) ? config.include.filter((entry) => entry !== ".next/types/**/*.ts") : [];

const tempConfigPath = join(root, "tsconfig.typecheck.tmp.json");
writeFileSync(
  tempConfigPath,
  JSON.stringify(
    {
      ...config,
      include,
    },
    null,
    2,
  ),
);

const result = spawnSync("npx", ["tsc", "--noEmit", "--project", tempConfigPath], {
  stdio: "inherit",
  cwd: root,
});

rmSync(tempConfigPath, { force: true });
process.exit(result.status ?? 1);
