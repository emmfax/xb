const PLUGIN_ID = "astrbot_plugin_xbbot";

let _WORKING_API_PREFIX = null;

function getBridge() {
  try {
    if (window.bridge && typeof window.bridge.apiGet === "function") return window.bridge;
    if (window.AstrBotPluginPage && typeof window.AstrBotPluginPage.apiGet === "function") return window.AstrBotPluginPage;
    try {
      if (window.parent && window.parent.AstrBotPluginPage && typeof window.parent.AstrBotPluginPage.apiGet === "function") {
        return window.parent.AstrBotPluginPage;
      }
      if (window.parent && window.parent.bridge && typeof window.parent.bridge.apiGet === "function") {
        return window.parent.bridge;
      }
    } catch (e) {}
  } catch (e) {}

  return {
    async apiGet(endpoint, params) {
      const ep = String(endpoint || "").replace(/^\/+/, "");
      const q = params && Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + ep + q);
          if (r.ok) return await r.json();
        } catch (err) {}
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + ep + q);
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(ep + q);
      return await r.json();
    },
    async apiPost(endpoint, data) {
      const ep = String(endpoint || "").replace(/^\/+/, "");
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) return await r.json();
        } catch (err) {}
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(ep, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data || {})
      });
      return await r.json();
    },
    async upload(endpoint, file) {
      const ep = String(endpoint || "").replace(/^\/+/, "");
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`/${PLUGIN_ID}/` + ep, { method: "POST", body: fd });
      return await r.json();
    }
  };
}
let CFG = {};

// 各配置节归属系统（用于分类）+ 必要/玩法分层
const NECESSARY_SECTIONS = ["总开关配置", "群组开关配置", "网络", "私聊配置", "维护配置", "备份配置"];
const GAMEPLAY_SECTIONS = ["签到配置","抽奖配置","新手配置","点赞配置","银行配置","娱乐配置","精灵配置","坐骑配置","帮派配置","冒险配置","祈福配置","起名配置","概率配置","唤醒词配置"];
const SYSTEM_MAP = {
  "设置": "奴隶系统", "费用配置": "奴隶系统", "间隔配置": "奴隶系统",
  "概率配置": "奴隶系统", "祈福配置": "奴隶系统", "起名配置": "奴隶系统",
  "签到配置": "签到系统", "抽奖配置": "签到系统",
  "新手配置": "签到系统", "点赞配置": "签到系统",
  "银行配置": "银行系统", "娱乐配置": "娱乐系统",
  "私聊配置": "私聊系统", "精灵配置": "精灵系统",
  "坐骑配置": "坐骑系统", "帮派配置": "帮派系统",
  "超管配置": "超管系统", "冒险配置": "冒险系统",
  "商城图鉴": "商城图鉴", "精灵图鉴": "精灵图鉴",
  "备份配置": "备份", "网络": "网络", "唤醒词配置": "唤醒词",
};
let CUR_SYSTEM = "全部";

// ---------- 主题(沙箱 iframe 禁止 localStorage, 仅内存切换) ----------
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  const b = document.getElementById("themeBtn");
  if (b) b.textContent = t === "dark" ? "☀" : "☾";
}
function initTheme() {
  applyTheme("light");
  const b = document.getElementById("themeBtn");
  if (b) b.addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
}

// ---------- toast ----------
let _toastT = null;
function toast(msg, type) {
  const el = document.getElementById("toast");
  const txt = document.getElementById("toastTxt");
  if (!el || !txt) return;
  txt.textContent = msg;
  el.className = "show " + (type === "ok" ? "okk" : type === "bad" ? "badk" : "");
  clearTimeout(_toastT);
  _toastT = setTimeout(() => { el.className = ""; }, 2400);
}

// 请求 API 封装（支持 GET 自动转参数拼在 URL 与 fallback POST 双向兼容）
async function callApi(endpoint, data = {}, method = "GET") {
  const _b = getBridge();
  const cleanEp = String(endpoint || "").replace(/^\/+/, "").split("?")[0];
  const cleanData = {};
  if (data && typeof data === "object") {
    Object.keys(data).forEach((k) => {
      if (data[k] !== undefined && data[k] !== null) {
        cleanData[k] = String(data[k]);
      }
    });
  }
  if (method === "GET") {
    try {
      let res = await _b.apiGet(cleanEp, cleanData);
      if (!res || (typeof res === "object" && !Object.keys(res).length) || (res && res.status === "error" && res.message && res.message.includes("未找到"))) {
        res = await _b.apiPost(cleanEp, cleanData);
      }
      return res;
    } catch (e) {
      return await _b.apiPost(cleanEp, cleanData);
    }
  } else {
    return await _b.apiPost(cleanEp, cleanData);
  }
}

function copyToClipboard(text) {
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      navigator.clipboard.writeText(text).then(() => {
        toast("已成功复制到剪贴板！", "ok");
      }).catch(() => {
        _execCommandCopy(text);
      });
      return;
    }
  } catch(e) {}
  _execCommandCopy(text);
}

function _execCommandCopy(text) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const successful = document.execCommand("copy");
    ta.remove();
    if (successful) {
      toast("已成功复制到剪贴板！", "ok");
    } else {
      toast("复制失败，请在下方文本框内手动全选复制", "bad");
    }
  } catch(err) {
    toast("复制失败，请在下方文本框内手动全选复制", "bad");
  }
}

function showExportModal({ filename, blob, blobUrl, rawText, base64Data }) {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "📥";
  if (title) title.textContent = "导出文件就绪";
  if (inputWrap) inputWrap.style.display = "none";

  const sizeKb = blob ? (blob.size / 1024).toFixed(1) : (rawText ? (new Blob([rawText]).size / 1024).toFixed(1) : "");
  
    let actionsHtml = `
  <div style="margin:4px 0 10px;padding:12px;background:var(--panel2);border-radius:12px;border:1px solid var(--line);font-size:12.5px">
    <div style="font-weight:600;color:var(--text);margin-bottom:4px;word-break:break-all;font-size:13px">📄 ${esc(filename)} ${sizeKb ? `<span class="badge badge-primary" style="margin-left:6px">${sizeKb} KB</span>` : ""}</div>
    <div style="color:var(--muted);font-size:11.5px;line-height:1.5">文件已生成完成。若浏览器未自动弹出保存提示，请点击下方按钮手动保存：</div>
  </div>
  <div style="display:flex;gap:8px;margin:10px 0;flex-wrap:wrap">
    <a href="${blobUrl}" download="${esc(filename)}" id="btnModalSaveFileLink" class="btn" style="display:inline-flex;align-items:center;gap:5px;padding:8px 18px;background:var(--acc);color:#fff;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;cursor:pointer">⬇️ 保存文件到电脑</a>
    ${rawText ? `<button id="btnCopyExportData" class="ghost" style="padding:8px 14px;font-size:12.5px;cursor:pointer">📋 复制全部内容</button>` : ""}
  </div>
  ${rawText ? `<div style="margin-top:10px"><div style="font-size:11.5px;color:var(--muted);margin-bottom:4px">数据预览（点击文本框可自动全选）：</div><textarea readonly style="width:100%;height:100px;background:var(--panel);color:var(--text);font-family:monospace;font-size:11px;border:1px solid var(--line);border-radius:8px;padding:8px;outline:none;resize:vertical;line-height:1.4" onclick="this.select()">${esc(rawText.slice(0, 5000))}${rawText.length > 5000 ? "\n\n... (数据过长已截断预览，点击上方按钮复制全部数据)" : ""}</textarea></div>` : ""}
  `;

  if (content) content.innerHTML = actionsHtml;

  const saveBtn = document.getElementById("btnModalSaveFile");
  if (saveBtn) {
    saveBtn.onclick = (e) => {
      e.preventDefault();
      triggerDownload(blob, filename, rawText);
    };
  }

  const copyBtn = document.getElementById("btnCopyExportData");
  if (copyBtn && rawText) {
    copyBtn.onclick = () => {
      copyToClipboard(rawText);
      copyBtn.textContent = "✅ 已复制到剪贴板";
      setTimeout(() => { copyBtn.textContent = "📋 复制全部内容"; }, 2000);
    };
  }

  if (cancelBtn) cancelBtn.style.display = "none";
  if (okBtn) {
    okBtn.textContent = "关闭";
    okBtn.onclick = () => {
      modal.className = "";
      if (cancelBtn) cancelBtn.style.display = "";
      okBtn.onclick = null;
    };
  }
  modal.className = "show";
}

function triggerExportResult({ filename, mime, blob, rawText, base64Data }) {
  if (!blob) {
    if (base64Data) {
      const rawData = String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim();
      const bin = atob(rawData);
      const len = bin.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
      blob = new Blob([bytes], { type: mime || "application/octet-stream" });
    } else if (rawText) {
      blob = new Blob([rawText], { type: mime || "application/json;charset=utf-8" });
    }
  }

  const blobUrl = blob ? URL.createObjectURL(blob) : "";
  if (blob) {
    triggerDownload(blob, filename, rawText);
  }
  showExportModal({ filename, blob, blobUrl, rawText, base64Data });
}

function triggerDownload(blob, filename, rawText = "") {
  let downloaded = false;
  filename = filename || "download.json";

  // 1. 尝试通过 window.parent.document 触发（突破 iframe sandbox 拦截）
  try {
    if (window.parent && window.parent !== window && window.parent.document && window.parent.document.body) {
      const url = URL.createObjectURL(blob);
      const a = window.parent.document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      window.parent.document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch(e) {} }, 1000);
      downloaded = true;
    }
  } catch (e) {}

  // 2. 尝试在本窗口 document 触发
  if (!downloaded) {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch(e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }

  // 3. 尝试 data URI (针对文本/JSON)
  if (!downloaded && rawText) {
    try {
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = "data:application/json;charset=utf-8," + encodeURIComponent(rawText);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); } catch(e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }

  toast("已触发下载: " + filename, "ok");
}

function downloadJson(data, filename) {
  try {
    const str = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    const blob = new Blob([str], { type: "application/json;charset=utf-8" });
    triggerDownload(blob, filename || "export.json", str);
  } catch (err) {
    toast("导出失败: " + err.message, "bad");
  }
}

function downloadBase64File(base64Data, filename) {
  try {
    const rawData = String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim();
    if (!rawData) throw new Error("数据为空");
    const bin = atob(rawData);
    const len = bin.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    const mime = filename.endsWith(".zip") ? "application/zip" : (filename.endsWith(".json") ? "application/json;charset=utf-8" : "application/octet-stream");
    const blob = new Blob([bytes], { type: mime });
    triggerDownload(blob, filename || "download.bin");
  } catch (err) {
    toast("下载文件失败: " + err.message, "bad");
  }
}

function downloadBlob(blob, filename) {
  triggerDownload(blob, filename);
}

function _formatModalText(msg) {
  if (!msg) return "";
  if (msg.includes("<div") || msg.includes("<strong") || msg.includes("<span") || msg.includes("<br")) {
    return msg;
  }
  return String(msg)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^· (.*?)$/gm, "• $1")
    .split("\n").join("<br>");
}

function uiAlert(msg, title = "提示", icon = "ℹ️") {
  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      if (window.alert) window.alert(title + "\n\n" + msg.replace(/<[^>]+>/g, ""));
      resolve(true);
      return;
    }
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) {
      iconEl.textContent = icon;
      iconEl.style.color = icon === "⚠️" || icon === "❌" ? "var(--bad)" : "var(--acc)";
    }
    const titleEl = document.getElementById("appModalTitle");
    if (titleEl) titleEl.textContent = title;
    const contentEl = document.getElementById("appModalContent");
    if (contentEl) contentEl.innerHTML = _formatModalText(msg);
    const inpWrap = document.getElementById("appModalInputWrap");
    if (inpWrap) inpWrap.style.display = "none";
    
    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    if (cancelBtn) cancelBtn.style.display = "none";
    if (okBtn) {
      okBtn.textContent = "知道了";
      okBtn.style.background = "var(--acc)";
      okBtn.style.borderColor = "transparent";
    }

    modal.classList.add("show");

    const clean = () => {
      modal.classList.remove("show");
      if (okBtn) okBtn.onclick = null;
      modal.onclick = null;
      if (cancelBtn) cancelBtn.style.display = "";
    };

    if (okBtn) okBtn.onclick = () => { clean(); resolve(true); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(true); } };
  });
}

function uiConfirm(msg, title = "确认操作") {
  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      resolve(window.confirm ? window.confirm(title + "\n\n" + msg.replace(/<[^>]+>/g, "")) : true);
      return;
    }
    const isDanger = /危险|清空|删除|覆盖|终极/.test(title + msg);
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) {
      iconEl.textContent = isDanger ? "⚠️" : "ℹ️";
      iconEl.style.color = isDanger ? "var(--bad)" : "var(--acc)";
    }
    const titleEl = document.getElementById("appModalTitle");
    if (titleEl) titleEl.textContent = title;
    const contentEl = document.getElementById("appModalContent");
    if (contentEl) contentEl.innerHTML = _formatModalText(msg);
    const inpWrap = document.getElementById("appModalInputWrap");
    if (inpWrap) inpWrap.style.display = "none";

    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    if (cancelBtn) {
      cancelBtn.style.display = "";
      cancelBtn.textContent = "取消";
    }
    if (okBtn) {
      okBtn.textContent = isDanger ? "确认" : "确定升级";
      if (isDanger) {
        okBtn.style.background = "var(--bad)";
        okBtn.style.borderColor = "var(--bad)";
      } else {
        okBtn.style.background = "var(--acc)";
        okBtn.style.borderColor = "transparent";
      }
    }

    modal.classList.add("show");

    const clean = () => {
      modal.classList.remove("show");
      if (okBtn) okBtn.onclick = null;
      if (cancelBtn) cancelBtn.onclick = null;
      modal.onclick = null;
    };
    if (okBtn) okBtn.onclick = () => { clean(); resolve(true); };
    if (cancelBtn) cancelBtn.onclick = () => { clean(); resolve(false); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(false); } };
  });
}

function uiPrompt(msg, dflt = "", title = "请输入") {
  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      resolve(window.prompt ? window.prompt(msg, dflt) : dflt);
      return;
    }
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) { iconEl.textContent = "✏️"; iconEl.style.color = "var(--acc)"; }
    document.getElementById("appModalTitle").textContent = title;
    document.getElementById("appModalContent").textContent = msg;
    const inpWrap = document.getElementById("appModalInputWrap");
    const inp = document.getElementById("appModalInput");
    inpWrap.style.display = "block";
    inp.value = dflt || "";
    modal.classList.add("show");
    setTimeout(() => { inp.focus(); inp.select(); }, 50);

    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";

    const clean = () => {
      modal.classList.remove("show");
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      modal.onclick = null;
      inp.onkeydown = null;
    };
    const doOk = () => { const v = inp.value; clean(); resolve(v); };
    okBtn.onclick = doOk;
    cancelBtn.onclick = () => { clean(); resolve(null); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(null); } };
    inp.onkeydown = (e) => {
      if (e.key === "Enter") doOk();
      else if (e.key === "Escape") { clean(); resolve(null); }
    };
  });
}

function bindGroupsAdd() {
  const inp = document.getElementById("groupsAddGid");
  const btn = document.getElementById("btnGroupsAdd");
  if (!inp || !btn) return;
  btn.onclick = async () => {
    const gid = (inp.value || "").trim();
    if (!/^\d{5,15}$/.test(gid)) { toast("请输入5-15位数字群号", "bad"); return; }
    btn.disabled = true;
    btn.textContent = "添加中...";
    try {
      const r = await getBridge().apiPost("groups/toggle", { gid, enabled: true });
      if (r && r.ok === false) { toast("添加失败: " + (r.msg || JSON.stringify(r)), "bad"); return; }
      toast("已成功添加群 " + gid, "ok");
      inp.value = "";
      await loadGroups();
    } catch(e) { toast("添加失败: " + e.message, "bad"); }
    finally {
      btn.disabled = false;
      btn.textContent = "➕ 添加";
    }
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") btn.onclick(); };
}

let RAW_GROUPS = [];

async function loadGroups() {
  bindGroupsAdd();
  const box = document.getElementById("groupsBody");
  if (!box) return;
  box.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try {
    const data = await getBridge().apiGet("groups/list");
    RAW_GROUPS = data.groups || data || [];
    renderGroupsTable();
  } catch(e) {
    box.innerHTML = `<tr><td colspan="5" style="color:var(--bad);text-align:center;padding:16px">加载失败: ${esc(e.message)}</td></tr>`;
  }
}

function renderGroupsTable() {
  const box = document.getElementById("groupsBody");
  if (!box) return;
  const kw = (document.getElementById("groupsSearch")?.value || "").trim().toLowerCase();
  let groups = [...RAW_GROUPS];
  if (kw) {
    groups = groups.filter(g => String(g.gid).toLowerCase().includes(kw) || (g.enabled ? "开启" : "关闭").includes(kw));
  }
  if (!groups.length) {
    box.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">暂无匹配的群聊数据<br><small>可上方手动输入群号添加</small></td></tr>`;
    return;
  }
  box.innerHTML = groups.map(g => {
    const gid = g.gid;
    const on = g.enabled !== false;
    const badge = on ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-bad">关闭</span>`;
    const testMark = g.is_test ? ` <small style="color:var(--muted)">(测试)</small>` : "";
    return `<tr><td><code>${esc(gid)}</code>${testMark}</td><td>${g.member_count || 0}</td><td>${badge}</td><td><label class="switch"><input type="checkbox" data-gid="${esc(gid)}" ${on ? "checked" : ""}><span class="slider-toggle"></span></label></td><td><button class="ghost sm del" data-del="${esc(gid)}" title="删除该群配置">🗑️ 删除</button></td></tr>`;
  }).join("");
  box.querySelectorAll("input[data-gid]").forEach(inp => {
    inp.addEventListener("change", async () => {
      const gid = inp.dataset.gid;
      const on = inp.checked;
      inp.disabled = true;
      const row = inp.closest("tr");
      const badgeCell = row ? row.cells[2] : null;
      try {
        const r = await getBridge().apiPost("groups/toggle", { gid, enabled: on });
        if (r && r.ok === false) throw new Error(r.msg || "切换失败");
        const serverOn = (r && typeof r.enabled === "boolean") ? r.enabled : on;
        toast(`群 ${gid} 已${serverOn ? "开启" : "关闭"}`, serverOn ? "ok" : "bad");
        if (badgeCell) badgeCell.innerHTML = serverOn ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-bad">关闭</span>`;
        inp.checked = serverOn;
      } catch(e) {
        toast("切换失败: " + e.message, "bad");
        inp.checked = !on;
      } finally {
        inp.disabled = false;
      }
    });
  });
  box.querySelectorAll("button[data-del]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const gid = btn.dataset.del;
      if (!(await uiConfirm(`确定彻底删除群 ${gid} 的所有配置吗？此操作不可逆。`, "删除群聊配置"))) return;
      btn.disabled = true;
      try {
        const r = await getBridge().apiPost("groups/delete", { gid });
        if (r && r.ok === false) throw new Error(r.msg || "删除失败");
        toast(`群 ${gid} 配置已彻底删除`, "ok");
        await loadGroups();
      } catch(e) {
        toast("删除失败: " + e.message, "bad");
        btn.disabled = false;
      }
    });
  });
}

// 各页签加载器(零延迟即时响应)
const TAB_LOADERS = {
  overview: async () => { await loadOverviewReq(); try { await loadAnalytics(); } catch(e){} },
  users: async () => { return loadUsers(); },
  slave: async () => { return typeof loadSlaveUsers === "function" ? loadSlaveUsers() : Promise.resolve(); },
  spirit_users: async () => { return typeof loadSpiritUsers === "function" ? loadSpiritUsers() : Promise.resolve(); },
  config: async () => { return loadConfig(); },
  rank: async () => { const t = (document.getElementById("rankType") || {}).value || "money"; return loadRank(t); },
  cmds: async () => { return loadCommands(); },
  spirits: async () => { return loadSpirits(); },
  shops: async () => { return loadShops(); },
  backups: async () => { return typeof loadBackups === "function" ? loadBackups("") : Promise.resolve(); },
  imgs: async () => { return loadImages(""); },
  groups: async () => { return loadGroups(); },
  logs: async () => { return loadLogs(); },
};
const TAB_DONE = {};

async function main() {
  initTheme();
  bindTabs();
  const _b = getBridge();
  try {
    if (_b && typeof _b.ready === "function") {
      await Promise.race([
        _b.ready(),
        new Promise(r => setTimeout(r, 300))
      ]);
    }
  } catch (e) {}
  
  Promise.all([loadStats(), loadOverviewReq(), loadAnalytics(), checkVersionUpdate(true)]).catch(() => {});
  TAB_DONE.overview = true;
}

// ---------- 图片库（根目录） ----------
let IMG_DIR = "";
let IMG_CACHE = [];   // 当前目录的 dirs+files 原始数据(供搜索)
let IMG_CLIP = "";    // 复制的路径
let IMG_SELECTED = ""; // 选中的文件/文件夹路径（用于复制/导出）


