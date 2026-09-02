const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadStats === 'function') {
    await window.loadStats();
    if (typeof window.loadOverviewReq === 'function') await window.loadOverviewReq();
    return;
  }
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const s = await bridge.apiGet("stats");
  const fmt = (n) => typeof n === "number" ? n.toLocaleString() : (n || 0);
  const el = document.getElementById("stats");
  if (!el) return;
  el.innerHTML = `<div class="card"><div class="num">${fmt(s.players?.wallet||0)}</div><div class="lab">钱包用户</div></div>`;
}
export default { load };
