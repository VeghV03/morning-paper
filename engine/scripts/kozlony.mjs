#!/usr/bin/env node

/**
 * kozlony.mjs · Magyar Közlöny letöltése és állítás-kinyerés
 *
 *   node scripts/kozlony.mjs              # új lapszámok letöltése + feldolgozása
 *   node scripts/kozlony.mjs --limit=3
 *   node scripts/kozlony.mjs --force      # meglévőket is újra
 *   node scripts/kozlony.mjs --read=1267/2026      # EGY jogszabály teljes szövege
 *
 * KÉT MÉLYSÉG, SZÁNDÉKOSAN.
 *   Alapfutás  → csak a TARTALOMJEGYZÉK. Index: mi létezik, miről szól. Olcsó.
 *   --read     → a TELJES SZÖVEG, de csak arra a jogszabályra, amire epizódot
 *                akarunk alapozni. A már letöltött .txt-ből dolgozik, nem tölt újra.
 *
 * Az egész Közlönyt kibontani feleslegesen drága: több ezer oldal jogi szöveg,
 * amiből évente néhány tucat kell. A mélységet a szerkesztői szándék dönti el.
 *
 * MIÉRT KÜLÖN SCRIPT.
 * A Közlöny nem hírforrás. Egy kihirdetett rendelet nem BIZONYÍTÉK a rendeletről —
 * az maga a rendelet. Ezért KONSTITUTÍV: egyetlen ilyen forrás elég az "established"
 * státuszhoz, míg négy egymást másoló lap nem elég.
 *
 * MIT CSINÁL
 *   1. Lekéri a lapszámlistát a magyarkozlony.hu címlapjáról.
 *   2. Az új lapszámok PDF-jét letölti és HASH-eli.
 *   3. pdftotext -layout → szöveg.
 *   4. A tartalomjegyzékből strukturált jogszabályokat bont ki.
 *   5. A törzsszövegből kikeresi a hatálybalépés dátumát.
 *
 * Kimenet:
 *   out/kozlony/<év>/MK-<szám>.pdf        nyers bájt
 *   out/kozlony/<év>/MK-<szám>.txt        kinyert szöveg
 *   out/kozlony/acts.jsonl                a jogszabályok, egy sor egy jogszabály
 */

import {createHash} from "node:crypto";
import {execFileSync} from "node:child_process";
import {existsSync, mkdirSync, writeFileSync, readFileSync, appendFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {extractActs} from "./lib/kozlony-parser.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "out", "kozlony");
const ACTS = join(OUT, "acts.jsonl");
const LIST_URL = "https://magyarkozlony.hu/";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36";

const args = process.argv.slice(2);
const LIMIT = Number((args.find(a => a.startsWith("--limit=")) || "=8").split("=")[1]) || 8;
const FORCE = args.includes("--force");
const val = (n) => { const a = args.find(x => x.startsWith(`--${n}=`)); return a ? a.slice(n.length + 3) : null; };

const HU_MONTH = {január: "01", február: "02", március: "03", április: "04", május: "05",
  június: "06", július: "07", augusztus: "08", szeptember: "09", október: "10",
  november: "11", december: "12"};

/** A típuskódból kiadó szerv. Amit nem tudunk, azt NEM találjuk ki — marad a kód. */
const ISSUER = {
  "Korm. rendelet": "Kormány", "Korm. határozat": "Kormány",
  "MNB rendelet": "Magyar Nemzeti Bank",
  "KE határozat": "köztársasági elnök",
  "OGY határozat": "Országgyűlés",
  "AB határozat": "Alkotmánybíróság",
  "BM rendelet": "Belügyminisztérium",
  "AM rendelet": "Agrárminisztérium",
  "törvény": "Országgyűlés",
};

const clean = (s) => s.replace(/\s+/g, " ").trim();

async function get(url, binary = false) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 90000);
  try {
    const res = await fetch(url, {signal: ctl.signal, redirect: "follow",
      headers: {"user-agent": UA}});
    const buf = Buffer.from(await res.arrayBuffer());
    if (!res.ok) return {ok: false, status: res.status};
    return {ok: true, status: res.status, buf, text: binary ? null : buf.toString("utf8")};
  } catch (e) { return {ok: false, status: 0, error: String(e?.message ?? e)}; }
  finally { clearTimeout(timer); }
}

