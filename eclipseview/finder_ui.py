# -*- coding: utf-8 -*-
"""El buscador de la propia página: localidad + radio sobre los miradores precalculados.

Sin servidor. La búsqueda entera es un filtro por distancia sobre `points.json`, y los
panoramas se dibujan en el navegador desde un perfil de horizonte compacto en vez de
mandar un SVG por punto.

Dos reglas que vienen de la línea de comandos:
  * la localidad se elige de una lista de sitios reales (Nominatim), nunca es texto
    libre convertido en coordenada;
  * el radio tiene tope, porque «10.000 km» devolvería el país entero y no
    significaría nada.
"""

MAX_RADIUS_KM = 100
DEFAULT_RADIUS_KM = 60

CSS = """
.finder{border:1px solid var(--sun);background:var(--panel);margin:24px 0 0}
.finder-in{padding:18px 20px;display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}
.fld{display:flex;flex-direction:column;gap:6px;flex:1 1 260px;position:relative}
.fld label{font:600 10px var(--mono);letter-spacing:.12em;text-transform:uppercase;
  color:var(--dim)}
.fld input[type=text]{background:var(--ground);border:1px solid var(--line);
  color:var(--text);padding:10px 12px;font:15px var(--sans);width:100%}
.fld input[type=text]:focus{outline:2px solid var(--sun);outline-offset:-1px}
.fclear{flex:0 0 auto;background:none;border:1px solid var(--line);color:var(--muted);
  padding:10px 14px;font:600 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;
  cursor:pointer}
.fclear:hover{border-color:var(--sun);color:var(--sun)}
.fclear:focus-visible{outline:2px solid var(--sun);outline-offset:2px}
.rad{flex:1 1 220px}
.rad .row{display:flex;align-items:center;gap:10px}
.rad input[type=range]{flex:1;accent-color:var(--sun)}
.rad .v{font:700 15px var(--mono);color:var(--sun);min-width:64px;text-align:right}
.sugg{position:absolute;top:100%;left:0;right:0;z-index:20;background:var(--panel);
  border:1px solid var(--sun);max-height:270px;overflow-y:auto;display:none}
.sugg.on{display:block}
.sugg button{display:block;width:100%;text-align:left;background:none;border:0;
  border-bottom:1px solid var(--line-soft);color:var(--text);padding:9px 12px;
  font:14px var(--sans);cursor:pointer}
.sugg button:hover,.sugg button:focus{background:var(--ground);outline:none}
.sugg .s2{display:block;font:11px var(--mono);color:var(--dim);margin-top:2px}
.fstatus{padding:0 20px 16px;font-size:13.5px;color:var(--muted)}
.fstatus b{color:var(--sun)}
.fres{border-top:1px solid var(--line-soft);background:var(--ground);
  padding:16px;display:flex;flex-direction:column;gap:16px}
/* Cada resultado es una tarjeta con su propio borde: pegadas unas a otras no se ve
   dónde acaba un mirador y empieza el siguiente. */
.fres .site{border:1px solid var(--line);background:var(--panel);margin:0}
.fres .site:hover{border-color:var(--dim)}
.fempty{padding:16px 20px;border-top:1px solid var(--line-soft);font-size:14.5px}
.chip{display:inline-block;font:600 11px var(--mono);padding:2px 8px;
  border:1px solid currentColor;margin-left:8px}
.chip.g{color:var(--good)} .chip.w{color:var(--warn)} .chip.b{color:var(--bad)}
.badges{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  justify-content:flex-end}
.badges .badge{margin-left:0}
.risk{position:relative;font:700 10px var(--mono);letter-spacing:.06em;
  color:var(--bad);border:1px solid currentColor;padding:3px 8px;cursor:help;
  white-space:nowrap}
.risk:focus{outline:2px solid var(--sun);outline-offset:2px}
.risk .tip{position:absolute;right:0;top:calc(100% + 8px);width:min(340px,78vw);
  background:var(--ground);color:var(--text);border:1px solid var(--bad);
  padding:11px 13px;font:400 12.5px/1.55 var(--sans);letter-spacing:0;
  white-space:normal;text-transform:none;z-index:30;
  opacity:0;visibility:hidden;transition:opacity .12s}
.risk:hover .tip,.risk:focus .tip{opacity:1;visibility:visible}
@media (prefers-reduced-motion:reduce){.risk .tip{transition:none}}
.ptcoord{font-family:var(--mono)!important;font-size:16px!important;letter-spacing:.01em}
.ptlinks{display:flex;flex-wrap:wrap;gap:10px 16px;margin:14px 0 0;
  font:600 12px var(--mono);align-items:center}
.ptlinks a{color:var(--sun);text-decoration:none;border-bottom:1px solid currentColor}
.ptlinks a.go{background:var(--sun);color:var(--ground);padding:5px 12px;
  border:0;letter-spacing:.03em}
.ptlinks a.go:hover{filter:brightness(1.12)}
.ptwarn{padding:13px 15px;margin:0;font-size:13.5px;color:var(--muted);
  background:var(--panel);border:1px solid var(--line-soft);border-left:2px solid var(--sun)}
.ptwarn b{color:var(--text)}
.spin{display:inline-block;width:11px;height:11px;border:2px solid var(--line);
  border-top-color:var(--sun);border-radius:50%;animation:sp .7s linear infinite;
  vertical-align:-1px;margin-right:7px}
@keyframes sp{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.spin{animation:none}}
"""


