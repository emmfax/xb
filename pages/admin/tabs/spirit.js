const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadSpirits === 'function') return window.loadSpirits();
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const d = await bridge.apiGet("spirits");
  const body = document.getElementById("spiritBody");
  if (!body) return;
  body.innerHTML = `<div class="hint">精灵数: ${Object.keys(d.spirits||{}).length}</div>`;
}
export default { load };