/** A címlapról: lapszám, dátum, PDF-URL. */
export function parseIssueList(html) {
  const pat = /(Magyar Közlöny\s+(\d{4})\.\s*évi\s*(\d+)\.\s*szám)([\s\S]{0,3000}?)href="([^"]*letoltes)"/g;
  const seen = new Map();
  let m;
  while ((m = pat.exec(html))) {
    const year = m[2], num = m[3], ctx = m[4], url = m[5];
    const key = `${year}/${num}`;
    const d = /(\d{4})\.\s*(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s*(\d{1,2})\./.exec(ctx);
    const iso = d ? `${d[1]}-${HU_MONTH[d[2]]}-${String(d[3]).padStart(2, "0")}` : null;
    if (!seen.has(key) || (iso && !seen.get(key).date)) {
      seen.set(key, {key, year, num, date: iso, url,
                     title: clean(m[1])});
    }
  }
  return [...seen.values()].sort((a, b) => Number(b.num) - Number(a.num));
}

function pdfToText(pdfPath, txtPath) {
  try {
    execFileSync("pdftotext", ["-layout", pdfPath, txtPath], {stdio: "pipe"});
    return readFileSync(txtPath, "utf8");
  } catch {
    try {                                            // tartalék: python
      const py = `import sys,pdfplumber\nwith pdfplumber.open(sys.argv[1]) as d:\n` +
                 ` open(sys.argv[2],'w',encoding='utf-8').write("\\n".join((p.extract_text() or "") for p in d.pages))`;
      execFileSync("python3", ["-c", py, pdfPath, txtPath], {stdio: "pipe"});
      return readFileSync(txtPath, "utf8");
    } catch { return null; }
  }
}

