const toast = window.toast || ((m)=>console.log(m));
function getBridge(){ return window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage; }
export async function load() {
  if (typeof window.loadSlaveUsers === 'function') {
    try{ return await window.loadSlaveUsers(); }catch(e){ console.warn('delegate slave failed',e); }
  }
  const bridge = getBridge();
  const body = document.getElementById("slaveBody");
  if (!body) return;
  if (!bridge) { body.innerHTML = `<tr><td colspan="8">桥接未就绪</td></tr>`; return; }
  const gid = (document.getElementById("slaveGid")?.value || "").trim();
  body.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try{
    const q = gid ? {gid} : {};
    const d = await bridge.apiGet("slave/users", q);
    if (!d || !Array.isArray(d) || !d.length) { body.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">暂无奴隶数据<br><small>群内发送 奴隶系统 指令后自动收录</small></td></tr>`; return; }
    // 复用 app.js 渲染若存在
    if (typeof window.renderSlaveTable === 'function' && Array.isArray(window.RAW_SLAVE_USERS)) {
      window.RAW_SLAVE_USERS = d;
      window.renderSlaveTable();
      return;
    }
    body.innerHTML = d.slice(0,300).map(r => `<tr>
      <td><span class="badge badge-primary">${r.gid||""}</span></td>
      <td><strong>${r.qq}</strong></td>
      <td>${r.name||""}</td>
      <td>${r.owner ? `<span class="badge badge-purple">👤 ${r.owner}</span>` : '<span style="color:var(--muted)">自由身</span>'}</td>
      <td><span style="font-weight:700">💰 ${(r.price||0).toLocaleString()}</span></td>
      <td><span class="badge badge-primary">${r.slaves||0} 人</span></td>
      <td>${r.protect ? `<span class="badge badge-success">🛡️ ${r.protect}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
      <td>${r.weapons ? `<span class="badge badge-warning">⚔️ ${(r.weapons||"").slice(0,30)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    </tr>`).join("");
  }catch(e){ body.innerHTML = `<tr><td colspan="8">加载失败: ${e.message}</td></tr>`; }
}
export default { load };
