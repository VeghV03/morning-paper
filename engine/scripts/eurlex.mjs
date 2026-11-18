#!/usr/bin/env node

/**
 * eurlex.mjs · uniós jog konstitutív forrásként
 *
 *   node scripts/eurlex.mjs                    # a figyelt dossziék mozgása
 *   node scripts/eurlex.mjs --read 32024R1689  # EGY jogszabály teljes magyar szövege
 *   node scripts/eurlex.mjs --read 32024R1689 --cikk 50
 *
 * KÉT MÉLYSÉG, SZÁNDÉKOSAN — ugyanaz a szerkezet, mint a kozlony.mjs-ben.
 *   Alapfutás → csak az INDEX: mi mozdult a figyelt dossziék körül. Olcsó.
 *   --read    → a TELJES hiteles magyar szöveg, de csak arra a jogszabályra,
 *               amire epizódot akarunk alapozni.
 *
 * MIÉRT NEM AZ EUR-LEX FŐOLDALÁRÓL.
 * Az eur-lex.europa.eu HTML-felülete botvédelem mögött van: gépi kérésre
 * HTTP 202-t ad NULLA bájttal, vagyis kihívást küld vissza, nem dokumentumot.
 * A Kiadóhivatal Cellar-végpontja viszont nyitva van, és ugyanazt a hiteles
 * szöveget adja — ez a helyes belépési pont, nem a főoldal.
 *
 * MIÉRT KONSTITUTÍV.
 * Egy kihirdetett uniós rendelet nem BIZONYÍTÉK a rendeletről — az maga a
 * rendelet. Ugyanaz a kategória, mint a Magyar Közlöny (D12): egyetlen ilyen
 * forrás elég az "established" státuszhoz, míg négy egymást másoló lap nem.
 *
 * MIÉRT SZÁMÍT, HOGY MAGYARUL VAN.
 * A magyar az EU egyik hivatalos nyelve, tehát minden jogi aktusnak van
 * HITELES magyar változata — nem fordítás, hanem egyenrangú szöveg. Ezért az
 * idézet-visszakeresés (verify-excerpts) rajta ugyanúgy működik, mint egy
 * magyar lap cikkén. Fordított szövegre ez nem volna igaz.
 *
 * Kimenet:
 *   out/eurlex/<CELEX>.xhtml   nyers bájt (ez a forrás)
 *   out/eurlex/<CELEX>.json    a kibontott rekord, cikkenkénti locatorral
 *   out/eurlex/watch.jsonl     a figyelés naplója, egy sor egy megtalált mű
 */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync, readFileSync, appendFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { adaptEurLexAct } from "./structured-source-adapters.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "out", "eurlex");
const WATCH_LOG = join(OUT, "watch.jsonl");
const DOSSIERS = join(ROOT, "data", "eu-dossiers.json");

const CELLAR_REST = "http://publications.europa.eu/resource/celex";
const CELLAR_SPARQL = "http://publications.europa.eu/webapi/rdf/sparql";
const UA = "morning-paper";
const HUN = "<http://publications.europa.eu/resource/authority/language/HUN>";

const args = process.argv.slice(2);
const val = (n) => {
  const i = args.indexOf(`--${n}`);
  if (i >= 0 && args[i + 1] && !args[i + 1].startsWith("--")) return args[i + 1];
  const eq = args.find((a) => a.startsWith(`--${n}=`));
  return eq ? eq.slice(n.length + 3) : null;
};
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

async function get(url, headers = {}) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 120000);
  try {
    const res = await fetch(url, { signal: ctl.signal, redirect: "follow",
      headers: { "user-agent": UA, ...headers } });
    const buf = Buffer.from(await res.arrayBuffer());
    return { ok: res.ok, status: res.status, buf, finalUrl: res.url };
  } catch (e) {
    return { ok: false, status: 0, error: String(e?.message ?? e) };
  } finally { clearTimeout(timer); }
}

async function sparql(query) {
  const body = new URLSearchParams({ query, format: "application/sparql-results+json" });
  const r = await get(`${CELLAR_SPARQL}?${body}`, { accept: "application/sparql-results+json" });
  if (!r.ok) throw new Error(`SPARQL_HIBA_${r.status}${r.error ? ` — ${r.error}` : ""}`);
  return JSON.parse(r.buf.toString("utf8")).results.bindings;
}

// ── EGY JOGSZABÁLY TELJES SZÖVEGE ──────────────────────────────────────────
export async function readAct(celex, { force = false } = {}) {
  mkdirSync(OUT, { recursive: true });
  const rawFile = join(OUT, `${celex}.xhtml`);
  const jsonFile = join(OUT, `${celex}.json`);

  let buf, url = `${CELLAR_REST}/${encodeURIComponent(celex)}`;
  if (existsSync(rawFile) && !force) {
    buf = readFileSync(rawFile);
    console.log(`  már megvan: ${rawFile} (${buf.length} bájt) — --force-szal újratölthető`);
  } else {
    // A nyelvi fejléc dönti el, melyik hiteles változat jön. Ha a magyar
    // hiányzik, NEM esünk vissza angolra: az idézet magyar szövegből kell.
    const r = await get(url, { accept: "application/xhtml+xml", "accept-language": "hun" });
    if (!r.ok) throw new Error(`CELLAR_HIBA_${r.status} — ${celex}${r.error ? ` (${r.error})` : ""}`);
    if (!r.buf?.length) throw new Error(`ÜRES_VÁLASZ — ${celex}`);
    buf = r.buf; url = r.finalUrl;
    writeFileSync(rawFile, buf);
  }

  const rec = adaptEurLexAct(buf.toString("utf8"), url, { celex });
  if (!rec.counts.cikk)
    throw new Error(`NINCS_CIKK — ${celex}: a válaszban nincs ELI-tagolás. ` +
      "Lehet, hogy ez a CELEX nem jogi aktus, vagy nincs magyar hiteles változata.");
  rec.full_document = { file: rawFile.replace(ROOT + "/", ""), sha256: sha256(buf), bytes: buf.length };
  rec.retention = { mode: "FULL" };
  writeFileSync(jsonFile, JSON.stringify(rec, null, 2) + "\n");
  return { rec, jsonFile, rawFile };
}

