# -*- coding: utf-8 -*-
"""The in-page finder: locality + radius over the precomputed recommendation points.

No backend. The whole search is a distance filter over `points.json`, and the
panoramas are drawn in the browser from a compact horizon profile rather than shipped
as one SVG per point.

Two rules carried over from the command line:
  * the locality is chosen from a list of real places (Nominatim), never free text
    turned into a coordinate;
  * the radius is capped, because "10000 km" would return the whole country and mean
    nothing.
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
               placeholder="Malgrat de Mar, Soria, Zaragoza…"
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
      st=document.getElementById('fstatus'), res=document.getElementById('fres');

  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;
    return d.innerHTML;}
  function n(v,d){d=d==null?2:d;return v.toFixed(d).replace('.',',');}
  function deg(v,d,sign){var s=(sign&&v>=0?'+':'')+n(v,d==null?2:d);return s+'\\u00b0';}
  function km(a,b,c,d){var x=(a-c)*111.2, y=(b-d)*111.32*Math.cos((a+c)/2*Math.PI/180);
    return Math.sqrt(x*x+y*y);}

  fetch('points.json').then(function(x){return x.json();}).then(function(j){
    DATA=j;
    st.innerHTML='<b>'+j.meta.n+' miradores</b> ya calculados para este eclipse. '+
      'Escribe una localidad y elígela de la lista.';
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

  function run(){
    if(!DATA||!ORIGIN) return;
    var rad=Math.min(+r.value,MAXR);
    var hits=DATA.points.map(function(p){
      return {p:p,d:km(ORIGIN.lat,ORIGIN.lon,p.lat,p.lon)};
    }).filter(function(h){return h.d<=rad;});
    hits.sort(function(a,b){
      if(b.p.total!==a.p.total) return b.p.total-a.p.total;
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
  }

  // Margen neto: terreno + lo que haya plantado encima. Si no se pudo comprobar, se
  // queda en el del terreno y la ficha lo dice: un dato que falta no puede aparentar
  // ser un dato bueno.
  function net(p){ return (p.clear_net!==undefined && p.obs_ok) ? p.clear_net : p.clear; }

  function card(h){
    var p=h.p, cl=net(p);
    var mc=cl>=2?'ok':(cl<0?'no':'w'), bc=p.total?'g':(cl>=2?'w':'b');
    var badge=p.total?('TOTALIDAD '+n(p.dur,0)+' s'):(n(p.obsc,1)+'% parcial');
    // Totalidad en el filo de la sombra: se avisa donde se mira, no enterrado en el
    // párrafo. No se cambia el orden -- la totalidad sigue siendo otra cosa -- pero el
    // riesgo tiene que ser visible antes de conducir 100 km.
    var risk='';
    if(p.total && p.dur < 30){
      var tip='Con '+n(p.dur,0)+' s est\u00e1s en el filo de la sombra. Mi c\u00e1lculo '+
        'tiene un sesgo de \u00b13 s y no modela el perfil real del limbo lunar '+
        '(los montes del borde de la Luna), que justo aqu\u00ed es lo que decide entre '+
        'ver corona y no verla: podr\u00edan ser 0 s. Para un cazador de eclipses el '+
        'riesgo compensa, porque unos segundos de corona no se parecen a nada. Para un '+
        'plan en familia, un parcial casi seguro con mejor margen suele ser mejor '+
        'idea. Moverse unos kil\u00f3metros hacia el centro de la franja lo resuelve.';
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
        num('sol oculto',(p.total?'100%':n(p.obsc,1)+'%'),'hi')+
        num('altura del sol',deg(p.alt,2))+
        num('horizonte real',deg(p.hz,2,true))+
        num('margen libre',deg(cl,2,true),mc)+
        num('hora',(p.t2||p.t))+
        num('árboles/edificios', p.obs_ok ? (p.obs>0? deg(p.obs,2,true) : 'nada') : 'sin comprobar',
            p.obs_ok ? '' : 'no')+
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
    else s+=' Eclipse <b>parcial</b>: '+n(p.obsc,2)+'% del disco oculto, sin corona.';
    if(p.obs_ok && p.obs>0 && p.obs_what){
      s+=' Ojo: hay <b>'+esc(p.obs_what)+'</b> de unos '+n(p.obs_h,0)+' m a '+
         n(p.obs_d,0)+' m, que levanta el horizonte a '+deg(p.obs,2,true)+
         (p.obs_meas?' (altura del mapa)':' (altura estimada)')+'.';
    } else if(!p.obs_ok){
      s+=' <b>Árboles y edificios sin comprobar</b> en este punto: el margen es solo el del terreno.';
    }
    s+=' A '+n(d,1)+' km en línea recta.';
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
    var lab=p.total?('TOTALIDAD '+p.t):(n(p.obsc,1)+'% oculto \\u00b7 '+p.t);
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