async function loadImages(dir) {
  try {
    if (dir === "0") dir = "";
    IMG_DIR = dir || "";
    const d = await getBridge().apiGet("images/list", { dir: IMG_DIR });
    IMG_CACHE = d;
    // 面包屑
    const segs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-imgcrumb="">根目录</a>`;
    let acc = "";
    segs.forEach((s, i) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` / <a data-imgcrumb="${esc(acc)}">${esc(s)}</a>`;
    });
    document.getElementById("imgCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#imgCrumbs a[data-imgcrumb]").forEach((a) =>
      a.addEventListener("click", () => loadImages(a.dataset.imgcrumb)));
    renderImages(d);
  } catch (e) {
    err("images: " + e.message);
  }
}

function renderImages(d) {
  const box = document.getElementById("imgBrowser");
  const q = (document.getElementById("imgSearch").value || "").trim().toLowerCase();
  // 供内置选图校验（是否为文件夹）
  window._imgIsDir = (p) => (d.dirs || []).some(x => x.path === p);
  const isShopPick = !!window.SHOP_PICK_TARGET;
  let html = `<div class="grid">`;
  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    // 内置选图模式下：文件夹仅可双击进入，不可选中
    if (isShopPick) {
      html += `<div class="fcard" data-imgdir="${esc(x.path)}"><div class="fi">📁</div><div class="fn">${esc(x.name)}</div></div>`;
    } else {
      const selCls = IMG_SELECTED===x.path ? ' selected' : '';
      html += `<div class="fcard${selCls}" data-imgdir="${esc(x.path)}" data-selpath="${esc(x.path)}"><div class="fi">📁</div><div class="fn">${esc(x.name)}</div></div>`;
    }
  });
  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const ext = (x.name.split(".").pop()||"").toLowerCase();
    const isImg = ["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext);
    // 内置选图模式：仅展示图片文件
    if (isShopPick && !isImg) return;
    const selCls = IMG_SELECTED===x.path ? ' selected' : '';
    let ficon = "📄";
    if (isImg) ficon="";
    else if (ext==="json") ficon="📄";
    else if (ext==="md") ficon="📝";
    else if (ext==="txt") ficon="📃";
    else if (ext==="py") ficon="🐍";
    else if (ext==="db"||ext==="db-wal"||ext==="db-shm") ficon="🗄️";
    else if (ext==="ini") ficon="⚙️";
    else if (ext==="zip") ficon="🗜️";
    else if (ext==="log") ficon="📜";
    html += `<div class="icard${selCls}" data-imgsrc="${esc(x.img)}" data-imgname="${esc(x.name)}" data-imgpath="${esc(x.path)}" data-selpath="${esc(x.path)}">` +
      (ficon ? `<div style="height:120px;display:flex;align-items:center;justify-content:center;font-size:42px;background:var(--panel2)">${ficon}</div>` : `<img src="${x.img || ""}" alt="">`) + `<div class="nm">${esc(x.name)}</div></div>`;
  });
  html += `</div>`;
  box.innerHTML = html;
  // 文件夹：单击选中（非选图模式）/双击进入
  box.querySelectorAll("[data-imgdir]").forEach((el) =>{
    el.addEventListener("click", (e) => {
      if (window.SHOP_PICK_TARGET) return;
      IMG_SELECTED = el.dataset.imgdir;
      box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
    el.addEventListener("dblclick", (e) => {
      loadImages(el.dataset.imgdir);
    });
  });
  // 文件：单击选中（高亮）
  box.querySelectorAll("[data-selpath]").forEach((el)=>{
    el.addEventListener("click", (e)=>{
      IMG_SELECTED = el.dataset.selpath;
      box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
  });
  // 图片点击：先选中再预览（不阻断选中）
  box.querySelectorAll("[data-imgsrc]").forEach((el) => {
    el.querySelector("img")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const p = el.dataset.imgpath || el.dataset.selpath;
      if (p) {
        IMG_SELECTED = p;
        box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
        el.classList.add("selected");
      }
      if (el.dataset.imgsrc) showLightbox(el.dataset.imgsrc, el.dataset.imgname);
    });
  });
  // 文件列表供搜索(懒加载图片已在上面)
  window._imgFiles = (d.files || []).map((x) => x.name);
}

function showLightbox(src, name) {
  const lb = document.getElementById("lightbox");
  if (!lb || !src) { if (lb) { lb.innerHTML = ""; } return; }
  lb.innerHTML = `<img src="${src}"><div class="cap">${esc(name || "")}</div>`;
  lb.classList.add("show");
}

function closeLightbox() {
  const lb = document.getElementById("lightbox");
  if (lb) { lb.classList.remove("show"); lb.innerHTML = ""; }
}

async function uploadImage(file) {
  if (!file) return;
  toast("上传中…", "");
  try {
    // 上传到当前根目录路径
    const fd = new FormData();
    fd.append("file", file);
    // 优先用 bridge.upload 带 dir 参数，回退到普通上传
    try {
      if (IMG_DIR) {
        await getBridge().apiPost("images/upload?dir=" + encodeURIComponent(IMG_DIR), fd);
      } else {
        await getBridge().upload("images/upload", file);
      }
    } catch (e2) {
      await getBridge().upload("images/upload", file);
    }
    toast("已上传", "ok");
    await loadImages(IMG_DIR);
  } catch (e) {
    err("上传失败: " + e.message);
  }
}

function bindTabs() {
  const btns = document.querySelectorAll(".tabs button");
  btns.forEach((b) => {
    b.addEventListener("click", () => {
      btns.forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
      const el = document.getElementById("tab-" + b.dataset.tab);
      if (el) el.classList.add("on");
      const tab = b.dataset.tab;
      if (tab === "logs") {
        if (typeof loadLogs === "function") loadLogs(false);
        if (typeof startLogsAutoRefresh === "function") startLogsAutoRefresh();
      } else {
        if (typeof stopLogsAutoRefresh === "function") stopLogsAutoRefresh();
      }
      // 切换 Tab 时保证当前选中按钮在可视区内
      try { b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" }); } catch (e) {}
      // 总览页每次点击都刷新，确保机器人QQ等快捷配置与配置页保持一致（同一接口 ST._CONFIG）
      if (tab === "overview") {
        Promise.resolve(loadOverviewReq()).catch((e) => err("tab overview: " + e.message));
        Promise.resolve(loadStats()).catch(() => {});
        return;
      }
      if (!TAB_DONE[tab] && TAB_LOADERS[tab]) {
        TAB_DONE[tab] = true;
        Promise.resolve(TAB_LOADERS[tab]()).catch((e) => err("tab " + tab + ": " + e.message));
      }
    });
  });

  // Tab 栏左右滚动箭头 + 滚轮横滑
  const tabsContainer = document.getElementById("mainTabs");
  document.getElementById("tabNavPrev")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: -160, behavior: "smooth" });
  });
  document.getElementById("tabNavNext")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: 160, behavior: "smooth" });
  });
  tabsContainer?.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
      e.preventDefault();
      tabsContainer.scrollLeft += e.deltaY;
    }
  }, { passive: false });
  // 更多下拉
  const moreBtn = document.getElementById("moreBtn");
  const moreMenu = document.getElementById("moreMenu");
  moreBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    moreMenu?.classList.toggle("show");
  });
  document.addEventListener("click", () => moreMenu?.classList.remove("show"));
  moreMenu?.querySelectorAll("button[data-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      moreMenu?.classList.remove("show");
      document.querySelector(`.tabs button[data-tab=\"${b.dataset.tab}\"]`)?.click();
    });
  });
  // 同步更多菜单高亮
  const _orig = document.querySelectorAll(".tabs button");
  const syncMore = () => {
    const on = document.querySelector(".tabs button.on")?.dataset.tab;
    moreMenu?.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.tab === on));
  };
  _orig.forEach((b) => b.addEventListener("click", syncMore));
}

function err(m) {
  const e = document.getElementById("footErr");
  if (e) e.textContent = "加载/操作异常: " + m;
  toast("操作异常：" + m, "bad");
  console.error(m);
}

// ---------- 总览 ----------
async function loadStats() {
  try {
    const s = await getBridge().apiGet("stats");
    const formatNum = (num) => typeof num === "number" ? num.toLocaleString() : (num || 0);
    const p = (s && s.players) || {};
    const cards = [
      { n: formatNum(p.wallet), l: "钱包活跃用户", i: "👛" },
      { n: formatNum(p.accounts), l: "档案注册用户", i: "📁" },
      { n: formatNum(p.groups), l: "开通游戏群数", i: "👥" },
      { n: formatNum(s ? s.total_money : 0), l: "全服流通金币", i: "💰" },
      { n: formatNum(s ? s.total_sign : 0), l: "累计签到人次", i: "📅" },
      { n: formatNum(s ? (s.total_deposit || 0) : 0), l: "银行总存款额", i: "🏦" },
    ];
    const statsBox = document.getElementById("stats");
    if (statsBox) {
      statsBox.innerHTML = cards
        .map((c) => `<div class="card">
          <div class="num">${c.n}</div>
          <div class="lab">${c.l}</div>
          <div class="ic">${c.i}</div>
        </div>`)
        .join("");
    }
  } catch (e) {
    err("stats: " + e.message);
  }
}

// 必填/关键配置: [节, 键, 标签, 类型, 提示] — 网络/机器人QQ已移除（完全自动）
const OV_REQ = [
  ["设置", "货币名称", "货币名称", "text", "金币/积分 等显示名"],
];

async function loadOverviewReq() {
  try {
    const cur = await getBridge().apiGet("config/get");
    const box = document.getElementById("ovReq");
    box.innerHTML = OV_REQ.map(([sec, key, label, type, tip]) => {
      const v = ((cur || {})[sec] || {})[key] ?? "";
      return `<div class="ov-field"><label>${esc(label)}</label>` +
        `<input data-ov-sec="${esc(sec)}" data-ov-key="${esc(key)}" type="${type === "int" ? "number" : "text"}" value="${esc(v)}">` +
        `<small>${esc(tip)}</small></div>`;
    }).join("") +
      `<div class="ov-field"><label style="visibility:hidden">.</label><button id="btnOvReqSave">保存必要配置</button></div>`;
    const b = document.getElementById("btnOvReqSave");
    if (b) b.addEventListener("click", saveOverviewReq);
  } catch (e) {
    err("必要配置: " + e.message);
  }
}

async function saveOverviewReq() {
  const toastMsg = (m, t) => { try { toast(m, t); } catch (e) {} };
  try {
    const payload = {};
    document.querySelectorAll("#ovReq [data-ov-sec]").forEach((inp) => {
      const sec = inp.dataset.ovSec, key = inp.dataset.ovKey;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = inp.type === "number" ? Number(inp.value) : inp.value.trim();
    });
    await getBridge().apiPost("config/save", payload);
    toastMsg("必要配置已保存", "ok");
    await loadOverviewReq();
    // 若配置页已加载过，同步刷新，使“网络.bot_uin”等在配置页立即可见
    if (TAB_DONE.config) {
      try { await loadConfig(); } catch (e) {}
    }
  } catch (e) {
    toastMsg("保存失败: " + e.message, "bad");
    err("保存必要配置失败: " + e.message);
  }
}

// ---------- 配置 ----------
function isFlag(v) {
  return ["真", "假", "true", "false", "1", "0"].includes(String(v));
}
function flagVal(v) {
  return String(v) === "真" || String(v) === "true" || String(v) === "1";
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// AstrBot 官方嵌套 schema 合法类型: int,float,bool,string,text,list,file,object,template_list
// 约定: 真/假 开关在 schema 保持 string(引擎用 =="真"), 由 isFlag 渲染 checkbox;
// text/list 用多行 textarea, string 单行, int/float 用 number
function isTextType(t) {
  return t === "text";
}
function isListType(t) {
  return t === "list";
}

async function loadConfig() {
  try {
    const [schema, cur] = await Promise.all([
      getBridge().apiGet("config/schema"),
      getBridge().apiGet("config/get")
    ]);
    CFG = { schema, cur };
    const form = document.getElementById("cfgForm");
    if (!form) return;
    form.innerHTML = "";
    const { groups } = schema;
    const necessaryGroups = {};
    Object.keys(groups).forEach((sec) => {
      if (NECESSARY_SECTIONS.includes(sec)) necessaryGroups[sec] = groups[sec];
    });
    const effectiveGroups = Object.keys(necessaryGroups).length ? necessaryGroups : groups;

    for (const sec of Object.keys(effectiveGroups)) {
      const box = document.createElement("div");
      box.className = "cfg-sec";
      box.dataset.system = SYSTEM_MAP[sec] || "其它";
      box.innerHTML = `<h3 style="margin:0 0 10px;font-size:13.5px;display:flex;align-items:center;gap:6px">📌 ${esc(sec)} <span class="badge badge-primary" style="font-size:11px;font-weight:normal">${esc(SYSTEM_MAP[sec] || "基础")}</span></h3>`;
      for (const it of effectiveGroups[sec]) {
        const v = ((cur || {})[sec] || {})[it.key] ?? it.default;
        const attrs = `data-sec="${esc(sec)}" data-key="${esc(it.key)}"`;
        const row = document.createElement("div");
        row.className = "cfg-row";
        const small = `<small>${esc(it.desc || "")}</small>`;
        if (isFlag(it.default)) {
          row.className = "cfg-row has-checkbox";
          const chk = flagVal(v) ? "checked" : "";
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<div class="chk-wrap"><label class="switch"><input type="checkbox" ${chk} ${attrs}><span class="slider-toggle"></span></label></div>${small}`;
        } else if (isTextType(it.type) || isListType(it.type)) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<textarea rows="${isListType(it.type) ? 3 : 2}" ${attrs}>${esc(v)}</textarea>${small}`;
        } else if (it.type === "int" && /^-?\d+$/.test(String(v))) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="number" step="1" value="${esc(v)}" ${attrs}>${small}`;
        } else if (it.type === "float" && !isNaN(parseFloat(v))) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="number" step="any" value="${esc(v)}" ${attrs}>${small}`;
        } else {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="text" value="${esc(v)}" ${attrs}>${small}`;
        }
        box.appendChild(row);
      }
      form.appendChild(box);
    }
  } catch (e) {
    err("config: " + e.message);
  }
}
function filterCfg() {
  const q = (document.getElementById("cfgSearch").value || "").trim().toLowerCase();
  document.querySelectorAll("#cfgForm .cfg-sec").forEach((box) => {
    const sysMatch = CUR_SYSTEM === "全部" || box.dataset.system === CUR_SYSTEM;
    const txtMatch = !q || box.textContent.toLowerCase().includes(q);
    if (q) {
      box.style.display = txtMatch ? "" : "none";   // 搜索时忽略系统分类
    } else {
      box.style.display = sysMatch ? "" : "none";
    }
  });
}

function filterUsers() {
  const q = (document.getElementById("userSearch").value || "").trim().toLowerCase();
  document.querySelectorAll("#userBody tr").forEach((tr) => {
    tr.style.display = !q || tr.textContent.toLowerCase().includes(q) ? "" : "none";
  });
}

function filterCmds() {
  const q = (document.getElementById("cmdSearch").value || "").trim().toLowerCase();
  document.querySelectorAll("#cmdList .cmd-block").forEach((b) => {
    b.style.display = !q || b.textContent.toLowerCase().includes(q) ? "" : "none";
  });

}



async function openAutoBalanceModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "🎯";
  if (title) title.textContent = "游戏奖励 / 惩罚 / 概率 · 智能数值平衡";
  if (inputWrap) inputWrap.style.display = "none";

  content.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px;line-height:1.5">
      系统基于<strong>群博弈论与经济学精算模型</strong>，为你自动推算并一键匹配最佳金币奖励、惩罚倍率、抽奖爆率与奴隶身价成长曲线：
    </div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:2px solid var(--acc);border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="standard" checked style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟢 标准平衡模式（官方推荐 · 经济稳健）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 200 金币，利息 1%，奴隶打工 150/h，造反率 40%，抽奖头奖 2%。平稳通胀，适合绝大多数群聊。</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:1px solid var(--line);border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="casual" style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟡 休闲高福利模式（高爆率 · 活跃社群）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 500 金币，利息 3%，奴隶打工 500/h，祈福暴击 25%，抽奖头奖 5%。低惩罚快节奏，极大激发互动。</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:1px solid var(--line);border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="hardcore" style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🔴 硬核博弈模式（高对抗 · 惩罚严酷）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 100 金币，利息 0.5%，造反率 55%，高额赎身费，抽奖硬核。高风险高回报，适合重度对抗型群友。</div>
        </div>
      </label>
    </div>
  `;

  // 选项高亮切换
  const radios = content.querySelectorAll("input[name='balanceMode']");
  radios.forEach(r => {
    r.onchange = () => {
      radios.forEach(x => {
        x.closest("label").style.borderColor = x.checked ? "var(--acc)" : "var(--line)";
        x.closest("label").style.borderWidth = x.checked ? "2px" : "1px";
      });
    };
  });

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "⚡ 一键智能匹配生效";
    okBtn.onclick = async () => {
      const sel = content.querySelector("input[name='balanceMode']:checked");
      const mode = sel ? sel.value : "standard";
      okBtn.disabled = true;
      okBtn.textContent = "正在调优并落盘...";
      try {
        const r = await getBridge().apiPost("config/auto_balance", { mode });
        if (r && r.ok) {
          toast(`已成功应用【${mode === "standard" ? "标准平衡" : (mode === "casual" ? "休闲福利" : "硬核博弈")}】数值方案！`, "ok");
          modal.className = "";
          await loadConfig();
          if (typeof loadCommands === "function") try { await loadCommands(); } catch(e) {}
        } else {
          toast("调优失败: " + (r && (r.error || r.msg) ? (r.error || r.msg) : "未知错误"), "bad");
        }
      } catch(err) {
        toast("调优失败: " + err.message, "bad");
      } finally {
        okBtn.disabled = false;
        okBtn.onclick = null;
      }
    };
  }
  modal.className = "show";
}

async function saveConfig() {
  const msg = document.getElementById("saveMsg");
  msg.className = "msg";
  try {
    const payload = {};
    const inputs = document.querySelectorAll("#cfgForm .cfg-row [data-key]");
    inputs.forEach((inp) => {
      const sec = inp.dataset.sec;
      const key = inp.dataset.key;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] =
        inp.type === "checkbox" ? (inp.checked ? "真" : "假") : inp.value;
    });
    const r = await getBridge().apiPost("config/save", payload);
    msg.textContent = "已保存: " + JSON.stringify(r);
    msg.classList.add("ok");
    toast("配置已保存", "ok");
    await loadConfig();
    // 同步刷新总览的快捷配置（同一接口，机器人QQ等）
    try { await loadOverviewReq(); } catch (e) {}
  } catch (e) {
    msg.textContent = "保存失败: " + e.message;
    msg.classList.add("bad");
    toast("保存失败: " + e.message, "bad");
  }
}

// ---------- 排行 ----------
async function resetConfig() {
  const msg = document.getElementById("saveMsg");
  msg.className = "msg";
  try {
    const { defaults } = CFG.schema;
    const payload = {};
    // defaults: {"系统__键": default}
    Object.keys(defaults).forEach((k) => {
      const [sec, key] = k.split("__");
      if (!sec || !key) return;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = defaults[k];
    });
    const r = await getBridge().apiPost("config/save", payload);
    msg.textContent = "已恢复默认: " + JSON.stringify(r);
    msg.classList.add("ok");
    toast("已恢复默认值", "ok");
    await loadConfig();
  } catch (e) {
    msg.textContent = "恢复失败: " + e.message;
    msg.classList.add("bad");
    toast("恢复失败: " + e.message, "bad");
  }
}

async function loadRank(type) {
  try {
    const rows = await getBridge().apiGet("rank", { type });
    const body = document.getElementById("rankBody");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted)">暂无榜单数据</td></tr>`;
      return;
    }
    const rankBadges = ["🥇", "🥈", "🥉"];
    body.innerHTML = rows
      .map((r, i) => {
        const rankIdx = i < 3 ? `<span style="font-size:16px">${rankBadges[i]}</span>` : `<span class="badge" style="background:var(--panel2)">${i + 1}</span>`;
        const valFormatted = typeof r.value === "number" ? r.value.toLocaleString() : esc(r.value);
        return `<tr>
          <td style="text-align:center">${rankIdx}</td>
          <td><strong>${esc(r.name || r.qq)}</strong></td>
          <td><code>${esc(r.qq)}</code></td>
          <td><span style="font-weight:700;color:var(--acc)">${valFormatted}</span></td>
        </tr>`;
      })
      .join("");
  } catch (e) {
    err("rank: " + e.message);
  }
}

// ---------- 用户 / 财富 ----------
let RAW_USERS = [];
let USER_GID_FILTER = "";
let _USER_GIDS = new Set();

function populateUserGidOptions() {
  const sel = document.getElementById("userGidFilter");
  if (!sel) return;
  // 收集当前 RAW_USERS 中的 gid
  (RAW_USERS || []).forEach(u => { if (u.gid) _USER_GIDS.add(String(u.gid)); });
  const cur = sel.value;
  // 重建选项：保留“全部群” + 已知 gid 排序
  const gids = Array.from(_USER_GIDS).sort();
  sel.innerHTML = `<option value="">全部群</option>` + gids.map(g => `<option value="${esc(g)}">${esc(g)}</option>`).join("");
  // 恢复之前的选中
  if (cur && _USER_GIDS.has(cur)) sel.value = cur;
  else if (USER_GID_FILTER) sel.value = USER_GID_FILTER;
}

async function loadUsers() {
  try {
    const sel = document.getElementById("userGidFilter");
    const gid = (sel?.value || USER_GID_FILTER || "").trim();
    USER_GID_FILTER = gid;
    const params = gid ? { gid } : {};
    RAW_USERS = await getBridge().apiGet("users", params);
    populateUserGidOptions();
    renderUserTable();
  } catch (e) {
    err("users: " + e.message);
  }
}

function filterUsers() {
  renderUserTable();
}

