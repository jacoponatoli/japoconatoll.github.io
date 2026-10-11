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
  function target(n) { return n && n.closest ? n.closest("a, button") : null; }

  document.addEventListener("pointerover", function (e) {
    var el = target(e.target);
    if (!el || el.contains(e.relatedTarget)) return; // ancora dentro lo stesso link: niente cambio
    paint(el);
  });
  document.addEventListener("focusin", function (e) {
    var el = target(e.target);
    if (el && !el.matches(":hover")) paint(el); // col mouse sopra (clic) il colore resta quello che c'è
  });
})();
