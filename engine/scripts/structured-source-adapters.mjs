#!/usr/bin/env node

import {createHash} from "node:crypto";
import {existsSync, mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {basename, dirname, extname, join, resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {decodeEntities} from "./fetch-article.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const clean = (s) => String(s ?? "").replace(/\s+/g, " ").trim();
const slug = (s) => clean(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase().slice(0, 100);

export function parseDelimited(text, delimiter = null) {
  const sample = String(text).split(/\r?\n/).slice(0, 5);
  const choices = [",", ";", "\t"];
  const delim = delimiter ?? choices.map((d) => ({d, n: sample.reduce((n, x) => n + x.split(d).length - 1, 0)}))
    .sort((a, b) => b.n - a.n)[0].d;
  const rows = []; let row = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === delim && !quoted) { row.push(cell); cell = ""; }
    else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some((x) => x !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return {delimiter: delim, rows};
}

const valueType = (values) => {
  const present = values.map(clean).filter(Boolean);
  if (!present.length) return "empty";
  if (present.every((v) => /^[-+]?\d+(?:[.,]\d+)?$/.test(v.replace(/\s/g, "")))) return "number";
  if (present.every((v) => /^\d{4}-\d{2}-\d{2}/.test(v))) return "date";
  return "string";
};

export function inspectTable(rows, options = {}) {
  if (!rows.length) throw new Error("A tábla üres.");
  const header = rows[0].map((x, i) => clean(x) || `column_${i + 1}`);
  if (new Set(header).size !== header.length) throw new Error("A tábla oszlopnevei nem egyediek.");
  const widthErrors = [];
  const records = rows.slice(1).map((cells, index) => {
    if (cells.length !== header.length) widthErrors.push({row: index + 2, expected: header.length, actual: cells.length});
    const values = Object.fromEntries(header.map((h, i) => [h, clean(cells[i])]));
    const row_id = sha256(Buffer.from(JSON.stringify(values))).slice(0, 16);
    return {row: index + 2, row_id, values};
  });
  const keys = options.keys ?? [];
  const seen = new Map(), duplicateKeys = [];
  for (const r of records) if (keys.length) {
    const k = keys.map((x) => r.values[x] ?? "").join("\u001f");
    if (seen.has(k)) duplicateKeys.push({key: k, rows: [seen.get(k), r.row]}); else seen.set(k, r.row);
  }
  const columns = header.map((name) => {
    const values = records.map((r) => r.values[name]);
    return {name, type: valueType(values), missing: values.filter((v) => v === "").length,
      unique: new Set(values.filter(Boolean)).size};
  });
  return {row_count: records.length, column_count: header.length, columns, key_columns: keys,
    duplicate_keys: duplicateKeys, width_errors: widthErrors, records};
}

export function adaptNjtHtml(html, url, meta = {}) {
  const raw = String(html);
  const title = clean(decodeEntities(raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? meta.title ?? ""));
  const body = decodeEntities(raw
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(script|style|nav|header|footer|svg)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<\/p>|<\/div>|<\/li>|<\/h\d>/gi, "\n")
    .replace(/<[^>]+>/g, " "))
    .split("\n").map(clean).filter((x) => x.length > 2);
  const sections = []; let current = {locator: "preamble", lines: []};
  for (const line of body) {
    const m = /^(\d+[A-Z]?\.)\s*§\s*(.*)$/u.exec(line);
    if (m) { if (current.lines.length) sections.push({...current, text: current.lines.join(" ")}); current = {locator: `${m[1]} §`, lines: [m[2]]}; }
    else current.lines.push(line);
  }
  if (current.lines.length) sections.push({...current, text: current.lines.join(" ")});
  return {schema_version: "1.0", adapter: "NJT_ELI_HTML", source_url: url, title,
    retrieved_at: new Date().toISOString(), sections: sections.map(({lines, ...x}) => x), metadata: meta};
}

// EUR-Lex / Cellar — hiteles magyar jogszabályszöveg. (D82)
//
// MIÉRT KÜLÖN ADAPTER, ÉS MIÉRT NEM AZ NJT-É.
// Az uniós jog ugyanaz a kategória, mint a Magyar Közlöny: KONSTITUTÍV.
// Egy kihirdetett rendelet nem bizonyíték a rendeletről — az maga a rendelet.
// A szerkezete viszont más: a magyar jog „N. §"-ra tagol, az uniós „N. cikk"-re,
// és a preambulumbekezdés külön műfaj, amire hivatkozni szoktak.
//
// A TAGOLÁST NEM SZÖVEGBŐL TALÁLGATJUK. A Cellar XHTML-je ELI-azonosítót visel
// minden egységen (`class="eli-subdivision" id="art_50"`). Ez azért számít,
// mert a törzsszövegben több száz „N. cikk" alakú HIVATKOZÁS van más
// jogszabályokra — szövegilleszkedéssel minden hivatkozás önálló locatornak
// látszana, és a locator rossz helyre mutatna.
const ELI_PREFIX = {
  art: (n) => `${n}. cikk`,
  rct: (n) => `(${n}) preambulumbekezdés`,
  cit: (n) => `${n}. bevezető hivatkozás`,
  anx: (n) => `${n}. melléklet`,
};

// A Cellar szövege tele van nem törő szóközzel (az AI Acten 9628 darab).
// A nyers bájt megmarad és hasholódik; a SZÁRMAZTATOTT szövegben viszont
// normalizáljuk, különben a szó szerint kimásolt idézet azért bukna meg a
// visszakeresésen, mert a szóköz nem ugyanaz a karakter.
const nbsp = (t) => String(t).replace(/\u00a0/g, " ").replace(/\u2011/g, "-");

export function adaptEurLexAct(xhtml, url, meta = {}) {
  const raw = nbsp(String(xhtml));
  const strip = (h) => clean(decodeEntities(String(h)
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<\/(p|div|h\d|li)>/gi, "\n")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<[^>]+>/g, " ")));

  // A cím TÖBB `oj-doc-ti` bekezdésből áll: jogszabályszám, dátum, tárgy. A
  // <title> elem nem használható — az a fájlnév (L_202401689HU.000101.fmx.xml).
  const title = [...raw.matchAll(/<p class="oj-doc-ti"[^>]*>([\s\S]*?)<\/p>/gi)]
    .map((m) => strip(m[1])).filter(Boolean).join(" ") || clean(meta.title ?? "");

  // Minden ELI-egység kezdete, a saját azonosítójával.
  const marks = [...raw.matchAll(/<div[^>]*class="eli-subdivision"\s+id="([a-z]+)_(\d+)"[^>]*>/gi)]
    .map((m) => ({ kind: m[1].toLowerCase(), num: m[2], tagAt: m.index, bodyAt: m.index + m[0].length }));

  // A szakasz a SAJÁT div-je végéig tart, nem a következő ELI-egység kezdetéig.
  // A kettő nem ugyanaz: a cikkek között fejezet- és szakaszcímek állnak, amik
  // nem ELI-egységek. A „következő egységig" szeletelés emiatt az 50. cikk
  // szövegéhez ragasztotta az „V. FEJEZET ÁLTALÁNOS CÉLÚ MI-MODELLEK" címet és
  // egy nyitó tag töredékét. A locator ilyenkor többet állít, mint amit a
  // dokumentum azon a helyen mond — pont az a hiba, amit a locator-kapu keres.
  const DIV = /<div\b[^>]*>|<\/div\s*>/gi;
  const zaroDiv = (from) => {
    DIV.lastIndex = from;
    let melyseg = 0, m;
    while ((m = DIV.exec(raw))) {
      melyseg += m[0][1] === "/" ? -1 : 1;
      if (melyseg === 0) return m.index;
    }
    return raw.length;
  };

  const sections = [];
  for (const { kind, num, tagAt, bodyAt } of marks) {
    const mk = ELI_PREFIX[kind];
    if (!mk) continue;                       // pbl/enc/fnp: konténer, nem locator
    const text = strip(raw.slice(bodyAt, zaroDiv(tagAt))).replace(/\s*\n\s*/g, " ").trim();
    if (text.length > 2) sections.push({ locator: mk(num), eli_id: `${kind}_${num}`, text });
  }

  return {
    schema_version: "1.0", adapter: "EURLEX_CELLAR_XHTML", constitutive: true,
    source_url: url, celex: meta.celex ?? null, language: "HUN",
    title, retrieved_at: new Date().toISOString(),
    counts: {
      cikk: sections.filter((x) => x.eli_id.startsWith("art_")).length,
      preambulumbekezdes: sections.filter((x) => x.eli_id.startsWith("rct_")).length,
    },
    sections, metadata: meta,
  };
}