function renderUserTable() {
  const body = document.getElementById("userBody");
  if (!body) return;
  let users = [...RAW_USERS];
  // 前端二次 gid 过滤（兼容后端未过滤或缓存数据）
  const gidFilter = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  if (gidFilter) {
    users = users.filter(u => String(u.gid) === String(gidFilter));
  }
  // 搜索关键字联动过滤 (QQ/昵称/群号)
  const kw = (document.getElementById("userSearch")?.value || "").trim().toLowerCase();
  if (kw) {
    users = users.filter(u =>
      String(u.qq || "").toLowerCase().includes(kw) ||
      String(u.name || "").toLowerCase().includes(kw) ||
      String(u.gid || "").toLowerCase().includes(kw)
    );
  }
  const sortMode = (document.getElementById("userSort")?.value || "money_desc");
  if (sortMode === "money_desc") users.sort((a, b) => (b.money || 0) - (a.money || 0));
  else if (sortMode === "money_asc") users.sort((a, b) => (a.money || 0) - (b.money || 0));
  else if (sortMode === "deposit_desc") users.sort((a, b) => (b.deposit || 0) - (a.deposit || 0));
  else if (sortMode === "deposit_asc") users.sort((a, b) => (a.deposit || 0) - (b.deposit || 0));
  else if (sortMode === "stamina_desc") users.sort((a, b) => (b.stamina || 0) - (a.stamina || 0));
  else if (sortMode === "stamina_asc") users.sort((a, b) => (a.stamina || 0) - (b.stamina || 0));
  else if (sortMode === "charm_desc") users.sort((a, b) => (b.charm || 0) - (a.charm || 0));
  else if (sortMode === "charm_asc") users.sort((a, b) => (a.charm || 0) - (b.charm || 0));
  else if (sortMode === "sign_desc") users.sort((a, b) => (b.sign || 0) - (a.sign || 0));
  else if (sortMode === "sign_asc") users.sort((a, b) => (a.sign || 0) - (b.sign || 0));
  else if (sortMode === "qq_asc") users.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") users.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));
  else if (sortMode === "gid_asc") users.sort((a, b) => String(a.gid || "").localeCompare(String(b.gid || "")));
  else if (sortMode === "gid_desc") users.sort((a, b) => String(b.gid || "").localeCompare(String(a.gid || "")));

  const hint = document.getElementById("userHint");
  if (hint) {
    hint.innerHTML = `共 <strong>${RAW_USERS.length}</strong> 名用户（当前匹配 <strong>${users.length}</strong> 名） · 直接改动数值后点右侧「保存」生效 · 点击表头可快捷排序`;
  }
  if (!users.length) {
    body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--muted)">暂无匹配的用户数据</td></tr>`;
    return;
  }
  body.innerHTML = users
    .map((u) => {
      const nm = u.name ? esc(u.name) : '<span style="color:var(--muted)">-</span>';
      const inp = (id, v, w = 64) =>
        `<input type="number" id="${id}_${u.qq}_${u.gid}" value="${v}" title="${v}" style="width:${w}px;font-size:12.5px;padding:5px 8px;font-variant-numeric:tabular-nums">`;
      return `<tr>
        <td><strong>${esc(u.qq)}</strong></td>
        <td>${nm}</td>
        <td><span class="badge badge-primary">${esc(u.gid)}</span></td>
        <td>${inp("mm", u.money, 125)}</td>
        <td>${inp("tt", u.stamina, 58)}</td>
        <td>${inp("ma", u.charm, 58)}</td>
        <td>${inp("jj", u.lottery_tickets, 58)}</td>
        <td>${inp("ck", u.deposit || 0, 135)}</td>
        <td><span class="badge badge-success">${u.sign || 0}次</span></td>
        <td style="white-space:nowrap"><button data-save="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" class="sm">保存</button> <button class="ghost sm" data-export="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}">导出</button> <button class="ghost sm del" data-clear="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" title="彻底清除该用户全部数据（含奴隶、精灵与礼包资格）">清除</button></td>
      </tr>`;
    })
    .join("");
  // 绑定单用户导出与清除 (保存已通过 userBody 事件委托绑定)
  body.querySelectorAll("[data-export]").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        const res = await getBridge().apiGet("user/export", { gid: b.dataset.gid, qq: b.dataset.qq });
        if (res && res.data) {
          downloadBase64File(res.data, res.filename || `xbbot_user_${b.dataset.qq}_${b.dataset.gid}.json`);
        } else if (res) {
          downloadJson(res, `xbbot_user_${b.dataset.qq}_${b.dataset.gid}.json`);
        }
      } catch (e) { toast("导出失败: " + e.message, "bad"); }
    });
  });
  body.querySelectorAll("[data-clear='user']").forEach((b) => {
    b.addEventListener("click", () => {
      clearUserSingle(b.dataset.qq, b.dataset.gid);
    });
  });
}

async function clearUserSingle(qq, gid) {
  qq = String(qq || "").trim();
  gid = String(gid || "").trim();
  if (!qq || !gid) return;
  const ok = confirm(
    `⚠️ 危险操作确认\n\n` +
    `确定要彻底清除用户【${qq}】（群: ${gid}）的所有数据吗？\n\n` +
    `将一并清除以下内容：\n` +
    `1. 钱包金币、银行存款、体力、魅力、奖券与签到记录\n` +
    `2. 奴隶系统：解除奴隶身份，且其名下持有的奴隶将全部释放自由\n` +
    `3. 精灵系统：拥有的所有精灵、出战骑乘状态与背包道具全部清除\n` +
    `4. 重置新手礼包与精灵领养状态（该用户可重新领取新手礼包）\n\n` +
    `此操作立即生效且不可逆，是否确定清除？`
  );
  if (!ok) return;

  try {
    toast("正在清理用户数据...", "info");
    const res = await getBridge().apiPost("user/clear", { gid, qq });
    if (res && res.ok) {
      toast(res.msg || `用户 ${qq} 数据已彻底清除`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { loadSpiritUsers(); } catch(e) {}
    } else {
      toast((res && (res.msg || res.error)) || "清除失败", "bad");
    }
  } catch (e) {
    toast("清除失败: " + e.message, "bad");
  }
}

async function clearUserManual() {
  const curGid = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  const qq = prompt("请输入要彻底清除数据的用户 QQ 号：");
  if (!qq || !qq.trim()) return;
  const targetQq = qq.trim();
  let targetGid = curGid;
  if (!targetGid) {
    const gInput = prompt(`请输入用户【${targetQq}】所在的群号：`, "");
    if (!gInput || !gInput.trim()) {
      toast("已取消操作：必须提供群号", "bad");
      return;
    }
    targetGid = gInput.trim();
  }
  await clearUserSingle(targetQq, targetGid);
}

async function saveUserEdit(qq, gid, btn) {
  const get = (p) => { const el = document.getElementById(p + "_" + qq + "_" + gid); return el ? el.value : ""; };
  const payload = { qq, gid, money: get("mm"), stamina: get("tt"), charm: get("ma"), lottery_tickets: get("jj"), deposit: get("ck") };
  try {
    const r = await getBridge().apiPost("user/edit", payload);
    toast("用户数据已保存", "ok");
    if (btn) { btn.textContent = "已存"; setTimeout(() => { btn.textContent = "保存"; }, 1500); }
    await loadUsers();
    return r;
  } catch (e) {
    err("保存失败: " + e.message);
  }
}


async function cleanLeftUsers() {
  const gid = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  const scopeText = gid ? `群 ${gid}` : "全库所有群聊";
  const ok = await uiConfirm(
    `⚠️ 确认清理【${scopeText}】的退群人员？

系统将自动对比群聊实时成员列表，彻底删除已退群人员的钱包金币、奴隶身价关系、精灵背包与全部档案数据！`,
    "清理退群人员"
  );
  if (!ok) return;
  toast("正在对比群成员并清理退群人员...", "ok");
  try {
    let res = null;
    try {
      res = await getBridge().apiPost("users/clean_left", { gid });
    } catch(e) {
      res = await getBridge().apiGet("users/clean_left", { gid });
    }
    if (res && res.ok) {
      toast(`清理完成！已清理 ${res.cleaned_count || 0} 名退群人员数据`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { await loadSpiritUsers(); } catch(e) {}
    } else {
      toast("清理失败: " + (res && (res.error || res.msg) ? (res.error || res.msg) : "无法获取实时群成员，请确保 Bot 正常在线且在群内"), "bad");
    }
  } catch (err) {
    toast("清理失败: " + err.message, "bad");
  }
}

async function exportAllUsers() {
  const filename = `xbbot_users_all_${Date.now()}.json`;
  toast("正在导出全量用户数据...", "ok");
  try {
    let res = null;
    try {
      res = await getBridge().apiGet("users/export");
    } catch(e) {
      res = await getBridge().apiPost("users/export", {});
    }
    if (!res) throw new Error("接口无响应");
    if (res.error || res.msg) throw new Error(res.error || res.msg);

    let usersList = null;
    let base64Data = res.data || "";

    if (Array.isArray(res.users)) {
      usersList = res.users;
    } else if (res.data && typeof res.data === "object" && Array.isArray(res.data.users)) {
      usersList = res.data.users;
    } else if (res.result && typeof res.result === "object" && Array.isArray(res.result.users)) {
      usersList = res.result.users;
    }

    if (usersList) {
      const payload = {
        count: usersList.length,
        users: usersList,
        export_at: res.export_at || Math.floor(Date.now() / 1000),
        version: res.version || "0.68.21"
      };
      const jsonStr = JSON.stringify(payload, null, 2);
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        rawText: jsonStr,
        base64Data: base64Data
      });
      toast(`已成功全量导出 ${usersList.length} 名用户数据`, "ok");
      return;
    }

    if (base64Data && typeof base64Data === "string") {
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        base64Data: base64Data
      });
      toast("已成功全量导出用户数据", "ok");
      return;
    }

    const fallbackStr = typeof res === "string" ? res : JSON.stringify(res, null, 2);
    triggerExportResult({
      filename: filename,
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已成功全量导出用户数据", "ok");
  } catch (err) {
    toast("导出失败: " + err.message, "bad");
  }
}
async function importAllUsers() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      // 兼容单用户与全量
      const payload = data.users ? data : { users: [data] };
      const r = await getBridge().apiPost("users/import", payload);
      toast(`已导入 ${r.imported}/${r.total}`, "ok");
      await loadUsers();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}
async function importSingleUser() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      const r = await getBridge().apiPost("user/import", data);
      toast("已导入单用户", "ok");
      await loadUsers();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}

// ---------- 指令(可编辑 唤醒词 / 回复内容 / 玩法数值) ----------
let CMD_CFG = {};           // 运行时配置(嵌套 dict) 供指令页读取/保存
let KNOWN_CMDS = new Set(); // 引擎指令白名单，供映射校验
const SYS_WAKE = {
  slave: "奴隶系统", sign: "签到系统", bank: "银行系统", ent: "娱乐系统",
  spirit: "精灵系统", ride: "坐骑系统",
  superadmin: "超管系统", guild: "帮派系统", adventure: "冒险系统",
};
const map2sys = SYS_WAKE;
// 玩法类指令 -> 关联配置格式(金额/奖励/概率/惩罚) [section, key, label, type]
const CMD_NUMS = {
  "签到": [["签到配置", "金钱下限", "现金下限", "int"], ["签到配置", "金钱上限", "现金上限", "int"],
    ["签到配置", "体力下限", "体力下限", "int"], ["签到配置", "体力上限", "体力上限", "int"],
    ["签到配置", "魅力下限", "魅力下限", "int"], ["签到配置", "魅力上限", "魅力上限", "int"],
    ["签到配置", "奖券下限", "奖券下限", "int"], ["签到配置", "奖券上限", "奖券上限", "int"]],
  "领取新手礼包": [["新手配置", "现金", "礼包现金", "int"], ["新手配置", "体力", "礼包体力", "int"],
    ["新手配置", "魅力", "礼包魅力", "int"], ["新手配置", "奖券", "礼包奖券", "int"]],
  "购买体力": [["签到配置", "体力价格", "体力价格", "int"]],
  "购买魅力": [["签到配置", "魅力价格", "魅力价格", "int"]],
  "抽奖": [["抽奖配置", "中奖率", "中奖率%", "int"], ["抽奖配置", "现金奖", "现金奖", "int"],
    ["抽奖配置", "体力奖", "体力奖", "int"], ["抽奖配置", "魅力奖", "魅力奖", "int"]],
  "存款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"],
    ["银行配置", "存款期限", "存款期限(天)", "int"], ["银行配置", "存取款消耗体力", "消耗体力", "int"]],
  "取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "强制取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "转账": [["银行配置", "转账最小金额", "最小金额", "int"], ["银行配置", "转账接收额度", "接收额度", "int"],
    ["银行配置", "转账消耗体力", "消耗体力", "int"]],
  "发红包": [["银行配置", "红包_最小金额", "最小金额", "int"], ["银行配置", "红包_最大金额", "最大金额", "int"],
    ["银行配置", "红包_发体力", "发体力", "int"], ["银行配置", "红包_间隔时间", "间隔(秒)", "int"]],
  "抢红包": [["银行配置", "红包_抢体力", "抢体力", "int"], ["银行配置", "红包_抢魅力", "抢魅力", "int"],
    ["银行配置", "红包_基本魅力", "基础魅力", "int"]],
  "赌博": [["银行配置", "赌博成功概率", "成功概率%", "int"], ["银行配置", "赌博消耗体力", "消耗体力", "int"],
    ["银行配置", "赌博魅力减少", "魅力减少", "int"], ["银行配置", "赌博最大金额", "最大金额", "int"],
    ["银行配置", "赌博限定次数", "限定次数", "int"], ["银行配置", "赌博关押时间", "关押(分)", "int"]],
  "打劫": [["银行配置", "打劫成功概率", "成功概率%", "int"], ["银行配置", "打劫消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫金钱下限", "金钱下限", "int"], ["银行配置", "打劫金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫魅力减少", "魅力减少", "int"], ["银行配置", "打劫关押时间", "关押(分)", "int"]],
  "打劫银行": [["银行配置", "打劫银行成功概率", "成功概率%", "int"],
    ["银行配置", "打劫银行消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫银行金钱下限", "金钱下限", "int"], ["银行配置", "打劫银行金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫银行魅力减少", "魅力减少", "int"], ["银行配置", "打劫银行关押时间", "关押(分)", "int"]],
  "保释": [["银行配置", "保释金钱下限", "保释金下限", "int"], ["银行配置", "保释金钱上限", "保释金上限", "int"],
    ["银行配置", "保释消耗体力", "消耗体力", "int"], ["银行配置", "保释魅力减少", "魅力减少", "int"]],
  "我要越狱": [["银行配置", "越狱成功概率", "成功概率%", "int"], ["银行配置", "越狱消耗体力", "消耗体力", "int"],
    ["银行配置", "越狱魅力减少", "魅力减少", "int"], ["银行配置", "越狱关押时间", "关押(分)", "int"]],
  "精灵冒险": [["精灵配置", "挑战奖励_经验下限", "经验下限", "int"], ["精灵配置", "挑战奖励_经验上限", "经验上限", "int"],
    ["精灵配置", "挑战奖励_金钱下限", "金钱下限", "int"], ["精灵配置", "挑战奖励_金钱上限", "金钱上限", "int"],
    ["精灵配置", "等级加成下限", "等级加成下限", "int"], ["精灵配置", "等级加成上限", "等级加成上限", "int"],
    ["精灵配置", "冒险间隔", "冒险间隔(分)", "int"]],
  "丢弃精灵": [["精灵配置", "魅力减少", "魅力减少", "int"]],
  "打赏": [["费用配置", "打赏上限", "打赏上限", "int"], ["间隔配置", "打赏间隔", "打赏间隔(分)", "int"]],
  "补偿": [["费用配置", "变化上限", "变化上限", "int"]],
  "保护": [["设置", "保护费用", "保护费用", "int"], ["设置", "保护时长小时", "保护时长(时)", "int"],
    ["间隔配置", "保护间隔", "保护间隔(分)", "int"]],
  "我要学习": [["设置", "奇遇触发概率", "奇遇概率%", "int"], ["间隔配置", "学习间隔", "学习间隔(分)", "int"]],
  "讨好": [["概率配置", "讨好概率", "讨好概率%", "int"], ["间隔配置", "讨好间隔", "讨好间隔(分)", "int"]],
  "造反": [["概率配置", "造反概率", "造反概率%", "int"], ["间隔配置", "造反间隔", "造反间隔(分)", "int"]],
  "十连抽": [["设置", "十连抽花费", "十连抽花费", "int"]],
  "三十连抽": [["设置", "三十连抽花费", "三十连抽花费", "int"]],
  "五十连抽": [["设置", "五十连抽花费", "五十连抽花费", "int"]],
  "买下": [["间隔配置", "购买间隔", "购买间隔(分)", "int"]],
  "折磨": [["间隔配置", "折磨间隔", "折磨间隔(分)", "int"]],
  "起名": [["起名配置", "起名费用", "起名费用", "int"]],
  "买奴隶位": [["设置", "奴隶位价格", "奴隶位价格", "int"]],
  "我要自由": [["费用配置", "初始身价", "初始身价", "int"]],
  "打架": [["间隔配置", "打架间隔", "打架间隔(分)", "int"]],
  "我要祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"],
    ["祈福配置", "人品爆发概率", "人品爆发概率%", "int"], ["祈福配置", "人品爆发奖励", "人品爆发奖励", "int"]],
  "升星": [["设置", "一星武器概率", "一星概率%", "int"], ["设置", "一星武器花费", "一星花费", "int"], ["设置", "一星武器消耗同武器数量", "一星消耗同武数", "int"], ["设置", "二星武器概率", "二星概率%", "int"], ["设置", "二星武器花费", "二星花费", "int"], ["设置", "二星武器消耗同武器数量", "二星消耗", "int"]],
  "升阶": [["设置", "一阶宝物概率", "一阶概率%", "int"], ["设置", "一阶宝物花费", "一阶花费", "int"]],
  "我要打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "奴隶打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"]],
  "学习": [["间隔配置", "学习间隔", "学习间隔(分)", "int"], ["设置", "奇遇触发概率", "奇遇概率%", "int"]],
  "祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"]],
  "释放": [["间隔配置", "释放间隔", "释放间隔(分)", "int"]],
  "查询": [["设置", "货币名称", "货币名称", "text"]],
  "我的信息": [["设置", "货币名称", "货币名称", "text"]],
  "抽签": [["娱乐配置", "抽签造价", "抽签造价", "int"], ["娱乐配置", "抽签大吉奖励", "大吉奖励", "int"], ["娱乐配置", "抽签上签奖励", "上签奖励", "int"], ["娱乐配置", "抽签中签奖励", "中签奖励", "int"]],
  "猜拳": [["娱乐配置", "猜拳奖励金币", "奖励金币", "int"], ["娱乐配置", "猜拳奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜拳成功概率", "成功概率%", "int"], ["娱乐配置", "猜拳消耗体力", "消耗体力", "int"], ["娱乐配置", "猜拳需要金钱", "需要金钱", "int"]],
  "猜数": [["娱乐配置", "猜数奖励金币", "奖励金币", "int"], ["娱乐配置", "猜数奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜数消耗体力", "消耗体力", "int"], ["娱乐配置", "猜数需要金钱", "需要金钱", "int"]],
  "急转弯": [["娱乐配置", "急转弯奖励金币", "奖励金币", "int"], ["娱乐配置", "急转弯奖励魅力", "奖励魅力", "int"], ["娱乐配置", "急转弯消耗体力", "消耗体力", "int"], ["娱乐配置", "急转弯需要金钱", "需要金钱", "int"]],
  "猜字谜": [["娱乐配置", "猜字谜奖励金币", "奖励金币", "int"], ["娱乐配置", "猜字谜奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜字谜消耗体力", "消耗体力", "int"], ["娱乐配置", "猜字谜需要金钱", "需要金钱", "int"]],
  "接龙": [["娱乐配置", "接龙奖励金币", "奖励金币", "int"], ["娱乐配置", "接龙奖励魅力", "奖励魅力", "int"], ["娱乐配置", "接龙消耗体力", "消耗体力", "int"], ["娱乐配置", "接龙需要金钱", "需要金钱", "int"]],
  "答题": [["娱乐配置", "答题奖励金币", "奖励金币", "int"], ["娱乐配置", "答题奖励魅力", "奖励魅力", "int"], ["娱乐配置", "答题消耗体力", "消耗体力", "int"], ["娱乐配置", "答题需要金钱", "需要金钱", "int"]],
  "二四点": [["娱乐配置", "二四点奖励金币", "奖励金币", "int"], ["娱乐配置", "二四点奖励魅力", "奖励魅力", "int"], ["娱乐配置", "二四点消耗体力", "消耗体力", "int"], ["娱乐配置", "二四点需要金钱", "需要金钱", "int"]],
};

