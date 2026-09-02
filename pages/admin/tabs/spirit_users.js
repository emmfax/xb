const toast = window.toast || ((m)=>console.log(m));
function getBridge(){ return window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage; }
export async function load() {
  if (typeof window.loadSpiritUsers === 'function') {
    try{ return await window.loadSpiritUsers(); }catch(e){ console.warn('delegate spirit failed',e); }
  }
  const bridge = getBridge();
  const body = document.getElementById("spiritUsersBody");
  if (!body) return;
  if (!bridge) { body.innerHTML = `<tr><td colspan="9">桥接未就绪</td></tr>`; return; }
  const gid = (document.getElementById("spiritGid")?.value || "").trim();
  body.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try{
    const q = gid ? {gid} : {};
    const d = await bridge.apiGet("spirit/users", q);
    if (!d || !Array.isArray(d) || !d.length) { body.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--muted)">暂无精灵用户<br><small>群内发送 精灵系统 指令后自动收录</small></td></tr>`; return; }
    if (typeof window.renderSpiritUsersTable === 'function' && Array.isArray(window.RAW_SPIRIT_USERS)) {
      window.RAW_SPIRIT_USERS = d;
      window.renderSpiritUsersTable();
      return;
    }
    body.innerHTML = d.slice(0,300).map(r => `<tr>
      <td><span class="badge badge-primary">${r.gid||""}</span></td>
      <td><strong>${r.qq}</strong></td>
      <td>${r.name||""}</td>
      <td><span class="badge badge-primary">${r.count||0} 只</span></td>
      <td>${r.active ? `<span class="badge badge-success">⚡ ${r.active}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
      <td>${r.best ? `<span class="badge badge-purple">🌟 ${r.best}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
      <td><span class="badge badge-warning">Lv.${r.max_level||0}</span></td>
      <td><span style="font-weight:700;color:var(--bad)">🔥 ${(r.total_power||0).toLocaleString()}</span></td>
      <td><span class="badge badge-primary">🎒 ${r.bag_count||0} 件</span></td>
    </tr>`).join("");
  }catch(e){ body.innerHTML = `<tr><td colspan="9">加载失败: ${e.message}</td></tr>`; }
}
export default { load };
