#!/usr/bin/env node
// Cikkszöveg-letöltő. (D66)
//   node scripts/fetch-article.mjs <url> [<url> ...] [--outdir DIR]
//
// A snapshot-feeds RSS-t hoz: címet és leadet. Az idézethez és a locatorhoz
// cikktörzs kell. Eddig ez kézzel ment, epizódonként — ez volt a napi több
// videó valódi szűk keresztmetszete, nem az értelmezés.
//
// Ugyanaz a fegyelem, mint a feed-pillanatképnél: a NYERS bájt a forrás, a
// kibontott szöveg származtatás. Ami nem a nyers bájtból jön, az nem forrás.
//
// A bekezdések SZÁMOZVA vannak. Ez a lényeg: a locator többé nem kézzel írt
// próza („cikk / a szerződésösszegek bekezdése"), hanem gépi hivatkozás
// („12. bekezdés"), amit a verify-excerpts.mjs vissza tud ellenőrizni.
import { createHash } from "node:crypto";
import { TextDecoder } from "node:util";
import { mkdirSync, writeFileSync, appendFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

// --- entitások ------------------------------------------------------------
const NAMED = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
  hellip: "…", mdash: "—", ndash: "–", laquo: "«", raquo: "»", bdquo: "„", ldquo: "“",
  rdquo: "”", sbquo: "‚", lsquo: "‘", rsquo: "’", eacute: "é", aacute: "á", oacute: "ó",
  uacute: "ú", iacute: "í", ouml: "ö", uuml: "ü", Ouml: "Ö", Uuml: "Ü", szlig: "ß",
  euro: "€", deg: "°", middot: "·", bull: "•", shy: "" };
export function decodeEntities(s) {
  return String(s)
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&([a-zA-Z]+);/g, (m, n) => (n in NAMED ? NAMED[n] : m));
}

// --- kibontás -------------------------------------------------------------
// Zaj, ami minden magyar hírportálon <p>-ben ül, de nem a cikk.
const BOILERPLATE = [
  /^(hirdetés|ajánló|kapcsolódó|címlapfotó|fotó:|forrás:|borítókép)/i,
  /süti|cookie|feliratkoz|hírlevél|kövess (minket|bennünket)|iratkozz/i,
  /^\s*(©|copyright)/i,
  /minden jog fenntartva/i,
  /támogasd a|támogatói program|előfizet/i,
];
const tagText = (html) => decodeEntities(html.replace(/<[^>]*>/g, " "))
  .replace(/\s+/g, " ").trim();

export function extractArticle(html) {
  // A nem-tartalmi elemeket bájtszinten kivágjuk, mielőtt bármit keresnénk.
  const clean = String(html)
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(script|style|noscript|svg|iframe|form|figure)\b[\s\S]*?<\/\1>/gi, " ");

  const meta = (prop) => {
    const re = new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]*content=["']([^"']*)["']`, "i");
    const re2 = new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]*(?:property|name)=["']${prop}["']`, "i");
    return decodeEntities((clean.match(re) ?? clean.match(re2))?.[1] ?? "") || null;
  };

  const blocks = [];
  for (const m of clean.matchAll(/<(p|h2|h3|blockquote)\b[^>]*>([\s\S]*?)<\/\1>/gi)) {
    const text = tagText(m[2]);
    if (!text) continue;
    blocks.push({ tag: m[1].toLowerCase(), text, at: m.index });
  }

  // A cikktörzset CSAK a <p> horgonyozza. A HVG ajánlósávja huszonhárom <h3>-ból
  // áll: darabszámra megverte a hétbekezdéses cikket, és a kibontó a menüt hozta
  // vissza cikk gyanánt. A futamokat ezért nem darabszám, hanem a <p>-k
  // KARAKTERTÖMEGE alapján rangsoroljuk — a címsor csak akkor kerül be, ha a
  // nyertes futam két szélső bekezdése közé esik.
  const ok = (b) => b.text.length >= 40 && !BOILERPLATE.some((r) => r.test(b.text));
  const anchors = blocks.filter((b) => b.tag === "p" && ok(b));
  let best = [], run = [];
  const mass = (r) => r.reduce((s, b) => s + b.text.length, 0);
  for (const a of anchors) {
    if (!run.length) { run = [a]; continue; }
    if (a.at - run[run.length - 1].at < 6000) run.push(a);
    else { if (mass(run) > mass(best)) best = run; run = [a]; }
  }
  if (mass(run) > mass(best)) best = run;

  const from = best[0]?.at ?? 0, to = best[best.length - 1]?.at ?? 0;
  const body = blocks
    .filter((b) => b.at >= from && b.at <= to && ok(b) && (b.tag === "p" || b.tag !== "p"))
    .filter((b) => b.tag === "p" || b.text.length >= 20);
  const paragraphs = body.map((b, i) => ({ n: i + 1, tag: b.tag, text: b.text }));

  // A statisztikai forrás a számot TÁBLÁZATBA teszi, nem bekezdésbe. A KSH
  // gyorstájékoztatójából a bekezdések csak a százalékos változást hozták — a
  // szintadat (5 785,9 milliárd Ft) a táblázatban ült, és így hivatkozhatatlan
  // maradt volna. A táblázat külön sáv: sor- és cellaszinten hivatkozható.
  const tables = [];
  for (const t of clean.matchAll(/<table\b[^>]*>([\s\S]*?)<\/table>/gi)) {
    const rows = [];
    for (const r of t[1].matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)) {
      const cells = [...r[1].matchAll(/<t[dh]\b[^>]*>([\s\S]*?)<\/t[dh]>/gi)]
        .map((c) => tagText(c[1])).filter((x) => x !== "");
      if (cells.length) rows.push({ r: rows.length + 1, cells });
    }
    if (rows.length >= 2) tables.push({ t: tables.length + 1, rows });
  }

  return {
    title: meta("og:title") ?? (decodeEntities(clean.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? "").trim() || null),
    published: meta("article:published_time") ?? meta("datePublished")
      ?? clean.match(/<time[^>]+datetime=["']([^"']+)["']/i)?.[1] ?? null,
    publisher: meta("og:site_name") ?? null,
    paragraphs, tables,
    word_count: paragraphs.reduce((s, p) => s + p.text.split(/\s+/).length, 0),
  };
}

