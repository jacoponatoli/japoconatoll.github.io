// Colore al passaggio, uguale in tutto il sito: ogni volta che il mouse (o il focus) entra in un link
// o in un pulsante, questo prende un colore nuovo. La tinta avanza di circa 137° (angolo aureo) più un
// piccolo scarto casuale, così si gira per tutta la ruota dei colori e due colori di fila non si somigliano.
// La tinta continua da una pagina all'altra finché si resta sul sito.
(function () {
  var KEY = "jn-hue", hue;
  try { hue = parseFloat(sessionStorage.getItem(KEY)); } catch (e) {}
  if (!(hue >= 0)) hue = Math.random() * 360;

  function next() {
    hue = (hue + 137.508 + (Math.random() * 40 - 20) + 360) % 360;
    try { sessionStorage.setItem(KEY, hue.toFixed(1)); } catch (e) {}
    var l = (hue > 200 && hue < 290) ? 68 : 58; // blu e viola più chiari, per restare leggibili sul nero
    return "hsl(" + hue.toFixed(0) + ", 100%, " + l + "%)";
  }
  window.jnNextColor = next;

  function paint(el) { el.style.setProperty("--hc", next()); }
  function target(n) { return n && n.closest ? n.closest("a, button, summary") : null; }

  document.addEventListener("pointerover", function (e) {
    var el = target(e.target);
    if (!el || el.contains(e.relatedTarget)) return; // ancora dentro lo stesso link: niente cambio
    paint(el);
  });
  document.addEventListener("focusin", function (e) {
    var el = target(e.target);
    if (el && !el.matches(":hover")) paint(el); // col mouse sopra (clic) il colore resta quello che c'è
  });
  // Link cliccati: restano del colore che avevano al clic (come le parole della home),
  // tutti quanti, finché si resta sul sito in questa scheda. Vale per links, portfolio e CV
  // (nel CV anche i titoli delle sezioni a tendina).
  var CK = "jn-cliccati", done = {};
  try { done = JSON.parse(sessionStorage.getItem(CK) || "{}") || {}; } catch (e) {}
  var st = document.createElement("style");
  st.textContent = "a.jn-done,summary.jn-done,summary.jn-done *{color:var(--done)!important}";
  document.head.appendChild(st);
  function key(a) { return location.pathname + "|" + (a.getAttribute("href") || a.tagName) + "|" + a.textContent.trim().slice(0, 80); }
  function mark(a, c) { a.style.setProperty("--done", c); a.classList.add("jn-done"); }
  function applyAll() {
    var links = document.querySelectorAll("a[href]:not(.float):not(.close):not(.crumb):not(.top), summary");
    for (var i = 0; i < links.length; i++) { var c = done[key(links[i])]; if (c && !links[i].classList.contains("jn-done")) mark(links[i], c); }
  }
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest("a[href], summary") : null;
    if (!a || a.matches(".float, .close, .crumb, .top")) return;
    var k = key(a), c = done[k] || a.style.getPropertyValue("--hc") || next();
    done[k] = c; mark(a, c);
    try { sessionStorage.setItem(CK, JSON.stringify(done)); } catch (e2) {}
  }, true);
  // le pagine che si ridisegnano (portfolio) riprendono i colori a ogni cambio
  if (window.MutationObserver) new MutationObserver(applyAll).observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", applyAll); else applyAll();
  addEventListener("pageshow", applyAll);
})();
