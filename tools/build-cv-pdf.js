// Genera cv/Jacopo_Natoli_CV.pdf da tools/cv-pdf.html (stessi dati di cv/cv.js).
// Uso: NODE_PATH=$(npm root -g) node tools/build-cv-pdf.js
const path = require("path");
const { chromium } = require("playwright");
(async () => {
  const root = path.resolve(__dirname, "..");
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("file://" + path.join(root, "tools", "cv-pdf.html"));
  await page.waitForSelector("body[data-ready]");
  await page.evaluate(() => document.fonts.ready);
  const month = new Date().toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  await page.pdf({
    path: path.join(root, "cv", "Jacopo_Natoli_CV.pdf"),
    format: "A4", printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate:
      '<div style="width:100%;font-family:Inter,Helvetica,Arial,sans-serif;font-size:7pt;color:#666;padding:0 18mm;display:flex;justify-content:space-between">' +
      "<span>Jacopo Natoli – Curriculum Vitae – " + month + "</span>" +
      '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
  });
  await browser.close();
  console.log("ok");
})();
