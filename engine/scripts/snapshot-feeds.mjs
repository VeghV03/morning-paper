#!/usr/bin/env node

/**
 * snapshot-feeds.mjs
 *
 * Lementi a hírforrások RSS-ét NYERS bájtként, hash-sel és időbélyeggel.
 *
 *   node scripts/snapshot-feeds.mjs           # mentés + jelentés
 *   node scripts/snapshot-feeds.mjs --probe   # csak teszteli az URL-eket, nem ment
 *   node scripts/snapshot-feeds.mjs --only=hvg,mti-os
 *
 * Miért nyers bájt: egy átalakított (markdown/HTML→szöveg) változat NEM forrás.
 * A B réteg (lineage) csak nyers bájtból vett szövegrészre hivatkozhat.
 *
 * Miért időbélyeg: a hvg feed ~30 perc alatt teljesen kicserélődik. Ami a
 * felfedezéskor nem lett lementve, azt később már nem lehet megnézni.
 *
 * Kimenet:
 *   out/feed-snapshots/<YYYY-MM-DD>/<id>__<HHMMSS>.xml   — nyers bájt
 *   out/feed-snapshots/<YYYY-MM-DD>/<id>__<HHMMSS>.items.jsonl — kibontott tételek
 *   out/feed-snapshots/manifest.jsonl                    — minden mentés naplója
 */

