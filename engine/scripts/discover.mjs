#!/usr/bin/env node
// Felderítés — egyetlen belépési pont. (D78)
//   node scripts/discover.mjs [YYYY-MM-DD] [--top N]
//
// Eddig két klaszterezés futott egymás mellett, és a rosszabbik döntött: a
// cím-alapú genealógia 3 jelöltet adott, az állítás-szintű 36-ot, és a napi
// audit a cím-alapún futott. Így a jobbik ág kimenete sehová nem vezetett.
//
// Mostantól az ÁLLÍTÁS-SZINTŰ klaszterezés a fő ág: az a kérdés, hogy két lap
// ugyanazt ÁLLÍTJA-e, nem az, hogy ugyanazt a CÍMET adta-e. A cím-egyezés
// másodlagos jelzés marad — ha megvan, megerősítés; ha nincs, nem kizáró ok.
//
// A rangsor nem szerkesztői döntés, hanem triázs. A gép megmondja, mi bír el
// epizódot; hogy melyiket érdemes elmondani, az az értelmezésé.
import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";
import { clusterClaims } from "./cluster-claims.mjs";

// Konstitutív forrás: a közzététel MAGA a tény. Ez a FORRÁSON múlik, nem a
// címszövegen — egy publicisztika arról, hogy valami „törvénysértő", nem
// konstitutív. Az első változat a címre illesztett, és ettől minden törvényt
// emlegető vélemény hivatalos iratnak látszott.
const KONSTITUTIV_FEED = new Set(["kozlony", "mkogy", "njt", "eurlex"]);
// A közlönyszám maga nem történet, hanem a tartalomjegyzéke. Alapnak jó,
// jelöltnek nem: sajtófeldolgozás nélkül nincs mit elmondani róla.
const TARTALOMJEGYZEK = /^(magyar közlöny|hivatalos értesítő)\s+\d{4}\.\s*évi/i;
// Gépi cikkletöltést tiltó kiadók — hírfolyam-jelzésnek jók, bizonyítéknak nem.
const TILTOTT_TORZS = new Set(["24", "24.hu"]);

function loadItems(day) {
  const dir = resolve("out/feed-snapshots", day);
  if (!existsSync(dir)) throw new Error(`NINCS_PILLANATKÉP:${day} — futtasd előbb: node scripts/snapshot-feeds.mjs`);
  const items = [];
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".items.jsonl"))) {
    const brand = f.split("__")[0];
    for (const line of readFileSync(join(dir, f), "utf8").split("\n").filter(Boolean)) {
      try {
        const o = JSON.parse(line);
        items.push({ ...o, brand, org: o.org ?? brand,
          constitutive: KONSTITUTIV_FEED.has(brand),
          index_only: TARTALOMJEGYZEK.test(o.title ?? "") });
      } catch { /* sérült sor: kihagyjuk, de a darabszám eltérése látszik a jelentésben */ }
    }
  }
  return items;
}

// Másodlagos jelzés: a cím-alapú genealógia ugyanezt a hírt egy klaszterbe tette-e.
function titleCrossCheck(day) {
  const f = resolve("out/genealogy", `${day}-genealogy.json`);
  if (!existsSync(f)) return null;
  const g = JSON.parse(readFileSync(f, "utf8"));
  const byLink = new Map();
  for (const c of g.clusters ?? [])
    for (const it of c.items ?? []) byLink.set(it.link, { cluster: c.cluster, k: c.k });
  return byLink;
}

