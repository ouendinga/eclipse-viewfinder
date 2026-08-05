# -*- coding: utf-8 -*-
"""Pronóstico de nubosidad para la hora del eclipse, en el navegador.

Por qué en el navegador y no cocinado en el dataset: un pronóstico caduca. Si se
hornease en `points.json` habría que reconstruir y redesplegar el sitio cada día para
que no mintiera, y el día que se olvidase estaría enseñando el pronóstico de hace una
semana con pinta de dato bueno. Pidiéndolo al abrir la búsqueda, o está fresco o no
está — y si el servicio no responde se dice, no se rellena con nada.

Sólo se piden los puntos que el usuario está viendo (ocho como mucho), en una única
petición con varias coordenadas.

OJO con la diferencia que la página tiene que dejar clarísima:
  * la CLIMATOLOGÍA (Eclipsophile) dice lo que suele pasar en agosto — no es un
    pronóstico y no caduca;
  * esto es un PRONÓSTICO a días vista, que cambia cada día y que a más de una semana
    vista no vale para decidir nada.
"""

API = 'https://api.open-meteo.com/v1/forecast'
SOURCE_LABEL = 'Open-Meteo'
SOURCE_URL = 'https://open-meteo.com/'
# A partir de aquí un pronóstico deja de ser información y pasa a ser ruido con
# aspecto de dato. Los modelos globales pierden habilidad muy rápido pasada una semana.
USEFUL_DAYS = 10

CSS = """
.fc{display:inline-flex;align-items:baseline;gap:6px}
.fc .v{font:700 15px var(--mono);font-variant-numeric:tabular-nums}
.fc.g .v{color:var(--good)} .fc.w .v{color:var(--warn)} .fc.b .v{color:var(--bad)}
.fc .u{font:600 10px var(--mono);color:var(--dim)}
.fcnote{font-size:12px;color:var(--dim);margin:10px 0 0}
.fcnote b{color:var(--muted)}
.fcwarn{color:var(--warn)}
"""


def script(event_date, hour_local, tz_name='Europe/Madrid'):
    """`hour_local` es la hora (0-23) a la que mirar el pronóstico: la de la totalidad."""
    return ('''<script>
(function(){
  var API=''' + repr(API) + ''', FECHA=''' + repr(event_date) + ''',
      HORA=''' + str(int(hour_local)) + ''', TZ=''' + repr(tz_name) + ''',
      UTILES=''' + str(int(USEFUL_DAYS)) + ''';
  var cache={};

  function clase(pct){ return pct<=25?'g':(pct<=60?'w':'b'); }

  // Cuántos días faltan. Un pronóstico a 40 días no existe: el modelo devuelve algo,
  // pero enseñarlo sería fabricar confianza.
  window.fcDiasVista=function(){
    return Math.round((Date.parse(FECHA+'T12:00:00Z')-Date.now())/86400000);
  };

  window.fcPide=function(puntos){
    var dias=window.fcDiasVista();
    if(dias>UTILES) return Promise.resolve(null);
    var lat=puntos.map(function(p){return p.lat.toFixed(4);}).join(','),
        lon=puntos.map(function(p){return p.lon.toFixed(4);}).join(',');
    var k=lat+'|'+lon;
    if(cache[k]) return Promise.resolve(cache[k]);
    var u=API+'?latitude='+lat+'&longitude='+lon+
      '&hourly=cloud_cover&start_date='+FECHA+'&end_date='+FECHA+
      '&timezone='+encodeURIComponent(TZ);
    return fetch(u).then(function(r){ if(!r.ok) throw 0; return r.json(); })
      .then(function(j){
        var lista=Array.isArray(j)?j:[j];
        var out=lista.map(function(L){
          var h=L.hourly, i=-1;
          for(var n=0;n<h.time.length;n++){
            if(parseInt(h.time[n].slice(11,13),10)===HORA){ i=n; break; }
          }
          return i<0?null:h.cloud_cover[i];
        });
        cache[k]=out; return out;
      }).catch(function(){ return undefined; });   // undefined = no se pudo, != null
  };

  window.fcHtml=function(pct){
    if(pct===null||pct===undefined) return '<span class="fc"><span class="v">—</span>'+
      '<span class="u">sin pronóstico</span></span>';
    return '<span class="fc '+clase(pct)+'"><span class="v">'+Math.round(pct)+
      '%</span><span class="u">nubes</span></span>';
  };
})();
</script>''')


def note_html():
    """La coletilla que evita que un pronóstico se lea como una promesa."""
    return (f'<p class="fcnote">La nubosidad es un <b>pronóstico</b> de '
            f'<a href="{SOURCE_URL}">{SOURCE_LABEL}</a> para la hora de la totalidad, '
            f'y cambia cada día: mírala otra vez la víspera. No es lo mismo que la '
            f'climatología de agosto que sale más abajo, que dice lo que <i>suele</i> '
            f'pasar. <span class="fcwarn">Ninguna de las dos es una garantía.</span></p>')
