# -*- coding: utf-8 -*-
"""Índice de apartados, en el margen derecho: el informe general es larguísimo y se
navega a ciegas.

El lenguaje visual no es nuevo: los panoramas de la página ya son ejes de instrumento
—una línea fina, marcas cortas, las etiquetas al lado y el Sol como un círculo
naranja—, así que el índice es el eje del documento. Cada apartado es una marca sobre
la línea y el apartado en el que estás es el círculo.

Se descartaron dos versiones antes de ésta, por si alguien tiene la tentación:
  * flotando en mitad del margen, con botón «Secciones» en móvil: parecía una pegatina
    pegada encima del texto, no una parte de la página;
  * con los títulos colocados en su posición proporcional dentro del documento, para
    que el hueco contase lo largo que era cada bloque: el resultado son huecos enormes
    e irregulares que se leen como una maqueta rota, no como información.
Reparto uniforme, por tanto. La posición dentro del documento la da la marca activa.

Los títulos salen de los `<h2>` de la propia página, nunca de una lista escrita a mano:
una lista aparte se desincroniza el día que se añade un bloque y nadie se entera.

La columna **ocupa sitio** (`padding-right` en el body) en vez de flotar encima del
texto. Por debajo de `MIN_WIDTH_PX` no cabe junto a la columna de 1000 px de contenido,
así que desaparece entera.
"""

MIN_WIDTH_PX = 1260
RAIL_PX = 184

CSS = """
.mmap{position:fixed;top:0;right:0;bottom:0;width:__RAILpx;z-index:40;display:none;
  background:var(--ground);border-left:1px solid var(--line-soft);
  overflow-y:auto;overscroll-behavior:contain;scrollbar-width:none}
.mmap::-webkit-scrollbar{width:0}
.mmap-in{min-height:100%;display:flex;flex-direction:column;justify-content:center;
  padding:28px 18px 28px 26px}
/* el eje: la misma línea fina que llevan los panoramas */
.mmap-list{position:relative}
.mmap-list::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:1px;
  background:var(--line)}
/* el hueco va en `margin`, no en `padding`: dentro de una caja con -webkit-line-clamp
   el relleno inferior deja asomar la línea recortada */
.mmap-i{position:relative;width:100%;margin:7px 0;border:0;
  -webkit-appearance:none;appearance:none;background:none;text-align:left;
  padding:0 0 0 17px;cursor:pointer;
  font:12px/1.34 var(--sans);color:var(--muted);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
/* la marca del eje, centrada en la primera línea */
.mmap-i::before{content:"";position:absolute;left:-3px;top:8px;width:7px;height:1px;
  background:var(--line)}
.mmap-i:hover{color:var(--text)}
.mmap-i:hover::before{background:var(--muted)}
.mmap-i:focus-visible{outline:2px solid var(--sun);outline-offset:1px}
/* dónde estás: el círculo del Sol sobre el eje */
.mmap-i[aria-current="true"]{color:var(--text);font-weight:600}
.mmap-i[aria-current="true"]::before{left:-3px;top:5px;width:7px;height:7px;
  border-radius:50%;background:var(--sun)}
@media (min-width:__MINWpx){
  .mmap{display:block}
  body{padding-right:__RAILpx}
}
@media (prefers-reduced-motion:no-preference){
  .mmap-i,.mmap-i::before{transition:color .14s ease,background-color .14s ease}
}
"""


def html():
    """Vacío a propósito: se rellena con los apartados que tenga la página."""
    return ('<nav class="mmap" id="mmap" aria-label="Apartados" hidden>'
            '<div class="mmap-in"><div class="mmap-list" id="mmapList"></div></div>'
            '</nav>')


def script():
    return """<script>
(function(){
  var rail=document.getElementById('mmap'), list=document.getElementById('mmapList');
  if(!rail||!list) return;
  var secs=[], items=[], active=-1;

  function build(){
    list.textContent=''; secs=[]; items=[];
    [].forEach.call(document.querySelectorAll('.wrap section'),function(s,i){
      var h2=s.querySelector('h2'); if(!h2) return;
      if(!s.id) s.id='s'+i;
      var b=document.createElement('button');
      b.type='button'; b.className='mmap-i';
      b.textContent=h2.textContent.replace(/\\s+/g,' ').trim();
      b.title=b.textContent;
      list.appendChild(b);
      secs.push(s); items.push(b);
    });
    if(items.length<3){ rail.hidden=true; return; }
    rail.hidden=false;
    active=-1; sync();
  }

  function sync(){
    // el apartado activo es el último cuyo título ya ha pasado el tercio superior:
    // con secciones tan altas, un IntersectionObserver apaga la marca a media lectura
    var line=innerHeight*0.34, n=0;
    for(var i=0;i<secs.length;i++){
      if(secs[i].getBoundingClientRect().top<=line) n=i; else break;
    }
    if(n===active) return;
    if(active>=0&&items[active]) items[active].removeAttribute('aria-current');
    if(items[n]){
      items[n].setAttribute('aria-current','true');
      // si el índice no cabe de una vez, que el activo no se quede fuera
      var r=items[n].getBoundingClientRect(), b=rail.getBoundingClientRect();
      if(r.top<b.top||r.bottom>b.bottom) items[n].scrollIntoView({block:'nearest'});
    }
    active=n;
  }

  var reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  list.addEventListener('click',function(e){
    var b=e.target.closest('.mmap-i'); if(!b) return;
    var s=secs[items.indexOf(b)];
    s.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
    history.replaceState(null,'','#'+s.id);
  });

  var tick=false;
  addEventListener('scroll',function(){
    if(tick) return; tick=true;
    requestAnimationFrame(function(){ sync(); tick=false; });
  },{passive:true});

  var rt;
  function later(){ clearTimeout(rt); rt=setTimeout(build,180); }
  addEventListener('resize',later,{passive:true});
  // el buscador pinta resultados y puede añadir apartados: hay que remirar
  new MutationObserver(later).observe(document.querySelector('.wrap'),
    {childList:true});
  build();
})();
</script>"""


CSS = CSS.replace('__RAIL', str(RAIL_PX)).replace('__MINW', str(MIN_WIDTH_PX))