/** Hatálybalépés a törzsszövegből, jogszabályszám közelében. */
function findEffectiveDate(text, actNumber) {
  const shortNum = actNumber.split(" ")[0];
  const idx = text.indexOf(shortNum, text.indexOf("Tartalomjegyzék") + 500);
  if (idx < 0) return null;
  const win = text.slice(idx, idx + 6000);
  const m = /(\d{4})\.\s*(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s*(\d{1,2})[-–]?\w*\s*(?:napján)?\s*lép\s+hatályba/i.exec(win);
  if (!m) return null;
  return `${m[1]}-${HU_MONTH[m[2].toLowerCase()]}-${String(m[3]).padStart(2, "0")}`;
}


// ─────────────────────────────────────────────────────────────────────────────
// --read : EGY jogszabály teljes szövege és állításai
// ─────────────────────────────────────────────────────────────────────────────

/** Oldalláb és fejléc eltávolítása, hogy ne szakítsa meg a mondatokat. */
function dropPageFurniture(text) {
  return text
    .replace(/^\s*\d{3,5}\s+M\s*A\s*G\s*Y\s*A\s*R\s+K\s*Ö\s*Z\s*L\s*Ö\s*N\s*Y[^\n]*$/gmi, "")
    .replace(/^\s*M\s*A\s*G\s*Y\s*A\s*R\s+K\s*Ö\s*Z\s*L\s*Ö\s*N\s*Y[^\n]*\d{3,5}\s*$/gmi, "")
    .replace(/^MAGYAR KÖZLÖNY[^\n]*$/gmi, "");
}

/** A jogszabály törzsszöveg-szelete: a saját fejlécétől a következő fejlécig. */
function sliceAct(text, shortNum) {
  const clean = dropPageFurniture(text);
  // Kétféle fejléc létezik, és ez nem egy mintával fedhető le:
  //   rendelet/határozat →  "A Kormány 1267/2026. (VIII. 26.) Korm. határozata"
  //   törvény            →  "2026. évi XLVII. törvény"   (önálló sor)
  const HEAD = /^(?:A |Az )?[^\n]{0,80}?(\d+\/\d{4}\.\s*\([IVXLC]+\.\s*\d+\.\))\s*(?:Korm\.|MNB|KE|OGY|AB|ME|IM|[A-ZÁÉÍÓÖŐÚÜŰ]{2,5})?\s*(?:rendelete|határozata|utasítása)/gm;
  const HEAD_TV = /^\s*(\d{4}\.\s*évi\s+[IVXLCDM]+\.)\s*törvény\s*$/gm;
  const heads = [];
  let m;
  while ((m = HEAD.exec(clean))) heads.push({num: m[1], start: m.index});
  while ((m = HEAD_TV.exec(clean))) heads.push({num: m[1].replace(/\s+/g, " ").trim(), start: m.index});
  heads.sort((a, b) => a.start - b.start);
  const iAt = heads.findIndex(h => h.num.startsWith(shortNum) || shortNum.startsWith(h.num));
  if (iAt < 0) return null;
  const from = heads[iAt].start;
  const to = iAt + 1 < heads.length ? heads[iAt + 1].start : Math.min(clean.length, from + 40000);
  return clean.slice(from, to).replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * Aláírások kibontása.
 *
 * FONTOS: a KE határozatot a köztársasági elnök írja alá, a miniszterelnök csak
 * ELLENJEGYZI. Ha csak az utolsó "s. k."-t nézzük, a döntést a miniszterelnöknek
 * tulajdonítjuk — ez egy hírműsorban súlyos tévedés lenne. Ezért minden aláírást
 * kigyűjtünk sorrendben, és az "Ellenjegyzem" utániakat külön jelöljük.
 */
function extractSignatures(body) {
  const lines = body.split("\n");
  const out = [];
  let counter = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*Ellenjegyzem/i.test(lines[i])) { counter = true; continue; }
    const m = /([A-ZÁÉÍÓÖŐÚÜŰ][\p{L}.\s-]{2,50}?)\s*s\.\s*k\.,/u.exec(lines[i]);
    if (!m) continue;
    const roles = [];
    for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
      const r = lines[j].trim().replace(/,$/, "");
      if (!r || /s\.\s*k\./.test(r) || /^Ellenjegyzem/i.test(r)) break;
      if (/^(Budapest|SP ügyszám)/i.test(r)) continue;
      if (r.length > 90) break;
      // A -layout kimenetben egy sorban két oszlop is lehet, nagy szóközzel
      // elválasztva. Csak az elsőt tartjuk meg — a második másik blokk.
      roles.push(clean(r.split(/\s{3,}/)[0]));
    }
    out.push({name: clean(m[1]), role: roles.join(", ") || null,
              countersignature: counter});
  }
  return out;
}

const AMOUNT_RE = /\b(\d[\d\s]{2,20})\s*(forint|milliárd forint|millió forint|euró)/gi;
const REF_RE = /\b(\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény|\d+\/\d{4}\.\s*\([IVXLC]+\.\s*\d+\.\)\s*[A-ZÁÉÍÓÖŐÚÜŰ.]*\s*(?:rendelet|határozat))/g;

/** Mit CSINÁL a pont? A vezérige dönti el. */
const VERB_KIND = [
  [/\bjóváhagyj\w+/i, "JÓVÁHAGYÁS"], [/\bfelhívj\w+/i, "FELHÍVÁS"],
  [/\begyetért\w*/i, "EGYETÉRTÉS"],  [/\bvállalj\w+/i, "VÁLLALÁS"],
  [/\belrendel\w*/i, "ELRENDELÉS"],  [/helyébe a következő (?:rendelkezés|szöveg|bekezdés)\w* lép/i, "MÓDOSÍTÁS"],
  [/\bszövegrész\w* helyébe\b/i, "MÓDOSÍTÁS"],
  [/\bkiegészül\w*/i, "MÓDOSÍTÁS"],
  [/\bmódosít\w*/i, "MÓDOSÍTÁS"],
  [/\bhatályát veszti|hatályon kívül/i, "HATÁLYON_KÍVÜL"],
  [/\bkinevez\w*/i, "KINEVEZÉS"],    [/\bfelment\w*/i, "FELMENTÉS"],
  [/\badományoz\w*/i, "ADOMÁNYOZÁS"],[/\bbiztosítj\w+/i, "FORRÁSBIZTOSÍTÁS"],
];

