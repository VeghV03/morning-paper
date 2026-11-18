const clean = (s) => String(s ?? "").replace(/\s+/g, " ").trim();
const ACT_RE = /^\s*(?<num>\d+\/\d{4}\.\s*\([IVXLC]+\.\s*\d+\.\))\s+(?<type>(?:Korm\.|MNB|KE|OGY|AB|ME|BM|AM|PM|EüM|MEKH|AÉM|[A-ZÁÉÍÓÖŐÚÜŰ]{2,8})\s+(?:rendelet|határozat|utasítás))\s+(?<rest>\S.*)$/u;
const TV_RE = /^\s*(?<num>\d{4}\.\s*évi\s+[IVXLCDM]+\.)\s+(?<type>törvény\w*)\s+(?<rest>\S.*)$/;
const PAGE_RE = /\s+(\d{3,5})\s*$/;

export function extractActs(text) {
  const i = text.indexOf("Tartalomjegyzék");
  if (i < 0) return [];
  const toc = text.slice(i + "Tartalomjegyzék".length);
  const end = toc.search(/^\s*\d{3,5}\s+MAGYAR KÖZLÖNY/m);
  const lines = (end >= 0 ? toc.slice(0, end) : toc.slice(0, 20000)).split("\n").map((line) => line.replace(/\s+$/, ""));
  const acts = []; let current = null;
  for (const line of lines) {
    const match = ACT_RE.exec(line) || TV_RE.exec(line);
    if (match && (!current || current.page)) {
      if (current) acts.push(current);
      const rest = match.groups.rest, page = PAGE_RE.exec(rest);
      current = {number: clean(match.groups.num), actType: clean(match.groups.type),
        title: clean(page ? rest.slice(0, page.index) : rest), page: page ? Number(page[1]) : null};
    } else if (current && line.trim()) {
      const page = PAGE_RE.exec(line);
      current.title = clean(`${current.title} ${page ? line.slice(0, page.index) : line}`);
      if (page && !current.page) current.page = Number(page[1]);
    }
  }
  if (current) acts.push(current);
  return acts.filter((act) => act.title.length > 6);
}