def html(max_radius=MAX_RADIUS_KM, default_radius=DEFAULT_RADIUS_KM):
    return f'''
<section id="buscador">
  <p class="eyebrow">Empieza por aquí</p>
  <h2>¿Desde dónde lo veo yo?</h2>
  <p class="prose">Pon tu pueblo y hasta dónde estás dispuesto a moverte. Te saco los
  <b>miradores ya calculados</b> que caen dentro, ordenados por margen sobre el
  terreno. El límite es {max_radius} km a propósito: más lejos y esto dejaría de ser
  una recomendación para ser un listado.</p>

  <div class="finder">
    <div class="finder-in">
      <div class="fld">
        <label for="q">Localidad</label>
        <input type="text" id="q" autocomplete="off" spellcheck="false"
               placeholder="Aguilar de Campoo, Soria, Zaragoza…"
               aria-describedby="fstatus">
        <div class="sugg" id="sugg" role="listbox" aria-label="Localidades"></div>
      </div>
      <div class="fld rad">
        <label for="r">Radio de búsqueda</label>
        <div class="row">
          <input type="range" id="r" min="10" max="{max_radius}" step="5"
                 value="{default_radius}">
          <span class="v" id="rv">{default_radius} km</span>
        </div>
      </div>
      <button type="button" class="fclear" id="fclear" hidden>Empezar de nuevo</button>
    </div>
    <p class="fstatus" id="fstatus">Escribe una localidad y elígela de la lista.</p>
    <div class="fres" id="fres"></div>
  </div>
</section>'''