/**
 * Mit csinál a pont? A SZÖVEGBEN LEGKORÁBBAN álló vezérige dönt, nem a lista
 * sorrendje. Enélkül egy idézett jogszabályrészben szereplő szó felülírja a
 * tényleges műveletet — egy módosító paragrafus "egyetértésnek" látszott.
 */
function classify(text) {
  // Az IDÉZETT jogszabályszöveget kivágjuk. Egy módosító paragrafus beidézi a
  // régi és az új szöveget is — azoknak a szavai nem a pont műveletét írják le.
  // Ami marad, az a pont SAJÁT megfogalmazása, akármilyen hosszú a bevezetője.
  const head = text.replace(/„[^”]*”/g, " ").replace(/"[^"]{20,}"/g, " ");
  let best = null, at = Infinity;
  for (const [re, kind] of VERB_KIND) {
    const m = new RegExp(re.source, re.flags.replace("g", "")).exec(head);
    if (m && m.index < at) { at = m.index; best = kind; }
  }
  return best ?? "EGYÉB";
}

/**
 * A számozott pontokból önálló állítások.
 *
 * A két jogszabályfajta MÁS szerkezetű, és ezt nem lehet egy szabállyal lefedni:
 *   határozat →  "1.", "2.", "3."  számozott döntési pontok
 *   rendelet  →  "1. §", "2. §"    szakaszok
 *
 * A számokat SORFOLYTONOSAN fogadjuk el (mindig a következő szám jöhet). Enélkül
 * a "19. §-a alapján" szövegközi hivatkozás új pontot nyitna — pontosan ez volt a
 * hiba az első változatban.
 */
function extractClaims(body, actType) {
  const isRendelet = /rendelet|törvény/i.test(actType);   // a törvény is §-okra tagolódik
  const SIGN = /\bs\.\s*k\.,/;
  const lines = body.split("\n");
  const items = [];
  let cur = null, expect = 1, inSign = false;

  for (const l of lines) {
    if (SIGN.test(l)) { inSign = true; continue; }     // aláírás után nincs több pont
    if (inSign) continue;

    const sec = /^\s{0,12}(\d{1,3})\.\s*§/.exec(l);              // rendelet-szakasz
    const pt  = /^\s{0,12}(\d{1,2})\.\s+(?!§)(\S.*)$/.exec(l);   // határozat-pont
    const resp = /^\s*Felelős:\s*(.*)$/.exec(l);
    const dead = /^\s*Határidő:\s*(.*)$/.exec(l);

    const startsNew = isRendelet
      ? (sec && Number(sec[1]) === expect)
      : (pt && !sec && Number(pt[1]) === expect);

    if (startsNew) {
      if (cur) items.push(cur);
      const n = Number(isRendelet ? sec[1] : pt[1]);
      const rest = isRendelet ? l.slice(sec.index + sec[0].length).trim() : pt[2].trim();
      cur = {n, text: rest, responsible: [], deadline: null};
      expect = n + 1;
    } else if (cur && resp) {
      cur.responsible.push(clean(resp[1]));
      cur._inResp = true;
    } else if (cur && dead) {
      cur.deadline = clean(dead[1]); cur._inResp = false;
    } else if (cur && cur._inResp && /^\s{10,}\S/.test(l) && !/^\s*\d/.test(l.trim())) {
      cur.responsible.push(clean(l));                  // többsoros felelős-lista
    } else if (cur && l.trim()) {
      cur._inResp = false;
      cur.text += " " + l.trim();
    }
  }
  if (cur) items.push(cur);

  const mapped = items.map(it => {
    const text = clean(it.text);
    const amounts = [...text.matchAll(AMOUNT_RE)].map(a => clean(a[0]));
    const kind = classify(text);
    return {n: it.n, kind, text,
            amounts: [...new Set(amounts)],
            responsible: [...new Set(it.responsible.filter(r => r && !SIGN.test(r)))],
            deadline: it.deadline};
  }).filter(c => c.text.length > 25);

  if (mapped.length) return mapped;

  // Sok határozatnak (OGY, KE) nincs számozott pontja — a törzs egyetlen prózaszöveg.
  // Ilyenkor a próza MAGA az állítás; üres kézzel visszatérni hiba lenne.
  const bodyLines = body.split("\n")
    .filter(l => !SIGN.test(l) && !/^\s*(Ellenjegyzem|Budapest,|SP ügyszám)/i.test(l));
  // Az első két sor a fejléc és a cím — a próza utánuk kezdődik.
  const prose = clean(bodyLines.slice(2).join(" ")).replace(/^\*+\s*/, "");
  if (prose.length < 40) return [];
  return [{n: 1, kind: classify(prose) === "EGYÉB" ? "PRÓZA" : classify(prose),
           text: prose, amounts: [...new Set([...prose.matchAll(AMOUNT_RE)].map(a => clean(a[0])))],
           responsible: [], deadline: null, shape: "PROSE"}];
}