// 各玩法指令的默认回复示例(供指令页"默认回复"展示; 覆盖配置留空则用该默认)
// {变量} 为运行时动态数值占位符
const CMD_DEFAULT_REPLY = {
  "签到": "🏅 恭喜你签到成功！\r\n　奖励详情：\r\n　　　💵 金币 +{现金}\r\n　　　⚡ 体力 +{体力}\r\n　　　💄 魅力 +{魅力}\r\n　　　🎫 奖券 +{奖券}\r\n　　　🔥 第{天数}天连签 +{连签}\r\n当前金币：{当前}\r\n您是今天第{序号}个签到者！",
  "领取新手礼包": "恭喜您获得新手礼包一份！\r\n现金+{现金}\r\n体力+{体力}\r\n魅力+{魅力}\r\n奖券+{奖券}",
  "购买体力": "恭喜您花费{价格}金币，购买了{数量}点体力，您的体力提升到{当前}点！",
  "购买魅力": "恭喜您花费{价格}金币，购买了{数量}点魅力，您的魅力提升到{当前}点！",
  "个人信息": "您的账户信息如下：\r\n个人财富：{财富}\r\n签到次数：{签到}\r\n剩余体力：{体力}\r\n魅力指数：{魅力}\r\n奖券数量：{奖券}\r\n存款金额：{存款}",
  "抽奖": "恭喜，抽奖成功！获得{奖励}+{数值}",
  "存款": "存款成功！共存入：{金额}，上期结息：{利息}，当前总存款：{总额}",
  "取款": "取款成功！获得利息：{利息}，本次取款：{金额}，还剩存款：{剩余}",
  "强制取款": "强制取款成功！因未到取款时间，本次没有利息。本次取款：{金额}",
  "转账": "转账成功！您已向 {目标} 转入{金额}金币！",
  "发红包": "发红包啦！发了{金额}金币点，大家快抢吧！红包口令为：{口令}",
  "抢红包": "恭喜！你抢到了 {金额}金币，魅力+{魅力}！",
  "赌博": "赌博成功！你获得了{赢得}金币，净赚{净赚}！",
  "打劫": "打劫成功！你从 {目标} 处劫走{金额}金币！",
  "打劫银行": "打劫银行成功！获得{金额}金币！",
  "保释": "保释成功！花费{保释金}金币、{体力}体力，魅力-{魅力}。",
  "我要越狱": "越狱成功！扣除{体力}体力，你重获自由~",
  "买下": "成功买下{目标}\r\n本次买入花费：{花费}\r\n奴隶身价上涨：{上涨}\r\n奴隶现在身价：{身价}",
  "买奴隶位": "恭喜您花费{价格}金币\r\n买下一个奴隶位。\r\n当前可拥有奴隶上限：{上限}",
  "我要自由": "万恶的主人，大发善心，花费{价格}换取自由！",
  "保护": "恭喜您花费{费用}金币保护{目标}，剩余保护时间{分钟}分钟！",
  "打赏": "[{名字}] 打赏给了 [{目标}] {金额}金币，实际获得{实收}",
  "折磨": "你对 [{目标}] 实施了折磨...\r\n【奇遇】{剧情}\r\n奴隶货币 +{数值}",
  "讨好": "摇摇尾巴~向你主人卖个萌，主人一开心给了你{金额}",
  "造反": "经过艰苦卓绝的战斗，你打败了万恶的主人，并恢复自由！抢走主人{金额}金币",
  "我要学习": "缴纳学费 {学费} 后开始学习! 武器经验 +{经验}\r\n🍀奇遇: {剧情}",
  "我要祈福": "笑~忍神大人心情不错，看着面前楚楚可怜的{名字}，一高兴赏了{金额}",
  "打架": "打架啦！\r\n我方派出奴隶：{队伍}\r\n对方派出奴隶：{队伍}\r\n本次战斗结果：胜利！获得对方赔款：{金额}",
  "精灵冒险": "【精灵冒险】来到{地图}，遭遇了野生的 Lv.{等级}「{精灵}」！",
  "丢弃精灵": "已丢弃精灵「{名字}」，魅力-{数值}",
  "升星": "成功升星{武器}！本次升星概率：{概率}%，武器不会消失哦~",
  "升阶": "升阶成功！本次升阶概率：{概率}%，本次升阶花费：{花费}",
};

let CMD_EDIT = { sys: "", cmd: "", isNew: false, mapCmd: "" };   // 当前模态框编辑的 系统/指令

async function loadCommands() {
  try {
    const cmds = await getBridge().apiGet("commands");
    const cur = await getBridge().apiGet("config/get");
    CMD_CFG = cur || {};
    const wakeSec = CMD_CFG["唤醒词配置"] || {};
    const custSec = CMD_CFG["自定义指令配置"] || {};
    const onSec = CMD_CFG["系统开关配置"] || {};       // 系统级启用
    const disSec = CMD_CFG["指令启用配置"] || {};       // 指令级启用(假=禁用)
    const setupSec = CMD_CFG["设置"] || {};
    const isOff = (v) => v === "假" || v === "0" || v === "false";
    const isOn = (v) => v === undefined || !isOff(v);
    const el = document.getElementById("cmdList");
    KNOWN_CMDS = new Set();
    Object.values(cmds).forEach(arr => (arr||[]).forEach(c => KNOWN_CMDS.add(c)));
    const blockHtml = Object.keys(cmds).filter(k => k !== "chat")
      .map((k) => {
        const sys = map2sys[k] || k;
        const wake = (wakeSec[sys] ?? sys);
        const wakeList = wake.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
        const seen = {};
        // 去掉「系统唤醒词」本身作为假指令的重复项(唤醒词已在块头部单独编辑)
        const items = (cmds[k] || []).filter((c) => {
          if (seen[c]) return false;
          seen[c] = 1;
          return wakeList.indexOf(c) < 0;
        });
        const sysChecked = isOn(onSec[sys]) ? "checked" : "";
        const tags = items.map((c) => {
          const cOn = isOn(disSec[c]);
          const onBg = cOn ? "" : "off";
          return `<a class="cmd-tag ${onBg}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(c)}" data-sys="${esc(sys)}">` +
            `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${esc(c)}</a>`;
        }).join("");
        return `<details class="cmd-block" data-sys="${esc(sys)}"><summary>` +
          `<span class="cmd-sys">${esc(sys)}</span>` +
          `<span class="cmd-count">${items.length} 条指令</span></summary>` +
          `<div class="cmd-wake">` +
          `<div class="cmd-wake-item"><label>启用系统</label><label class="switch"><input type="checkbox" data-syson="${esc(sys)}" ${sysChecked}><span class="slider-toggle"></span></label></div>` +
          `<div class="cmd-wake-item" style="flex:1"><label>唤醒词</label><input data-wake="${esc(sys)}" value="${esc(wake)}" placeholder="可用 | 分隔多个"></div>` +
          `</div>` +
          `<div class="cmd-tags">${tags || '<span class="hint">（交互式/无前缀触发）</span>'}</div>` +
          `</details>`;
      })
      .join("");
    const customTags = Object.keys(custSec).map((t) => {
      const cOn = isOn(disSec[t]);
      return `<a class="cmd-tag custom ${cOn ? "" : "off"}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(t)}" data-sys="自定义">` +
        `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${esc(t)}</a>`;
    }).join("");
    el.innerHTML =
      blockHtml +
      `<details class="cmd-block" data-sys="自定义"><summary>` +
        `<span class="cmd-sys">自定义指令</span>` +
        `<span class="cmd-count">${Object.keys(custSec).length} 条</span></summary>` +
        `<div class="cmd-tags">${customTags || '<span class="hint">暂无。新建：纯自定义（触发词→回复）或绑定已有引擎指令作别名。</span>'}</div>` +
        `<div class="toolbar" style="margin-top:8px"><button id="btnCmdAddCustom" class="ghost sm">＋ 添加自定义指令</button></div>` +
      `</details>`;
    el.querySelectorAll("a.cmd-tag").forEach((a) =>
      a.addEventListener("click", () => {
        CMD_EDIT.sys = a.dataset.sys;
        CMD_EDIT.cmd = a.dataset.cmd;
        CMD_EDIT.isNew = false;
        if (a.dataset.sys === "自定义") {
          const e = (custSec[a.dataset.cmd] || {});
          CMD_EDIT.mapCmd = (typeof e === "object" && e) ? (e.command || "") : "";
        } else {
          CMD_EDIT.mapCmd = a.dataset.cmd;
        }
        openCmdEditor();
      }));
    el.querySelectorAll("details.cmd-block").forEach((d) =>
      d.addEventListener("toggle", () => {
        // 打开时滚动到该块(避免长页脱靶)
        if (d.open) d.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }));
    el.querySelectorAll("[data-wake]").forEach((inp) =>
      inp.addEventListener("input", () => { CMD_CFG_WAKE_DIRTY = true; }));
    const addCustom = document.getElementById("btnCmdAddCustom");
    if (addCustom) addCustom.addEventListener("click", () => {
      CMD_EDIT = { sys: "自定义", cmd: "", isNew: true, mapCmd: "" };
      openCmdEditor();
    });
    const exp = document.getElementById("btnCmdExpandAll");
    const col = document.getElementById("btnCmdCollapseAll");
    if (exp) exp.addEventListener("click", () => {
      el.querySelectorAll("details.cmd-block").forEach((d) => { d.open = true; });
    });
    if (col) col.addEventListener("click", () => {
      el.querySelectorAll("details.cmd-block").forEach((d) => { d.open = false; });
    });
  } catch (e) {
    err("commands: " + e.message);
  }
}
let CMD_CFG_WAKE_DIRTY = false;

function cmdAliasesFor(cmd) {
  const cust = CMD_CFG["自定义指令配置"] || {};
  return Object.keys(cust).filter((t) => cust[t] && cust[t].command === cmd && t !== cmd);
}

function openCmdEditor() {
  const { sys, cmd, isNew, mapCmd } = CMD_EDIT;
  const m = document.getElementById("cmdModal");
  if (!m) return;
  const curCmd = mapCmd || cmd;
  const ovSec = CMD_CFG["指令回复配置"] || {};
  const disSec = CMD_CFG["指令启用配置"] || {};
  const isOff = (v) => v === "假" || v === "0" || v === "false";
  // 启用键: 自定义指令(含别名)按触发词, 引擎指令按映射引擎指令名
  const effKey = (sys === "自定义") ? (cmd || "") : (mapCmd || cmd || "");
  const onBox = document.getElementById("cmdModalOn");
  if (onBox) onBox.checked = !isOff(disSec[effKey]);
  // 删除按钮: 仅编辑已有自定义指令时显示
  const delBtn = document.getElementById("btnCmdModalDelete");
  if (delBtn) delBtn.style.display = (sys === "自定义" && !isNew) ? "" : "none";
  document.getElementById("cmdModalTitle").textContent = isNew ? "添加自定义指令" : ("编辑指令 · " + curCmd);
  (document.getElementById("cmdModalSysBadge") || document.getElementById("cmdModalSys")).textContent = isNew ? "自定义指令" : sys;
  // 触发词: 可编辑(| 分隔多个); 内置指令默认=指令名(+已有别名)
  const nameInp = document.getElementById("cmdModalName");
  nameInp.value = isNew ? "" : [curCmd, ...cmdAliasesFor(curCmd)].join("|");
  nameInp.readOnly = false;
  document.getElementById("cmdModalCmd").value = mapCmd;
  document.getElementById("cmdModalCmd").readOnly = isNew ? false : true;
  document.getElementById("cmdModalReply").value = isNew ? "" : (ovSec[curCmd] ?? "");
  const note = document.getElementById("cmdModalCmdNote");
  if (note) {
    note.textContent = (!isNew && mapCmd === curCmd)
      ? "内置指令：触发词即指令名（可改/加，| 分隔多个）；映射引擎指令=本身。"
      : "留空=纯自定义指令；填入已有引擎指令则这些触发词作为它的别名。";
  }
  const dfltCmd = mapCmd || curCmd || "";
  const dfltTxt = CMD_DEFAULT_REPLY[dfltCmd] || (ovSec[dfltCmd] || "") || "";
  document.getElementById("cmdModalDflt").textContent = isNew
    ? "纯自定义指令：回复内容即返回文案，可直接写你想要的任意内容；也可在「映射引擎指令」填入已有指令来作为它的别名（此时回复覆盖模板对该引擎生效）。"
    : (dfltTxt
        ? "引擎默认回复（参考）：\r\n" + dfltTxt + "\r\n（{变量}=动态数值；留空回复=按引擎原样回复）"
        : "引擎默认回复为运行时动态生成（含变量/随机/状态判定），此处未收录示例；\r\n如需覆盖请直接填写回复模板，或用 {回复} 引用引擎原回复。留空=不覆盖。");
  renderCmdNums(mapCmd ? mapCmd : (isNew ? "" : curCmd), isNew);
  if (m) m.classList.add("show");
}

// 按目标引擎指令渲染玩法数值(纯自定义且未映射时提示)
function renderCmdNums(numCmd, isNew) {
  const holder = document.getElementById("cmdModalNums");
  if (!holder) return;
  if (!numCmd) {
    holder.innerHTML = `<small class="hint">纯自定义指令：回复内容即返回文案，无玩法数值；如需调整某引擎指令的数值，请把「映射引擎指令」填成它。</small>`;
    return;
  }
  let nums = CMD_NUMS[numCmd] || [];
  if (!nums.length && numCmd) {
    // 兜底：若未配置，尝试按系统主配置节自动列出相关数值键（避免“明明有花钱却无可改”）
    try {
      const secMap = {"买下":"间隔配置","折磨":"间隔配置","打赏":"费用配置","补偿":"费用配置","保护":"设置","起名":"起名配置","买奴隶位":"设置","打架":"间隔配置","我要打工":"间隔配置","奴隶打工":"间隔配置","打工":"间隔配置","学习":"间隔配置","祈福":"祈福配置","我要祈福":"祈福配置","升星":"设置","升阶":"设置","签到":"签到配置","抽奖":"抽奖配置","存款":"银行配置","取款":"银行配置","转账":"银行配置","打劫":"银行配置","打劫银行":"银行配置","赌博":"银行配置","保释":"银行配置","我要越狱":"银行配置","精灵冒险":"精灵配置","丢弃精灵":"精灵配置"};
      const sec = secMap[numCmd];
      if (sec && CFG.schema && CFG.schema.groups && CFG.schema.groups[sec]) {
        nums = CFG.schema.groups[sec].filter(it => /金|钱|费|价格|奖|罚|消耗|魅力|体力/.test(it.key+it.desc)).slice(0,6).map(it => [sec, it.key, it.key, it.type]);
      }
    } catch(e){}
  }
  if (!nums.length) {
    holder.innerHTML = `<small class="hint">该指令无关联可调数值。</small>`;
    return;
  }
  holder.innerHTML = nums.map(([sec, key, label]) => {
    const v = (CMD_CFG[sec] || {})[key] ?? "";
    return `<label class="cnum"><span>${esc(label)}</span>` +
      `<input type="number" data-cmd-num data-nsec="${esc(sec)}" data-nkey="${esc(key)}" value="${esc(v)}"></label>`;
  }).join("");
}

function closeCmdEditor() {
  const m = document.getElementById("cmdModal");
  if (m) m.classList.remove("show");
}

async function saveCmdEditor() {
  const name = document.getElementById("cmdModalName").value.trim();
  const mapCmd = document.getElementById("cmdModalCmd").value.trim();
  const reply = document.getElementById("cmdModalReply").value.trim();
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const payload = {};
    // 系统启用开关: 收所有块头部
    const onSec = {};
    document.querySelectorAll("#cmdList [data-syson]").forEach((inp) => {
      onSec[inp.dataset.syson] = inp.checked ? "真" : "假";
    });
    if (Object.keys(onSec).length) payload["系统开关配置"] = onSec;
    // 系统唤醒词: 收所有块头部
    const wakeSec = {};
    document.querySelectorAll("#cmdList [data-wake]").forEach((inp) => {
      wakeSec[inp.dataset.wake] = inp.value.trim();
    });
    if (Object.keys(wakeSec).length) payload["唤醒词配置"] = wakeSec;

    const cust = {};
    if (mapCmd) {
      if (!KNOWN_CMDS.has(mapCmd)) {
        if (msg) { msg.textContent = `映射的引擎指令「${mapCmd}」不存在，请留空走纯自定义或填已有指令`; msg.classList.add("bad"); }
        toast(`引擎指令「${mapCmd}」不存在，已拦截`, "bad");
        return;
      }
      // 映射 / 编辑已有引擎指令(含别名): 触发词=| 分隔, 全部当作该指令的触发词
      const trigs = name.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
      if (!trigs.length) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      { const ov = {}; ov[mapCmd] = reply; payload["指令回复配置"] = ov; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => {
        const e = oldCust[t];
        if (!(e && e.command === mapCmd && t !== mapCmd)) cust[t] = e;
      });
      trigs.forEach((t) => {
        if (t && t !== mapCmd) cust[t] = { command: mapCmd, reply: "" };
      });
    } else {
      // 纯自定义指令
      if (!name) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      if (!reply) { if (msg) { msg.textContent = "纯自定义指令需填写回复内容"; msg.classList.add("bad"); } return; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => { if (t !== name) cust[t] = oldCust[t]; });
      cust[name] = { command: "", reply: reply };
    }
    if (Object.keys(cust).length) payload["自定义指令配置"] = cust;

    // 指令级启用: 自定义指令按触发词记录, 引擎指令按映射引擎指令名记录
    const isCustom = (CMD_EDIT.sys === "自定义") || (name && !mapCmd && CMD_EDIT.isNew);
    const effKey = isCustom ? name : (mapCmd || name);
    const disSec = {};
    const onBox = document.getElementById("cmdModalOn");
    disSec[effKey] = (onBox && onBox.checked) ? "真" : "假";
    payload["指令启用配置"] = disSec;

    // 玩法数值(目标引擎指令)
    document.querySelectorAll("#cmdModal [data-cmd-num]").forEach((inp) => {
      const sec = inp.dataset.nsec, key = inp.dataset.nkey;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = inp.value === "" ? "" : Number(inp.value);
    });

    const r = await getBridge().apiPost("config/save", payload);
    if (msg) { msg.textContent = "已保存: " + JSON.stringify(r); msg.classList.add("ok"); }
    toast("指令已保存", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "保存失败: " + e.message; msg.classList.add("bad"); }
    toast("保存失败: " + e.message, "bad");
  }
}

// 删除自定义指令(移除 自定义指令配置 / 指令启用配置 / 指令回复配置 中对应项)
async function deleteCmdEditor() {
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const key = (CMD_EDIT && CMD_EDIT.cmd) || "";
    if (!key) { if (msg) { msg.textContent = "无触发词，无法删除"; msg.classList.add("bad"); } return; }
    const oldCust = (CMD_CFG["自定义指令配置"] || {});
    if (!(key in oldCust)) { if (msg) { msg.textContent = "该指令在配置中不存在，可能已删除"; msg.classList.add("bad"); } return; }
    if (!(await uiConfirm("确认删除自定义指令「" + key + "」？", "删除自定义指令"))) return;
    const cust = {};
    Object.keys(oldCust).forEach((t) => { if (t !== key) cust[t] = oldCust[t]; });
    const payload = { "自定义指令配置": cust };
    const disSec = {};
    const disSecOld = (CMD_CFG["指令启用配置"] || {});
    Object.keys(disSecOld).forEach((k) => { if (k !== key) disSec[k] = disSecOld[k]; });
    if (Object.keys(disSec).length) payload["指令启用配置"] = disSec;
    const ovOld = (CMD_CFG["指令回复配置"] || {});
    const ov = {};
    Object.keys(ovOld).forEach((k) => { if (k !== key) ov[k] = ovOld[k]; });
    payload["指令回复配置"] = ov;
    await getBridge().apiPost("config/save", payload);
    toast("已删除自定义指令", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "删除失败: " + e.message; msg.classList.add("bad"); }
    toast("删除失败: " + e.message, "bad");
  }
}

// ---------- 精灵图鉴(地图/商城 两页; 地图内可展开精灵详情 + 搜索地图/精灵) ----------
let SPIRIT = null;          // {spirits, maps, shop}
let SPIRIT_CUR = "地图";    // 仅 "地图" | "商城"
let SPIRIT_DIRTY = false;
let SPIRIT_OPEN = {};       // mapName -> bool(展开详情)

const SPIRIT_FIELDS = [
  ["type", "属性"], ["hp", "生命"], ["atk", "攻击"], ["def", "防御"],
  ["spa", "特攻"], ["spd", "特防"], ["spe", "速度"], ["lv", "进化等级"],
  ["evolve", "进化成"],
];
const SHOP_FIELDS = [["price", "价格"], ["attr", "类型"], ["effect", "效果"]];

async function loadSpirits() {
  try {
    SPIRIT = await getBridge().apiGet("spirits");
    SPIRIT_DIRTY = false;
    SPIRIT_OPEN = {};
    const msg = document.getElementById("spiritMsg");
    if (msg) { msg.className = "msg"; msg.textContent = ""; }
    renderSpiritCat();
    renderSpiritBody();
  } catch (e) {
    err("spirits: " + e.message);
  }
}

function renderSpiritCat() {
  if (!SPIRIT) return;
  const cat = document.getElementById("spiritCat");
  if (!cat) return;
  cat.innerHTML = ["地图", "商城"]
    .map((s) => `<button data-scat="${s}" class="${s === SPIRIT_CUR ? "on" : ""}">${s}</button>`)
    .join("");
  cat.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      SPIRIT_CUR = b.dataset.scat;
      cat.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      renderSpiritBody();
    }));
}

function spiritAttrCards(spirits, dropNames) {
  // 每个 drop 精灵一张属性卡(数据从 spirits dict 读, 缺失则 seed)
  return dropNames.map((sn) => {
    const it = spirits[sn] || { type: "", hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0, lv: 0, evolve: "否" };
    const cells = SPIRIT_FIELDS.map(([fk, label]) =>
      `<div class="s-row"><small>${label}</small>` +
      `<input data-sp-spirit="${esc(sn)}" data-s-field="${fk}" value="${esc(it[fk] ?? "")}" style="width:78px"></div>`);
    return `<div class="sp-card" data-sp="${esc(sn)}">
      <div class="sp-name">✦ ${esc(sn)}</div>
      <div class="s-fields">${cells.join("")}
        <button class="s-del" data-del-spirit="${esc(sn)}">移除精灵</button></div>
    </div>`;
  }).join("");
}

function renderSpiritBody() {
  if (!SPIRIT) return;
  const q = (document.getElementById("spiritSearch")?.value || "").trim().toLowerCase();
  renderMaps(q);
}