export function adaptKozlonyAct(act, issuePdfPath) {
  if (!act.number || !act.issue) throw new Error("A közlönyrekordból hiányzik a jogszabályszám vagy lapszám.");
  const pdf = readFileSync(issuePdfPath);
  return {schema_version: "1.0", adapter: "MAGYAR_KOZLONY_ACT", constitutive: true,
    act_number: act.number, act_type: act.actType, issuer: act.issuer, title: act.title,
    issue: act.issue, issue_date: act.issueDate, effective_date: act.effectiveDate ?? null,
    locator: `Magyar Közlöny ${act.issue} · nyomtatott oldal ${act.page ?? "—"}`,
    full_document: {file: issuePdfPath.replace(ROOT + "/", ""), sha256: sha256(pdf), bytes: pdf.length},
    claims: act.claims ?? [], signatures: act.signatures ?? [], references: act.references ?? []};
}

async function fetchBuffer(url) {
  const res = await fetch(url, {redirect: "follow", headers: {"user-agent": "morning-paper"}});
  const buf = Buffer.from(await res.arrayBuffer());
  if (!res.ok) throw new Error(`HTTP_${res.status} ${url}`);
  return {buf, finalUrl: res.url, contentType: res.headers.get("content-type")};
}

async function fetchFirst(urls) {
  let last;
  for (const url of urls) try { return {...await fetchBuffer(url), requestedUrl: url}; }
  catch (error) { last = error; }
  throw last;
}