if (val("read")) {
  const want = val("read").trim();
  if (!existsSync(ACTS)) { console.error("\n  Nincs acts.jsonl — futtasd előbb alapmódban.\n"); process.exit(1); }
  const all = readFileSync(ACTS, "utf8").split("\n").filter(Boolean).map(JSON.parse);
  const act = all.find(a => a.number.startsWith(want) || a.id.startsWith(want));
  if (!act) {
    console.error(`\n  Nincs ilyen jogszabály: ${want}`);
    console.error(`  Elérhető például: ${all.slice(-3).map(a => a.number.split(" ")[0]).join(", ")}\n`);
    process.exit(1);
  }
  const [year, num] = act.issue.split("/");
  const txtPath = join(OUT, year, `MK-${num}.txt`);
  if (!existsSync(txtPath)) { console.error(`\n  Hiányzik a szöveg: ${txtPath}\n`); process.exit(1); }

  const text = readFileSync(txtPath, "utf8");
  const body = sliceAct(text, act.number.split(" ")[0]);
  if (!body) { console.error(`\n  Nem találom a törzsszöveget ehhez: ${act.number}\n`); process.exit(1); }

  const claims = extractClaims(body, act.actType);
  const refs = [...new Set([...body.matchAll(REF_RE)].map(r => clean(r[1])))]
    .filter(r => !r.startsWith(act.number.split(" ")[0]));
  const signatures = extractSignatures(body);
  const signer = signatures.find(x => !x.countersignature) ?? null;
  const counters = signatures.filter(x => x.countersignature);

  const rec = {
    ...act,
    depth: "FULL_TEXT",
    signatures,
    signatory: signer ? `${signer.name}${signer.role ? ", " + signer.role : ""}` : null,
    countersignedBy: counters.map(c => `${c.name}${c.role ? ", " + c.role : ""}`),
    references: refs,
    claims,
    fullText: body,
    readAt: new Date().toISOString(),
    review: "MACHINE_EXTRACTED",
  };
  const dir = join(OUT, "acts"); mkdirSync(dir, {recursive: true});
  const slug = `${act.number} ${act.actType}`
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
  const file = join(dir, `${slug}.json`);
  writeFileSync(file, JSON.stringify(rec, null, 2));

  console.log(`\n${act.number} ${act.actType}`);
  console.log(`${act.title}`);
  console.log(`kiadó: ${act.issuer}`);
  if (rec.signatory) console.log(`aláírta: ${rec.signatory}`);
  for (const c of rec.countersignedBy) console.log(`ellenjegyezte: ${c}`);
  console.log(`lapszám: ${act.issue} · ${act.issueDate ?? "—"}${act.effectiveDate ? ` · hatályba: ${act.effectiveDate}` : ""}`);
  console.log(`\n${claims.length} kibontott döntési pont:\n`);
  for (const c of claims) {
    console.log(`  ${c.n}. [${c.kind}]`);
    console.log(`     ${c.text.slice(0, 150)}${c.text.length > 150 ? "…" : ""}`);
    if (c.amounts.length)     console.log(`     összeg:   ${c.amounts.join(" · ")}`);
    if (c.responsible.length) console.log(`     felelős:  ${c.responsible.join(" · ")}`);
    if (c.deadline)           console.log(`     határidő: ${c.deadline}`);
    console.log("");
  }
  if (refs.length) console.log(`  hivatkozott jogszabályok: ${refs.slice(0, 6).join(" · ")}`);
  console.log(`\n  Kiírva: ${file.replace(ROOT + "/", "")}`);
  console.log(`  Konstitutív forrás — egyetlen ilyen elég az "established" státuszhoz.\n`);
  process.exit(0);
}