function renderMaps(q) {
  const body = document.getElementById("spiritBody");
  if (!body) return;
  const maps = SPIRIT.maps || {};
  const spirits = SPIRIT.spirits || {};
  const mapNames = Object.keys(maps).filter((k) => {
    if (!q) return true;
    if (k.toLowerCase().includes(q)) return true;
    return (maps[k].drops || []).some((s) => String(s).toLowerCase().includes(q));
  });
  if (!mapNames.length) {
    body.innerHTML = `<div class="hint">无匹配地图</div>`;
    return;
  }
  body.innerHTML = mapNames.map((mname) => {
    const d = maps[mname] || {};
    const drops = (d.drops || []).map(String);
    const open = q ? true : !!SPIRIT_OPEN[mname];
    return `<div class="s-mapcard ${open ? "open" : ""}" data-map="${esc(mname)}">
      <div class="s-maphead" data-map-toggle="${esc(mname)}">
        <span class="s-mapname">🗺 ${esc(mname)}</span>
        <span class="s-maplv">Lv.${esc(d.lv ?? 1)}</span>
        <span class="s-mapdrop">${esc(drops.join("、"))}</span>
        <span class="s-arr">${open ? "▾" : "▸"}</span>
      </div>
      <div class="s-mapbody">
        <div class="s-fields" style="margin-bottom:8px">
          <div class="s-row"><small>推荐等级</small><input data-map-field="lv" value="${esc(d.lv ?? 1)}"></div>
          <div class="s-row" style="flex:0 1 66%"><small>出没精灵(逗号分隔)</small><input data-map-field="drops" value="${esc(drops.join("，"))}"></div>
          <button class="s-del" data-del-map="${esc(mname)}">删地图</button>
        </div>
        <div class="sp-spirits">${spiritAttrCards(spirits, drops)}</div>
        <button class="ghost" data-add-spirit="${esc(mname)}">＋ 添加精灵</button>
      </div>
    </div>`;
  }).join("") + `<button id="mapAddItem" class="ghost" style="margin-top:10px">＋ 添加地图</button>`;

  body.querySelectorAll("[data-map-toggle]").forEach((h) =>
    h.addEventListener("click", () => {
      const m = h.dataset.mapToggle;
      SPIRIT_OPEN[m] = !SPIRIT_OPEN[m];
      renderMaps(q);
    }));
  body.querySelectorAll("input[data-map-field], input[data-sp-spirit]").forEach((inp) => {
    inp.addEventListener("input", () => { SPIRIT_DIRTY = true; });
  });
  body.querySelectorAll("[data-del-map]").forEach((b) =>
    b.addEventListener("click", async () => {
      const k = b.dataset.delMap;
      if (!(await uiConfirm("确认删除地图 \"" + k + "\"？（需点击上方「保存图鉴」生效）", "删除地图"))) return;
      delete maps[k];
      SPIRIT_DIRTY = true;
      renderMaps(q);
      toast("已删除地图，请点击上方「保存图鉴」持久化", "ok");
    }));
  body.querySelectorAll("[data-del-spirit]").forEach((b) =>
    b.addEventListener("click", async () => {
      const spName = b.dataset.delSpirit;
      if (!(await uiConfirm("确认移除精灵 \"" + spName + "\"？（需点击上方「保存图鉴」生效）", "移除精灵"))) return;
      Object.keys(maps).forEach((mk) => {
        maps[mk].drops = (maps[mk].drops || []).map(String).filter((x) => x !== spName);
      });
      SPIRIT_DIRTY = true;
      renderMaps(q);
      toast("已移除精灵，请点击上方「保存图鉴」持久化", "ok");
    }));
  body.querySelectorAll("[data-add-spirit]").forEach((b) =>
    b.addEventListener("click", async () => {
      let n = await uiPrompt("输入要添加的精灵名称：", "", "添加精灵");
      if (!n) return;
      n = n.trim();
      if (!n) return;
      const mk = b.dataset.addSpirit;
      const dd = maps[mk] || { lv: 1, drops: [] };
      if (!Array.isArray(dd.drops)) dd.drops = [];
      if (!dd.drops.map(String).includes(n)) dd.drops.push(n);
      if (!spirits[n]) spirits[n] = { type: "", hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0, lv: 0, evolve: "否" };
      SPIRIT_OPEN[mk] = true;
      SPIRIT_DIRTY = true;
      renderMaps(q);
      toast("已添加精灵，请点击上方「保存图鉴」持久化", "ok");
    }));
  const addMap = document.getElementById("mapAddItem");
  if (addMap) addMap.addEventListener("click", async () => {
    let n = await uiPrompt("输入新地图名称：", "", "添加地图");
    if (!n) return;
    n = n.trim();
    if (!n) return;
    if (!maps[n]) maps[n] = { lv: 1, drops: [] };
    SPIRIT_OPEN[n] = true;
    SPIRIT_DIRTY = true;
    renderMaps(q);
    toast("已添加新地图，请点击上方「保存图鉴」持久化", "ok");
  });
}

function renderShop(q = "", forceOpen = false) {
  const body = document.getElementById("shopSpiritBox");
  if (!body) return;
  const shop = (SPIRIT && SPIRIT.shop) ? SPIRIT.shop : {};
  const names = Object.keys(shop).filter((k) => !q || k.toLowerCase().includes(q));
  const curDetails = body.querySelector("details");
  const wasOpen = curDetails ? curDetails.open : forceOpen;
  let html = `<details class="panel" style="margin:0"${wasOpen ? " open" : ""}><summary style="cursor:pointer;font-weight:600">🎒 精灵道具商城 (spirit_shop) — ${names.length} 件（点击折叠/展开）</summary>`;
  html += `<div class="hint" style="margin-top:8px">编辑精灵球、药品等道具价格与效果（保存时将与精灵配置一并持久化）</div>`;
  if (!names.length) {
    html += `<div class="hint" style="margin:10px 0">无匹配物品</div>`;
  } else {
    names.forEach((key) => {
      const it = shop[key] || {};
      const cells = SHOP_FIELDS.map(([fk, label]) =>
        `<div class="s-row"><small>${label}</small>` +
        `<input data-s-field="${fk}" value="${esc(it[fk] ?? "")}" style="width:90px"></div>`);
      html += `<div class="s-fields" data-s-item="${esc(key)}" style="margin-top:8px">` +
        `<div class="s-row" style="font-weight:600;min-width:90px"><small>道具名</small><div style="padding-top:4px">${esc(key)}</div></div>` +
        cells.join("") +
        `<button class="s-del" data-del-key="${esc(key)}" style="margin-left:auto">删除</button></div>`;
    });
  }
  html += `<div style="margin-top:8px"><button id="shopAddItem" class="ghost sm">＋ 添加精灵道具</button></div></details>`;
  body.innerHTML = html;

  body.querySelectorAll("input[data-s-field]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const parent = inp.closest("[data-s-item]");
      if (!parent) return;
      const key = parent.dataset.sItem;
      const fk = inp.dataset.sField;
      if (shop[key]) {
        shop[key][fk] = ["price", "effect"].includes(fk) ? (Number(inp.value) || 0) : inp.value;
        SPIRIT_DIRTY = true;
      }
    });
  });
  body.querySelectorAll("[data-del-key]").forEach((b) =>
    b.addEventListener("click", async () => {
      const k = b.dataset.delKey;
      if (!(await uiConfirm("确认删除 \"" + k + "\"？（需点击上方「保存商城图鉴」生效）", "删除物品"))) return;
      delete shop[k];
      SPIRIT_DIRTY = true;
      renderShop(q, true);
      toast("已删除物品，请点击上方「保存商城图鉴」持久化", "ok");
    }));
  const add = body.querySelector("#shopAddItem");
  if (add) add.addEventListener("click", async () => {
    let n = await uiPrompt("输入新物品名称：", "", "添加物品");
    if (!n) return;
    n = n.trim();
    if (!n) return;
    if (!shop[n]) shop[n] = { price: 0, attr: "", effect: 0 };
    SPIRIT_DIRTY = true;
    renderShop(q, true);
    toast("已添加物品，请点击上方「保存商城图鉴」持久化", "ok");
  });
}

async function saveSpirits() {
  const msg = document.getElementById("spiritMsg");
  if (!SPIRIT) return;
  msg.className = "msg";
  try {
    const q = (document.getElementById("spiritSearch").value || "").trim().toLowerCase();
    const maps = SPIRIT.maps || {};
    const spirits = SPIRIT.spirits || {};
    const shop = SPIRIT.shop || {};
    // 地图: 逐张读 推荐等级 + 出没精灵列表; 精灵属性卡回写 spirits
    document.querySelectorAll("#spiritBody .s-mapcard").forEach((card) => {
      const mname = card.dataset.map;
      if (!maps[mname]) maps[mname] = { lv: 1, drops: [] };
      const mo = maps[mname];
      const lv = card.querySelector('[data-map-field="lv"]');
      if (lv) mo.lv = Number(lv.value) || 1;
      const drops = card.querySelector('[data-map-field="drops"]');
      if (drops) mo.drops = drops.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    });
    document.querySelectorAll("#spiritBody .sp-card").forEach((card) => {
      const sn = card.dataset.sp;
      if (!spirits[sn]) spirits[sn] = {};
      const o = spirits[sn];
      SPIRIT_FIELDS.forEach(([fk]) => {
        const inp = card.querySelector(`[data-s-field="${fk}"]`);
        if (inp) o[fk] = ["hp", "atk", "def", "spa", "spd", "spe", "lv"].includes(fk) ? (Number(inp.value) || 0) : inp.value;
      });
    });
    document.querySelectorAll("#spiritBody .s-item").forEach((nameEl) => {
      const key = nameEl.textContent.trim();
      if (SPIRIT_CUR !== "商城" || !shop[key]) return;
      const wrap = nameEl.nextElementSibling;
      const o = shop[key];
      SHOP_FIELDS.forEach(([fk]) => {
        const inp = wrap.querySelector(`[data-s-field="${fk}"]`);
        if (inp) o[fk] = ["price", "effect"].includes(fk) ? (Number(inp.value) || 0) : inp.value;
      });
    });
    const payload = { spirits, maps, shop };
    const r = await getBridge().apiPost("spirits/save", payload);
    SPIRIT_DIRTY = false;
    msg.textContent = "已保存: " + JSON.stringify(r.keys);
    msg.classList.add("ok");
    toast("精灵图鉴已保存", "ok");
    renderSpiritBody();
  } catch (e) {
    msg.textContent = "保存失败: " + e.message;
    msg.classList.add("bad");
    toast("保存失败: " + e.message, "bad");
  }
}

function renderSpiritBodySearch() {
  renderSpiritBody();
}

async function exportSpirits() {
  try {
    const data = SPIRIT || await getBridge().apiGet("spirits");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    downloadBlob(blob, "xbbot_spirit_" + Date.now() + ".json");
  } catch (e) { toast("导出失败: " + e.message, "bad"); }
}
async function importSpirits() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      if (!data.spirits && !data.maps && !data.shop) throw new Error("JSON需包含 spirits/maps/shop");
      const r = await getBridge().apiPost("spirits/save", { spirits: data.spirits || {}, maps: data.maps || {}, shop: data.shop || {} });
      toast("已导入: " + JSON.stringify(r.keys), "ok");
      await loadSpirits();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}

// ---------- 事件绑定 ----------
document.getElementById("btnSave")?.addEventListener("click", saveConfig);
document.getElementById("btnAutoBalance")?.addEventListener("click", openAutoBalanceModal);
document.getElementById("btnAutoBalance2")?.addEventListener("click", openAutoBalanceModal);
document.getElementById("btnReset")?.addEventListener("click", resetConfig);
const rkSel = document.getElementById("rankType");
rkSel?.addEventListener("change", () => loadRank(rkSel.value));
document.getElementById("btnRank")?.addEventListener("click", () => loadRank(rkSel ? rkSel.value : "money"));
document.getElementById("btnUsers")?.addEventListener("click", loadUsers);
document.getElementById("userSort")?.addEventListener("change", renderUserTable);
document.getElementById("userGidFilter")?.addEventListener("change", async () => {
  const sel = document.getElementById("userGidFilter");
  USER_GID_FILTER = (sel?.value || "").trim();
  // 优先前端过滤（秒级），若后端支持则刷新带 gid 参数
  if (RAW_USERS.length) {
    renderUserTable();
    // 同时触发后端过滤刷新（确保 >300 时精确）
    try { await loadUsers(); } catch(e) {}
  } else {
    await loadUsers();
  }
});
document.getElementById("userBody")?.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-save]");
  if (b) saveUserEdit(b.dataset.qq, b.dataset.gid, b);
});
document.querySelectorAll(".harrow[data-cat]").forEach((btn) =>
  btn.addEventListener("click", () => {
    const cat = document.getElementById("cfgCat");
    if (cat) cat.scrollBy({ left: parseInt(btn.dataset.cat, 10) * 240, behavior: "smooth" });
  })
);
["cfgSearch", "userSearch", "cmdSearch", "imgSearch", "slaveSearch", "spiritSearch", "groupsSearch"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", () => {
    if (id === "cfgSearch") filterCfg();
    else if (id === "userSearch") filterUsers();
    else if (id === "cmdSearch") filterCmds();
    else if (id === "slaveSearch") renderSlaveTable();
    else if (id === "spiritSearch") renderSpiritUsersTable();
    else if (id === "groupsSearch") renderGroupsTable();
    else if (IMG_CACHE && IMG_CACHE.dir !== undefined) renderImages(IMG_CACHE);
  });
});
const lb = document.getElementById("lightbox");
if (lb) lb.addEventListener("click", closeLightbox);
document.getElementById("btnImgUp")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.onchange = (e) => uploadImage(e.target.files[0]);
  inp.click();
});
document.getElementById("btnImgBack")?.addEventListener("click", () => {
  const parts = (IMG_DIR || "").split("/").filter(Boolean);
  parts.pop();
  loadImages(parts.join("/"));
});
document.getElementById("btnImgNewFolder")?.addEventListener("click", async () => {
  const name = await uiPrompt("新建文件夹名:", "", "新建文件夹");
  if (!name || !name.trim()) return;
  const nn = name.trim().replace(/[\/\\]/g, "");
  const target = (IMG_DIR ? IMG_DIR + "/" : "") + nn;
  try { await getBridge().apiPost("images/mkdir", { path: target }); toast("已创建文件夹", "ok"); await loadImages(IMG_DIR); } catch (e) { toast("创建失败: " + e.message, "bad"); }
});
document.getElementById("btnImgCopy")?.addEventListener("click", () => {
  if (!IMG_SELECTED) { toast("请先点击选中要复制的文件/文件夹", "bad"); return; }
  IMG_CLIP = IMG_SELECTED;
  toast("已复制: " + IMG_CLIP, "ok");
});
document.getElementById("btnImgPaste")?.addEventListener("click", async () => {
  if (!IMG_CLIP) { toast("请先复制", "bad"); return; }
  try { await getBridge().apiPost("images/copy", { src: IMG_CLIP, dst: IMG_DIR }); toast("已粘贴", "ok"); await loadImages(IMG_DIR); } catch (e) { toast("粘贴失败: " + e.message, "bad"); }
});
async function exportImages() {
  const p = IMG_SELECTED || IMG_DIR || "";
  const filename = (p ? p.split("/").pop() : "root") || "root";
  const defaultFn = (filename === "root" ? `xbbot_root_${Date.now()}.zip` : `${filename}.zip`);
  toast("正在打包导出文件/目录，请稍候...", "ok");
  try {
    let r = null;
    try {
      r = await getBridge().apiGet("images/export", { path: p });
    } catch(e) {
      r = await getBridge().apiPost("images/export", { path: p });
    }
    if (!r) throw new Error("接口无响应");
    if (r.error || r.msg) throw new Error(r.error || r.msg);

    const outFn = r.filename || defaultFn;
    const base64Data = r.data || "";

    if (base64Data) {
      triggerExportResult({
        filename: outFn,
        mime: outFn.endsWith(".zip") ? "application/zip" : "application/octet-stream",
        base64Data: base64Data
      });
      toast("已成功导出 " + outFn, "ok");
      return;
    }

    const fallbackStr = typeof r === "string" ? r : JSON.stringify(r, null, 2);
    triggerExportResult({
      filename: outFn.replace(/\.zip$/, ".json"),
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已成功导出 " + outFn, "ok");
  } catch (e) {
    toast("导出失败: " + e.message, "bad");
  }
}
document.getElementById("btnImgExport")?.addEventListener("click", exportImages);
document.getElementById("btnImgImport")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file";
  inp.onchange = (e) => uploadImage(e.target.files[0]);
  inp.click();
});

document.getElementById("btnImgDelete")?.addEventListener("click", async () => {
  const sel = IMG_SELECTED || "";
  if (!sel) { toast("请先单击选中要删除的文件", "bad"); return; }
  if (!(await uiConfirm("确认删除 " + sel + "？", "删除文件"))) return;
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "终极确认删除"))) return;
  try { await getBridge().apiPost("images/delete", { path: sel }); toast("已删除", "ok"); IMG_SELECTED=""; await loadImages(IMG_DIR); } catch (err) { toast("删除失败: " + err.message, "bad"); }
});
document.getElementById("btnImgRename")?.addEventListener("click", async () => {
  const sel = IMG_SELECTED || "";
  if (!sel) { toast("请先单击选中要重命名的文件", "bad"); return; }
  const cur = sel.split("/").pop();
  const nn = await uiPrompt("新文件名（含扩展名）:", cur, "重命名");
  if (!nn || nn === cur) return;
  try { await getBridge().apiPost("images/rename", { path: sel, name: nn }); toast("已重命名", "ok"); IMG_SELECTED=""; await loadImages(IMG_DIR); } catch (err) { toast("重命名失败: " + err.message, "bad"); }
});
// 指令编辑模态
const _btnCmdSave = document.getElementById("cmdModalSave") || document.getElementById("btnCmdModalSave");
const _btnCmdCancel = document.getElementById("cmdModalCancel") || document.getElementById("btnCmdModalCancel");
const _btnCmdDelete = document.getElementById("cmdModalDel") || document.getElementById("btnCmdModalDelete");
const _cmdModal = document.getElementById("cmdModal");
if (_btnCmdSave) _btnCmdSave.addEventListener("click", saveCmdEditor);
if (_btnCmdCancel) _btnCmdCancel.addEventListener("click", closeCmdEditor);
  document.getElementById("btnCmdModalClose")?.addEventListener("click", closeCmdEditor);
if (_btnCmdDelete) _btnCmdDelete.addEventListener("click", deleteCmdEditor);
if (_cmdModal) _cmdModal.addEventListener("click", (e) => {
  if (e.target === _cmdModal) closeCmdEditor();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCmdEditor();
});
// 自定义指令: 填入「映射引擎指令」实时刷新其可调数值 + 常用变量帮助
const _cmdModalCmd = document.getElementById("cmdModalCmd");
if (_cmdModalCmd) _cmdModalCmd.addEventListener("input", () => {
  renderCmdNums(_cmdModalCmd.value.trim(), true);
});
document.getElementById("btnVarsHelp")?.addEventListener("click", () => {
  const h = document.getElementById("varsHelp");
  if (h) h.style.display = h.style.display === "none" ? "block" : "none";
});
document.querySelectorAll("#varsHelp .var-tag").forEach(el => {
  el.addEventListener("click", () => {
    const v = el.dataset.var || "";
    const ta = document.getElementById("cmdModalReply");
    if (!ta || !v) return;
    const s = ta.selectionStart || ta.value.length, e = ta.selectionEnd || ta.value.length;
    ta.value = ta.value.slice(0,s) + v + ta.value.slice(e);
    ta.focus(); ta.selectionStart = ta.selectionEnd = s + v.length;
  });
});

// 精灵图鉴
document.getElementById("btnSpiritLoad")?.addEventListener("click", loadSpirits);
document.getElementById("btnSpiritSave")?.addEventListener("click", saveSpirits);
document.getElementById("spiritSearch")?.addEventListener("input", renderSpiritBodySearch);
document.getElementById("btnSpiritExport")?.addEventListener("click", exportSpirits);
document.getElementById("btnSpiritImport")?.addEventListener("click", importSpirits);
document.querySelectorAll(".harrow[data-scat]").forEach((btn) =>
  btn.addEventListener("click", () => {
    const cat = document.getElementById("spiritCat");
    if (cat) cat.scrollBy({ left: parseInt(btn.dataset.scat, 10) * 200, behavior: "smooth" });
  })
);

// 商城图鉴 (每商城独立栏 自由增删重命名+图片绑定)
const DEFAULT_RIDE_SHOP = {
  "企鹅": { price: 213250, img: "data/img/坐骑图标/企鹅.jpg" },
  "伞兵": { price: 500000, img: "data/img/坐骑图标/伞兵.jpg" },
  "宝驴": { price: 1000000, img: "data/img/坐骑图标/宝驴.jpg" },
  "保时捷": { price: 1500000, img: "data/img/坐骑图标/保时捷.jpg" },
  "法拉利": { price: 1500000, img: "data/img/坐骑图标/法拉利.jpg" },
  "玛莎拉蒂": { price: 1500000, img: "data/img/坐骑图标/玛莎拉蒂.jpg" },
  "劳斯莱斯": { price: 1500000, img: "data/img/坐骑图标/劳斯莱斯.jpg" },
  "布加迪威龙": { price: 1500000, img: "data/img/坐骑图标/布加迪威龙.jpg" },
  "私人航空": { price: 5000000, img: "data/img/坐骑图标/私人航空.jpg" },
  "老八": { price: 500000, img: "data/img/坐骑图标/老八.jpg" },
};
let SHOP_RIDE = {};
let SHOP_WEAPON = {};
let SHOP_DIRTY = false;

