const toast = window.toast || ((m)=>console.log(m));
function getBridge(){ return window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage; }
function bindGroupsAdd() {
  const inp = document.getElementById("groupsAddGid");
  const btn = document.getElementById("btnGroupsAdd");
  if (!inp || !btn || btn.dataset.bound) return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", async () => {
    const gid = (inp.value||"").trim();
    if (!/^\d{5,15}$/.test(gid)) { toast("请输入5-15位数字群号","bad"); return; }
    const bridge2 = getBridge();
    if (!bridge2) { toast("桥接未就绪","bad"); return; }
    btn.disabled = true;
    try {
      const r = await bridge2.apiPost("groups/toggle", { gid, enabled: true });
      if (r && r.ok === false) { toast("添加失败: "+(r.msg||JSON.stringify(r)),"bad"); return; }
      toast("已添加群 "+gid,"ok");
      inp.value="";
      await load();
    } catch(e){ toast("添加失败: "+e.message,"bad"); }
    finally { btn.disabled = false; }
  });
  inp.addEventListener("keydown", (e)=>{ if(e.key==="Enter") btn.click(); });
}
export async function load() {
  bindGroupsAdd();
  const bridge = getBridge();
  const box = document.getElementById("groupsBody");
  if (!box) return;
  if (!bridge) { box.innerHTML = `<tr><td colspan="5">桥接未就绪</td></tr>`; return; }
  box.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try {
    const data = await bridge.apiGet("groups/list");
    const groups = data.groups || data || [];
    if (!groups.length) {
      box.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">暂无群聊（发送任意指令后自动收录）<br><small>可上方手动输入群号添加</small></td></tr>`;
      return;
    }
    box.innerHTML = groups.map(g => {
      const gid = g.gid;
      const on = g.enabled !== false;
      const badge = on ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-danger">关闭</span>`;
      const testMark = g.is_test ? ` <small style="color:var(--muted)">(测试)</small>` : "";
      return `<tr><td><code>${gid}</code>${testMark}</td><td>${g.member_count||0}</td><td>${badge}</td><td><label class="switch"><input type="checkbox" data-gid="${gid}" ${on?"checked":""}><span class="slider-toggle"></span></label></td><td><button class="ghost sm del" data-del="${gid}" title="删除该群配置">🗑️ 删除</button></td></tr>`;
    }).join("");
    box.querySelectorAll("input[data-gid]").forEach(inp => {
      inp.addEventListener("change", async () => {
        const gid = inp.dataset.gid;
        const on = inp.checked;
        inp.disabled = true;
        const row = inp.closest("tr");
        const badgeCell = row ? row.cells[2] : null;
        try{
          const r = await bridge.apiPost("groups/toggle", { gid, enabled: on });
          if (r && r.ok === false) throw new Error(r.msg||"切换失败");
          // 以服务端返回为准，避免 list 缓存导致回显旧值
          const serverOn = (r && typeof r.enabled === "boolean") ? r.enabled : on;
          toast(`群 ${gid} 已${serverOn?"开启":"关闭"}`, serverOn?"ok":"bad");
          if (badgeCell) badgeCell.innerHTML = serverOn ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-danger">关闭</span>`;
          inp.checked = serverOn;
        }catch(e){ toast("切换失败: "+e.message,"bad"); inp.checked = !on; if (badgeCell) badgeCell.innerHTML = !on ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-danger">关闭</span>`; }
        finally{ inp.disabled = false; }
      });
    });
    box.querySelectorAll("[data-del]").forEach(btn=>{
      btn.addEventListener("click", async ()=>{
        const gid = btn.dataset.del;
        let ok = true;
        try {
          ok = window.confirm ? window.confirm(`确认删除群 ${gid} 的开关配置？\n删除后该群将从列表移除（不删用户数据）`) : true;
        } catch(e) {
          ok = true;
        }
        if (!ok) return;
        try{
          await bridge.apiPost("groups/delete", { gid });
          toast("已删除 "+gid,"ok");
          await load();
        }catch(e){ toast("删除失败: "+e.message,"bad"); }
      });
    });
  } catch (e) {
    box.innerHTML = `<tr><td colspan="5">加载失败: ${e.message} <button class="ghost sm" onclick="location.reload()">重试</button></td></tr>`;
  }
}
export default { load };