def script(max_radius=MAX_RADIUS_KM):
    return '''
<script>
(function(){
  var AZ_LO=262, AZ_HI=300, ALT_LO=-1.6, SUN_R=0.2665, MAXR=''' + str(max_radius) + ''';
  var DATA=null, ORIGIN=null, TIMER=null, ABORT=null;
  var q=document.getElementById('q'), sugg=document.getElementById('sugg'),
      r=document.getElementById('r'), rv=document.getElementById('rv'),
      st=document.getElementById('fstatus'), res=document.getElementById('fres'),
      clr=document.getElementById('fclear');
  var INICIAL='Escribe una localidad y elígela de la lista.';

  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;
    return d.innerHTML;}
  function n(v,d){d=d==null?2:d;return v.toFixed(d).replace('.',',');}
  function deg(v,d,sign){var s=(sign&&v>=0?'+':'')+n(v,d==null?2:d);return s+'\\u00b0';}
  function km(a,b,c,d){var x=(a-c)*111.2, y=(b-d)*111.32*Math.cos((a+c)/2*Math.PI/180);
    return Math.sqrt(x*x+y*y);}

  fetch('points.json').then(function(x){return x.json();}).then(function(j){
    DATA=j;
    INICIAL='<b>'+j.meta.n+' miradores</b> ya calculados para este eclipse. '+
      'Escribe una localidad y elígela de la lista.';
    if(!ORIGIN) st.innerHTML=INICIAL;
    var p=new URLSearchParams(location.search);
    if(p.get('lat')&&p.get('lon')){
      ORIGIN={lat:parseFloat(p.get('lat')),lon:parseFloat(p.get('lon')),
              name:p.get('n')||'tu punto'};
      q.value=ORIGIN.name; if(p.get('r')){r.value=p.get('r');rv.textContent=r.value+' km';}
      run();
    }
  }).catch(function(){st.textContent='No he podido cargar los puntos precalculados.';});

  r.addEventListener('input',function(){rv.textContent=r.value+' km';
    if(ORIGIN) run();});

  q.addEventListener('input',function(){
    clearTimeout(TIMER); var v=q.value.trim();
    if(v.length<3){sugg.classList.remove('on');return;}
    TIMER=setTimeout(function(){lookup(v);},450);   // Nominatim: 1 req/s máximo
  });
  q.addEventListener('keydown',function(e){
    if(e.key==='Escape'){sugg.classList.remove('on');}
  });
  document.addEventListener('click',function(e){
    if(!sugg.contains(e.target)&&e.target!==q) sugg.classList.remove('on');
  });

  var SETTLE={city:1,town:1,village:1,hamlet:1,municipality:1,suburb:1,quarter:1,
              locality:1,island:1,borough:1,isolated_dwelling:1};
  var FEAT={peak:1,volcano:1,saddle:1,ridge:1,cape:1,cliff:1};

  function lookup(v){
    if(ABORT) ABORT.abort();
    ABORT=new AbortController();
    st.innerHTML='<span class="spin"></span>Buscando &laquo;'+esc(v)+'&raquo;…';
    var u='https://nominatim.openstreetmap.org/search?format=jsonv2&limit=12'+
          '&addressdetails=1&accept-language=es&q='+encodeURIComponent(v);
    fetch(u,{signal:ABORT.signal}).then(function(x){return x.json();}).then(function(a){
      // Mismo criterio que en el CLI: solo poblaciones y accidentes geográficos,
      // nunca texto libre convertido en coordenada.
      var out=[];
      a.forEach(function(o){
        var t=o.type, at=o.addresstype, cls=o.class||o.category, kind=null;
        if(cls==='place'&&SETTLE[t]) kind='n';
        else if(cls==='natural'&&FEAT[t]) kind='f';
        else if(t==='administrative'&&SETTLE[at]) kind='n';
        if(!kind) return;
        var ad=o.address||{}, bits=[];
        ['county','state','country'].forEach(function(k){
          if(ad[k]&&bits.indexOf(ad[k])<0&&bits.length<2) bits.push(ad[k]);});
        out.push({name:o.name||o.display_name.split(',')[0], sub:bits.join(', '),
                  lat:parseFloat(o.lat), lon:parseFloat(o.lon), kind:kind,
                  osm:o.osm_type+'/'+o.osm_id});
      });
      if(!out.length){
        sugg.classList.remove('on');
        st.innerHTML='&laquo;'+esc(v)+'&raquo; no aparece como población ni como '+
          'accidente geográfico. Prueba con el nombre oficial del municipio.';
        return;
      }
      sugg.innerHTML=out.map(function(o,i){
        return '<button type="button" data-i="'+i+'" role="option">'+esc(o.name)+
          '<span class="s2">'+esc(o.sub)+(o.kind==='f'?' · cumbre':'')+
          ' · '+esc(o.osm)+'</span></button>';}).join('');
      sugg.classList.add('on');
      st.innerHTML='Elige cuál de los '+out.length+':';
      Array.prototype.forEach.call(sugg.querySelectorAll('button'),function(b){
        b.addEventListener('click',function(){
          ORIGIN=out[+b.dataset.i]; q.value=ORIGIN.name;
          sugg.classList.remove('on'); run();});
      });
    }).catch(function(e){ if(e.name!=='AbortError')
      st.textContent='No he podido consultar el buscador de lugares.'; });
  }

  // El ensayo trae tablas y fichas con «km hasta el punto» sin rellenar: la distancia
  // no tiene respuesta hasta que el lector dice desde dónde viene. En cuanto elige
  // localidad se recalculan todas desde ahí, en vez de contestar siempre desde
  // Barcelona, que para quien lee esto desde Vigo es ruido.
  function retag(){
    if(!ORIGIN) return;
    [].forEach.call(document.querySelectorAll('.dcol[data-lat]'),function(el){
      var d=Math.round(km(ORIGIN.lat,ORIGIN.lon,+el.dataset.lat,+el.dataset.lon));
      var v=el.querySelector('.v'), k=el.querySelector('.k');
      if(v){ v.textContent=d+' km'; if(k) k.textContent='desde '+ORIGIN.name; }
      else el.textContent=d;
    });
    [].forEach.call(document.querySelectorAll('th.dcol'),function(el){
      el.textContent='km desde '+ORIGIN.name;
    });
  }

  // Volver al principio de verdad. Antes no había manera: borrabas el texto y los
  // resultados del pueblo anterior seguían ahí, y la búsqueda se quedaba pegada en la
  // dirección (?lat=…&n=…), así que recargar tampoco servía.
  function limpiar(){
    ORIGIN=null;
    q.value=''; sugg.classList.remove('on'); sugg.innerHTML='';
    res.innerHTML=''; st.innerHTML=INICIAL;
    clr.hidden=true;
    // las columnas de distancia vuelven a su estado neutro
    [].forEach.call(document.querySelectorAll('.dcol[data-lat]'),function(el){
      var v=el.querySelector('.v');
      if(v){ v.textContent='—'; var k=el.querySelector('.k');
             if(k) k.textContent='distancia'; }
      else el.textContent='—';
    });
    [].forEach.call(document.querySelectorAll('th.dcol'),function(el){
      el.textContent='km hasta el punto'; });
    var u=new URL(location);
    ['lat','lon','n','r'].forEach(function(k){ u.searchParams.delete(k); });
    history.replaceState(null,'',u.pathname+u.search+u.hash);
    q.focus();
  }
  clr.addEventListener('click',limpiar);
  // borrar el texto a mano equivale a empezar de nuevo: dejar resultados de un pueblo
  // que ya no está escrito es lo que confundía
  q.addEventListener('input',function(){ if(!q.value.trim()&&ORIGIN) limpiar(); });

  function run(){
    if(!DATA||!ORIGIN) return;
    clr.hidden=false;
    retag();
    var rad=Math.min(+r.value,MAXR);
    var hits=DATA.points.map(function(p){
      return {p:p,d:km(ORIGIN.lat,ORIGIN.lon,p.lat,p.lon)};
    }).filter(function(h){return h.d<=rad;});
    // Una totalidad de 5 s se listaba por delante de un parcial del 99,4 % con mucho
    // mejor margen, sólo por ser totalidad. Ahora "totalidad" significa la que
    // confirman LOS DOS modelos: el de esfera calibrada contra el IGN y el del perfil
    // real del limbo lunar. Si sólo la ve uno, no encabeza la lista: se coloca entre
    // los parciales por su margen, con su aviso, porque puede no haber corona.
    hits.sort(function(a,b){
      var A=solida(a.p), B=solida(b.p);
      if(A!==B) return B-A;
      return net(b.p)-net(a.p);});

    var url=new URL(location); url.searchParams.set('lat',ORIGIN.lat.toFixed(4));
    url.searchParams.set('lon',ORIGIN.lon.toFixed(4));
    url.searchParams.set('n',ORIGIN.name); url.searchParams.set('r',rad);
    history.replaceState(null,'',url);

    if(!hits.length){
      var near=DATA.points.map(function(p){
        return km(ORIGIN.lat,ORIGIN.lon,p.lat,p.lon);}).sort(function(a,b){
        return a-b;})[0];
      res.innerHTML='<div class="fempty">No hay ningún mirador calculado a menos de '+
        '<b>'+rad+' km</b> de '+esc(ORIGIN.name)+'. El más cercano está a <b>'+
        Math.round(near)+' km</b>: sube el radio si puedes moverte tanto.</div>';
      st.innerHTML='0 miradores dentro de '+rad+' km.';
      return;
    }
    var tot=hits.filter(function(h){return h.p.total;}).length;
    st.innerHTML='<b>'+hits.length+'</b> miradores a menos de '+rad+' km de '+
      esc(ORIGIN.name)+(tot?', '+tot+' de ellos con totalidad':', ninguno con totalidad')+
      '. Ordenados por margen sobre el terreno.';
    res.innerHTML='<p class="ptwarn">Cada resultado es un <b>punto concreto</b> con '+
      'sus coordenadas, no una recomendaci&oacute;n de pueblo: el municipio solo dice '+
      'd&oacute;nde cae. Ir al centro de esa localidad puede no servir. '+
      'Son puntos del <b>terreno</b>: comprueba en el mapa que se llega y que no es '+
      'finca privada.</p>'+
      hits.slice(0,8).map(card).join('');
    pideNubes(hits.slice(0,8).map(function(h){return h.p;}));
  }

  // El pronóstico llega después de pintar: la ficha no se queda esperando a un tercero.
  // Si no llega, el hueco se queda en "sin pronóstico", que es la verdad.
  function pideNubes(puntos){
    if(!window.fcPide||!puntos.length) return;
    window.fcPide(puntos).then(function(pcts){
      if(pcts===null){                       // demasiado lejos para que signifique algo
        [].forEach.call(res.querySelectorAll('.fcslot'),function(el){
          el.querySelector('.v').innerHTML='<span class="fc"><span class="v">—</span>'+
            '<span class="u">aún lejos</span></span>';});
        return;
      }
      puntos.forEach(function(p,i){
        var el=res.querySelector('.fcslot[data-fc="'+p.i+'"]');
        if(el) el.querySelector('.v').innerHTML=window.fcHtml(pcts&&pcts[i]);
      });
    });
  }

  // Margen neto: terreno + lo que haya plantado encima. Si no se pudo comprobar, se
  // queda en el del terreno y la ficha lo dice: un dato que falta no puede aparentar
  // ser un dato bueno.
  function net(p){ return (p.clear_net!==undefined && p.obs_ok) ? p.clear_net : p.clear; }

  // Totalidad SÓLIDA: la que ven los dos modelos. El de esfera está calibrado contra
  // las cifras publicadas del IGN y la NASA; el otro usa el perfil real del limbo lunar
  // (topografía LOLA + la libración del día). Mientras no haya dato de limbo se cae al
  // criterio de siempre, no se inventa una confirmación.
  function solida(p){
    if(p.total_limb===undefined) return p.total ? 1 : 0;
    return (p.total && p.total_limb) ? 1 : 0;
  }
  // Rango de duración según los dos modelos: es la incertidumbre de verdad, medida.
  function durLo(p){
    if(p.dur_limb===undefined) return p.dur;
    return Math.min(p.dur, p.total_limb ? p.dur_limb : 0);
  }
  function durHi(p){
    if(p.dur_limb===undefined) return p.dur;
    return Math.max(p.dur, p.dur_limb);
  }
  // Un punto SIN totalidad no puede leerse "100,0%": 99,951 redondeado a una decimal
  // da 100,0 y, pegado a la palabra "parcial", parece un fallo del cálculo justo en
  // los puntos donde más se mira.
  //
  // La regla es la misma que la de i18n.obscuration, que ya la aplicaba en los
  // informes: se añaden decimales hasta que el número se queda por debajo de 100. Si
  // aquí se truncara, el informe y la web dirían cosas distintas del mismo punto
  // (99,95% frente a 99,9%), que es peor que cualquiera de las dos por separado.
  function obscTxt(p,d){
    d=(d==null)?1:d;
    if(p.total) return n(p.obsc,d);
    for(var k=d;k<=3;k++){
      var s=n(p.obsc,k);
      if(parseFloat(s.replace(',','.'))<100) return s;
    }
    return '>'+n(99.999,3);
  }

  // Accesibilidad a partir de las etiquetas de OpenStreetMap. Lo que NO se puede es
  // interpretar el silencio: la mayoría de vías no llevan surface/smoothness, así que
  // «sin datos» se dice, no se traduce por «fácil».
  function acc_label(p){
    if(!p.acc_ok||!p.acc) return 'sin comprobar';
    var a=p.acc, pv=a.paved, dr=a.drive;
    if(pv && pv.m<=100) return 'asfalto a '+n(pv.m,0)+' m';
    if(dr && dr.m<=150) return (dr.kind==='track'?'pista':'v\u00eda')+' a '+n(dr.m,0)+' m'+
      (dr.hard&&dr.hard.length?' \u00b7 dura':'');
    if(pv) return 'asfalto a '+(pv.m>=1000? n(pv.m/1000,1)+' km':n(pv.m,0)+' m');
    if(dr) return 'pista a '+(dr.m>=1000? n(dr.m/1000,1)+' km':n(dr.m,0)+' m');
    if(a.walk) return 'solo sendero';
    return 'sin v\u00eda en 1,2 km';
  }
  function acc_class(p){
    if(!p.acc_ok||!p.acc) return 'no';
    var a=p.acc;
    if(a.paved && a.paved.m<=150) return 'ok';
    if(a.drive && a.drive.m<=150 && !(a.drive.hard||[]).length) return '';
    return 'no';
  }

  function card(h){
    var p=h.p, cl=net(p);
    var mc=cl>=2?'ok':(cl<0?'no':'w'), bc=p.total?'g':(cl>=2?'w':'b');
    // Cuando los dos modelos difieren de verdad, la chapa enseña el RANGO en vez de un
    // número redondo: fingir precisión donde no la hay es lo que había que quitar.
    var badge;
    if(!p.total){ badge=obscTxt(p,1)+'% parcial'; }
    else if(p.dur_limb!==undefined && Math.abs(durHi(p)-durLo(p))>=5){
      badge='TOTALIDAD '+n(durLo(p),0)+'–'+n(durHi(p),0)+' s';
    } else { badge='TOTALIDAD '+n(p.dur,0)+' s'; }
    // Totalidad en el filo de la sombra: se avisa donde se mira, no enterrado en el
    // párrafo. No se cambia el orden -- la totalidad sigue siendo otra cosa -- pero el
    // riesgo tiene que ser visible antes de conducir 100 km.
    // El aviso del filo ya no es gen\u00e9rico: lo decide el contraste entre los dos
    // modelos. Antes dec\u00eda "podr\u00edan ser 0 s" siempre, que era una suposici\u00f3n.
    var risk='', tip='';
    if(p.total && p.total_limb===false){
      tip='Aqu\u00ed los dos modelos NO se ponen de acuerdo. Con la Luna como esfera salen '+
        n(p.dur,0)+' s de totalidad, pero con el perfil real de su limbo \u2014los montes '+
        'y valles del borde, medidos por la sonda LRO\u2014 no queda totalidad. Puede que '+
        's\u00f3lo veas las perlas de Baily. Unos kil\u00f3metros hacia el centro de la franja '+
        'lo resuelven.';
      risk='<span class="risk" tabindex="0" role="note" aria-label="'+tip+'">'+
           'SIN TOTALIDAD SEGURA<span class="tip">'+tip+'</span></span>';
    } else if(!p.total && p.total_limb){
      // El caso contrario, y el más frecuente: la esfera no ve totalidad y el perfil
      // real del limbo sí, unos segundos. Callarlo sería esconder un cálculo que
      // tenemos. Prometerlo, mentir. Se dice lo que hay.
      tip='Justo en el filo. Con la Luna como esfera aquí no hay totalidad, pero con el '+
        'perfil real de su limbo —los montes del borde, medidos por la sonda LRO— '+
        'salen unos '+n(p.dur_limb,0)+' s. Puede que veas corona unos segundos, o sólo '+
        'las perlas de Baily. Si vas a por la corona, muévete hacia el centro de la '+
        'franja; si te pilla de paso, mira igual: un '+obscTxt(p,1)+'% ya es un '+
        'espectáculo.';
      risk='<span class="risk" tabindex="0" role="note" aria-label="'+tip+'">'+
           'PUEDE HABER UNOS SEGUNDOS<span class="tip">'+tip+'</span></span>';
    } else if(p.total && durLo(p) < 30){
      tip='Con unos '+n(durLo(p),0)+' s est\u00e1s en el filo de la sombra. Los dos modelos '+
        'ven totalidad \u2014el de esfera, calibrado contra el IGN, y el del perfil real '+
        'del limbo lunar\u2014 y le dan entre '+n(durLo(p),0)+' y '+n(durHi(p),0)+' s. Aun '+
        'as\u00ed es poco: el limbo est\u00e1 medido a unos 2 km de resoluci\u00f3n y ah\u00ed eso son '+
        'segundos. Para un cazador de eclipses compensa, porque unos segundos de '+
        'corona no se parecen a nada. Para un plan en familia, un parcial casi seguro '+
        'con mejor margen suele ser mejor idea.';
      risk='<span class="risk" tabindex="0" role="note" aria-label="'+tip+'">'+
           'AL BORDE \u00b7 RIESGO ALTO<span class="tip">'+tip+'</span></span>';
    }
    function num(k,v,c){return '<div class="num '+(c||'')+'"><div class="k">'+k+
      '</div><div class="v">'+v+'</div></div>';}
    // El titular es el PUNTO. El municipio es solo dónde cae: ponerlo en grande hace
    // que la gente conduzca al centro del pueblo, que es justo el sitio que puede
    // tener el horizonte tapado.
    var coord=n(p.lat,5)+', '+n(p.lon,5);
    // Navegar, no solo mirar: el punto es el destino, y con coordenadas exactas
    // porque el centro del municipio puede estar a kilómetros y con el monte delante.
    var nav='https://www.google.com/maps/dir/?api=1&destination='+p.lat+','+p.lon+
            '&travelmode=driving';
    var gmaps='https://www.google.com/maps/search/?api=1&query='+p.lat+','+p.lon;
    var osm='https://www.openstreetmap.org/?mlat='+p.lat+'&mlon='+p.lon+'#map=15/'+p.lat+'/'+p.lon;
    return '<article class="site">'+
      '<div class="site-h"><h3 class="ptcoord">'+coord+'</h3>'+
      '<span class="place">'+(p.place? 'en el t&eacute;rmino de '+esc(p.place):'')+
      '</span><span class="badges"><span class="badge '+bc+'">'+badge+
      '</span>'+risk+'</span></div>'+
      '<div class="nums">'+
        num('distancia',n(h.d,1)+' km')+
        num('altitud',p.elev+' m')+
        num('sol oculto',(p.total?'100%':obscTxt(p,1)+'%'),'hi')+
        num('altura del sol',deg(p.alt,2))+
        num('horizonte real',deg(p.hz,2,true))+
        num('margen libre',deg(cl,2,true),mc)+
        num('hora',(p.t2||p.t))+
        num('árboles/edificios', p.obs_ok ? (p.obs>0? deg(p.obs,2,true) : 'nada') : 'sin comprobar',
            p.obs_ok ? '' : 'no')+
        num('acceso', acc_label(p), acc_class(p))+
        // el hueco del pronóstico: se rellena cuando llega, o se queda en "—". Nunca
        // se inventa un valor mientras tanto.
        '<div class="num fcslot" data-fc="'+p.i+'"><div class="k">nubes (pron.)</div>'+
        '<div class="v">'+(window.fcHtml?window.fcHtml(undefined):'—')+'</div></div>'+
      '</div>'+
      '<div class="panowrap">'+pano(p)+'</div>'+
      '<div class="why">'+why(p,h.d)+
        '<div class="ptlinks">'+
        '<a class="go" href="'+nav+'" target="_blank" rel="noopener">C&oacute;mo llegar \u2197</a>'+
        '<a href="'+gmaps+'" target="_blank" rel="noopener">Ver en el mapa \u2197</a>'+
        '<a href="'+osm+'" target="_blank" rel="noopener">OpenStreetMap \u2197</a>'+
        (p.sv?'<a href="'+p.sv+'" target="_blank" rel="noopener">Street View mirando al Sol \u2197</a>':'')+
        '</div>'+
      '</div></article>';
  }

  function why(p,d){
    var t=p.clear/0.53;
    var s;
    if(p.clear<0) s='<b>No sirve:</b> el terreno se levanta '+deg(p.hz,2,true)+
      ' y el Sol solo llega a '+deg(p.alt,2)+'.';
    else if(p.clear<2) s='<b>Justo:</b> '+deg(p.clear,2,true)+' sobre la silueta, unas '+
      n(t,1)+' veces el diámetro del Sol. Ve a verlo antes.';
    else s='<b>Margen cómodo:</b> '+deg(p.clear,2,true)+' libres, unas '+n(t,0)+
      ' veces el diámetro del Sol.';
    if(p.total && p.dur < 30) s+=' Aquí entra la totalidad, pero solo <b>'+n(p.dur,0)+
      ' s</b>: est&aacute;s justo en el borde de la sombra, donde el margen de error '+
      'del c&aacute;lculo es alto y basta desplazarse unos kil&oacute;metros hacia el '+
      'centro de la franja para ganar mucho.';
    else if(p.total) s+=' Aquí hay <b>totalidad: '+n(p.dur,0)+' s</b>, de '+p.t2+' a '+p.t3+'.';
    else s+=' Eclipse <b>parcial</b>: '+obscTxt(p,2)+'% del disco oculto, sin corona.';
    if(p.obs_ok && p.obs>0 && p.obs_what){
      s+=' Ojo: hay <b>'+esc(p.obs_what)+'</b> de unos '+n(p.obs_h,0)+' m a '+
         n(p.obs_d,0)+' m, que levanta el horizonte a '+deg(p.obs,2,true)+
         (p.obs_meas?' (altura del mapa)':' (altura estimada)')+'.';
    } else if(!p.obs_ok){
      s+=' <b>Árboles y edificios sin comprobar</b> en este punto: el margen es solo el del terreno.';
    }
    s+=' A '+n(d,1)+' km en línea recta.';
    if(p.acc_ok && p.acc){
      var a=p.acc, bits=[];
      if(a.paved) bits.push('carretera asfaltada a '+(a.paved.m>=1000?n(a.paved.m/1000,1)+' km':n(a.paved.m,0)+' m'));
      else bits.push('<b>ninguna carretera asfaltada</b> en 1,2 km');
      if(a.drive && (!a.paved || a.drive.m < a.paved.m)){
        var dur=(a.drive.hard||[]).length;
        bits.push((a.drive.kind==='track'?'pista':'v\u00eda')+' a '+n(a.drive.m,0)+' m'+
          (dur? ' que OSM marca como <b>dura</b> ('+esc(a.drive.hard.join(', '))+'): '+
                'cuenta con 4x4 o con andar' :
                (a.drive.rated? '' : ' (sin etiquetas de firme: no se sabe c&oacute;mo est&aacute;)')));
      }
      if(a.walk) bits.push('sendero a '+n(a.walk.m,0)+' m');
      s+=' <b>Acceso:</b> '+bits.join('; ')+'.';
    } else if(!p.acc_ok){
      s+=' <b>Acceso sin comprobar.</b>';
    }
    return s;
  }

  // Panorama dibujado en el navegador desde el perfil compacto: mismo diseño que el
  // de los informes, sin enviar un SVG por punto.
  function pano(p){
    var W=820,H=352,pl=44,pb=32,pt=12,pr=10;
    var iw=W-pl-pr, ih=H-pt-pb, dp=iw/(AZ_HI-AZ_LO), altHi=ALT_LO+ih/dp;
    function X(a){return pl+(a-AZ_LO)*dp;}
    function Y(v){return pt+(altHi-v)*dp;}
    var o=['<svg viewBox="0 0 '+W+' '+H+'" class="pano" xmlns="http://www.w3.org/2000/svg" role="img">'];
    o.push('<title>Horizonte real hacia el ONO y trayectoria del Sol</title>');
    o.push('<rect class="sky" x="'+pl+'" y="'+pt+'" width="'+iw+'" height="'+ih+'"/>');
    for(var v=0;v<=altHi;v+=2){var y=Y(v);
      o.push('<line class="grid'+(v===0?' zero':'')+'" x1="'+pl+'" y1="'+y.toFixed(1)+
        '" x2="'+(pl+iw)+'" y2="'+y.toFixed(1)+'"/>');
      o.push('<text class="ylab" x="'+(pl-7)+'" y="'+(y+3.5).toFixed(1)+'">'+v+'\\u00b0</text>');}
    for(var a=265;a<=AZ_HI;a+=5){var x=X(a);
      o.push('<line class="grid" x1="'+x.toFixed(1)+'" y1="'+pt+'" x2="'+x.toFixed(1)+
        '" y2="'+(pt+ih)+'"/>');
      o.push('<text class="xlab" x="'+x.toFixed(1)+'" y="'+(pt+ih+14)+'">'+a+'\\u00b0</text>');}
    var pts=[];
    for(var i=0;i<p.prof.length;i++){
      var az=AZ_LO+i*DATA.meta.az_step, hv=p.prof[i]/100;
      pts.push(X(az).toFixed(1)+','+Math.min(Math.max(Y(hv),pt),pt+ih).toFixed(1));}
    o.push('<polygon class="terrain" points="'+pl+','+(pt+ih)+' '+pts.join(' ')+' '+
      (pl+iw)+','+(pt+ih)+'"/>');
    var sr=SUN_R*dp, tp=[];
    p.sun.forEach(function(s){ if(s[0]>=AZ_LO&&s[0]<=AZ_HI) tp.push(X(s[0]).toFixed(1)+','+Y(s[1]).toFixed(1)); });
    if(tp.length) o.push('<polyline class="track" points="'+tp.join(' ')+'"/>');
    p.sun.forEach(function(s){
      if(s[0]<AZ_LO||s[0]>AZ_HI||s[1]<ALT_LO) return;
      var idx=Math.round((s[0]-AZ_LO)/DATA.meta.az_step);
      var hv=(p.prof[Math.max(0,Math.min(p.prof.length-1,idx))]||0)/100;
      o.push('<circle class="sunstep'+(s[1]<hv?' buried':'')+'" cx="'+X(s[0]).toFixed(1)+
        '" cy="'+Y(s[1]).toFixed(1)+'" r="'+sr.toFixed(1)+'"/>');});
    var x0=X(p.az), y0=Y(p.alt), mo=p.moon, rs=mo[2]*dp, rm=mo[3]*dp;
    var hid=p.alt<p.hz;
    if(p.total) o.push('<circle class="corona" cx="'+x0.toFixed(1)+'" cy="'+y0.toFixed(1)+
      '" r="'+(rs*2.6).toFixed(1)+'"/>');
    o.push('<circle class="sundisc'+(hid?' hidden':'')+'" cx="'+x0.toFixed(1)+'" cy="'+
      y0.toFixed(1)+'" r="'+rs.toFixed(2)+'"/>');
    o.push('<circle class="moondisc'+(hid?' hidden':'')+'" cx="'+(x0+mo[0]*dp).toFixed(2)+
      '" cy="'+(y0-mo[1]*dp).toFixed(2)+'" r="'+rm.toFixed(2)+'"/>');
    if(hid) o.push('<circle class="hidering" cx="'+x0.toFixed(1)+'" cy="'+y0.toFixed(1)+
      '" r="'+(rs*1.9).toFixed(1)+'"/>');
    var lab=p.total?('TOTALIDAD '+p.t):(obscTxt(p,1)+'% oculto \\u00b7 '+p.t);
    var halo=p.total?rs*2.6:rs*1.6, ly=Math.max(y0-halo-8,pt+11);
    o.push('<line class="callout" x1="'+x0.toFixed(1)+'" y1="'+(ly+3).toFixed(1)+
      '" x2="'+x0.toFixed(1)+'" y2="'+(y0-halo).toFixed(1)+'"/>');
    o.push('<text class="mlab" x="'+x0.toFixed(1)+'" y="'+ly.toFixed(1)+'">'+lab+'</text>');
    // recuadro ampliado: a escala real el creciente mide menos de un píxel
    var R=44, mag=R/rs, cx=pl+R+16, cy=pt+R+16;
    o.push('<circle class="insetbg" cx="'+cx+'" cy="'+cy+'" r="'+(R*1.5)+'"/>');
    if(p.total) o.push('<circle class="corona" cx="'+cx+'" cy="'+cy+'" r="'+(R*1.45)+'"/>');
    o.push('<circle class="sundisc" cx="'+cx+'" cy="'+cy+'" r="'+R+'"/>');
    o.push('<circle class="moondisc" cx="'+(cx+mo[0]*dp*mag).toFixed(2)+'" cy="'+
      (cy-mo[1]*dp*mag).toFixed(2)+'" r="'+(rm*mag).toFixed(2)+'"/>');
    o.push('<text class="ilab" x="'+cx+'" y="'+(cy+R*1.5+12)+'">\\u00d7'+
      mag.toFixed(0)+' aumentos</text>');
    return o.join('')+'</svg>';
  }
})();
</script>'''
