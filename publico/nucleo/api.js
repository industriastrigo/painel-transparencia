/* Comunicação com os endpoints da API FastAPI. */

export const API = '';

export async function buscar(rota, parametros = {}, { sinal } = {}) {
  const url = new URL(`${API}${rota}`, location.origin);
  for (const [k, v] of Object.entries(parametros)) {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, v);
    }
  }
  const r = await fetch(url.toString(), { signal: sinal });
  if (!r.ok) {
    const texto = await r.text().catch(() => '');
    throw new Error(`HTTP ${r.status}${texto ? `: ${texto}` : ''}`);
  }
  return r.json();
}
