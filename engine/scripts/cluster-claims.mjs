// Állítás-szintű klaszterezés. (D42)
// A régi klaszterező címegyezésre csoportosított, és eldobta az egyforrású
// tételeket — tegnap 160-ból 144-et. Egy egyforrású hír viszont konstitutív
// forrással vagy erős folyamattal simán lehet epizód. Itt nem tételeket
// csoportosítunk, hanem ÁLLÍTÁSOKAT: a szingli állítás is állítás, csak k = 1.
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const STOP = new Set("a az egy és de vagy hogy is mint nem meg már csak ha majd volt lesz lehet ez ezt azt ki be fel le át el ide oda ott itt után előtt között szerint miatt által való vala nak nek ban ben ból ből ra re tól től val vel".split(/\s+/));
// English, German and French function words (E12 in morning-paper): titles in those languages
// share them by accident, never by story. None of them is a Hungarian word longer than two letters.
for (const w of ("the and for with from that this are was were have had will would can could not but its his her their they " +
  "after over into about than more new says said amid who what when how why our your all out off just also been being ahead " +
  "under against between while during before die der das und ein eine einen dem den des auf für von ist nicht sich bei nach " +
  "wie aus zum zur über les une pour dans est sur avec qui que aux ses son pas plus ont été cette entre après").split(" ")) STOP.add(w);
const stem = (w) => (w.length > 7 ? w.slice(0, 7) : w);
const toks = (s) => String(s).toLowerCase().normalize("NFC")
  .replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/)
  .filter((w) => w.length > 2 && !STOP.has(w)).map(stem);

// Az állításkulcs: a cím érdemi szavai. Két tétel akkor ugyanazt állítja, ha
// a kulcsaik átfedése nagy — átfedési együttható, nem Jaccard, mert a hosszak
// erősen eltérnek.
const overlap = (a, b) => {
  const A = new Set(a), B = new Set(b);
  if (!A.size || !B.size) return 0;
  let hit = 0; for (const x of A) if (B.has(x)) hit++;
  return hit / Math.min(A.size, B.size);
};

// Mechanizmus-jel: szabály, testület, közpénz vagy eljárás. Ugyanaz a lista,
// mint a napi auditban — a szerkesztői kapu gépi előszűrője.
const MECH = /hivatal|miniszt|államtitkár|bizottság|törvény|rendelet|alaptörvény|határozat|közbeszerz|támogatás|milliárd|költségvetés|alapítvány|csőd|eljárás|kinevez|jelöl|parlament|országgyűl|szabály|felügyel|szerződés|per\b|bírság|adó\b|díj\b|engedély|minister|parliament|court|ruling|\blaw\b|\bbill\b|budget|billion|tender|appoint|regulat|sanction|election|\bvote|\btax\b|investigat|indict|lawsuit|treaty/i;

export function clusterClaims(items, { threshold = 0.45, minShared = 2 } = {}) {
  const withTok = items.map((it) => ({ ...it, tok: toks(it.title) }));
  const used = new Set(), clusters = [];
  for (let i = 0; i < withTok.length; i++) {
    if (used.has(i)) continue;
    const group = [withTok[i]]; used.add(i);
    for (let j = i + 1; j < withTok.length; j++) {
      if (used.has(j)) continue;
      const shared = withTok[i].tok.filter((t) => withTok[j].tok.includes(t)).length;
      if (shared >= minShared && overlap(withTok[i].tok, withTok[j].tok) >= threshold) {
        group.push(withTok[j]); used.add(j);
      }
    }
    const orgs = [...new Set(group.map((g) => g.org ?? g.brand))];
    const text = group.map((g) => g.title).join(" ");
    clusters.push({
      claimKey: [...new Set(group[0].tok)].slice(0, 8).join("+"),
      title: group[0].title,
      members: group.map((g) => ({ brand: g.brand ?? g.org, title: g.title, link: g.link })),
      orgs,
      // Egyforrású is klaszter — csak jelöljük, hogy az.
      singleSource: orgs.length < 2,
      constitutive: group.some((g) => g.constitutive === true),
      mechanismHits: [...new Set((text.match(new RegExp(MECH, "gi")) ?? []).map((s) => s.toLowerCase()))],
    });
  }
  return clusters.sort((a, b) => b.orgs.length - a.orgs.length || b.mechanismHits.length - a.mechanismHits.length);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const day = process.argv[2] ?? new Date().toISOString().slice(0, 10);
  const dir = resolve("out/feed-snapshots", day);
  const items = [];
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".items.jsonl"))) {
    const brand = f.split("__")[0];
    for (const line of readFileSync(join(dir, f), "utf8").split("\n").filter(Boolean)) {
      try { const o = JSON.parse(line); items.push({ ...o, brand, org: o.org ?? brand }); } catch {}
    }
  }
  const clusters = clusterClaims(items);
  const multi = clusters.filter((c) => !c.singleSource);
  const mech = clusters.filter((c) => c.mechanismHits.length > 0);
  const candidates = clusters.filter((c) => c.mechanismHits.length > 0 && (c.constitutive || true));
  mkdirSync("out/genealogy", { recursive: true });
  writeFileSync(`out/genealogy/${day}-claim-clusters.json`,
    JSON.stringify({ day, itemCount: items.length, clusters }, null, 2) + "\n");
  console.log(`\nÁLLÍTÁS-KLASZTEREZÉS — ${day}`);
  console.log(`  tétel:                 ${items.length}`);
  console.log(`  állítás-klaszter:      ${clusters.length}   (a régi: csak a több-szervezetesek)`);
  console.log(`  ebből több-forrású:    ${multi.length}`);
  console.log(`  ebből egyforrású:      ${clusters.length - multi.length}  — k = 1, közzététellel`);
  console.log(`  mechanizmus-jellel:    ${mech.length}`);
  console.log(`  epizód-jelölt:         ${candidates.length}\n`);
  for (const c of mech.slice(0, 12))
    console.log(`  ${c.singleSource ? "○" : "●"} ${String(c.orgs.length)}f  ${c.title.slice(0, 66)}`);
}
