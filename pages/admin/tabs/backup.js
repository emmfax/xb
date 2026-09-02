const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadBackups === 'function') return window.loadBackups("");
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const d = await bridge.apiGet("backups/list", {});
  const el = document.getElementById("backupBrowser");
  if (el) el.innerHTML = `<div class="hint">备份数: ${(d.files||[]).length}</div>`;
}
export default { load };
