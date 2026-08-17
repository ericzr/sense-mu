const requiredMajor = 24;
const actualMajor = Number.parseInt(process.versions.node.split(".")[0] ?? "", 10);

if (actualMajor !== requiredMajor) {
  console.error(
    `SenseMu Web requires Node.js ${requiredMajor}.x. ` +
      `Found ${process.version}. Run \`nvm use\` from the repository root before continuing.`,
  );
  process.exit(1);
}
