#!/usr/bin/env node
"use strict";

/**
 * Minimal smoke test for map.html (HANDOFF: UI outside harness scope).
 * Flow: page load → 60年実行 → year 60 → assert stats.
 *
 * Usage: node scripts/smoke_map.js [port]
 * Exit 0 = PASS, 1 = FAIL.
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const ROOT = path.resolve(__dirname, "..");
const PORT = +(process.argv[2] || 8765);
const TIMEOUT_MS = 120_000;

function mime(fp) {
  if (fp.endsWith(".html")) return "text/html; charset=utf-8";
  if (fp.endsWith(".js")) return "application/javascript; charset=utf-8";
  return "application/octet-stream";
}

function startServer() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = req.url.split("?")[0];
      const rel = url === "/" ? "/map.html" : url;
      const fp = path.join(ROOT, rel);
      if (!fp.startsWith(ROOT) || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": mime(fp) });
      fs.createReadStream(fp).pipe(res);
    });
    srv.listen(PORT, "127.0.0.1", () => resolve(srv));
  });
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ].filter(Boolean);
  return candidates;
}

async function main() {
  const srv = await startServer();
  let browser;
  for (const exe of findChrome()) {
    try {
      browser = await puppeteer.launch({
        executablePath: exe,
        headless: "new",
        args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
      });
      break;
    } catch (_) { /* try next */ }
  }
  if (!browser) {
    console.error(JSON.stringify({ status: "SKIP", reason: "Chrome not found" }));
    srv.close();
    process.exit(0);
  }

  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  try {
    await page.goto(`http://127.0.0.1:${PORT}/map.html`, {
      waitUntil: "networkidle0",
      timeout: TIMEOUT_MS,
    });

    const initErr = await page.evaluate(() => {
      const el = document.getElementById("js-err");
      const visible = window.getComputedStyle(el).display !== "none";
      return { visible, text: el.textContent.trim() };
    });
    if (initErr.visible && initErr.text) {
      throw new Error(`Init error banner: ${initErr.text}`);
    }

    // Auto-run on init (or wait for first completion)
    await page.waitForFunction(
      () => document.getElementById("vacPol").textContent !== "–",
      { timeout: TIMEOUT_MS },
    );

    const afterLoad = await page.evaluate(() => ({
      vacBase: document.getElementById("vacBase").textContent,
      vacPol: document.getElementById("vacPol").textContent,
      demoPol: document.getElementById("demoPol").textContent,
      year: document.getElementById("year").value,
      btnRun: document.getElementById("btnRun").textContent,
    }));

    // Explicit 60年実行 click
    await page.click("#btnRun");
    await page.waitForFunction(
      () => !document.getElementById("btnRun").disabled,
      { timeout: TIMEOUT_MS },
    );

    await page.evaluate(() => {
      const yr = document.getElementById("year");
      yr.value = "60";
      yr.dispatchEvent(new Event("input", { bubbles: true }));
    });

    await page.waitForFunction(
      () => document.getElementById("yearLbl").textContent === "60",
      { timeout: 5000 },
    );

    const at60 = await page.evaluate(() => ({
      yearLbl: document.getElementById("yearLbl").textContent,
      vacBase: document.getElementById("vacBase").textContent,
      vacPol: document.getElementById("vacPol").textContent,
      demoPol: document.getElementById("demoPol").textContent,
      diffN: document.getElementById("diffN").textContent,
      clu: document.getElementById("clu").textContent,
    }));

    const vacPol = parseFloat(at60.vacPol);
    const demoPol = parseFloat(at60.demoPol);
    if (Number.isNaN(vacPol)) throw new Error(`Invalid vacPol at year 60: ${at60.vacPol}`);
    if (vacPol < 0 || vacPol > 20) {
      throw new Error(`vacPol at year 60 out of expected range: ${at60.vacPol}`);
    }
    if (Number.isNaN(demoPol) || demoPol <= 0) {
      throw new Error(`demoPol at year 60 should be >0 with tax=2 sub=150: ${at60.demoPol}`);
    }
    if (+at60.diffN <= 0) {
      throw new Error("baseline and intervention maps should differ at year 60");
    }

    const report = {
      status: "PASS",
      afterLoad,
      at60,
      consoleErrors: consoleErrors.filter((e) => !/favicon|404/.test(e)),
    };
    console.log(JSON.stringify(report, null, 2));
  } catch (err) {
    console.error(JSON.stringify({
      status: "FAIL",
      error: String(err.message || err),
      consoleErrors,
    }, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
    srv.close();
  }
}

main();
