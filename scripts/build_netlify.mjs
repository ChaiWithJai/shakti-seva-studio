import { cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const source = resolve(root, "static");
const destination = resolve(root, "dist");
const assets = resolve(destination, "assets");

await rm(destination, { recursive: true, force: true });
await mkdir(assets, { recursive: true });
await cp(resolve(source, "index.html"), resolve(destination, "index.html"));
await cp(resolve(source, "guidance.html"), resolve(destination, "guidance.html"));
for (const name of ["app.js", "styles.css", "guidance.css", "shakti-seva-mark.svg", "jai-portrait-motion.jpg", "jai-dogged-pursuits.jpg", "jai-studio.jpg"]) {
  await cp(resolve(source, name), resolve(assets, name));
}
console.log("Built the allowlisted Netlify site in dist/");
