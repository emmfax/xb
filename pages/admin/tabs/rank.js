const toast = window.toast || ((m)=>console.log(m));
export async function load(type) {
  if (typeof window.loadRank === 'function') return window.loadRank(type || document.getElementById("rankType")?.value || "money");
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const rows = await bridge.apiGet("rank", { type: type || "money" });
  const body = document.getElementById("rankBody");
  if (!body) return;
  if (!rows.length) { body.innerHTML = `<tr><td colspan="4">暂无数据</td></tr>`; return; }
  body.innerHTML = rows.map((r,i) => `<tr><td>${i+1}</td><td>${r.name||r.qq}</td><td>${r.value}</td></tr>`).join("");
}
export default { load };
