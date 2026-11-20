// Walks the phone page in a real browser (test_page.py): Chrome's DevTools Protocol over Node's own
// WebSocket. Opens the paper with the test code, visits each route, and prints each page's text
// and every error the page threw.
const [port, url, repo, code, ...routes] = process.argv.slice(2);

const tab = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail; });
let n = 0;
const waiting = new Map(), errors = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (waiting.has(d.id)) { waiting.get(d.id)(d.result); waiting.delete(d.id); }
  if (d.method === "Runtime.exceptionThrown") {
    const x = d.params.exceptionDetails;
    errors.push((x.exception && x.exception.description) || x.text);
  }
  if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error")
    errors.push(d.params.args.map((a) => a.value ?? a.description).join(" "));
};
const send = (method, params = {}) => new Promise((ok) => { waiting.set(++n, ok); ws.send(JSON.stringify({ id: n, method, params })); });
const js = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;
const pause = (ms) => new Promise((ok) => setTimeout(ok, ms));
async function until(expression) {
  for (let i = 0; i < 100; i++, await pause(100)) if (await js(expression)) return true;
  return false;
}
// a page is drawn when show() has replaced the marker and nothing is still loading
const drawn = `!document.getElementById("walk") && document.getElementById("main").innerText.trim() !== ""`;
const mark = `document.getElementById("main").insertAdjacentHTML("afterbegin", "<i id=walk></i>")`;

await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 375, height: 812, deviceScaleFactor: 2, mobile: true });
await send("Page.navigate", { url });
if (!(await until(`!!document.getElementById("setup")`))) throw new Error("no setup form");
await js(mark);
await js(`(() => { const f = document.getElementById("setup");
  f.repo.value = ${JSON.stringify(repo)}; f.token.value = "test"; f.code.value = ${JSON.stringify(code)};
  f.requestSubmit(); })()`);
const pages = {};
for (const route of routes) {
  if (route) { await js(mark); await js(`location.hash = ${JSON.stringify(route)}`); }
  const ok = await until(drawn);
  await pause(300); // what a route draws after its first paint
  pages[route] = ok ? await js(`document.getElementById("main").innerText`) : null;
  const shown = await js(`(document.querySelector("main p.empty") || {}).innerText`); // route() shows what it caught
  if (shown) errors.push(`#${route}: ${shown}`);
}
process.stdout.write(JSON.stringify({ pages, errors }));
ws.close();