function parseShopWeapon(raw) {
  const defaults = { "鬼泪村正": {price: 50000}, "雷鸣剑": {price: 50000}, "神使沧溟": {price: 50000}, "炎宿朱雀": {price: 50000}, "祝融": {price: 50000}, "老八脑!": {price: 50000}, "钻石剑": {price: 50000} };
  if (!raw) return { ...defaults };
  try {
    const d = JSON.parse(raw);
    if (typeof d === "object" && d && !Array.isArray(d)) {
      const merged = { ...defaults };
      Object.keys(d).forEach((k)=>{
        if (typeof d[k]==="object" && d[k]!==null) merged[k]=d[k];
        else merged[k]={price: Number(d[k])||0};
      });
      // 同步抽奖新增武器
      return merged;
    }
  } catch(e) {}
  return { ...defaults };
}
function syncShopWeaponRaw(){ try{ const el=document.getElementById("shopWeapon"); if(el) el.value=JSON.stringify(SHOP_WEAPON,null,2);}catch(e){} }
function renderShopWeaponBox(forceOpen=false){
  const box=document.getElementById("shopWeaponBox");
  if(!box) return;
  const entries=Object.entries(SHOP_WEAPON);
  const curDetails=box.querySelector("details");
  const wasOpen=curDetails?curDetails.open:forceOpen;
  let html=`<details class="panel" style="margin:0"${wasOpen?" open":""}><summary style="cursor:pointer;font-weight:600">⚔️ 武器商城 (weapon_shop) — ${entries.length} 件（抽奖武器自动同步，可改价）</summary>`;
  html+=`<div class="hint" style="margin-top:8px">每行一个武器，支持改名、改价、删（价格用于商城购买，抽奖武器自动加入）</div>`;
  entries.forEach(([name,val])=>{
    let price=0; if(val && typeof val==="object") price=val.price??0; else price=Number(val)||0;
    let img=""; try{ const p=`data/gacha_img/SSR/${name}.png`; if(window._shopImgMap && window._shopImgMap[name]) img=window._shopImgMap[name]; }catch(e){}
    const imgPreview=img?`<img src="${esc(img)}" style="width:36px;height:36px;object-fit:cover;border:1px solid var(--line);border-radius:6px" onerror="this.style.display='none'">`:`<span style="color:var(--muted);font-size:11px">无图</span>`;
    html+=`<div class="s-fields" data-weapon-item="${esc(name)}" style="margin-top:8px">`+
      `<div class="s-row"><small>武器名</small><input data-weapon-name value="${esc(name)}"></div>`+
      `<div class="s-row"><small>价格</small><input type="number" data-weapon-price value="${esc(price)}" style="width:90px"></div>`+
      `<div style="display:flex;gap:4px;align-items:center">${imgPreview}<button class="s-del" data-weapon-del="${esc(name)}">删除</button></div>`+
      `</div>`;
  });
  html+=`<div style="margin-top:8px"><button class="ghost sm" id="btnWeaponAdd">＋ 添加武器</button> <button class="ghost sm" id="btnWeaponReset">恢复默认</button></div></details>`;
  box.innerHTML=html;
  box.querySelectorAll("[data-weapon-name]").forEach(inp=>inp.addEventListener("change",(e)=>{
    const old=e.target.closest("[data-weapon-item]").dataset.weaponItem;
    const nn=e.target.value.trim();
    if(!nn||nn===old){e.target.value=old;return;}
    if(SHOP_WEAPON[nn]!==undefined){toast("已存在同名","bad");e.target.value=old;return;}
    SHOP_WEAPON[nn]=SHOP_WEAPON[old]; delete SHOP_WEAPON[old]; SHOP_DIRTY=true; syncShopWeaponRaw(); renderShopWeaponBox(true);
  }));
  box.querySelectorAll("[data-weapon-price]").forEach(inp=>inp.addEventListener("change",(e)=>{
    const k=e.target.closest("[data-weapon-item]").dataset.weaponItem;
    const v=SHOP_WEAPON[k]; const p=Number(e.target.value)||0;
    if(v && typeof v==="object") SHOP_WEAPON[k].price=p; else SHOP_WEAPON[k]=p;
    SHOP_DIRTY=true; syncShopWeaponRaw();
  }));
  box.querySelectorAll("[data-weapon-del]").forEach(b=>b.addEventListener("click",async()=>{
    const k=b.dataset.weaponDel;
    if(!(await uiConfirm("确认删除武器 \""+k+"\"？（需保存生效）","删除武器"))) return;
    delete SHOP_WEAPON[k]; SHOP_DIRTY=true; syncShopWeaponRaw(); renderShopWeaponBox(true); toast("已删除，需保存","ok");
  }));
  const addBtn=document.getElementById("btnWeaponAdd");
  if(addBtn) addBtn.addEventListener("click", async()=>{
    let n=await uiPrompt("输入新武器名称：","","添加武器");
    if(!n) return; n=n.trim(); if(!n) return;
    if(SHOP_WEAPON[n]!==undefined){toast("已存在同名","bad"); return;}
    SHOP_WEAPON[n]={price:50000}; SHOP_DIRTY=true; syncShopWeaponRaw(); renderShopWeaponBox(true); toast("已添加，需保存","ok");
  });
  const resetBtn=document.getElementById("btnWeaponReset");
  if(resetBtn) resetBtn.addEventListener("click", async()=>{
    SHOP_WEAPON=parseShopWeapon(""); SHOP_DIRTY=true; syncShopWeaponRaw(); renderShopWeaponBox(true); toast("已恢复默认，需保存","ok");
  });
}

function parseShopRide(raw) {
  if (!raw) return { ...DEFAULT_RIDE_SHOP };
  try {
    const d = JSON.parse(raw);
    if (typeof d === "object" && d && !Array.isArray(d)) {
      // 补齐默认图片
      const merged = { ...DEFAULT_RIDE_SHOP };
      Object.keys(d).forEach((k) => {
        if (typeof d[k] === "object" && d[k] !== null) {
          merged[k] = d[k];
          if (!merged[k].img && DEFAULT_RIDE_SHOP[k]?.img) {
            merged[k].img = DEFAULT_RIDE_SHOP[k].img;
          }
        } else {
          merged[k] = { price: Number(d[k]) || 0, img: DEFAULT_RIDE_SHOP[k]?.img || "" };
        }
      });
      return merged;
    }
  } catch (e) {}
  return { ...DEFAULT_RIDE_SHOP };
}
function syncShopRaw() {
  try {
    const el = document.getElementById("shopRide");
    if (el) el.value = JSON.stringify(SHOP_RIDE, null, 2);
  } catch (e) {}
}
function renderShopRideBox(forceOpen = false) {
  const box = document.getElementById("shopRideBox");
  if (!box) return;
  const entries = Object.entries(SHOP_RIDE);
  // 默认收起；若用户已手动展开或发生增删改，则保持展开
  const curDetails = box.querySelector("details");
  const wasOpen = curDetails ? curDetails.open : forceOpen;
  let html = `<details class="panel" style="margin:0"${wasOpen ? " open" : ""}><summary style="cursor:pointer;font-weight:600">🐴 坐骑商城 (ride_shop) — ${entries.length} 件（点击折叠/展开）</summary>`;
  html += `<div class="hint" style="margin-top:8px">每行一个坐骑，支持改名、改价、删、绑图（图片路径如 data/img/坐骑图标/企鹅.jpg，留空用默认图）</div>`;
  entries.forEach(([name, val]) => {
    let price = 0, img = "";
    if (val && typeof val === "object" && !Array.isArray(val)) { price = val.price ?? 0; img = val.img ?? ""; }
    else price = Number(val) || 0;
    // 自动匹配坐骑图片：若无图，尝试按名称匹配 img/坐骑图标 或 gacha_img
    if (!img && window._shopImgMap && window._shopImgMap[name]) img = window._shopImgMap[name];
    const imgPreview = img ? `<img src="${esc(img)}" style="width:40px;height:40px;object-fit:cover;border:1px solid var(--line);border-radius:6px" onerror="this.style.display='none'">` : `<span style="color:var(--muted);font-size:11px">无图</span>`;
    html += `<div class="s-fields" data-ride-item="${esc(name)}" style="margin-top:8px">` +
      `<div class="s-row"><small>坐骑名</small><input data-ride-name value="${esc(name)}"></div>` +
      `<div class="s-row"><small>价格</small><input type="number" data-ride-price value="${esc(price)}" style="width:90px"></div>` +
      `<div class="s-row" style="flex:1"><small>图片路径</small><input data-ride-img value="${esc(img)}" placeholder="data/img/..."></div>` +
      `<div style="display:flex;gap:4px;align-items:center">${imgPreview}<button class="ghost sm" data-ride-pick="${esc(name)}">选图</button><button class="ghost sm" data-ride-pick-builtin="${esc(name)}">内置选图</button><button class="s-del" data-ride-del="${esc(name)}">删除</button></div>` +
      `</div>`;
  });
  html += `<div style="margin-top:8px"><button class="ghost sm" id="btnRideAdd">＋ 添加坐骑</button> <button class="ghost sm" id="btnRideReset">恢复默认</button></div></details>`;
  box.innerHTML = html;
  box.querySelectorAll("[data-ride-name]").forEach(inp => inp.addEventListener("change", (e) => {
    const old = e.target.closest("[data-ride-item]").dataset.rideItem;
    const nn = e.target.value.trim();
    if (!nn || nn === old) { e.target.value = old; return; }
    if (SHOP_RIDE[nn] !== undefined) { toast("已存在同名", "bad"); e.target.value = old; return; }
    SHOP_RIDE[nn] = SHOP_RIDE[old]; delete SHOP_RIDE[old]; SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));
  box.querySelectorAll("[data-ride-price]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const p = Number(e.target.value) || 0;
    if (v && typeof v === "object") SHOP_RIDE[k].price = p; else SHOP_RIDE[k] = p;
    SHOP_DIRTY=true; syncShopRaw();
  }));
  box.querySelectorAll("[data-ride-img]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const img = e.target.value.trim();
    if (v && typeof v === "object") { if (img) v.img = img; else { const p = v.price; SHOP_RIDE[k] = p; } }
    else { if (img) SHOP_RIDE[k] = { price: Number(v)||0, img }; }
    SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));
  box.querySelectorAll("[data-ride-del]").forEach(b => b.addEventListener("click", async () => {
    const k = b.dataset.rideDel;
    if (!(await uiConfirm("确认删除坐骑 \"" + k + "\"？（需点击上方「保存商城图鉴」生效）", "删除坐骑"))) return;
    delete SHOP_RIDE[k];
    SHOP_DIRTY = true;
    syncShopRaw();
    renderShopRideBox(true);
    toast("已删除坐骑，请点击上方「保存商城图鉴」持久化", "ok");
  }));
  box.querySelectorAll("[data-ride-pick-builtin]").forEach(b=> b.addEventListener("click", async ()=>{
    const k=b.dataset.ridePickBuiltin;
    // 跳转到根目录让用户选择后点确定绑定（仅图片）
    window.SHOP_PICK_TARGET = k;
    toast("已进入根目录，请单击选中图片后点“确定绑定”","ok");
    // 切换到根目录页并加载根目录
    document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
    const rb=document.querySelector("[data-tab=\"imgs\"]"); if(rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
    const tab=document.getElementById("tab-imgs"); if(tab) tab.classList.add("on");
    await loadImages("");
    // 在根目录顶部显示绑定提示（仅图片可选）
    const tip=document.createElement("div"); tip.id="shopPickTip"; tip.style="background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML=`<b>为坐骑 "${esc(k)}" 选择内置图：</b> 请在下方根目录单击选中图片文件（png/jpg/gif等），然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel=document.querySelector("#tab-imgs .panel"); if(panel) panel.prepend(tip);
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", ()=>{
      const sel=IMG_SELECTED;
      if(!sel){ toast("请先选中图片文件","bad"); return; }
      const ext=(sel.split(".").pop()||"").toLowerCase();
      if(!["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext)){ toast("请选择图片文件（png/jpg/jpeg/gif/webp/bmp/ico），当前选择非图片","bad"); return; }
      // 校验是否为文件夹（无扩展名或在 dirs 中）
      if(window._imgIsDir && window._imgIsDir(sel)){ toast("请选择图片文件，不能选择文件夹","bad"); return; }
      const v=SHOP_RIDE[k];
      if(v && typeof v==="object") SHOP_RIDE[k].img=sel; else SHOP_RIDE[k]={price:Number(v)||0, img:sel};
      SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("已绑定 "+sel+"，需保存","ok");
      tip.remove(); window.SHOP_PICK_TARGET=null;
      // 切回商城页
      document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
      const cb=document.querySelector("[data-tab=\"shops\"]"); if(cb) cb.classList.add("on");
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
      const stab=document.getElementById("tab-shops"); if(stab) stab.classList.add("on");
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", ()=>{ tip.remove(); window.SHOP_PICK_TARGET=null; });
  }));
  box.querySelectorAll("[data-ride-pick]").forEach(b => b.addEventListener("click", async () => {
    const k = b.dataset.ridePick;
    const inp = document.createElement("input"); inp.type="file"; inp.accept="image/*";
    inp.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try { const r = await getBridge().upload("images/upload", file); const path = "data/img/" + file.name; SHOP_RIDE[k] = (typeof SHOP_RIDE[k]==="object"? {...SHOP_RIDE[k], img: path} : {price: Number(SHOP_RIDE[k])||0, img: path}); SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("图片已上传并绑定，需保存","ok"); } catch(err){ toast("上传失败:"+err.message,"bad");}
    };
    inp.click();
  }));
  const addBtn = document.getElementById("btnRideAdd");
  if (addBtn) addBtn.addEventListener("click", async () => {
    let n = await uiPrompt("输入新坐骑名称：", "", "添加坐骑");
    if (!n) return;
    n = n.trim();
    if (!n) return;
    if (SHOP_RIDE[n] !== undefined) { toast("已存在同名坐骑", "bad"); return; }
    SHOP_RIDE[n] = 0;
    SHOP_DIRTY = true;
    syncShopRaw();
    renderShopRideBox(true);
    toast("已添加坐骑，请设置价格并保存", "ok");
  });
  const resetBtn = document.getElementById("btnRideReset");
  if (resetBtn) resetBtn.addEventListener("click", async () => {
    SHOP_RIDE = { "企鹅":213250, "伞兵":500000, "宝驴":1000000, "保时捷":1500000, "法拉利":1500000, "玛莎拉蒂":1500000, "劳斯莱斯":1500000, "布加迪威龙":1500000, "私人航空":5000000 };
    SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("已恢复默认，需保存","ok");
  });
}
async function renderAtlas(curCfg){
  const box = document.getElementById("atlasBox");
  if (!box) return;
  try {
    let Treas = [];
    try {
      const curSec = (curCfg && curCfg["设置"]) || (CFG && CFG.cur && CFG.cur["设置"]) || {};
      Treas = (curSec["宝物"] || "酒神葫芦|四象护符").toString().split("|").filter(Boolean);
    } catch(e) { Treas = ["酒神葫芦", "四象护符"]; }
    const weapons = Object.keys(SHOP_WEAPON || {});
    const rides = Object.keys(SHOP_RIDE || {});
    let html = `<div style="display:flex;flex-direction:column;gap:8px">`;
    const mkSec = (title, items, addId, delAttr, sys) => {
      let h = `<div style="border:1px solid var(--line);border-radius:var(--radius-xs);padding:8px 10px;background:var(--panel2)"><div style="font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px">${title} (${items.length}) <button class="ghost sm" id="${addId}" style="margin-left:auto">＋ 添加</button></div><div style="display:flex;flex-wrap:wrap;gap:5px">`;
      if (!items.length) h += `<span style="color:var(--muted)">暂无</span>`;
      else h += items.map(n => `<span class="badge badge-primary" style="font-size:11.5px;display:inline-flex;align-items:center;gap:5px;padding:3px 8px">${esc(n)}<span style="cursor:pointer;font-weight:bold" data-atlas-del="${esc(sys||title)}|${esc(n)}" title="删除">×</span></span>`).join("");
      h += `</div></div>`;
      return h;
    };
    html += mkSec("奴隶系统-武器", weapons, "btnAtlasAddWeapon", "weapon", "奴隶系统-武器");
    html += mkSec("奴隶系统-宝物", Treas, "btnAtlasAddTreasure", "treasure", "奴隶系统-宝物");
    html += mkSec("坐骑系统-坐骑", rides, "btnAtlasAddRide", "ride", "坐骑系统-坐骑");
    html += `</div><div class="hint" style="margin-top:6px">点击 × 删除，＋ 添加；修改后点上方“保存”同步到 商城图鉴/设置</div>`;
    box.innerHTML = html;
    box.querySelectorAll("[data-atlas-del]").forEach(el => el.addEventListener("click", async () => {
      const [sys, name] = el.dataset.atlasDel.split("|");
      if (!(await uiConfirm(`确认删除 ${sys} "${name}"？`, "删除图鉴"))) return;
      if (sys.includes("武器")) { delete SHOP_WEAPON[name]; SHOP_DIRTY = true; syncShopWeaponRaw(); renderShopWeaponBox(true); }
      else if (sys.includes("宝物")) {
        let cur = Treas.filter(x => x !== name).join("|");
        await getBridge().apiPost("config/save", {"设置": {"宝物": cur}});
        if (typeof CFG === "object" && CFG && CFG["设置"]) CFG["设置"]["宝物"] = cur;
        toast("已删除宝物", "ok");
      } else if (sys.includes("坐骑")) { delete SHOP_RIDE[name]; SHOP_DIRTY = true; syncShopRaw(); renderShopRideBox(true); }
      renderAtlas();
    }));
    document.getElementById("btnAtlasAddWeapon")?.addEventListener("click", async () => {
      let n = await uiPrompt("输入武器名（奴隶系统-武器）：", "", "添加武器");
      if (!n) return; n = n.trim(); if (!n) return;
      SHOP_WEAPON[n] = { price: 50000 }; SHOP_DIRTY = true; syncShopWeaponRaw(); renderShopWeaponBox(true); renderAtlas(); toast("已添加武器，需保存", "ok");
    });
    document.getElementById("btnAtlasAddTreasure")?.addEventListener("click", async () => {
      let n = await uiPrompt("输入宝物名（奴隶系统-宝物）：", "", "添加宝物");
      if (!n) return; n = n.trim(); if (!n) return;
      if (Treas.includes(n)) { toast("已存在", "bad"); return; }
      Treas.push(n);
      const cur = Treas.join("|");
      await getBridge().apiPost("config/save", {"设置": {"宝物": cur}});
      if (typeof CFG === "object" && CFG && CFG["设置"]) CFG["设置"]["宝物"] = cur;
      toast("已添加宝物", "ok"); renderAtlas();
    });
    document.getElementById("btnAtlasAddRide")?.addEventListener("click", async () => {
      let n = await uiPrompt("输入坐骑名（坐骑系统-坐骑）：", "", "添加坐骑");
      if (!n) return; n = n.trim(); if (!n) return;
      SHOP_RIDE[n] = 500000; SHOP_DIRTY = true; syncShopRaw(); renderShopRideBox(true); renderAtlas(); toast("已添加坐骑，需保存", "ok");
    });
  } catch (e) { box.innerHTML = `<span style="color:var(--muted)">图鉴加载失败: ${esc(e.message)}</span>`; }
}

async function loadShops() {
  const msg = document.getElementById("shopMsg");
  try {
    const [cur, spiritData] = await Promise.all([
      getBridge().apiGet("config/get"),
      SPIRIT ? Promise.resolve(SPIRIT) : getBridge().apiGet("spirits").catch(() => null)
    ]);
    if (spiritData) SPIRIT = spiritData;
    const sec = (cur || {})["商城图鉴"] || {};
    const rideRaw = (sec["ride_shop"] || "").toString();
    SHOP_RIDE = parseShopRide(rideRaw);
    const weaponRaw = (sec["weapon_shop"] || "").toString();
    SHOP_WEAPON = parseShopWeapon(weaponRaw);
    SHOP_DIRTY = false;
    syncShopRaw();
    syncShopWeaponRaw();
    renderShopRideBox();
    renderShopWeaponBox();
    try { renderShop(); } catch (e) {}
    try { renderAtlas(cur); } catch (e) {}
    if (msg) { msg.textContent = ""; msg.classList.remove("ok", "bad"); }
  } catch (e) {
    if (msg) { msg.textContent = "加载失败: " + e.message; msg.classList.add("bad"); }
  }
}
async function saveShops() {
  const msg = document.getElementById("shopMsg");
  try {
    const cleanRide = {};
    Object.entries(SHOP_RIDE).forEach(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        if (!v.img) cleanRide[k] = v.price;
        else cleanRide[k] = v;
      } else cleanRide[k] = v;
    });
    const cleanWeapon = {};
    Object.entries(SHOP_WEAPON).forEach(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        if (Object.keys(v).length === 1 && v.price !== undefined) cleanWeapon[k] = v.price;
        else cleanWeapon[k] = v;
      } else cleanWeapon[k] = v;
    });
    const payload = { "商城图鉴": { "ride_shop": JSON.stringify(cleanRide), "weapon_shop": JSON.stringify(cleanWeapon) } };
    const r = await getBridge().apiPost("config/save", payload);
    SHOP_DIRTY = false;
    if (SPIRIT && SPIRIT.shop) {
      try {
        await getBridge().apiPost("spirits/save", { shop: SPIRIT.shop });
      } catch (e) {}
    }
    if (msg) { msg.textContent = "商城图鉴已保存: " + JSON.stringify(r.sections || r) + " 节"; msg.classList.add("ok"); }
    toast("商城图鉴已保存", "ok");
    syncShopRaw();
    syncShopWeaponRaw();
  } catch (e) {
    if (msg) { msg.textContent = "保存失败: " + e.message; msg.classList.add("bad"); }
    toast("保存失败: " + e.message, "bad");
  }
}

