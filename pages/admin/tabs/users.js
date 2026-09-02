function getBridge(){ return window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage; }
export async function load() {
  if (typeof window.loadUsers === 'function') {
    try{ return await window.loadUsers(); }catch(e){ console.warn('delegate users failed',e); }
  }
  const bridge = getBridge();
  const body = document.getElementById("userBody");
  if (!body) return;
  if (!bridge) { body.innerHTML = `<tr><td colspan="10">桥接未就绪</td></tr>`; return; }
  body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try{
    const gid = (document.getElementById("userGidFilter")?.value || "").trim();
    const q = gid ? {gid} : {};
    const d = await bridge.apiGet("users", q);
    if (!Array.isArray(d) || !d.length) { body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--muted)">暂无用户<br><small>群内发送任意指令后自动收录</small></td></tr>`; return; }
    if (typeof window.renderUserTable === 'function' && typeof window.RAW_USERS !== 'undefined') {
      window.RAW_USERS = d;
      window.renderUserTable();
      return;
    }
    body.innerHTML = d.slice(0,300).map(r => `<tr><td><strong>${r.qq}</strong></td><td>${r.name||""}</td><td><span class="badge badge-primary">${r.gid||""}</span></td><td>💰 ${r.money||0}</td><td>⚡ ${r.stamina||0}</td><td>💄 ${r.charm||0}</td><td>🎫 ${r.lottery_tickets||0}</td><td>🏦 ${r.deposit||0}</td><td>${r.sign||0}次</td><td><button class="ghost sm" disabled>保存需主表</button></td></tr>`).join("");
  }catch(e){ body.innerHTML = `<tr><td colspan="10">加载失败: ${e.message}</td></tr>`; }
}
export default { load };
