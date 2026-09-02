const toast = window.toast || ((m)=>console.log(m));
export async function load() {
  if (typeof window.loadConfig === 'function') return window.loadConfig();
  const bridge = window.bridge || window.AstrBotPluginPage || window.parent?.AstrBotPluginPage;
  const schema = await bridge.apiGet("config/schema");
  const cur = await bridge.apiGet("config/get");
  const form = document.getElementById("cfgForm");
  if (!form) return;
  form.innerHTML = Object.keys(schema.groups||{}).slice(0,3).map(sec => `<fieldset><legend>${sec}</legend></fieldset>`).join("");
}
export default { load };
