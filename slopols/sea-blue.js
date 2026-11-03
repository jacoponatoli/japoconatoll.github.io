/* SLOPOLS — filtri blu

   Ogni tanto tutto lo schermo passa in una gamma di blu del mare: a volte un velo appena,
   a volte un monocromo profondo, a volte un gradiente come la profondità dell'acqua.
   Gli episodi arrivano a caso, durano a caso, cambiano modo di fondersi con l'immagine,
   e ogni tanto scattano veloci, come il mare a scatti. Nelle transizioni del video a volte cambia. */
(() => {
  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const d = document.createElement('div');
  Object.assign(d.style, { position: 'fixed', inset: 0, zIndex: 2, pointerEvents: 'none', opacity: 0 });
  document.body.appendChild(d);

  // modi di fusione con il video, ognuno con il suo intervallo di intensità
  const MODES = [
    ['color', .35, .9],        // monocromo blu
    ['hue', .4, .95],          // stessa luce, tutto blu
    ['multiply', .25, .7],     // acqua profonda, scura
    ['soft-light', .3, .85],   // velo
    ['overlay', .2, .6],
    ['screen', .1, .35],       // luce d'acqua
    ['luminosity', .15, .35]   // a volte il blu porta solo la luce
  ];
  // blu del mare: dal ciano dell'acqua bassa al blu notte dell'abisso
  const blue = () => { const h = rnd(186, 232), s = rnd(45, 100), l = rnd(14, 55); return [h, s, l]; };
  const hsl = ([h, s, l], dl = 0) => `hsl(${h.toFixed(0)} ${s.toFixed(0)}% ${Math.max(3, l + dl).toFixed(0)}%)`;

  let mode = 'soft-light', timer = 0, drift = 0;
  function background(c) {
    const r = Math.random();
    if (r < .45) return hsl(c);
    if (r < .8) {                                          // gradiente: verso il fondo più scuro, come la profondità
      const c2 = [c[0] + rnd(-18, 18), c[1], c[2]];
      return `linear-gradient(${rnd(150, 210).toFixed(0)}deg, ${hsl(c, rnd(5, 20))}, ${hsl(c2, -rnd(10, 30))})`;
    }
    return `radial-gradient(ellipse at ${rnd(20, 80).toFixed(0)}% ${rnd(10, 60).toFixed(0)}%, ${hsl(c, 15)}, ${hsl(c, -25)})`;
  }
  function set(opacity, secs) { d.style.transition = `opacity ${secs}s ease-in-out, background ${Math.max(secs, 3)}s ease`; d.style.opacity = opacity; }

  function episode() {
    clearTimeout(timer); clearInterval(drift);
    if (Math.random() < .45) {                             // spesso niente filtro: "ogni tanto"
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
  addEventListener('slopols:trans', () => { if (Math.random() < .25) episode(); });
})();