// Triázs. Nem publikációs döntés — az a szerkesztői szerződésé az epizódnál.
// Itt csak az a kérdés: van-e elég a nap végén ahhoz, hogy nekiálljunk.
export function triage(c, cross) {
  const okok = [];
  const torzsKepes = c.members.filter((m) => !TILTOTT_TORZS.has(m.brand) && !KONSTITUTIV_FEED.has(m.brand));
  const orgs = new Set(torzsKepes.map((m) => m.brand)).size;
  const csakKozlony = c.members.every((m) => KONSTITUTIV_FEED.has(m.brand));

  if (c.constitutive) okok.push("konstitutív forrás (közlöny/határozat)");
  if (orgs >= 2) okok.push(`${orgs} lap cikktörzse letölthető`);
  if (c.mechanismHits.length) okok.push(`mechanizmus-jel: ${c.mechanismHits.slice(0, 3).join(", ")}`);
  if (cross) okok.push("a cím-alapú klaszterezés is egybe tette");

  // A pontszám sorrendet ad, nem minőséget ítél.
  const pont = (csakKozlony ? 0 : (c.constitutive ? 40 : 0)) + Math.min(orgs, 4) * 15
    + Math.min(c.mechanismHits.length, 4) * 8 + (cross ? 10 : 0);

  let verdikt;
  // A közlöny önmagában ALAP: konstitutív bizonyíték egy másik történethez,
  // de sajtófeldolgozás nélkül nincs miről videót csinálni.
  if (csakKozlony) verdikt = "ALAP";
  else if (c.constitutive && orgs >= 1) verdikt = "EPIZÓD";
  else if (orgs >= 2 && c.mechanismHits.length) verdikt = "EPIZÓD";
  else if (orgs >= 2) verdikt = "FÜGGŐBEN";
  else verdikt = "NEM";

  const akadaly = [];
  if (csakKozlony) akadaly.push("csak közlöny — sajtófeldolgozás nélkül nincs történet, de más epizód alapja lehet");
  else if (!torzsKepes.length) akadaly.push("egyik kiadó sem enged gépi cikkletöltést");
  if (orgs < 2 && !c.constitutive) akadaly.push("egyetlen letölthető forrás, nincs konstitutív alap");
  return { verdikt, pont, okok, akadaly, torzsKepesOrgs: orgs };
}

function main() {
  const day = process.argv.find((a) => /^\d{4}-\d{2}-\d{2}$/.test(a)) ?? new Date().toISOString().slice(0, 10);
  const ti = process.argv.indexOf("--top");
  const top = ti > -1 ? Number(process.argv[ti + 1]) : 15;

  const items = loadItems(day);
  const clusters = clusterClaims(items);            // FŐ ÁG
  const cross = titleCrossCheck(day);               // másodlagos jelzés

  const rows = clusters.map((c) => {
    const x = cross ? c.members.some((m) => cross.has(m.link)) : false;
    return { ...c, ...triage(c, x) };
  }).sort((a, b) => b.pont - a.pont);

  const epizod = rows.filter((r) => r.verdikt === "EPIZÓD");
  const fuggo = rows.filter((r) => r.verdikt === "FÜGGŐBEN");
  const alap = rows.filter((r) => r.verdikt === "ALAP");

  mkdirSync("out/discovery", { recursive: true });
  const out = { day, generated_at: new Date().toISOString(),
    feed_items: items.length, clusters: clusters.length,
    primary: "claim-level", cross_check: cross ? "title-genealogy" : null,
    counts: { episode: epizod.length, pending: fuggo.length, backing: alap.length,
      rejected: rows.length - epizod.length - fuggo.length - alap.length },
    candidates: rows.slice(0, 60) };
  const file = `out/discovery/${day}.json`;
  writeFileSync(file, JSON.stringify(out, null, 2) + "\n");

  console.log(`FELDERÍTÉS — ${day}`);
  console.log(`${items.length} hírfolyam-tétel · ${clusters.length} állítás-klaszter · fő ág: állítás-szintű`);
  console.log(`${epizod.length} epizód-jelölt · ${fuggo.length} függőben · ${alap.length} közlönyalap\n`);
  for (const [i, r] of rows.slice(0, top).entries()) {
    const jel = { EPIZÓD: "●", FÜGGŐBEN: "○", ALAP: "▣", NEM: "·" }[r.verdikt];
    console.log(`${String(i + 1).padStart(2)}. ${jel} ${String(r.pont).padStart(3)}  ${r.title.slice(0, 74)}`);
    console.log(`       ${r.okok.join(" · ") || "nincs jelzés"}`);
    if (r.akadaly.length) console.log(`       AKADÁLY: ${r.akadaly.join(" · ")}`);
    console.log(`       ${[...new Set(r.members.map((m) => m.brand))].join(", ")}`);
  }
  console.log(`\nKiírva: ${file}`);
  console.log(`A rangsor triázs, nem szerkesztői döntés: azt mondja meg, mi BÍR EL epizódot.`);
}
if (import.meta.url === `file://${process.argv[1]}`) main();