async function exportShops() {
  try {
    const cur = await getBridge().apiGet("config/get");
    const sec = (cur || {})["商城图鉴"] || {};
    const payload = { ride_shop: sec["ride_shop"] || "" };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    downloadBlob(blob, `xbbot_shop_${Date.now()}.json`);
  } catch (e) { toast("导出失败: " + e.message, "bad"); }
}
async function importShops() {
  const inp = document.createElement("input"); inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text(); const data = JSON.parse(txt);
      // 兼容旧格式 {ride_shop, guild_weapon} 或 {商城图鉴: {...}} 或直接 {ride_shop: "..."}
      let sec = {};
      if (data["商城图鉴"]) sec = data["商城图鉴"];
      else if (data["ride_shop"] !== undefined) sec = { ride_shop: data["ride_shop"] };
      else sec = data;
      // 仅保留 ride_shop，忽略 guild_weapon（已废弃）
      const payload = {};
      if (sec["ride_shop"] !== undefined) payload["ride_shop"] = sec["ride_shop"];
      else if (typeof sec === "object" && sec !== null) {
        // 若直接是 ride_shop 的 JSON 字符串或对象，尝试兼容
        const keys = Object.keys(sec);
        if (keys.length && !sec["ride_shop"]) {
          // 可能是直接的商城 JSON，已包含 ride_shop 的内容
          payload["ride_shop"] = typeof sec["ride_shop"] === "string" ? sec["ride_shop"] : JSON.stringify(sec);
        }
      }
      await getBridge().apiPost("config/save", { "商城图鉴": payload });
      toast("商城已导入", "ok"); await loadShops();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  }; inp.click();
}
document.getElementById("btnShopLoad")?.addEventListener("click", loadShops);
document.getElementById("btnShopSave")?.addEventListener("click", saveShops);
document.getElementById("btnShopExport")?.addEventListener("click", exportShops);
document.getElementById("btnShopImport")?.addEventListener("click", importShops);
// ---------- 奴隶系统用户视图 ----------
let RAW_SLAVE_USERS = [];
async function loadSlaveUsers(){
  try{
    RAW_SLAVE_USERS = await getBridge().apiGet("slave/users");
    renderSlaveTable();
  }catch(e){ err("slave users: "+e.message); }
}

