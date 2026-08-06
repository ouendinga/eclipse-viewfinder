"""La hoja de estilos que comparten los informes del eclipse."""

CSS = """
:root{
  --ground:#0e131a; --panel:#141b24; --line:#243040; --line-soft:#1b2431;
  --text:#dde4ec; --muted:#8b9aac; --dim:#66788c;
  --sun:#e08a2e; --corona:#bcd8e8; --sky:#131c27;
  --terrain:#050809; --terrain-edge:#2c3a49;
  --grid:#22303f; --grid-strong:#3a4d61;
  --good:#57a06c; --warn:#c9962c; --bad:#bd5340;
  --serif:Georgia,"Iowan Old Style","Times New Roman",serif;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:light){
  :root{
    --ground:#e7eaee; --panel:#f4f6f8; --line:#c4ccd6; --line-soft:#d6dce4;
    --text:#161d26; --muted:#546375; --dim:#71818f;
    --sun:#b4681a; --corona:#2c5f7d; --sky:#dce6ee;
    --terrain:#2a3542; --terrain-edge:#4b5b6b;
    --grid:#c3cdd8; --grid-strong:#8fa1b2;
    --good:#2f7a48; --warn:#8f6a12; --bad:#a13e2c;
  }
}
:root[data-theme="dark"]{
  --ground:#0e131a; --panel:#141b24; --line:#243040; --line-soft:#1b2431;
  --text:#dde4ec; --muted:#8b9aac; --dim:#66788c;
  --sun:#e08a2e; --corona:#bcd8e8; --sky:#131c27;
  --terrain:#050809; --terrain-edge:#2c3a49;
  --grid:#22303f; --grid-strong:#3a4d61;
  --good:#57a06c; --warn:#c9962c; --bad:#bd5340;
}
:root[data-theme="light"]{
  --ground:#e7eaee; --panel:#f4f6f8; --line:#c4ccd6; --line-soft:#d6dce4;
  --text:#161d26; --muted:#546375; --dim:#71818f;
  --sun:#b4681a; --corona:#2c5f7d; --sky:#dce6ee;
  --terrain:#2a3542; --terrain-edge:#4b5b6b;
  --grid:#c3cdd8; --grid-strong:#8fa1b2;
  --good:#2f7a48; --warn:#8f6a12; --bad:#a13e2c;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--text);
  font-family:var(--sans);font-size:16px;line-height:1.62;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px 80px}
.prose{max-width:66ch}
h1,h2,h3{font-family:var(--serif);font-weight:600;text-wrap:balance;line-height:1.18;margin:0}
h1{font-size:clamp(30px,5vw,46px);letter-spacing:-.01em}
h2{font-size:clamp(21px,2.6vw,27px);margin:0 0 6px}
h3{font-size:18px;margin:0}
p{margin:0 0 14px}
a{color:var(--sun)}
.eyebrow{font:600 11px/1.4 var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--dim);margin:0 0 12px}
header.top{padding:56px 0 30px;border-bottom:1px solid var(--line)}
.lede{font-family:var(--serif);font-size:clamp(17px,2.1vw,21px);line-height:1.5;
  color:var(--text);margin:18px 0 0;max-width:60ch}
.lede b{color:var(--sun);font-weight:600}
section{padding:38px 0;border-bottom:1px solid var(--line-soft)}
section:last-of-type{border-bottom:0}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px;background:var(--line-soft);border:1px solid var(--line-soft);margin:22px 0 0}
.fact{background:var(--panel);padding:13px 15px}
.fact .k{font:600 10px/1.3 var(--mono);letter-spacing:.11em;text-transform:uppercase;
  color:var(--dim)}
.fact .v{font-family:var(--mono);font-size:19px;font-variant-numeric:tabular-nums;
  margin-top:5px;color:var(--sun)}
.fact .n{font-size:12px;color:var(--muted);margin-top:2px;line-height:1.4}
.mapbox{margin:22px 0 8px;border:1px solid var(--line);background:#0e1116;overflow-x:auto}
.mapbox svg{display:block;width:100%;min-width:640px;height:auto}
.caption{font-size:13px;color:var(--muted);margin:9px 0 0;max-width:70ch}
.legendrow{display:flex;flex-wrap:wrap;gap:16px;margin:12px 0 0;
  font:500 12px var(--mono);color:var(--muted)}
/* El símbolo dice QUÉ es la cosa, no solo de qué color: un punto para los puntos, una
   raya para la línea central y un rectángulo para la franja, que es una zona. Con todo
   redondo, la leyenda decía que la franja era un punto. */
.legendrow i{display:inline-block;width:10px;height:10px;border-radius:50%;
  margin-right:6px;vertical-align:-1px}
.legendrow i.line{width:22px;height:0;border-radius:0;border-top:2px dashed currentColor;
  background:none !important;vertical-align:3px}
.legendrow i.area{width:20px;height:11px;border-radius:0;border:1px solid currentColor;
  vertical-align:-1px}
.site{border:1px solid var(--line);background:var(--panel);margin:20px 0 0}
.site.hero{border-color:var(--sun)}
.site.bad{border-color:var(--bad)}
.site-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;
  padding:15px 17px 0}
.site-h .rank{font:700 11px var(--mono);letter-spacing:.1em;color:var(--dim);
  text-transform:uppercase}
.site-h .place{font-size:13px;color:var(--muted);font-family:var(--mono)}
.badge{margin-left:auto;font:700 11px var(--mono);letter-spacing:.07em;
  padding:3px 9px;border:1px solid currentColor;text-transform:uppercase;white-space:nowrap}
.badge.g{color:var(--good)} .badge.w{color:var(--warn)} .badge.b{color:var(--bad)}
.nums{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));
  gap:1px;background:var(--line-soft);margin:14px 0 0;border-top:1px solid var(--line-soft)}
.num{background:var(--panel);padding:9px 12px}
.num .k{font:600 9.5px var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.num .v{font-family:var(--mono);font-size:15px;font-variant-numeric:tabular-nums;margin-top:3px}
.num.hi .v{color:var(--sun)}
.num.ok .v{color:var(--good)}
.num.no .v{color:var(--bad)}
.site .why{padding:13px 17px 16px;font-size:14.5px;color:var(--text);max-width:74ch}
.site .why b{color:var(--sun);font-weight:600}
.panowrap{border-top:1px solid var(--line-soft);overflow-x:auto;background:var(--sky)}
.panowrap svg{display:block;width:100%;min-width:660px;height:auto}
.pano .sky{fill:var(--sky)}
.pano .grid{stroke:var(--grid);stroke-width:.55;fill:none}
.pano .grid.zero{stroke:var(--grid-strong);stroke-width:1;stroke-dasharray:4 3}
.pano .ylab{fill:var(--dim);font:500 9.5px var(--mono);text-anchor:end}
.pano .xlab{fill:var(--dim);font:500 9.5px var(--mono);text-anchor:middle}
.pano .terrain{fill:var(--terrain);stroke:var(--terrain-edge);stroke-width:1}
.pano .track{fill:none;stroke:var(--sun);stroke-width:1;stroke-dasharray:2 3;opacity:.5}
.pano .sunstep{fill:var(--sun);opacity:.32}
.pano .sunstep.buried{opacity:.07}
.pano .corona{fill:var(--corona);opacity:.17}
.pano .eclipsed{fill:#05080b;stroke:var(--corona);stroke-width:1.1}
/* Sun and Moon drawn at true angular size and relative position */
.pano .insetbg{fill:var(--ground);fill-opacity:.72;stroke:var(--line);stroke-width:1}
.pano .ilab{fill:var(--dim);font:600 9px var(--mono);text-anchor:middle;
  letter-spacing:.08em}
.pano .sundisc.hidden{opacity:.34}
.pano .moondisc.hidden{opacity:.34}
.pano .hidering{fill:none;stroke:var(--bad);stroke-width:1.2;stroke-dasharray:3 3}
.pano .sundisc{fill:var(--sun)}
.pano .sundisc.tot{fill:var(--sun);opacity:.9}
.pano .moondisc{fill:#05080b;stroke:var(--corona);stroke-width:.5;stroke-opacity:.45}
@media (prefers-color-scheme:light){.pano .moondisc{fill:#111a24}}
:root[data-theme="dark"] .pano .moondisc{fill:#05080b}
:root[data-theme="light"] .pano .moondisc{fill:#111a24}
.pano .callout{stroke:var(--corona);stroke-width:.7;opacity:.55}
.pano .mlab{fill:var(--corona);font:700 9.5px var(--mono);text-anchor:middle;letter-spacing:.07em}
.tablewrap{overflow-x:auto;margin:20px 0 0;border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:13.5px}
th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line-soft);
  font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
th{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);
  background:var(--panel);font-weight:700;position:sticky;top:0}
td:first-child,th:first-child{text-align:left;font-family:var(--sans);white-space:normal;
  min-width:170px}
tbody tr:hover{background:var(--panel)}
td.g{color:var(--good)} td.w{color:var(--warn)} td.b{color:var(--bad)}
.note{border-left:2px solid var(--sun);padding:2px 0 2px 15px;margin:20px 0;
  font-size:14.5px;color:var(--text);max-width:70ch}
.note.warn{border-color:var(--bad)}
ul{margin:0 0 14px;padding-left:20px}
li{margin:0 0 7px}
.steps{list-style:none;padding:0;counter-reset:s}
.steps li{counter-increment:s;padding-left:30px;position:relative;margin-bottom:10px}
.steps li::before{content:counter(s);position:absolute;left:0;top:1px;
  font:700 11px var(--mono);color:var(--sun);border:1px solid var(--line);
  width:20px;height:20px;display:grid;place-items:center}
code{font-family:var(--mono);font-size:.9em;background:var(--panel);
  padding:1px 5px;border:1px solid var(--line-soft)}
footer{padding:30px 0 0;font-size:13px;color:var(--muted)}
footer a{color:var(--muted);text-decoration:underline}
:focus-visible{outline:2px solid var(--sun);outline-offset:2px}
@media (max-width:620px){
  .site-h{padding:13px 13px 0}.site .why{padding:12px 13px 14px}
  .badge{margin-left:0}
}
"""