// A magyar oldalak egy része máig ISO-8859-2. UTF-8-ként olvasva az ékezetes
// betűk elromlanak — és az idézet-visszaellenőrzés némán hamisan bukna.
export function detectCharset(buf, contentType) {
  const head = buf.subarray(0, 4096).toString("latin1");
  const m = head.match(/<meta[^>]+charset=["']?\s*([\w-]+)/i)
    ?? head.match(/content=["'][^"']*charset=\s*([\w-]+)/i)
    ?? String(contentType ?? "").match(/charset=\s*([\w-]+)/i);
  const cs = (m?.[1] ?? "utf-8").toLowerCase();
  return cs === "iso-8859-1" ? "windows-1252" : cs;
}

// --- letöltés -------------------------------------------------------------
const slugOf = (u) => { const x = new URL(u);
  return (x.hostname.replace(/^www\./, "") + x.pathname).replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").slice(0, 90); };

export async function fetchArticle(url, outdir) {
  const res = await fetch(url, { headers: { "User-Agent": UA, "Accept": "text/html" }, redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP_${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  const sha256 = createHash("sha256").update(buf).digest("hex");
  const now = new Date();
  const day = now.toISOString().slice(0, 10);
  const stamp = now.toISOString().slice(11, 19).replace(/:/g, "");
  const dir = join(outdir, day);
  mkdirSync(dir, { recursive: true });
  const base = `${slugOf(url)}__${stamp}`;
  writeFileSync(join(dir, `${base}.html`), buf);           // NYERS bájt — ez a forrás

  const charset = detectCharset(buf, res.headers.get("content-type"));
  let text;
  try { text = new TextDecoder(charset).decode(buf); }
  catch { text = buf.toString("utf8"); }
  const art = extractArticle(text);
  const derived = { url, final_url: res.url, fetched_at: now.toISOString(), sha256,
    byte_length: buf.length, charset, raw_file: join(day, `${base}.html`), ...art };
  writeFileSync(join(dir, `${base}.paragraphs.json`), JSON.stringify(derived, null, 2) + "\n");
  appendFileSync(join(outdir, "manifest.jsonl"),
    JSON.stringify({ fetched_at: derived.fetched_at, url, sha256, bytes: buf.length,
      paragraphs: art.paragraphs.length, words: art.word_count, file: derived.raw_file }) + "\n");
  return derived;
}

async function main() {
  const args = process.argv.slice(2);
  const oi = args.indexOf("--outdir");
  const outdir = oi > -1 ? args[oi + 1] : join(ROOT, "out", "article-snapshots");
  const urls = args.filter((a, i) => a.startsWith("http") && !(oi > -1 && i === oi + 1));
  if (!urls.length) { console.error("használat: node scripts/fetch-article.mjs <url> [<url> ...] [--outdir DIR]"); process.exit(2); }
  mkdirSync(outdir, { recursive: true });
  let hiba = 0;
  for (const u of urls) {
    try {
      const d = await fetchArticle(u, outdir);
      const tsor = (d.tables ?? []).reduce((n, t) => n + t.rows.length, 0);
      console.log(`${d.paragraphs.length.toString().padStart(3)} bekezdés · ${String(d.word_count).padStart(5)} szó · ${String(tsor).padStart(3)} táblázatsor · ${d.sha256.slice(0, 12)} · ${d.title ?? "(nincs cím)"}`);
      const pk = d.paragraphs.filter((x) => x.tag === "p").length;
      if (pk < 3) console.warn(`   FIGYELEM: csak ${pk} valódi bekezdés — lehet, hogy fizetőfal vagy JS-ből épülő oldal. A nyers bájt megvan: ${d.raw_file}`);
    } catch (e) { hiba++; console.error(`HIBA  ${u}  ${e.message}`); }
  }
  process.exit(hiba ? 1 : 0);
}
if (import.meta.url === `file://${process.argv[1]}`) await main();
