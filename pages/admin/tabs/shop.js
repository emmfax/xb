const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadShops === 'function') return window.loadShops();
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const d = await bridge.apiGet("config/get");
  const el = document.getElementById("shopRideBox");
  if (el) el.innerHTML = `<div class="hint">商城已加载</div>`;
}
export default { load };
