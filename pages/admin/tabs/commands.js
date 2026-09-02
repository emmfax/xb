const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadCommands === 'function') return window.loadCommands();
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const d = await bridge.apiGet("commands");
  const el = document.getElementById("cmdList");
  if (!el) return;
  el.innerHTML = `<div class="hint">指令数: ${Object.keys(d||{}).length}</div>`;
}
export default { load };