import {createHash} from "node:crypto";
import {mkdirSync, writeFileSync, appendFileSync, readFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = join(ROOT, "out", "feed-snapshots");
const MANIFEST = join(BASE, "manifest.jsonl");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36";

/**
 * status: "confirmed" = 2026-08-26-án nyers bájtból ellenőrizve.
 *         "candidate"  = FELTÉTELEZETT útvonal, a script deríti ki, működik-e.
 * Több URL esetén az elsőt próbálja, ami 200-at és XML-t ad.
 */
const SOURCES = [
  {id: "telex",  org: "Telex",  status: "confirmed", kind: "rss", article_fetch: "ok", urls: ["https://telex.hu/rss"]},
  {id: "444",    org: "444",    status: "confirmed", kind: "rss", article_fetch: "ok", urls: ["https://444.hu/feed"]},
  {id: "hvg",    org: "HVG",    status: "confirmed", kind: "rss", article_fetch: "ok", urls: ["https://hvg.hu/rss"]},
  // article_fetch: enged-e a kiadó GÉPI cikktörzs-letöltést. Ez nem ízlés kérdése:
  // idézet és locator csak cikktörzsből köthető, tehát a "blocked" források a
  // hírfolyamon túl nem használhatók bizonyítékként. 2026-08-28-i mérés.
  {id: "portfolio", org: "Portfolio", status: "confirmed", kind: "rss", article_fetch: "ok",
   urls: ["https://www.portfolio.hu/rss/all.xml", "https://www.portfolio.hu/rss/gazdasag.xml"]},
  {id: "24",     org: "24.hu",  status: "confirmed", kind: "rss", article_fetch: "blocked",
   note: "HTTP 403 a cikktörzsre — csak hírfolyam-jelzésre használható, bizonyítékra nem", urls: [
    "https://24.hu/feed/",
  ]},
  // E848 (MCQ79, 2026-10-25): the daily news map counts outlets, so it needs the whole Hungarian spectrum, government-close
  // outlets too – all checked 200 with items that day. Feed signals; an article is evidence only where it can be fetched.
  {id: "index", org: "Index", status: "confirmed", kind: "rss", urls: ["https://index.hu/24ora/rss/"]},
  {id: "magyarnemzet", org: "Magyar Nemzet", status: "confirmed", kind: "rss", urls: ["https://magyarnemzet.hu/feed"]},
  {id: "mandiner", org: "Mandiner", status: "confirmed", kind: "rss", urls: ["https://mandiner.hu/rss"]},
  {id: "origo", org: "Origo", status: "confirmed", kind: "rss", urls: ["https://www.origo.hu/publicapi/hu/rss/origo/articles"]},
  {id: "nepszava", org: "Népszava", status: "confirmed", kind: "rss", urls: ["https://nepszava.hu/feed/"]},
  {id: "vg", org: "Világgazdaság", status: "confirmed", kind: "rss", urls: ["https://www.vg.hu/feed"]},
  {id: "economx", org: "Economx", status: "confirmed", kind: "rss", urls: ["https://www.economx.hu/feed"]},
  {id: "merce", org: "Mérce", status: "confirmed", kind: "rss", urls: ["https://merce.hu/feed/"]},
  {id: "atlatszo", org: "Átlátszó", status: "confirmed", kind: "rss", urls: ["https://atlatszo.hu/feed/"]},
  {id: "direkt36", org: "Direkt36", status: "confirmed", kind: "rss", urls: ["https://www.direkt36.hu/feed/"]},

  // ——— MTI ———
  // Az MTI drótja előfizetéses, RSS-e nincs. A NYILVÁNOS oldalt kérjük le HTML-ként.
  // Ez a lineage kulcsforrása: ha megvan az MTI szövege, a származást nem
  // következtetni kell, hanem ÖSSZE lehet hasonlítani.
  {id: "mti", org: "MTI", status: "confirmed", kind: "html", urls: [
    "https://mti.hu/",
  ]},

  // ——— KÜLFÖLDI / GEOPOLITIKAI ———
  // Fontos: a Reuters és az AP maga hírügynökség. Ezek CHANNEL-ek, nem
  // folyamatok: továbbítanak, nem tudnak meg. Ha egy állítást csak ügynökségek
  // hoznak, az k = 1 marad, bármennyi lap veszi is át. (D43)
  {id: "aljazeera", org: "Al Jazeera", status: "confirmed", kind: "rss", foreign: true,
   urls: ["https://www.aljazeera.com/xml/rss/all.xml"]},
  {id: "reuters", org: "Reuters", status: "confirmed", kind: "rss", foreign: true,
   role: "WIRE", channel: true, urls: ["https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best"]},
  {id: "ap", org: "AP", status: "confirmed", kind: "rss", foreign: true,
   role: "WIRE", channel: true, urls: ["https://rsshub.app/apnews/topics/world-news"]},
  {id: "politico-eu", org: "Politico Europe", status: "confirmed", kind: "rss", foreign: true,
   urls: ["https://www.politico.eu/feed/"]},
  {id: "euractiv", org: "Euractiv", status: "confirmed", kind: "rss", foreign: true,
   urls: ["https://www.euractiv.com/feed/"]},
  {id: "bbc", org: "BBC", status: "confirmed", kind: "rss", foreign: true,
   urls: ["https://feeds.bbci.co.uk/news/world/rss.xml"]},
  {id: "dw", org: "Deutsche Welle", status: "confirmed", kind: "rss", foreign: true,
   urls: ["https://rss.dw.com/rdf/rss-en-world"]},
  // E109 (2026-10-11): Guardian and Spiegel for discovery and quoting.
  {id: "guardian", org: "The Guardian", status: "candidate", kind: "rss", foreign: true,
   urls: ["https://www.theguardian.com/world/rss", "https://www.theguardian.com/international/rss"]},
  {id: "spiegel", org: "Der Spiegel", status: "candidate", kind: "rss", foreign: true,
   urls: ["https://www.spiegel.de/international/index.rss", "https://www.spiegel.de/schlagzeilen/index.rss"]},
  // E836 (MCQ77, 2026-10-25): the primary international circle and the second viewpoints beside it, all checked 200 with
  // items that day. `paywalled`: only the feed and the open part of an article are read, never around the wall; what the
  // closed part says is corroborated elsewhere or said as „A … értesülése szerint” (visual-engine-reference/src/news-desk-v1.mjs).
  {id: "nyt", org: "The New York Times", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml"]},
  {id: "lemonde", org: "Le Monde", status: "confirmed", kind: "rss", foreign: true, paywalled: true,
   urls: ["https://www.lemonde.fr/en/international/rss_full.xml", "https://www.lemonde.fr/international/rss_full.xml"]},
  {id: "france24", org: "France 24", status: "confirmed", kind: "rss", foreign: true, urls: ["https://www.france24.com/en/rss"]},
  {id: "ft", org: "Financial Times", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://www.ft.com/world?format=rss"]},
  {id: "wsj", org: "The Wall Street Journal", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://feeds.a.dj.com/rss/RSSWorldNews.xml"]},
  {id: "economist", org: "The Economist", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://www.economist.com/europe/rss.xml"]},
  {id: "lefigaro", org: "Le Figaro", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://www.lefigaro.fr/rss/figaro_international.xml"]},
  {id: "faz", org: "Frankfurter Allgemeine", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://www.faz.net/rss/aktuell/politik/ausland/"]},
  {id: "timesofisrael", org: "The Times of Israel", status: "confirmed", kind: "rss", foreign: true, urls: ["https://www.timesofisrael.com/feed/"]},
  {id: "haaretz", org: "Haaretz", status: "confirmed", kind: "rss", foreign: true, paywalled: true, urls: ["https://www.haaretz.com/srv/haaretz-latest-headlines"]},
  {id: "kyivindependent", org: "The Kyiv Independent", status: "confirmed", kind: "rss", foreign: true, urls: ["https://kyivindependent.com/news-archive/rss/"]},
  {id: "pravda-ua", org: "Ukrainska Pravda", status: "confirmed", kind: "rss", foreign: true, urls: ["https://www.pravda.com.ua/eng/rss/"]},

  // ——— ELSŐDLEGES, HIVATALOS FORRÁS ———
  // A Magyar Közlöny más kategória, mint a négy lap. Egy kihirdetett rendelet
  // nem BIZONYÍTÉK a rendeletről — az maga a rendelet. Ezért KONSTITUTÍV:
  // egyetlen ilyen forrás is elég az "established" státuszhoz (lásd D12).
  // E109: government news page (HTML; official statements, quotable as primary source).
  {id: "kormany", org: "kormany.hu", status: "candidate", kind: "html", role: "OFFICIAL_STATEMENT",
   urls: ["https://kormany.hu/hirek"]},
  {id: "kozlony", org: "Magyar Közlöny", status: "confirmed", kind: "html",
   role: "OFFICIAL_RECORD", constitutive: true, urls: [
    "https://magyarkozlony.hu/",
  ]},

  // Az uniós jog ugyanaz a kategória, mint a Közlöny: KONSTITUTÍV. Egy
  // kihirdetett rendelet nem bizonyíték a rendeletről — az maga a rendelet.
  // NEM hírfolyamként kezeljük: az eur-lex.europa.eu HTML-felülete botvédelem
  // mögött van (HTTP 202, nulla bájt), és a Hivatalos Lap napi termése több
  // száz dokumentum, amiből évente néhány kell. A felderítés ezért NEM innen
  // indul: a `scripts/eurlex.mjs` a `data/eu-dossiers.json` figyelt dossziéit
  // kérdezi, és a teljes szöveget csak arra kérjük le, amiből epizód lesz.
  {id: "eurlex", org: "Az Európai Unió Hivatalos Lapja", status: "confirmed", kind: "external",
   role: "OFFICIAL_RECORD", constitutive: true, skip_snapshot: true,
   note: "külön szkript kezeli: node scripts/eurlex.mjs — a Cellar-végponton át, nem a főoldalról",
   urls: ["http://publications.europa.eu/resource/celex/"]},
];

// A reader's own outlets: PAPER_OUTLETS names a JSON array of the same shape as SOURCES, and
// replaces it. Unset, the list above is used. `--list` prints that list.
const OUTLETS = process.env.PAPER_OUTLETS
  ? JSON.parse(readFileSync(process.env.PAPER_OUTLETS, "utf8"))
  : SOURCES;

const WIRE_MARKERS = ["MTI", "Reuters", "AP", "AFP", "Interfax", "TASZSZ", "dpa", "EFE"];

const args = process.argv.slice(2);
const PROBE_ONLY = args.includes("--probe");
const onlyArg = args.find((a) => a.startsWith("--only="));
const ONLY = onlyArg ? onlyArg.slice(7).split(",").map((s) => s.trim()) : null;

const pad = (n) => String(n).padStart(2, "0");
const stamp = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const clock = (d) => `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;

/** Egy tag tartalma, CDATA-t lehántva. */
function tag(block, name) {
  const re = new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i");
  const m = block.match(re);
  if (!m) return null;
  return m[1].replace(/^<!\[CDATA\[/, "").replace(/\]\]>$/, "").trim();
}

/** RSS <item> és Atom <entry> egyaránt. */
function splitItems(xml) {
  const rss = xml.match(/<item(?:\s[^>]*)?>[\s\S]*?<\/item>/gi) || [];
  if (rss.length) return rss;
  return xml.match(/<entry(?:\s[^>]*)?>[\s\S]*?<\/entry>/gi) || [];
}

function extractItems(xml) {
  return splitItems(xml).map((b) => ({
    guid: tag(b, "guid") ?? tag(b, "id"),
    title: tag(b, "title"),
    link: tag(b, "link"),
    pubDate: tag(b, "pubDate") ?? tag(b, "updated") ?? tag(b, "published"),
    author: tag(b, "author") ?? tag(b, "dc:creator") ?? tag(b, "creator"),
    sourceTag: tag(b, "source"),
    categories: (b.match(/<category(?:\s[^>]*)?>([\s\S]*?)<\/category>/gi) || [])
      .map((c) => c.replace(/<[^>]+>/g, "").trim())
      .filter(Boolean),
    descriptionLength: (tag(b, "description") ?? tag(b, "summary") ?? "").length,
  }));
}

/**
 * Melyik mezőben van a hírügynökségi jelölés, és milyen gyakran?
 * Ez adja meg, mennyit ér egyáltalán a feed-réteg lineage szempontból.
 */
function attributionReport(items) {
  const fields = ["author", "sourceTag"];
  const out = {};
  for (const f of fields) {
    const present = items.filter((i) => i[f]).length;
    const values = new Map();
    let wire = 0;
    for (const i of items) {
      const v = i[f];
      if (!v) continue;
      values.set(v, (values.get(v) || 0) + 1);
      if (WIRE_MARKERS.some((w) => new RegExp(`\\b${w}\\b`).test(v))) wire += 1;
    }
    const top = [...values.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    out[f] = {present, distinct: values.size, wireTagged: wire, top};
  }
  return out;
}

async function tryUrl(url) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 25000);
  try {
    const res = await fetch(url, {
      signal: ctl.signal,
      redirect: "follow",
      headers: {"user-agent": UA, accept: "application/rss+xml, application/xml, text/xml, */*"},
    });
    const buf = Buffer.from(await res.arrayBuffer());
    return {ok: res.ok, status: res.status, buf, finalUrl: res.url};
  } catch (err) {
    return {ok: false, status: 0, error: String(err?.message ?? err)};
  } finally {
    clearTimeout(timer);
  }
}

async function handle(src, dayDir, now) {
  // Külön szkript kezeli; a hírfolyam-mentés nem értelmezhető rá.
  if (src.skip_snapshot) return {id: src.id, skipped: true, note: src.note};
  for (const url of src.urls) {
    const r = await tryUrl(url);
    if (!r.ok || !r.buf?.length) continue;
    const text = r.buf.toString("utf8");
    const kind = src.kind ?? "rss";
    if (kind === "rss" && !/<(rss|feed|rdf:RDF)/i.test(text)) continue; // hibaoldal, nem feed
    if (kind === "html" && !/<html/i.test(text)) continue;

    const items = kind === "html" ? extractHtmlLinks(text, url) : extractItems(text);
    const rec = {
      id: src.id,
      org: src.org,
      declaredStatus: src.status,
      url,
      finalUrl: r.finalUrl,
      httpStatus: r.status,
      bytes: r.buf.length,
      sha256: createHash("sha256").update(r.buf).digest("hex"),
      retrievedAt: now.toISOString(),
      itemCount: items.length,
      attribution: attributionReport(items),
    };

    if (!PROBE_ONLY) {
      mkdirSync(dayDir, {recursive: true});
      const base = `${src.id}__${clock(now)}`;
      const xmlPath = join(dayDir, `${base}.xml`);
      writeFileSync(xmlPath, r.buf);                       // NYERS bájt, érintetlenül
      writeFileSync(
        join(dayDir, `${base}.items.jsonl`),
        items.map((i) => JSON.stringify(i)).join("\n") + "\n",
      );
      rec.snapshotPath = xmlPath.replace(ROOT + "/", "");
      appendFileSync(MANIFEST, JSON.stringify(rec) + "\n");
    }
    return rec;
  }
  return {
    id: src.id,
    org: src.org,
    declaredStatus: src.status,
    failed: true,
    triedUrls: src.urls,
    retrievedAt: now.toISOString(),
  };
}

/**
 * HTML-oldalról cikklinkeket és címeket szed ki. Durva, de elég ahhoz,
 * hogy legyen mit letölteni a genealógia-lépésben.
 */
function extractHtmlLinks(html, baseUrl) {
  const base = new URL(baseUrl);
  const seen = new Map();
  const re = /<a\s[^>]*href=["']([^"']+)["'][^>]*>([\s\S]{0,300}?)<\/a>/gi;
  let m;
  while ((m = re.exec(html))) {
    let href = m[1];
    const title = m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (!title || title.length < 20) continue;              // menüpont, nem cikk
    if (/^(#|mailto:|javascript:)/i.test(href)) continue;
    try { href = new URL(href, base).toString(); } catch { continue; }
    if (new URL(href).hostname !== base.hostname) continue; // külső link
    if (!seen.has(href)) {
      seen.set(href, {guid: href, title, link: href, pubDate: null,
                      author: null, sourceTag: null, categories: [],
                      descriptionLength: 0});
    }
  }
  return [...seen.values()];
}

export {tag, splitItems, extractItems, extractHtmlLinks, attributionReport, WIRE_MARKERS};

// A futtatható rész csak közvetlen hívásra indul, hogy a fenti tiszta
// függvények importálhatók és tesztelhetők legyenek.
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {

const now = new Date();
const dayDir = join(BASE, stamp(now));
if (!PROBE_ONLY) mkdirSync(BASE, {recursive: true});

if (args.includes("--list")) {
  console.log(JSON.stringify(SOURCES, null, 2));
  process.exit(0);
}
const targets = OUTLETS.filter((s) => !ONLY || ONLY.includes(s.id));
const results = [];
for (const src of targets) results.push(await handle(src, dayDir, now));

// ——— jelentés ———
console.log(`\nfeed snapshot — ${now.toISOString()}${PROBE_ONLY ? "  [PROBE, nem ment]" : ""}`);
console.log("─".repeat(96));
console.log(
  "forrás".padEnd(10) + "állapot".padEnd(12) + "tételek".padStart(8) +
  "  bájt".padStart(10) + "   hírügynökségi jelölés",
);
console.log("─".repeat(96));

for (const r of results) {
  if (r.skipped) {
    console.log(`${r.id.padEnd(10)}${"KÜLÖN".padEnd(12)}${"—".padStart(8)}${"—".padStart(10)}   ${r.note ?? "külön szkript kezeli"}`);
    continue;
  }
  if (r.failed) {
    console.log(`${r.id.padEnd(10)}${"NEM ÉL".padEnd(12)}${"—".padStart(8)}${"—".padStart(10)}   próbált: ${r.triedUrls.join(" , ")}`);
    continue;
  }
  const a = r.attribution.author;
  const s = r.attribution.sourceTag;
  const best = a.wireTagged >= s.wireTagged ? {f: "author", ...a} : {f: "source", ...s};
  const pct = r.itemCount ? Math.round((best.wireTagged / r.itemCount) * 100) : 0;
  const note = best.wireTagged
    ? `<${best.f}> — ${best.wireTagged}/${r.itemCount} (${pct}%)`
    : "NINCS — a feed-réteg vak";
  console.log(
    r.id.padEnd(10) + "ÉL".padEnd(12) +
    String(r.itemCount).padStart(8) + String(r.bytes).padStart(10) + `   ${note}`,
  );
}

console.log("─".repeat(96));
for (const r of results) {
  if (r.failed || r.skipped) continue;
  const top = r.attribution.author.top;
  if (!top.length) continue;
  console.log(`\n  ${r.id} — leggyakoribb <author> értékek:`);
  for (const [v, c] of top) console.log(`      ${String(c).padStart(4)}x  ${v}`);
}

const live = results.filter((r) => !r.failed && !r.skipped);
const dead = results.filter((r) => r.failed);
const skipped = results.filter((r) => r.skipped);
console.log(`\n  ${live.length} él, ${dead.length} nem.`);
if (dead.length) {
  console.log(`  Nem élő: ${dead.map((d) => d.id).join(", ")} — az URL-jeik feltételezettek voltak.`);
  console.log("  Ha böngészőből működik valamelyik, írd be a helyes URL-t a SOURCES tömbbe.");
}
if (!PROBE_ONLY) console.log(`  Mentve: ${dayDir.replace(ROOT + "/", "")}\n`);
else console.log("");

}
