const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const resources = path.join(root, "resources");
const outputDir = path.join(root, "build");

const html = fs.readFileSync(path.join(resources, "sergeant-command-center-v2.html"), "utf8");
const css = fs.readFileSync(path.join(resources, "sergeant-command-center-v2.css"), "utf8");
const responsiveCss = fs.readFileSync(path.join(resources, "sergeant-command-center-v2-responsive.css"), "utf8");
const script = fs.readFileSync(path.join(resources, "sergeant-command-center-v2.js"), "utf8");

const preview = html
  .replace("/* SERGEANT_CSS */", css)
  .replace("/* SERGEANT_RESPONSIVE_CSS */", responsiveCss)
  .replace("// SERGEANT_JS", script)
  .replace("<!-- SERGEANT_HOST_BOOTSTRAP -->", "");

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(path.join(outputDir, "command-center-preview.html"), preview, "utf8");
console.log("Built build/command-center-preview.html");