// ═════════════════════════════════════════════════════════════════════════════
console.log(`\nMagyar Közlöny — letöltés és állítás-kinyerés`);

const list = await get(LIST_URL);
if (!list.ok) { console.error(`  Nem érhető el a lista (${list.status}${list.error ? " " + list.error : ""})\n`); process.exit(1); }

const issues = parseIssueList(list.text).slice(0, LIMIT);
console.log(`  ${issues.length} lapszám a címlapon\n`);

const known = new Set(existsSync(ACTS)
  ? readFileSync(ACTS, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l).id) : []);

let newActs = 0, newIssues = 0;

for (const iss of issues) {
  const dir = join(OUT, iss.year);
  const pdfPath = join(dir, `MK-${iss.num}.pdf`);
  const txtPath = join(dir, `MK-${iss.num}.txt`);
  mkdirSync(dir, {recursive: true});

  if (existsSync(pdfPath) && !FORCE) { console.log(`  ${iss.key.padEnd(12)} már megvan`); continue; }

  const r = await get(iss.url, true);
  if (!r.ok) { console.log(`  ${iss.key.padEnd(12)} ! letöltés sikertelen (${r.status})`); continue; }
  if (r.buf.subarray(0, 4).toString() !== "%PDF") { console.log(`  ${iss.key.padEnd(12)} ! nem PDF`); continue; }

  writeFileSync(pdfPath, r.buf);
  const sha = createHash("sha256").update(r.buf).digest("hex");
  const text = pdfToText(pdfPath, txtPath);
  if (!text) { console.log(`  ${iss.key.padEnd(12)} ! szövegkinyerés sikertelen (kell: pdftotext vagy pdfplumber)`); continue; }

  const acts = extractActs(text);
  newIssues++;
  console.log(`  ${iss.key.padEnd(12)} ${iss.date ?? "—"}  ${(r.buf.length / 1024 | 0)}kB  →  ${acts.length} jogszabály`);

  for (const a of acts) {
    const id = `${a.number} ${a.actType}`;
    if (known.has(id) && !FORCE) continue;
    known.add(id);
    const rec = {
      id, issue: iss.key, issueDate: iss.date,
      number: a.number, actType: a.actType,
      issuer: ISSUER[a.actType] ?? a.actType.split(" ")[0],
      title: a.title, page: a.page,
      effectiveDate: findEffectiveDate(text, a.number),
      // Ez a lényeg: nem beszámoló, hanem maga a tény.
      processKind: "OFFICIAL_RECORD", constitutive: true,
      source: {url: iss.url, sha256: sha, retrievedAt: new Date().toISOString(),
               localPdf: pdfPath.replace(ROOT + "/", "")},
      basis: "PUBLISHED", review: "MACHINE_EXTRACTED",
    };
    appendFileSync(ACTS, JSON.stringify(rec) + "\n");
    newActs++;
  }
}

console.log(`\n  ${newIssues} új lapszám, ${newActs} új jogszabály`);
console.log(`  Napló: ${ACTS.replace(ROOT + "/", "")}`);
if (newActs) {
  const last = readFileSync(ACTS, "utf8").split("\n").filter(Boolean).slice(-4).map(JSON.parse);
  console.log(`\n  Utolsó találatok:`);
  for (const a of last) {
    console.log(`    [${a.issuer}] ${a.number} ${a.actType}`);
    console.log(`      ${a.title.slice(0, 96)}${a.effectiveDate ? `  · hatályba: ${a.effectiveDate}` : ""}`);
  }
}
console.log("");
