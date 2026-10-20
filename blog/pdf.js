// Salva PDF: per ogni articolo del blog. Basta un pulsante con data-pdf e questo script.
// Apre la stampa del browser con una versione pulita (fondo bianco, testo nero, niente pulsanti):
// da lì si sceglie "Salva come PDF". Si stampa solo la lingua che si sta leggendo.
(function () {
  var css = "@page{margin:18mm 16mm}" +
    "@media print{" +
    "html,body{background:#fff!important;color:#000!important}" +
    "body{padding:0!important;font-size:11pt;line-height:1.55}" +
    "*{color:#000!important;background:transparent!important;box-shadow:none!important}" +
    "a{text-decoration:none!important}" +
    ".close,.tools,.crumb,.end,.back,.tr,[hidden]{display:none!important}" +
    "article{max-width:none!important;margin:0!important}" +
    "header{margin:0 0 10mm!important}" +
    "h1{font-size:48pt!important;margin:0 0 4mm!important}" +
    "h2{border-top:0.5pt solid #000!important;color:#000!important;break-after:avoid}" +
    "p,li{orphans:3;widows:3}" +
    ".gif{break-inside:avoid;margin:8mm 0!important}.gif img{max-height:110mm;width:auto!important;max-width:100%}" +
    ".notes{font-size:9pt!important}" +
    ".pdf-src{display:block!important;margin-top:8mm;font-size:8pt;letter-spacing:.08em;text-transform:uppercase}" +
    "}" +
    ".pdf-src{display:none}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  // in fondo alla stampa: da dove viene il testo
  var arts = document.querySelectorAll("article");
  for (var i = 0; i < arts.length; i++) {
    var p = document.createElement("p"); p.className = "pdf-src";
    p.textContent = "Jacopo Natoli · jacoponatoli.net" + location.pathname;
    arts[i].appendChild(p);
  }
  var bs = document.querySelectorAll("[data-pdf]");
  for (var j = 0; j < bs.length; j++) bs[j].addEventListener("click", function () {
    var t = document.title;
    // il nome del file PDF lo prende dal titolo della pagina
    document.title = this.getAttribute("data-pdf");
    window.print();
    setTimeout(function () { document.title = t; }, 1000);
  });
})();
