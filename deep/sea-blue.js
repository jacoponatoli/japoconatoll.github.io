/* SLOPOLS — filtri blu

   Ogni tanto tutto lo schermo passa in una gamma di blu del mare: a volte un velo appena,
   a volte un monocromo profondo, a volte un gradiente come la profondità dell'acqua.
   Gli episodi arrivano a caso, durano a caso, cambiano modo di fondersi con l'immagine,
   e ogni tanto scattano veloci, come il mare a scatti. Nelle transizioni del video a volte cambia. */
(() => {
function layer(Z, OFF, P) {   // più livelli indipendenti di colore, ognuno con i suoi episodi
  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const d = document.createElement('div');
  Object.assign(d.style, { position: 'fixed', inset: 0, zIndex: Z, pointerEvents: 'none', opacity: 0 });
  document.body.appendChild(d);

  // modi di fusione con il video, ognuno con il suo intervallo di intensità
  const MODES = [
    ['color', .35, .9],        // monocromo blu
    ['hue', .4, .95],          // stessa luce, tutto blu
    ['multiply', .25, .7],     // acqua profonda, scura
    ['soft-light', .3, .85],   // velo
    ['overlay', .2, .6],
    ['screen', .1, .35],       // luce d'acqua
    ['luminosity', .15, .35],  // a volte il blu porta solo la luce
    ['exclusion', .08, .25],   // il mare in negativo, appena
    ['difference', .06, .2]
  ];
  // blu del mare: dal ciano dell'acqua bassa al blu notte dell'abisso
  // gamma più ampia: dal verde acqua al blu oltremare e al viola dell'abisso, dal quasi nero all'azzurro chiaro
  const blue = () => { const r = Math.random(), h = r < .2 ? rnd(165, 188) : r < .85 ? rnd(188, 235) : rnd(235, 252), s = rnd(30, 100), l = rnd(8, 72); return [h, s, l]; };
  const hsl = ([h, s, l], dl = 0) => `hsl(${h.toFixed(0)} ${s.toFixed(0)}% ${Math.max(3, l + dl).toFixed(0)}%)`;

  let mode = 'soft-light', timer = 0, drift = 0;
  function background(c) {
    const r = Math.random();
    if (r < .3) return hsl(c);
    const stops = n => Array.from({ length: n }, (_, i) => {   // più passaggi: dall'azzurro di superficie al blu del fondo
      const k = i / (n - 1), cc = [c[0] + rnd(-22, 22), Math.min(100, Math.max(25, c[1] + rnd(-25, 20))), c[2]];
      return `${hsl(cc, 22 - k * 50 + rnd(-6, 6))} ${(k * 100 + (i && i < n - 1 ? rnd(-8, 8) : 0)).toFixed(0)}%`; }).join(', ');
    if (r < .72) return `linear-gradient(${rnd(140, 220).toFixed(0)}deg, ${stops(Math.floor(rnd(3, 6)))})`;
    if (r < .88) return `radial-gradient(ellipse at ${rnd(15, 85).toFixed(0)}% ${rnd(5, 60).toFixed(0)}%, ${stops(Math.floor(rnd(3, 5)))})`;
    return `radial-gradient(ellipse at ${rnd(10, 90).toFixed(0)}% ${rnd(0, 40).toFixed(0)}%, ${hsl([c[0] + 15, c[1], c[2]], 25)} 0%, transparent 55%), ` +
           `linear-gradient(${rnd(160, 200).toFixed(0)}deg, ${stops(4)})`;     // una luce d'acqua sopra la profondità
  }
  function set(opacity, secs) { d.style.transition = `opacity ${secs}s ease-in-out, background ${Math.max(secs, 3)}s ease`; d.style.opacity = opacity; }

  function episode() {
    clearTimeout(timer); clearInterval(drift);
    if (Math.random() < OFF) {                             // spesso niente filtro: "ogni tanto"
      set(0, rnd(3, 10));
      timer = setTimeout(episode, rnd(15, 60) * 1000);
      return;
    }
    const [m, lo, hi] = pick(MODES), c = blue(), op = rnd(lo, hi);
    const quick = Math.random() < .15, fade = quick ? rnd(.08, .4) : rnd(3, 12);
    const go = () => {
      d.style.mixBlendMode = mode = m;
      d.style.background = background(c);
      set(op, fade);
      drift = setInterval(() => {                         // il colore deriva dentro l'episodio
        c[0] = Math.min(235, Math.max(182, c[0] + rnd(-6, 6))); c[2] = Math.min(60, Math.max(10, c[2] + rnd(-5, 5)));
        d.style.background = background(c);
        if (Math.random() < .2) d.style.opacity = Math.min(1, Math.max(.05, op * rnd(.6, 1.3)));
      }, rnd(4, 9) * 1000);
    };
    // il modo di fusione non si può sfumare: se cambia, prima scompare
    if (m !== mode && +getComputedStyle(d).opacity > .02) { set(0, quick ? .15 : rnd(1.5, 4)); setTimeout(go, quick ? 160 : 4000); }
    else go();
    timer = setTimeout(episode, (quick ? rnd(1.5, 6) : rnd(12, 50)) * 1000);
  }
  timer = setTimeout(episode, rnd(10, 30) * 1000);
  addEventListener('slopols:trans', () => { if (Math.random() < P) episode(); });
}
layer(2, .35, .25);
layer(3, .55, .35);
layer(4, .75, .2);
})();