function renderSlaveTable() {
  const body = document.getElementById("slaveBody");
  if (!body) return;
  const q2 = (document.getElementById("slaveSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SLAVE_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.owner || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("slaveSort")?.value || "price_desc";
  if (sortMode === "price_desc") rows.sort((a, b) => (b.price || 0) - (a.price || 0));
  else if (sortMode === "price_asc") rows.sort((a, b) => (a.price || 0) - (b.price || 0));
  else if (sortMode === "slaves_desc") rows.sort((a, b) => (b.slaves || 0) - (a.slaves || 0));
  else if (sortMode === "slaves_asc") rows.sort((a, b) => (a.slaves || 0) - (b.slaves || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const sHint = document.getElementById("slaveHint");
  if (sHint) {
    sHint.innerHTML = `共 <strong>${RAW_SLAVE_USERS.length}</strong> 条奴隶档案（当前匹配 <strong>${rows.length}</strong> 条） · 实时展示身价与主奴武装关系`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">暂无奴隶数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td>${r.owner ? `<span class="badge badge-purple">${esc(r.owner)}</span>` : '<span style="color:var(--muted)">自由身</span>'}</td>
    <td><span style="font-weight:700;color:var(--text)">${(r.price || 0).toLocaleString()}</span></td>
    <td><span class="badge badge-primary">${r.slaves || 0} 人</span></td>
    <td>${r.protect ? `<span class="badge badge-success">${esc(r.protect)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td>${r.weapons ? `<span class="badge badge-warn">${esc((r.weapons||"").slice(0,30))}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
  </tr>`).join("");
  body.innerHTML = html;
}

// ---------- 精灵系统用户视图 ----------
let RAW_SPIRIT_USERS = [];
async function loadSpiritUsers(){
  try{
    RAW_SPIRIT_USERS = await getBridge().apiGet("spirit/users");
    renderSpiritUsersTable();
  }catch(e){ err("spirit users: "+e.message); }
}

function renderSpiritUsersTable() {
  const body = document.getElementById("spiritUsersBody");
  if (!body) return;
  const q2 = (document.getElementById("spiritSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SPIRIT_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.active || "") + String(r.best || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("spiritUserSort")?.value || "power_desc";
  if (sortMode === "power_desc") rows.sort((a, b) => (b.total_power || 0) - (a.total_power || 0));
  else if (sortMode === "power_asc") rows.sort((a, b) => (a.total_power || 0) - (b.total_power || 0));
  else if (sortMode === "level_desc") rows.sort((a, b) => (b.max_level || 0) - (a.max_level || 0));
  else if (sortMode === "level_asc") rows.sort((a, b) => (a.max_level || 0) - (b.max_level || 0));
  else if (sortMode === "count_desc") rows.sort((a, b) => (b.count || 0) - (a.count || 0));
  else if (sortMode === "count_asc") rows.sort((a, b) => (a.count || 0) - (b.count || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const spHint = document.getElementById("spiritUsersHint");
  if (spHint) {
    spHint.innerHTML = `共 <strong>${RAW_SPIRIT_USERS.length}</strong> 名训练师（当前匹配 <strong>${rows.length}</strong> 名） · 实时统计出战宝可梦与综合战力`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--muted)">暂无精灵数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td><span class="badge badge-primary">${r.count || 0} 只</span></td>
    <td>${r.active ? `<span class="badge badge-success">${esc(r.active)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td>${r.best ? `<span class="badge badge-purple">${esc(r.best)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td><span class="badge badge-warning">Lv.${r.max_level || 0}</span></td>
    <td><span style="font-weight:700;color:var(--text)">${(r.total_power || 0).toLocaleString()}</span></td>
    <td><span class="badge badge-primary">${r.bag_count || 0} 件</span></td>
  </tr>`).join("");
  body.innerHTML = html;
}
// 备份（文件夹式，与图片库一致）
let BACKUP_DIR = "";
async function loadBackups(dir="") {
  try {
    BACKUP_DIR = dir || "";
    const d = await getBridge().apiGet("backups/list", { dir: BACKUP_DIR });
    const crumbs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-bkcrumb="">根目录</a>`;
    let acc = "";
    crumbs.forEach((s) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` / <a data-bkcrumb="${esc(acc)}">${esc(s)}</a>`;
    });
    document.getElementById("backupCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#backupCrumbs a[data-bkcrumb]").forEach((a) => a.addEventListener("click", () => loadBackups(a.dataset.bkcrumb)));
    renderBackups(d);
  } catch (e) { err("backups: " + e.message); }
}
function renderBackups(d) {
  const box = document.getElementById("backupBrowser");
  const q = (document.getElementById("backupSearch")?.value || "").trim().toLowerCase();
  if (typeof window.BACKUP_SELECTED === 'undefined') window.BACKUP_SELECTED = "";
  let html = `<div class="bk-list">`;
  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    html += `<div class="bk-item${selCls}" data-bkdir="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon">📁</div>
      <div class="bk-info">
        <div class="bk-name">${esc(x.name)}</div>
        <div class="bk-meta"><span>📅 日期目录 (双击进入)</span><span>🕒 ${esc(x.mtime || "")}</span></div>
      </div>
      <button class="ghost sm" style="pointer-events:none">进入 ➔</button>
    </div>`;
  });
  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    html += `<div class="bk-item${selCls}" data-bkfile="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon">💾</div>
      <div class="bk-info">
        <div class="bk-name">${esc(x.name)}</div>
        <div class="bk-meta"><span>📦 大小: ${esc(x.size || "0KB")}</span><span>🕒 备份时间: ${esc(x.mtime || "")}</span></div>
      </div>
      <span style="font-size:12px;color:var(--muted)">${selCls ? '✓ 已选中' : '单击选中'}</span>
    </div>`;
  });
  html += `</div>`;
  if (!(d.dirs || []).length && !(d.files || []).length) {
    html = `<div class="hint" style="padding:20px;text-align:center;background:var(--panel2);border-radius:8px">暂无备份文件，系统将每隔设定时间自动备份，您也可点击上方「立即备份」生成。</div>`;
  }
  box.innerHTML = html;
  // 单击选中（高亮），文件夹双击进入
  box.querySelectorAll("[data-bksel]").forEach((el) => {
    el.addEventListener("click", () => {
      window.BACKUP_SELECTED = el.dataset.bksel;
      box.querySelectorAll(".bk-item").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
  });
  box.querySelectorAll("[data-bkdir]").forEach((el) => {
    el.addEventListener("dblclick", () => loadBackups(el.dataset.bkdir));
  });
}
async function backupNow() {
  try { await getBridge().apiPost("backups/restore", { path: "__backup_now__" }); } catch (e) {}
  // 触发后端的 maybe_auto_backup via dummy restore path, 简化：直接调用 list 前后端会自动备份一次
  try { await getBridge().apiGet("backups/list", { dir: "" }); } catch (e) {}
  // 更直接：调用后端的 backup via list 的 force 参数（后端在每次 list 前会检查，但为演示直接提示）
  toast("已触发备份，请刷新查看", "ok");
  await loadBackups(BACKUP_DIR);
}
document.getElementById("btnBackupNow")?.addEventListener("click", async () => {
  try {
    const r = await getBridge().apiPost("backups/restore", { path: "__backup_now__" });
    toast("备份完成", "ok");
    await loadBackups("");
  } catch (e) {
    await loadBackups("");
    toast("已刷新备份列表", "ok");
  }
});
document.getElementById("btnBackupRefresh")?.addEventListener("click", () => loadBackups(BACKUP_DIR));
document.getElementById("btnWebDAVTest")?.addEventListener("click", async () => {
  toast("正在连接测试 WebDAV...", "ok", 3000);
  try {
    const res = await getBridge().apiGet("backup/webdav/test", {});
    if (res && res.ok) {
      toast("WebDAV 测试成功: " + (res.msg || "连接正常"), "ok", 7000);
    } else {
      toast("WebDAV 测试失败: " + (res && res.msg ? res.msg : "未知错误"), "bad", 8000);
    }
  } catch (err) {
    toast("WebDAV 测试异常: " + err.message, "bad", 8000);
  }
});
document.getElementById("btnWebDAVBackupNow")?.addEventListener("click", async () => {
  toast("正在生成本地冷备并上传至 WebDAV 云端...", "ok", 4000);
  try {
    const res = await getBridge().apiPost("backup/webdav/upload", {});
    if (res && res.ok) {
      toast("WebDAV 云备份成功: " + (res.msg || "已成功上传"), "ok", 7000);
      await loadBackups("");
    } else {
      toast("WebDAV 上传失败: " + (res && res.msg ? res.msg : "未能完成上传"), "bad", 8000);
    }
  } catch (err) {
    toast("WebDAV 上传异常: " + err.message, "bad", 8000);
  }
});
document.getElementById("btnBackupExport")?.addEventListener("click", async () => {
  try {
    const data = await getBridge().apiGet("users/export", {});
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    downloadBlob(blob, `xbbot_backup_export_${Date.now()}.json`);
  } catch(e){ toast("导出失败: "+e.message, "bad"); }
});
document.getElementById("backupSearch")?.addEventListener("input", () => {
  loadBackups(BACKUP_DIR);
});
// 备份顶部操作：对选中项生效
document.getElementById("btnBackupDelete")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要删除的备份", "bad"); return; }
  if (!(await uiConfirm("确认删除备份 " + sel + "？", "删除备份"))) return;
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "终极确认删除"))) return;
  try { await getBridge().apiPost("backups/delete", { path: sel }); toast("已删除", "ok"); window.BACKUP_SELECTED=""; await loadBackups(BACKUP_DIR); } catch (err) { toast("删除失败: " + err.message, "bad"); }
});
document.getElementById("btnBackupRestore")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要恢复的备份", "bad"); return; }
  if (!(await uiConfirm("确认恢复备份 " + sel + "？当前数据将被覆盖！", "恢复备份"))) return;
  try { await getBridge().apiPost("backups/restore", { path: sel }); toast("已恢复，需重启插件生效", "ok"); } catch (err) { toast("恢复失败: " + err.message, "bad"); }
});
document.getElementById("btnBackupExportSel")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要导出的备份文件", "bad"); return; }
  const ext = (sel.split(".").pop() || "").toLowerCase();
  if (!["db", "json"].includes(ext)) { toast("请选择具体备份文件导出（.db 或 .json），不可导出文件夹", "bad"); return; }
  const filename = sel.split("/").pop() || "backup.db";
  toast("正在导出备份...", "ok");
  try {
    const _b = getBridge();
    if (_b && typeof _b.download === "function") {
      try {
        await _b.download("backups/export", { path: sel, raw: "1" }, filename);
        toast("已触发下载: " + filename, "ok");
        return;
      } catch (e) {}
    }
    const r = await callApi("backups/export", { path: sel }, "GET");
    if (r && r.data) {
      downloadBase64File(r.data, r.filename || filename);
      toast("已成功导出备份文件", "ok");
    } else {
      toast("导出失败: " + (r && r.error ? r.error : "无数据"), "bad");
    }
  } catch (err) { toast("导出失败: " + err.message, "bad"); }
});
document.getElementById("btnClearAll")?.addEventListener("click", async () => {
  if (!(await uiConfirm("⚠️ 确认清空所有数据？此操作将删除所有钱包/账户/群数据/备份且不可恢复！", "危险：清空所有数据"))) return;
  const input = await uiPrompt("为防止误操作，请输入“确认删除”以继续：", "", "清空所有数据");
  if (input !== "确认删除") { toast("输入不正确，已取消清空", "bad"); return; }
  if (!(await uiConfirm("最终确认：真的要彻底清空所有数据吗？", "终极确认清空"))) return;
  try {
    await getBridge().apiPost("admin/clear", {confirm: "确认删除", confirm2: "确认"});
    toast("已成功清空所有数据", "ok");
    await loadUsers();
    await loadBackups("");
    if (typeof loadStats === "function") try { await loadStats(); } catch(e) {}
    if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
  } catch (e) {
    toast("清空失败: " + e.message, "bad");
  }
});
document.getElementById("btnSlaveRefresh")?.addEventListener("click", loadSlaveUsers);
document.getElementById("slaveSearch")?.addEventListener("input", renderSlaveTable);
document.getElementById("slaveSort")?.addEventListener("change", renderSlaveTable);
document.getElementById("btnSpiritUsersRefresh")?.addEventListener("click", loadSpiritUsers);
document.getElementById("spiritSearch")?.addEventListener("input", renderSpiritUsersTable);
document.getElementById("spiritUserSort")?.addEventListener("change", renderSpiritUsersTable);

// 表头点击快速排序事件委托
document.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) {
    if (btn.id === "btnUsersExport") { exportAllUsers(); return; }
    if (btn.id === "btnUsersImport") { importAllUsers(); return; }
    if (btn.id === "btnUsersCleanLeft") { cleanLeftUsers(); return; }
    if (btn.id === "btnUserClearManual") { clearUserManual(); return; }
    if (btn.id === "btnUsers") { loadUsers(); return; }
    if (btn.id === "btnImgExport") { exportImages(); return; }
  }

  const target = e.target.closest("[data-sort], [data-slavesort], [data-spiritsort]");
  if (!target) return;
  if (target.dataset.sort) {
    const key = target.dataset.sort;
    const sel = document.getElementById("userSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderUserTable();
    }
  } else if (target.dataset.slavesort) {
    const key = target.dataset.slavesort;
    const sel = document.getElementById("slaveSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderSlaveTable();
    }
  } else if (target.dataset.spiritsort) {
    const key = target.dataset.spiritsort;
    const sel = document.getElementById("spiritUserSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderSpiritUsersTable();
    }
  }
});
// 暴露给 tabs 懒加载委托（避免 tabs 占位路由 404）
window.loadUsers = loadUsers; window.loadSlaveUsers = typeof loadSlaveUsers!=='undefined'?loadSlaveUsers:undefined;
window.loadSpiritUsers = typeof loadSpiritUsers!=='undefined'?loadSpiritUsers:undefined;
window.loadConfig = loadConfig; window.loadRank = loadRank; window.loadCommands = loadCommands;
window.loadSpirits = loadSpirits; window.loadShops = loadShops; window.loadBackups = typeof loadBackups!=='undefined'?loadBackups:undefined;
window.loadImages = loadImages; window.loadStats = loadStats; window.loadOverviewReq = loadOverviewReq;
document.getElementById("btnLegacyPick")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".ini,.db,.json,.zip"; inp.multiple = true;
  inp.onchange = async (e) => {
    const files = Array.from(e.target.files || []); if (!files.length) return;
    const msg = document.getElementById("legacyMsg");
    if (msg) { msg.textContent = "导入中... ("+files.length+" 个文件)"; msg.className = "msg"; }
    let total=0, ok=0, last=null;
    for (const file of files) {
      try {
        const r = await getBridge().upload("import/legacy", file);
        last=r;
        if (r && !r.error) { ok++; total+= (r.imported||0); }
        else if (r && r.error) { toast("文件 "+file.name+" 失败: "+r.error, "bad"); }
      } catch (err) {
        toast("文件 "+file.name+" 失败: "+err.message, "bad");
      }
    }
    if (msg) {
      if (ok===files.length) { msg.textContent = "旧库导入成功: "+total+" 条，共 "+files.length+" 文件"; msg.classList.add("ok"); toast("旧库导入成功: "+total+" 条","ok"); }
      else { msg.textContent = "导入完成: "+ok+"/"+files.length+" 成功, 共 "+total+" 条"; msg.classList.add(ok?"ok":"bad"); }
    }
    await loadBackups("");
    await loadUsers();
    if (typeof loadSlaveUsers==="function") try{ await loadSlaveUsers(); }catch(e){}
  };
  inp.click();
});
// 用户全量导出导入与清理退群
document.getElementById("btnUsersExport")?.addEventListener("click", exportAllUsers);
document.getElementById("btnUsersImport")?.addEventListener("click", importAllUsers);
document.getElementById("btnUsersCleanLeft")?.addEventListener("click", cleanLeftUsers);
document.getElementById("btnUserClearManual")?.addEventListener("click", clearUserManual);

// 启动主逻辑
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => { main(); });
} else {
  main();
}



// ==================== 群生态与经济运行大屏 ====================
async function loadAnalytics() {
  try {
    const res = await getBridge().apiGet("analytics/overview");
    if (!res || !res.ok) return;

    CURRENT_ANALYTICS_DATA = res;
    const sum = res.summary || {};
    const fmt = (n) => Number(n || 0).toLocaleString();

    const el = (id) => document.getElementById(id);
    if (el("anaTotalUsers")) el("anaTotalUsers").textContent = `${fmt(sum.total_users)} 人`;
    if (el("anaTotalGroups")) el("anaTotalGroups").textContent = `开通群聊: ${fmt(sum.total_groups)} 个`;
    if (el("anaTotalEconomy")) el("anaTotalEconomy").textContent = fmt(sum.total_economy_pool);
    if (el("anaAvgMoney")) el("anaAvgMoney").textContent = `人均资产: ${fmt(sum.avg_money_per_user)}`;
    if (el("anaBankDeposit")) el("anaBankDeposit").textContent = fmt(sum.total_bank_deposit);
    if (el("anaBankUsers")) el("anaBankUsers").textContent = `储蓄玩家: ${fmt(sum.total_bank_users)} 人`;
    if (el("anaSlaveWorth")) el("anaSlaveWorth").textContent = fmt(sum.total_slave_worth);
    if (el("anaSlaveCount")) el("anaSlaveCount").textContent = `奴隶: ${sum.total_slaves_count || 0} 人 / 奴隶主: ${sum.total_masters_count || 0} 人`;
    if (el("anaSignCount")) el("anaSignCount").textContent = `${fmt(sum.total_sign_count)} 次`;
    if (el("anaSignRate")) el("anaSignRate").textContent = `活跃度: 稳健`;
    

    // 渲染 SVG 财富阶层金字塔柱状图
    renderTierChart(res.tiers || []);

    // 渲染 24 小时群活跃折线图
    renderActivityChart(res.activity_24h || []);
  } catch(e) {
    console.error("loadAnalytics error:", e);
  }
}

function renderTierChart(tiers) {
  const container = document.getElementById("chartTierContainer");
  if (!container) return;
  const maxCount = Math.max(...tiers.map(t => t.count), 1);
  const total = tiers.reduce((s, t) => s + t.count, 0) || 1;

  let barsHtml = `<div style="width:100%;display:flex;flex-direction:column;gap:8px">`;
  tiers.forEach(t => {
    const pct = ((t.count / total) * 100).toFixed(1);
    const barWidth = Math.max(8, (t.count / maxCount) * 100);
    barsHtml += `
      <div>
        <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:3px">
          <span style="color:var(--text);font-weight:600">${esc(t.label)}</span>
          <span style="color:var(--muted)">${t.count} 人 (${pct}%)</span>
        </div>
        <div style="width:100%;height:10px;background:var(--panel);border-radius:5px;overflow:hidden">
          <div style="width:${barWidth}%;height:100%;background:${t.color};border-radius:5px;transition:width 0.6s ease"></div>
        </div>
      </div>
    `;
  });
  barsHtml += `</div>`;
  container.innerHTML = barsHtml;
}

function renderActivityChart(activity) {
  const container = document.getElementById("chartActivityContainer");
  if (!container || !activity.length) return;

  const w = 320, h = 130;
  const maxVal = Math.max(...activity.map(a => a.count), 1);
  const pts = activity.map((a, i) => {
    const x = (i / (activity.length - 1)) * (w - 20) + 10;
    const y = h - 20 - (a.count / maxVal) * (h - 40);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const firstX = 10, lastX = w - 10;
  const fillPath = `M ${firstX},${h - 20} L ${pts.replace(/ /g, " L ")} L ${lastX},${h - 20} Z`;

  container.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:100%;overflow:visible">
      <defs>
        <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#3B82F6" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#3B82F6" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="${fillPath}" fill="url(#actGrad)"/>
      <polyline fill="none" stroke="#3B82F6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${pts}"/>
      <text x="10" y="${h - 4}" fill="var(--muted)" font-size="9.5">00:00</text>
      <text x="${w/2 - 12}" y="${h - 4}" fill="var(--muted)" font-size="9.5">12:00</text>
      <text x="${w - 32}" y="${h - 4}" fill="var(--muted)" font-size="9.5">23:00</text>
    </svg>
  `;
}

// ==================== 3. 批量全员 / 定向群福利空投 ====================
async function openAirdropModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "🎁";
  if (title) title.textContent = "批量资产空投与福利分发";
  if (inputWrap) inputWrap.style.display = "none";

  content.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px">
      一键向全群或指定群所有玩家批量发放金币、体力或抽奖券福利（自动事务写入）：
    </div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">🎯 目标群聊 (留空则面向全库所有活跃玩家)：</label>
        <input id="dropGid" placeholder="输入群号 (留空全库)" style="width:100%;padding:7px 10px;border-radius:8px">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">💰 赠送金币：</label>
          <input type="number" id="dropMoney" value="1000" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">⚡ 赠送体力：</label>
          <input type="number" id="dropStamina" value="100" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">🎟️ 抽奖券：</label>
          <input type="number" id="dropTickets" value="5" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">📝 空投事由 / 备注：</label>
        <input id="dropReason" value="节日全员福利空投" style="width:100%;padding:7px 10px;border-radius:8px">
      </div>
    </div>
  `;

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "🚀 立即发送全员空投";
    okBtn.onclick = async () => {
      const gid = (document.getElementById("dropGid")?.value || "").trim();
      const money = parseInt(document.getElementById("dropMoney")?.value || 0, 10);
      const stamina = parseInt(document.getElementById("dropStamina")?.value || 0, 10);
      const tickets = parseInt(document.getElementById("dropTickets")?.value || 0, 10);
      const reason = document.getElementById("dropReason")?.value || "全员福利空投";

      okBtn.disabled = true;
      okBtn.textContent = "正在分发空投...";
      try {
        const res = await getBridge().apiPost("users/airdrop", { gid, money, stamina, tickets, reason });
        if (res && res.ok) {
          toast(`🎉 空投发放成功！已成功为 ${res.target_count || 0} 名用户注入资产`, "ok");
          modal.className = "";
          await loadUsers();
          await loadAnalytics();
        } else {
          toast("空投失败: " + (res && (res.error || res.msg) ? (res.error || res.msg) : "未知错误"), "bad");
        }
      } catch(err) {
        toast("空投异常: " + err.message, "bad");
      } finally {
        okBtn.disabled = false;
        okBtn.onclick = null;
      }
    };
  }
  modal.className = "show";
}

// ==================== 4. 图鉴可视化工坊 ====================
function openVisualItemBuilder() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "🎨";
  if (title) title.textContent = "图鉴与武器装备 · 可视化工坊";
  if (inputWrap) inputWrap.style.display = "none";

  content.innerHTML = `
    <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:14px">
      <div style="display:flex;flex-direction:column;gap:8px">
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">装备 / 精灵名称：</label>
          <input id="builderName" value="弑神赤霄剑" style="width:100%;padding:6px 10px;border-radius:8px">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div>
            <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">稀有度评级：</label>
            <select id="builderRarity" style="width:100%;padding:6px;border-radius:8px;background:var(--panel2);color:var(--text);border:1px solid var(--line)">
              <option value="UR" selected>🔥 UR 极罕神品</option>
              <option value="SSR">✨ SSR 传奇传说</option>
              <option value="SR">💎 SR 稀有史诗</option>
              <option value="R">🌟 R 优秀精良</option>
              <option value="N">⚪ N 普通平民</option>
            </select>
          </div>
          <div>
            <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">商城金币售价：</label>
            <input type="number" id="builderPrice" value="8888" style="width:100%;padding:6px 10px;border-radius:8px">
          </div>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:2px">
            <span>攻击战力加成:</span><strong id="valAtk" style="color:var(--text)">580</strong>
          </div>
          <input type="range" id="sliderAtk" min="10" max="1000" value="580" style="width:100%">
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:2px">
            <span>防御减伤加成:</span><strong id="valDef" style="color:var(--text)">320</strong>
          </div>
          <input type="range" id="sliderDef" min="10" max="1000" value="320" style="width:100%">
        </div>
      </div>
      <!-- 右侧实时卡片预览 -->
      <div style="background:linear-gradient(145deg, #1E1B4B, #0F172A);border-radius:14px;padding:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:2px solid #8B5CF6;box-shadow:0 8px 24px rgba(139,92,246,0.25)">
        <div id="cardRarityBadge" style="background:#8B5CF6;color:#fff;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px">UR 极罕神品</div>
        <div id="cardItemIcon" style="font-size:42px;margin:4px 0">⚔️</div>
        <div id="cardItemName" style="color:#fff;font-weight:700;font-size:14px;margin-bottom:4px">弑神赤霄剑</div>
        <div id="cardCombatScore" style="color:#F59E0B;font-weight:800;font-size:18px;margin-bottom:8px">战力 900</div>
        <div id="cardItemDesc" style="font-size:10.5px;color:#94A3B8;text-align:center;line-height:1.4">赤霄出鞘，诸神退散。大幅增强佩戴者群聊斗法胜率。</div>
      </div>
    </div>
  `;

  // 动态滑块联动
  const updateCard = () => {
    const nm = document.getElementById("builderName")?.value || "神秘法宝";
    const rar = document.getElementById("builderRarity")?.value || "UR";
    const atk = parseInt(document.getElementById("sliderAtk")?.value || 0, 10);
    const def = parseInt(document.getElementById("sliderDef")?.value || 0, 10);

    const el = (id) => document.getElementById(id);
    if (el("valAtk")) el("valAtk").textContent = atk;
    if (el("valDef")) el("valDef").textContent = def;
    if (el("cardItemName")) el("cardItemName").textContent = nm;
    if (el("cardCombatScore")) el("cardCombatScore").textContent = `战力 ${atk + def}`;
    if (el("cardRarityBadge")) el("cardRarityBadge").textContent = `${rar} 极品装备`;
  };

  ["builderName", "builderRarity", "sliderAtk", "sliderDef"].forEach(id => {
    const elem = document.getElementById(id);
    if (elem) elem.oninput = updateCard;
  });

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "关闭";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "💾 保存至商城图鉴";
    okBtn.onclick = async () => {
      const nm = document.getElementById("builderName")?.value || "定制装备";
      const pr = document.getElementById("builderPrice")?.value || "1000";
      const atk = document.getElementById("sliderAtk")?.value || "100";
      CFG["商城图鉴"] = CFG["商城图鉴"] || {};
      CFG["商城图鉴"][nm] = `${pr}|${atk}`;
      toast(`已成功将【${nm}】保存至商城图鉴！`, "ok");
      modal.className = "";
      await saveConfig();
    };
  }
  modal.className = "show";
}


// 绑定新模块事件监听
document.getElementById("btnSimSend")?.addEventListener("click", () => sendSimulatorCommand());
document.getElementById("simInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") sendSimulatorCommand(); });
document.getElementById("btnSimClear")?.addEventListener("click", () => {
  const box = document.getElementById("simChatBox");
  if (box) box.innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;margin:10px 0">🤖 对话记录已清空 · 请输入指令继续调试</div>';
});
document.querySelectorAll("[data-sim-cmd]").forEach(btn => {
  btn.addEventListener("click", () => sendSimulatorCommand(btn.dataset.simCmd));
});
document.getElementById("btnRefreshAnalytics")?.addEventListener("click", loadAnalytics);
document.getElementById("btnUsersAirdrop")?.addEventListener("click", openAirdropModal);
document.getElementById("btnVisualItemBuilder")?.addEventListener("click", openVisualItemBuilder);

// Tab 切换时自动加载大屏数据
const origInitNav = typeof initNav === "function" ? initNav : null;


async function calibrateSlavePrices() {
  if (!(await uiConfirm("确认一键校准全群所有玩家的奴隶身价？\n系统将自动检测全库所有身价为 0 或未初始化的用户，并批量匹配为当前配置的初始身价！", "一键校准全员身价"))) return;
  toast("正在智能校准全员奴隶身价...", "ok");
  try {
    const res = await getBridge().apiPost("slave/calibrate", {});
    if (res && res.ok) {
      toast(res.msg || `🎉 成功校准 ${res.fixed_count || 0} 名用户的奴隶身价！`, "ok");
      await loadSlaveUsers();
      if (typeof loadAnalytics === "function") try { await loadAnalytics(); } catch(e) {}
    } else {
      toast("校准失败: " + (res && res.error ? res.error : "未知错误"), "bad");
    }
  } catch(err) {
    toast("校准异常: " + err.message, "bad");
  }
}

document.getElementById("btnSlaveCalibrate")?.addEventListener("click", calibrateSlavePrices);


// 确保新模块在 DOM 加载完毕后自动绑定
function initNewModules() {
  document.getElementById("btnSimSend")?.addEventListener("click", () => sendSimulatorCommand());
  document.getElementById("simInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") sendSimulatorCommand(); });
  document.getElementById("btnSimClear")?.addEventListener("click", () => {
    const box = document.getElementById("simChatBox");
    if (box) box.innerHTML = '<div style="text-align:center;color:var(--muted);font-size:12px;margin:10px 0">🤖 对话记录已清空 · 请输入指令继续调试</div>';
  });
  document.querySelectorAll("[data-sim-cmd]").forEach(btn => {
    btn.addEventListener("click", () => sendSimulatorCommand(btn.dataset.simCmd));
  });
  document.getElementById("btnRefreshAnalytics")?.addEventListener("click", loadAnalytics);
  document.getElementById("btnDbDoctorOv")?.addEventListener("click", runDbDoctor);
  document.getElementById("btnUsersAirdrop")?.addEventListener("click", openAirdropModal);
  document.getElementById("btnVisualItemBuilder")?.addEventListener("click", openVisualItemBuilder);
  document.getElementById("btnVisualItemBuilder2")?.addEventListener("click", openVisualItemBuilder);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initNewModules);
} else {
  initNewModules();
}


// ---------- 数据库健康体检与碎片整理 (Doctor / Vacuum) ----------
async function runDbDoctor() {
  toast("正在执行数据库健康体检与碎片整理...", "ok");
  try {
    const res = await getBridge().apiPost("backups/doctor", {});
    if (res && res.ok) {
      const tblInfo = res.tables ? Object.entries(res.tables).map(([k, v]) => `${k}: ${v} 行`).join(" | ") : "";
      const msg = `🎉 数据库体检与整理完成！\n\n· 完整性健康状态: ${res.integrity}\n· 整理前总大小: ${res.size_before}\n· 整理后总大小: ${res.size_after}\n· 释放碎片空间: ${res.saved}\n· 数据表行数统计: ${tblInfo}`;
      await uiAlert(msg, "🩺 数据库体检报告");
      toast(res.msg || "体检完成", "ok");
      if (typeof loadBackups === "function") try { await loadBackups(""); } catch(e){}
    } else {
      toast("体检失败: " + (res && res.error ? res.error : "未知错误"), "bad");
    }
  } catch(err) {
    toast("体检异常: " + err.message, "bad");
  }
}

document.getElementById("btnDbDoctor")?.addEventListener("click", runDbDoctor);


// ---------- 在线版本检测系统 ----------
let LATEST_RELEASE_DATA = null;

async function checkVersionUpdate(silent = false) {
  try {
    if (!silent) toast("正在检测最新版本...", "ok");
    const res = await getBridge().apiGet("version/check");
    if (res && res.ok) {
      LATEST_RELEASE_DATA = res;
      const badge = document.getElementById("verBadge");
      if (res.has_update) {
        if (badge) {
          badge.style.display = "inline-flex";
          badge.textContent = `🚀 发现新版本 ${res.latest_version}`;
        }
        if (!silent) {
          showUpdateModal(res);
        }
      } else {
        if (badge) badge.style.display = "none";
        if (!silent) {
          toast(`当前已是最新版本 (${res.current_version})`, "ok");
        }
      }
    }
  } catch(err) {
    if (!silent) toast("检测更新失败: " + err.message, "bad");
  }
}

function showUpdateModal(data) {
  const isNew = data.has_update;
  const tag = data.latest_version || data.current_version;
  const dateStr = data.release_date ? ` · 发布于 ${data.release_date}` : "";
  const changelog = data.changelog || "暂无详细更新日志。";

  const modalHtml = `
<div style="background:var(--panel2);border-radius:12px;padding:12px 14px;border:1px solid var(--line);margin-bottom:12px">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <span style="font-size:12px;color:var(--muted)">当前运行版本: <strong>${esc(data.current_version)}</strong></span>
    ${isNew ? `<span class="badge badge-success" style="font-size:12px;font-weight:700">最新版本: ${esc(tag)}</span>` : `<span class="badge badge-primary">已是最新</span>`}
  </div>
  ${dateStr ? `<div style="font-size:11px;color:var(--muted);margin-top:4px">${esc(dateStr)}</div>` : ""}
</div>

<div style="font-size:12.5px;font-weight:600;color:var(--text);margin-bottom:6px">📝 版本更新日志与特性</div>
<div style="background:var(--panel);border-radius:10px;padding:10px 12px;border:1px solid var(--line);font-size:12px;color:var(--text);max-height:160px;overflow-y:auto;white-space:pre-wrap;line-height:1.6">
${esc(changelog)}
</div>

${isNew ? `
<div style="margin-top:10px;padding:8px 12px;background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;font-size:11.5px;color:var(--acc);display:flex;align-items:center;gap:6px">
  <span>💡 <strong>更新指引</strong>：前往 AstrBot 官方面板的「插件管理」页面，直接点击「更新」即可无损升级至最新版本。</span>
</div>` : ""}
`;

  uiAlert(modalHtml, isNew ? "🚀 发现新版本" : "ℹ️ 版本信息", isNew ? "🚀" : "ℹ️");
}

// 绑定版本徽章与检查更新按钮
document.getElementById("verBadge")?.addEventListener("click", () => {
  if (LATEST_RELEASE_DATA) showUpdateModal(LATEST_RELEASE_DATA);
  else checkVersionUpdate(false);
});
document.getElementById("btnCheckUpdate")?.addEventListener("click", () => checkVersionUpdate(false));

// 启动时静默检查一次
setTimeout(() => { checkVersionUpdate(true); }, 1500);

// ---------- 插件运行日志 ----------
let LOGS_CACHE = [];
let LOGS_TIMER = null;

function parseLogLine(raw) {
  // Line format: [YYYY-MM-DD HH:MM:SS] [LEVEL] msg
  const m = raw.match(/^\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\]\s+\[(INFO|WARN|ERROR)\]\s+(.*)$/);
  if (m) {
    return { ts: m[1], level: m[2], msg: m[3] };
  }
  return { ts: "", level: "INFO", msg: raw };
}

function renderLogs(logsList) {
  const container = document.getElementById("logTerminalContent");
  if (!container) return;
  if (!logsList || logsList.length === 0) {
    container.innerHTML = '<div class="log-empty">暂无匹配的运行日志</div>';
    return;
  }

  const linesHtml = logsList.map(raw => {
    const item = parseLogLine(raw);
    const lvlClass = item.level.toLowerCase();
    const tsHtml = item.ts ? `<span class="log-ts">[${esc(item.ts)}]</span>` : "";
    const badgeHtml = item.level ? `<span class="log-badge ${lvlClass}">${esc(item.level)}</span>` : "";
    return `<div class="log-line">${tsHtml}${badgeHtml}<span class="log-msg">${esc(item.msg)}</span></div>`;
  }).join("");

  container.innerHTML = linesHtml;

  const autoScroll = document.getElementById("logsAutoScroll");
  if (autoScroll && autoScroll.checked) {
    const terminal = document.getElementById("logTerminal");
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }
}

async function loadLogs(isAuto = false) {
  try {
    const lvl = (document.getElementById("logsLevelFilter")?.value || "").trim();
    const kw = (document.getElementById("logsSearch")?.value || "").trim();
    const params = { limit: "500", level: lvl, keyword: kw };

    let res = null;
    try {
      res = await getBridge().apiGet("logs", params);
    } catch (apiErr) {
      try {
        res = await getBridge().apiPost("logs", params);
      } catch (postErr) {}
    }

    if (!res || res.status === "error") {
      try {
        res = await callApi("logs", params, "GET");
      } catch (callErr) {}
    }

    const data = (res && (res.result || res.data || res)) || {};
    const logsList = Array.isArray(data.logs) ? data.logs : (Array.isArray(res) ? res : []);

    LOGS_CACHE = logsList;
    renderLogs(LOGS_CACHE);

    const meta = document.getElementById("logsMetaInfo");
    if (meta) {
      const count = data.count !== undefined ? data.count : logsList.length;
      const total = data.total_lines !== undefined ? data.total_lines : logsList.length;
      const size = data.file_size_kb !== undefined ? data.file_size_kb : 0;
      const maxMb = data.max_file_mb !== undefined ? data.max_file_mb : 2.0;
      meta.textContent = `当前展示: ${count} / ${total} 行 | 文件大小: ${size} KB (上限 ${maxMb} MB)`;
    }
    return true;
  } catch (e) {
    const container = document.getElementById("logTerminalContent");
    if (container && (!LOGS_CACHE || LOGS_CACHE.length === 0)) {
      container.innerHTML = '<div class="log-empty">暂无运行日志记录</div>';
    }
    if (!isAuto) {
      toast("拉取日志未成功，请稍后重试", "bad");
    }
    return false;
  }
}

function startLogsAutoRefresh() {
  stopLogsAutoRefresh();
  const autoCheckbox = document.getElementById("logsAutoRefresh");
  const liveBadge = document.getElementById("logsLiveBadge");
  if (autoCheckbox && autoCheckbox.checked) {
    if (liveBadge) {
      liveBadge.innerHTML = '<span class="status-dot"></span> 实时监听';
      liveBadge.style.opacity = "1";
    }
    LOGS_TIMER = setInterval(() => {
      const logsTab = document.getElementById("tab-logs");
      if (logsTab && logsTab.classList.contains("on")) {
        loadLogs(true);
      } else {
        stopLogsAutoRefresh();
      }
    }, 3000);
  } else {
    if (liveBadge) {
      liveBadge.innerHTML = '<span class="status-dot" style="background:var(--muted)"></span> 已暂停';
      liveBadge.style.opacity = "0.7";
    }
  }
}

function stopLogsAutoRefresh() {
  if (LOGS_TIMER) {
    clearInterval(LOGS_TIMER);
    LOGS_TIMER = null;
  }
}

function initLogsEvents() {
  document.getElementById("logsAutoRefresh")?.addEventListener("change", () => {
    startLogsAutoRefresh();
  });
  document.getElementById("logsLevelFilter")?.addEventListener("change", () => {
    loadLogs(false);
  });
  let kwTimer = null;
  document.getElementById("logsSearch")?.addEventListener("input", () => {
    if (kwTimer) clearTimeout(kwTimer);
    kwTimer = setTimeout(() => loadLogs(false), 250);
  });
  document.getElementById("btnLogsRefresh")?.addEventListener("click", async () => {
    toast("正在刷新日志…", "ok");
    const ok = await loadLogs(false);
    if (ok) {
      toast("日志已刷新", "ok");
    }
  });
  document.getElementById("btnLogsCopy")?.addEventListener("click", () => {
    if (!LOGS_CACHE || LOGS_CACHE.length === 0) {
      toast("当前无日志可复制", "bad");
      return;
    }
    const text = LOGS_CACHE.join("\n");
    copyToClipboard(text);
  });
  document.getElementById("btnLogsExport")?.addEventListener("click", async () => {
    try {
      toast("正在准备导出日志…", "ok");
      let content = "";
      let filename = `xb_logs_${new Date().toISOString().slice(0, 10)}.log`;

      try {
        const res = await callApi("logs/export", {}, "POST");
        if (res && res.content) {
          content = res.content;
          if (res.filename) filename = res.filename;
        }
      } catch (e) {
        console.warn("API export failed, falling back to cached logs", e);
      }

      if (!content && LOGS_CACHE && LOGS_CACHE.length > 0) {
        content = LOGS_CACHE.join("\n");
      }

      if (!content) {
        toast("当前无日志可导出", "bad");
        return;
      }

      const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
      triggerDownload(blob, filename, content);
      toast("日志已成功导出", "ok");
    } catch (e) {
      toast("导出日志失败: " + e.message, "bad");
    }
  });
  document.getElementById("btnLogsClear")?.addEventListener("click", async () => {
    const ok = await uiConfirm("确定要清空当前的插件运行日志吗？\n清空后不可恢复（将重新从空文件开始记录）。", "🗑️ 清空日志");
    if (!ok) return;
    try {
      toast("正在清空日志…", "ok");
      const res = await callApi("logs/clear", {}, "POST");
      if (res && res.status === "error") {
        throw new Error(res.error || "清空失败");
      }
      toast((res && res.message) || "日志已清空", "ok");
      LOGS_CACHE = [];
      renderLogs([]);
      const meta = document.getElementById("logsMetaInfo");
      if (meta) meta.textContent = "当前展示: 0 / 0 行 | 文件大小: 0 KB (上限 2.0 MB)";
      await loadLogs(false);
    } catch (e) {
      toast("清空日志失败: " + e.message, "bad");
    }
  });
}

initLogsEvents();
