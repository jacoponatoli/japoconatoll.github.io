// AMBIENET — le poesie da leggere.
// Prende il compositore di POESIA LA NOTIZIA (lo stesso codice della pagina, letto dal suo index.html)
// e i titoli del giorno (news.json), e compone alcune poesie nuove in forme dall'endecasillabo alla terza rima.
// Scrive poems.json: [{form, name, title, lines:[...], stanze con ""}].
import fs from 'node:fs'; import vm from 'node:vm';
const BASE = process.env.PLN_BASE || 'https://raw.githubusercontent.com/jacoponatoli/poesia_la_notizia/main/';
const get = async f => { if (process.env.PLN_DIR) return fs.readFileSync(process.env.PLN_DIR + '/' + f, 'utf8'); const r = await fetch(BASE + f); if (!r.ok) throw new Error(f + ' ' + r.status); return r.text(); };
const html = await get('index.html'), news = JSON.parse(await get('news.json'));
const a = html.indexOf('/* ---------- metrica italiana'), b = html.indexOf('/* ---------- fonti dal vivo');
if (a < 0 || b < 0) throw new Error('compositore non trovato');
const api = vm.runInNewContext(html.slice(a, b) + '\n;({buildCorpus, compose, FORMS})', {});
const C = api.buildCorpus(news.items || [], news.foreign || []);
const IDS = ['endecasillabo', 'haiku', 'settenari', 'madrigale', 'ottava', 'libero', 'sciolti', 'alternata', 'baciata', 'incrociata', 'terzarima'];
const N = +(process.env.N || 6), out = [];
for (let i = 0; i < N * 3 && out.length < N; i++) {
  const form = api.FORMS.find(f => f.id === IDS[Math.floor(Math.random() * IDS.length)]);
  let p; try { p = api.compose(C, form); } catch (e) { continue; }
  const lines = [];
  for (const l of p) {
    if (l.br) { if (lines.length && lines[lines.length - 1] !== '') lines.push(''); continue; }
    const t = l.foreign ? l.text : (l.parts || []).map(x => x.text).join(' ');
    if (t && t.trim()) lines.push(t.trim().replace(/^./, c => c.toUpperCase()));
  }
  while (lines.length && lines[lines.length - 1] === '') lines.pop();
  if (lines.filter(Boolean).length) out.push({ form: form.id, name: form.name, title: p.title || '', lines });
}
fs.writeFileSync('poems.json', JSON.stringify(out, null, 1));
console.log(out.map(p => `${p.name}: ${p.lines.filter(Boolean).length} versi`).join('\n'));