// ── A FIGYELT DOSSZIÉK ─────────────────────────────────────────────────────
// A hasznos jelzés nem az, hogy egy rendelet LÉTEZIK — az nem hír. Az, hogy
// megjelent valami ÚJ, ami hivatkozik rá: módosítás, végrehajtási aktus,
// bizottsági javaslat vagy jelentés. Ez a mozgás, amiből történet lehet.
export function citingQuery(celex, limit = 12) {
  return `PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?date ?title WHERE {
  ?base cdm:resource_legal_id_celex "${celex}"^^xsd:string .
  ?w cdm:work_cites_work ?base .
  ?w cdm:resource_legal_id_celex ?celex .
  ?w cdm:work_date_document ?date .
  OPTIONAL { ?e cdm:expression_belongs_to_work ?w ;
                cdm:expression_uses_language ${HUN} ;
                cdm:expression_title ?title . }
} ORDER BY DESC(?date) LIMIT ${limit}`;
}

function seenSet() {
  if (!existsSync(WATCH_LOG)) return new Set();
  return new Set(readFileSync(WATCH_LOG, "utf8").split("\n").filter(Boolean)
    .map((l) => { try { return JSON.parse(l).celex; } catch { return null; } }).filter(Boolean));
}

async function watch() {
  const cfg = JSON.parse(readFileSync(DOSSIERS, "utf8"));
  mkdirSync(OUT, { recursive: true });
  const latott = seenSet();
  const elso = latott.size === 0;
  let ujOssz = 0;

  for (const d of cfg.dossiers) {
    process.stdout.write(`\n${d.nev}  (${d.celex})\n`);
    let rows;
    try { rows = await sparql(citingQuery(d.celex)); }
    catch (e) { console.error(`  ${e.message}`); continue; }

    const uj = rows.filter((r) => !latott.has(r.celex.value));
    console.log(`  ${rows.length} hivatkozó mű · ebből új: ${uj.length}`);
    for (const r of rows.slice(0, 6)) {
      const jel = latott.has(r.celex.value) ? "  " : "→ ";
      const cim = r.title?.value ?? "(nincs magyar cím a nyilvántartásban)";
      console.log(`  ${jel}${r.celex.value.padEnd(14)} ${r.date.value}  ${cim.slice(0, 78)}`);
    }
    for (const r of uj) {
      appendFileSync(WATCH_LOG, JSON.stringify({
        dossier: d.id, celex: r.celex.value, date: r.date.value,
        title: r.title?.value ?? null, seen_at: new Date().toISOString(),
      }) + "\n");
      latott.add(r.celex.value);
    }
    ujOssz += uj.length;
  }

  console.log(elso
    ? `\nElső futás: ${ujOssz} mű felvéve a naplóba. Innentől csak a VÁLTOZÁS látszik.`
    : `\n${ujOssz} új mű a legutóbbi futás óta.`);
  if (ujOssz && !elso)
    console.log(`Teljes szöveghez:  node scripts/eurlex.mjs --read <CELEX>`);
}

// ── CLI ────────────────────────────────────────────────────────────────────
async function main() {
  const celex = val("read");
  if (celex) {
    const { rec, jsonFile, rawFile } = await readAct(celex, { force: args.includes("--force") });
    console.log(`\n${rec.title.slice(0, 120)}`);
    console.log(`\n  ${rec.counts.cikk} cikk · ${rec.counts.preambulumbekezdes} preambulumbekezdés`);
    console.log(`  nyers bájt: ${rawFile}`);
    console.log(`  sha256: ${rec.full_document.sha256.slice(0, 32)}…  (${rec.full_document.bytes} bájt)`);
    console.log(`  rekord: ${jsonFile}`);

    const cikk = val("cikk");
    if (cikk) {
      const sec = rec.sections.find((s) => s.locator === `${cikk}. cikk`);
      if (!sec) { console.error(`\nNincs ${cikk}. cikk ebben a jogszabályban.`); process.exit(1); }
      console.log(`\n── ${sec.locator} ──\n${sec.text}\n`);
    } else {
      console.log(`\n  Egy cikk szövegéhez: --cikk <szám>`);
    }
    return;
  }
  if (args.includes("--help") || args.includes("-h")) {
    console.log("használat:\n  eurlex.mjs                      a figyelt dossziék mozgása\n" +
      "  eurlex.mjs --read <CELEX>       egy jogszabály teljes magyar szövege\n" +
      "  eurlex.mjs --read <CELEX> --cikk 50\n  eurlex.mjs --read <CELEX> --force");
    return;
  }
  await watch();
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(String(e.message ?? e)); process.exit(1); });
}