async function main() {
  const args = process.argv.slice(2), mode = args.shift();
  const value = (name) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : null; };
  const outdir = resolve(value("outdir") ?? join(ROOT, "out", "structured-sources"));
  mkdirSync(outdir, {recursive: true});

  if (mode === "table") {
    const file = resolve(args.find((a) => !a.startsWith("--")) ?? "");
    if (!existsSync(file)) throw new Error(`Hiányzó tábla: ${file}`);
    const raw = readFileSync(file), ext = extname(file).toLowerCase();
    let rows;
    if ([".csv", ".tsv"].includes(ext)) rows = parseDelimited(raw.toString("utf8"), ext === ".tsv" ? "\t" : null).rows;
    else if (ext === ".json") {
      const parsed = JSON.parse(raw); const list = Array.isArray(parsed) ? parsed : parsed.data;
      if (!Array.isArray(list) || !list.length) throw new Error("A JSON-tábla nem rekordtömb.");
      const cols = [...new Set(list.flatMap(Object.keys))]; rows = [cols, ...list.map((r) => cols.map((c) => r[c] ?? ""))];
    } else throw new Error("Támogatott általános formátum: CSV, TSV, JSON.");
    const report = inspectTable(rows, {keys: clean(value("key")).split(",").filter(Boolean)});
    const manifest = {schema_version: "1.0", adapter: "GENERIC_DATA_TABLE", source_file: file,
      source_sha256: sha256(raw), bytes: raw.length, generated_at: new Date().toISOString(), ...report};
    const out = join(outdir, `${basename(file, ext)}.table.json`); writeFileSync(out, JSON.stringify(manifest, null, 2) + "\n");
    console.log(`Tábla: ${report.row_count} sor × ${report.column_count} oszlop · ${out}`);
    if (report.width_errors.length || report.duplicate_keys.length) process.exitCode = 1;
    return;
  }

  if (mode === "njt") {
    const url = args.find((a) => a.startsWith("http")); if (!url) throw new Error("NJT ELI URL szükséges.");
    const got = await fetchBuffer(url), base = `njt-${slug(got.finalUrl)}`;
    const rawFile = join(outdir, `${base}.html`); writeFileSync(rawFile, got.buf);
    const record = adaptNjtHtml(got.buf.toString("utf8"), got.finalUrl, {requested_url: url});
    record.full_document = {file: rawFile.replace(ROOT + "/", ""), sha256: sha256(got.buf), bytes: got.buf.length};
    const out = join(outdir, `${base}.json`); writeFileSync(out, JSON.stringify(record, null, 2) + "\n");
    console.log(`NJT: ${record.sections.length} locator · ${out}`); return;
  }

  if (mode === "ksh") {
    const id = value("dataset"), resource = value("resource");
    if (!id || !resource) throw new Error("KSH mód: --dataset <id> --resource <id> szükséges.");
    const base = `https://data.ksh.hu/datasets/${encodeURIComponent(id)}`;
    const [data, schema, metadata] = await Promise.all([
      fetchBuffer(`${base}/data/${encodeURIComponent(resource)}.csv`),
      fetchFirst([`${base}/schema/${encodeURIComponent(resource)}.json`, `${base}/schema/${encodeURIComponent(resource)}.xml`]),
      fetchBuffer(`${base}/metadata.rdf`),
    ]);
    const dir = join(outdir, `ksh-${slug(id)}-${slug(resource)}`); mkdirSync(dir, {recursive: true});
    const schemaExt = schema.requestedUrl.endsWith(".xml") ? "xml" : "json";
    writeFileSync(join(dir, "data.csv"), data.buf); writeFileSync(join(dir, `schema.${schemaExt}`), schema.buf); writeFileSync(join(dir, "metadata.rdf"), metadata.buf);
    const parsed = parseDelimited(data.buf.toString("utf8"));
    const report = inspectTable(parsed.rows, {keys: clean(value("key")).split(",").filter(Boolean)});
    const manifest = {schema_version: "1.0", adapter: "KSH_HIGH_VALUE_DATASET", dataset_id: id, resource_id: resource,
      source_url: `${base}/data/${resource}.csv`, retrieved_at: new Date().toISOString(),
      full_retention: {
        data: {file: join(dir, "data.csv").replace(ROOT + "/", ""), sha256: sha256(data.buf), bytes: data.buf.length},
        schema: {file: join(dir, `schema.${schemaExt}`).replace(ROOT + "/", ""), sha256: sha256(schema.buf), bytes: schema.buf.length, format: schemaExt},
        metadata: {file: join(dir, "metadata.rdf").replace(ROOT + "/", ""), sha256: sha256(metadata.buf), bytes: metadata.buf.length},
      }, ...report};
    writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
    console.log(`KSH: ${report.row_count} sor × ${report.column_count} oszlop · ${dir}`);
    if (report.width_errors.length || report.duplicate_keys.length) process.exitCode = 1;
    return;
  }

  if (mode === "kozlony") {
    const actFile = resolve(value("act") ?? ""), pdf = resolve(value("pdf") ?? "");
    if (!existsSync(actFile) || !existsSync(pdf)) throw new Error("Közlöny mód: --act <json> --pdf <lapszám.pdf> szükséges.");
    const record = adaptKozlonyAct(JSON.parse(readFileSync(actFile, "utf8")), pdf);
    const out = join(outdir, `${slug(record.act_number)}.kozlony.json`); writeFileSync(out, JSON.stringify(record, null, 2) + "\n");
    console.log(`Közlöny: ${record.act_number} · ${out}`); return;
  }

  console.error("használat: structured-source-adapters.mjs <table|njt|ksh|kozlony> ..."); process.exit(2);
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
