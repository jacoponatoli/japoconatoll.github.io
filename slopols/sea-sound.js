/* SLOPOLS — suono del mare

   Registrazioni di mare e acqua da archivi aperti (Wikimedia Commons, Internet Archive),
   raccolte ogni 6 ore nel ramo "slopols-sound": l'archivio si rinnova sempre.
   Due o tre "maree" si alternano: pezzi rallentati, filtrati, che vagano nello spazio stereo
   e ogni tanto si inceppano (a scatti, come il video). Sopra, il ronzio dei pixel:
   il mare ridotto a pochi bit, un ronzio digitale basso, granelli di dati.
   Tutto evolve: nei primi minuti cresce, poi i parametri derivano lentamente, sempre diversi.
   Nelle transizioni del video il mare si sgretola in bit.
   Tasto M: audio sì/no. */
(() => {
  const RAW = 'https://raw.githubusercontent.com/jacoponatoli/japoconatoll.github.io/slopols-sound/';
  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const noise = x => { const h = n => { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); };
    const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return h(i) * (1 - u) + h(i + 1) * u; };

  let ctx = null, master, comp, seaBus, crush, crushIn, crushWet, humGain, list = [], t0 = 0, muted = false, trans = 0;
  const cache = new Map();                       // file -> AudioBuffer (pochi alla volta)

  // --- avvio: i browser vogliono un gesto (in museo: Chrome con --autoplay-policy=no-user-gesture-required) ---
  const hint = document.createElement('div');
  hint.textContent = 'sound';
  Object.assign(hint.style, { position: 'fixed', left: '16px', bottom: '14px', zIndex: 5, color: '#fff', opacity: 0,
    font: '12px ui-monospace,Menlo,monospace', letterSpacing: '.15em', transition: 'opacity 1.5s', cursor: 'pointer' });
  document.body.appendChild(hint);

  async function init() {
    if (ctx) { if (ctx.state !== 'running') await ctx.resume().catch(() => {}); hideHint(); return; }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    t0 = ctx.currentTime;
    comp = ctx.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 4;
    master = ctx.createGain(); master.gain.value = 0;
    master.connect(comp); comp.connect(ctx.destination);
    master.gain.setTargetAtTime(0.9, ctx.currentTime, 4);      // entra piano

    seaBus = ctx.createGain(); seaBus.connect(master);
    // bitcrusher: il mare a pochi bit e con pochi campioni
    const src = `class Crush extends AudioWorkletProcessor{
      static get parameterDescriptors(){return[{name:'bits',defaultValue:8,minValue:1,maxValue:16},{name:'down',defaultValue:6,minValue:1,maxValue:80}]}
      constructor(){super();this.h=[0,0];this.c=0}
      process(ins,outs,p){const a=ins[0],b=outs[0];if(!a||!a.length)return true;const L=b[0].length;
        for(let n=0;n<L;n++){const bt=p.bits.length>1?p.bits[n]:p.bits[0],dn=Math.max(1,Math.round(p.down.length>1?p.down[n]:p.down[0]));
          if((this.c+n)%dn===0){const q=Math.pow(2,bt-1);for(let ch=0;ch<b.length;ch++){const x=a[ch]||a[0];this.h[ch]=Math.round(x[n]*q)/q;}}
          for(let ch=0;ch<b.length;ch++)b[ch][n]=this.h[ch];}
        this.c+=L;return true}}
      registerProcessor('slopols-crush',Crush);`;
    try {
      await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([src], { type: 'application/javascript' })));
      crush = new AudioWorkletNode(ctx, 'slopols-crush', { outputChannelCount: [2] });
    } catch (e) { crush = ctx.createGain(); }
    crushIn = ctx.createGain(); crushWet = ctx.createGain(); crushWet.gain.value = 0;
    const crushHp = ctx.createBiquadFilter(); crushHp.type = 'highpass'; crushHp.frequency.value = 180;
    seaBus.connect(crushIn); crushIn.connect(crush); crush.connect(crushHp); crushHp.connect(crushWet); crushWet.connect(master);

    // ronzio dei pixel: oscillatori bassi, filtrati, che passano anche nel crusher
    humGain = ctx.createGain(); humGain.gain.value = 0;
    const humF = ctx.createBiquadFilter(); humF.type = 'bandpass'; humF.Q.value = 3; humF.frequency.value = 220;
    humGain.connect(humF); humF.connect(master); humF.connect(crushIn);
    const base = pick([43, 50, 55, 60, 73]);
    [[1, 'square', .5], [2.01, 'sawtooth', .3], [3.5, 'square', .15], [0.5, 'triangle', .6]].forEach(([m, type, g]) => {
      const o = ctx.createOscillator(), gg = ctx.createGain(); o.type = type; o.frequency.value = base * m;
      o.detune.value = rnd(-12, 12); gg.gain.value = g * .08; o.connect(gg); gg.connect(humGain); o.start();
      setInterval(() => o.detune.setTargetAtTime(rnd(-25, 25), ctx.currentTime, 3), 7000 + Math.random() * 6000);
    });
    humF._f = humF;
    setInterval(() => humF.frequency.setTargetAtTime(rnd(90, 900), ctx.currentTime, 4), 5000);

    try { list = await (await fetch(RAW + 'list.json?' + Date.now())).json(); } catch (e) { list = []; }
    setInterval(async () => { try { list = await (await fetch(RAW + 'list.json?' + Date.now())).json(); } catch (e) {} }, 30 * 60e3);
    if (!list.length) { console.log('[slopols sound] archivio non ancora pronto'); }
    tide(); setTimeout(tide, rnd(8, 18) * 1000);
    evolve(); grains(); stutterLoop();
    hideHint();
  }
  function hideHint() { if (ctx && ctx.state === 'running') hint.style.opacity = 0; }

  async function buffer(item) {
    if (cache.has(item.file)) return cache.get(item.file);
    const ab = await (await fetch(RAW + item.file)).arrayBuffer();
    const b = await ctx.decodeAudioData(ab);
    cache.set(item.file, b);
    while (cache.size > 8) cache.delete(cache.keys().next().value);
    return b;
  }
  const age = () => ctx ? ctx.currentTime - t0 : 0;
  const grow = () => Math.min(1, age() / 600);                    // nei primi 10 minuti cresce

  // --- maree: un pezzo di mare rallentato, filtrato, che vaga; poi lascia il posto a un altro ---
  const voices = new Set();
  async function tide() {
    if (!list.length) { setTimeout(tide, 20000); return; }
    let b, item;
    try { item = pick(list); b = await buffer(item); } catch (e) { setTimeout(tide, 3000); return; }
    const now = ctx.currentTime, life = rnd(25, 70), fadeIn = rnd(4, 12), fadeOut = rnd(6, 14);
    const s = ctx.createBufferSource(); s.buffer = b; s.loop = true;
    s.loopStart = rnd(0, b.duration * .5); s.loopEnd = Math.min(b.duration, s.loopStart + rnd(8, b.duration));
    const rate = rnd(.5, 1) * (Math.random() < .15 ? .6 : 1);   // rallentato, a volte molto
    s.playbackRate.value = rate;
    const f = ctx.createBiquadFilter(); f.type = Math.random() < .75 ? 'lowpass' : 'bandpass'; f.frequency.value = rnd(400, 6000); f.Q.value = rnd(.3, 4);
    const p = ctx.createStereoPanner(); p.pan.value = rnd(-.6, .6);
    const g = ctx.createGain(); g.gain.value = 0;
    s.connect(f); f.connect(p); p.connect(g); g.connect(seaBus);
    g.gain.setTargetAtTime(rnd(.45, .9), now, fadeIn / 3);
    s.start(now, s.loopStart);
    const v = { s, f, p, g, rate, b, item }; voices.add(v);
    const drift = setInterval(() => {                              // il mare si muove: filtro, spazio, velocità
      const t = ctx.currentTime;
      f.frequency.setTargetAtTime(rnd(250, 7000), t, rnd(2, 6));
      p.pan.setTargetAtTime(rnd(-.8, .8), t, rnd(3, 8));
      s.playbackRate.setTargetAtTime(rate * rnd(.85, 1.1) * (trans ? .7 : 1), t, 2);
    }, 4000 + Math.random() * 4000);
    setTimeout(() => {                                             // la prossima marea entra prima che questa se ne vada
      tide();
      g.gain.setTargetAtTime(0, ctx.currentTime, fadeOut / 3);
      setTimeout(() => { try { s.stop(); } catch (e) {} clearInterval(drift); voices.delete(v); }, fadeOut * 1000 + 500);
    }, life * 1000);
  }

  // --- a scatti: un frammento di mare si inceppa e si ripete ---
  function stutter(force) {
    const vs = [...voices]; if (!vs.length || muted) return;
    const v = pick(vs), b = v.b, len = rnd(.04, .35), reps = Math.floor(rnd(3, force ? 16 : 9));
    const at = rnd(0, b.duration - len), now = ctx.currentTime + .02;
    const g = ctx.createGain(); g.gain.value = rnd(.3, .7) * (force ? 1 : grow()); g.connect(Math.random() < .5 ? crushIn : seaBus);
    for (let i = 0; i < reps; i++) {
      const s = ctx.createBufferSource(); s.buffer = b; s.playbackRate.value = v.rate * (force ? rnd(.5, 1.5) : 1);
      const e = ctx.createGain(); s.connect(e); e.connect(g);
      const t = now + i * len; e.gain.setValueAtTime(0, t); e.gain.linearRampToValueAtTime(1, t + .005); e.gain.setValueAtTime(1, t + len - .01); e.gain.linearRampToValueAtTime(0, t + len);
      s.start(t, at, len);
    }
  }
  function stutterLoop() {
    const dens = (.15 + .85 * noise(age() / 60 + 3)) * grow();          // densità che deriva
    if (Math.random() < dens) stutter(false);
    setTimeout(stutterLoop, rnd(1.5, 9) * 1000 / Math.max(.2, dens));
  }

  // --- granelli di dati: brevi impulsi quantizzati, come pixel che passano ---
  function grain(force) {
    const now = ctx.currentTime, d = rnd(.015, .12), sr = ctx.sampleRate, n = Math.floor(sr * d);
    const b = ctx.createBuffer(1, n, sr), x = b.getChannelData(0);
    const kind = Math.floor(Math.random() * 3), per = Math.floor(rnd(8, 200)), q = Math.pow(2, Math.floor(rnd(1, 4)));
    let h = 0;
    for (let i = 0; i < n; i++) {
      if (i % per === 0) h = kind === 0 ? (Math.random() * 2 - 1) : kind === 1 ? (h > 0 ? -1 : 1) : Math.sin(i / per * 6.28);
      x[i] = Math.round(h * q) / q * (1 - i / n);
    }
    const s = ctx.createBufferSource(); s.buffer = b; const g = ctx.createGain(); const p = ctx.createStereoPanner();
    g.gain.value = rnd(.03, .12) * (force ? 1.6 : 1); p.pan.value = rnd(-1, 1);
    s.connect(g); g.connect(p); p.connect(master); s.start(now);
  }
  function grains() {
    const dens = (noise(age() / 45 + 11) * .8 + .1) * grow() + trans * .9;
    if (!muted && Math.random() < dens) { grain(trans > 0); if (Math.random() < dens * .5) setTimeout(() => grain(trans > 0), rnd(20, 120)); }
    setTimeout(grains, rnd(60, 900) / Math.max(.3, dens * 3));
  }

  // --- deriva lenta di tutto: nessun minuto uguale a un altro ---
  function evolve() {
    const t = age(), now = ctx.currentTime, gr = grow();
    const crushAmt = (.05 + .45 * noise(t / 80 + 1)) * gr;
    if (!trans) {
      crushWet.gain.setTargetAtTime(crushAmt, now, 3);
      if (crush.parameters) {
        crush.parameters.get('bits').setTargetAtTime(4 + 8 * noise(t / 50 + 5), now, 3);
        crush.parameters.get('down').setTargetAtTime(2 + 30 * noise(t / 70 + 9), now, 3);
      }
      humGain.gain.setTargetAtTime((.15 + .85 * noise(t / 120 + 21)) * gr * .5, now, 5);
      seaBus.gain.setTargetAtTime(.9 - crushAmt * .5, now, 3);
    }
    setTimeout(evolve, 2000);
  }

  // --- transizioni del video: il mare si sgretola in bit, poi torna ---
  addEventListener('slopols:trans', e => {
    if (!ctx || muted) return;
    const dur = Math.max(1, (e.detail && e.detail.dur) || 4), now = ctx.currentTime, k = rnd(.5, 1);
    trans = 1;
    crushWet.gain.setTargetAtTime(.5 + .4 * k, now, dur * .15);
    if (crush.parameters) {
      crush.parameters.get('bits').setTargetAtTime(rnd(2, 5), now, dur * .2);
      crush.parameters.get('down').setTargetAtTime(rnd(15, 70), now, dur * .2);
    }
    seaBus.gain.setTargetAtTime(.35, now, dur * .2);
    humGain.gain.setTargetAtTime(.55, now, dur * .2);
    voices.forEach(v => v.s.playbackRate.setTargetAtTime(v.rate * rnd(.45, .8), now, dur * .3));
    if (Math.random() < .7) stutter(true);
    setTimeout(() => { if (Math.random() < .5) stutter(true); }, dur * 500);
  });
  addEventListener('slopols:hold', () => {
    if (!ctx) return; trans = 0;
    const now = ctx.currentTime;
    seaBus.gain.setTargetAtTime(.9, now, 1.5);
    voices.forEach(v => v.s.playbackRate.setTargetAtTime(v.rate, now, 1.5));
  });

  // --- comandi ---
  ['pointerdown', 'keydown', 'touchstart'].forEach(ev => addEventListener(ev, e => {
    if (ev === 'keydown' && e.key.toLowerCase() === 'm' && ctx) {
      muted = !muted; master.gain.setTargetAtTime(muted ? 0 : .9, ctx.currentTime, .3); return;
    }
    init();
  }, { passive: true }));
  init().then(() => {                                    // se il browser permette l'autoplay, parte da solo
    if (ctx.state !== 'running') { hint.style.opacity = .55; setTimeout(() => { if (ctx.state !== 'running') hint.style.opacity = .25; }, 8000); }
  });
})();
