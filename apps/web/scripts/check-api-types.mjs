import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webDirectory = resolve(scriptDirectory, "..");
const contractPath = resolve(webDirectory, "../api/openapi.json");
const generatedPath = resolve(webDirectory, "lib/generated/core-api.ts");
const temporaryDirectory = mkdtempSync(join(tmpdir(), "sensemu-openapi-"));
const temporaryOutput = join(temporaryDirectory, "core-api.ts");
const executable = resolve(
  webDirectory,
  `node_modules/.bin/openapi-typescript${process.platform === "win32" ? ".cmd" : ""}`,
);

try {
  execFileSync(executable, [contractPath, "-o", temporaryOutput], { stdio: "ignore" });
  const generated = readFileSync(temporaryOutput);
  const committed = readFileSync(generatedPath);
  if (!generated.equals(committed)) {
    console.error("Core API generated types are out of date. Run `npm run api:types`.");
    process.exitCode = 1;
  }
} finally {
  rmSync(temporaryDirectory, { force: true, recursive: true });
}
