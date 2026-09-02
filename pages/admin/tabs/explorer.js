const toast = window.toast || ((m)=>console.log(m));
export async function load(dir) {
  if (typeof window.loadImages === 'function') return window.loadImages(dir||"");
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const d = await bridge.apiGet("images/list", { dir: dir || "" });
  const el = document.getElementById("imgBrowser");
  if (el) el.innerHTML = `<div class="hint">文件数: ${(d.files||[]).length}</div>`;
}
export default { load };
