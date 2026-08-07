# -*- coding: utf-8 -*-
"""Cuenta atrás hasta la primera totalidad en España.

El instante NO está escrito a mano: sale del dataset (el `t2` más temprano de todos los
puntos con totalidad), igual que el resto de cifras de la página. Si se recalculan los
puntos y el minuto cambia, la cuenta atrás cambia sola.

Cuenta en tiempo del usuario, no del servidor: se construye un instante UTC y el
navegador hace la resta. Así vale igual desde Canarias que desde Berlín, que es donde
una cuenta atrás escrita en hora peninsular engañaría.
"""

import datetime

from . import events


def _utc_iso(ev, hora_local):
    """Hora local del evento -> instante UTC en ISO, para el navegador.

    Acepta 'HH:MM' y 'HH:MM:SS'. Los contactos del dataset llevan segundos desde que
    una totalidad de 58 s llegó a mostrarse como «de 20:28 a 20:28»; desempaquetar dos
    trozos a ciegas hacía que la cuenta atrás reventara con el formato nuevo.
    """
    partes = [int(x) for x in hora_local.split(':')]
    h, m = partes[0], partes[1]
    s = partes[2] if len(partes) > 2 else 0
    # Restar el huso puede cruzar la medianoche en los dos sentidos, y entonces cambia
    # el DÍA. Antes se ajustaba la hora y se dejaba la fecha del evento, que para este
    # eclipse da igual (es de tarde) pero le pondría al siguiente una cuenta atrás con
    # 24 h de error sin avisar.
    base = datetime.datetime.fromisoformat(ev.iso_date).replace(
        hour=h, minute=m, second=s, tzinfo=datetime.timezone.utc)
    utc = base - datetime.timedelta(hours=ev.tz_offset_h)
    return utc.strftime('%Y-%m-%dT%H:%M:%SZ')


CSS = """
/* Sólo borde ARRIBA: va dentro de header.top, que ya cierra con el suyo, y con los dos
   salían dos rayas seguidas. */
.cdown{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 18px;
  border-top:1px solid var(--line);padding:14px 0 0;margin:22px 0 0}
.cdown .lab{font:600 10px var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--dim)}
.cdown .clock{display:flex;gap:14px;align-items:baseline}
.cdown .u{display:flex;align-items:baseline;gap:4px}
.cdown .n{font:700 clamp(22px,3.4vw,34px)/1 var(--mono);color:var(--sun);
  font-variant-numeric:tabular-nums}
.cdown .s{font:600 10px var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted)}
.cdown .when{font-size:13px;color:var(--muted)}
.cdown.done .n{color:var(--corona)}
"""


def html(first_totality_hhmm, ev=None):
    ev = ev or events.DEFAULT
    iso = _utc_iso(ev, first_totality_hhmm)
    return f'''<div class="cdown" id="cdown" data-utc="{iso}" hidden>
  <span class="lab">Falta para la totalidad</span>
  <span class="clock" id="cdclock"></span>
  <span class="when">primera totalidad en España, {first_totality_hhmm}
  {ev.tz_label}, {ev.iso_date}</span>
</div>'''


def script():
    return """<script>
(function(){
  var el=document.getElementById('cdown'), clock=document.getElementById('cdclock');
  if(!el||!clock) return;
  var t=Date.parse(el.dataset.utc);
  if(isNaN(t)) return;
  el.hidden=false;

  function pinta(){
    var d=t-Date.now();
    if(d<=0){
      el.classList.add('done');
      // Durante y después: la cuenta atrás dejaría de significar nada, y un 00:00:00
      // congelado parece que la página está rota.
      clock.innerHTML='<span class="u"><span class="n">Hoy</span></span>';
      el.querySelector('.lab').textContent='El eclipse ya ha empezado';
      return true;
    }
    var s=Math.floor(d/1000), dias=Math.floor(s/86400), h=Math.floor(s%86400/3600),
        m=Math.floor(s%3600/60), seg=s%60;
    function u(n,txt){ return '<span class="u"><span class="n">'+n+
      '</span><span class="s">'+txt+'</span></span>'; }
    clock.innerHTML=u(dias,dias===1?'día':'días')+u(h,'h')+
      u(('0'+m).slice(-2),'min')+u(('0'+seg).slice(-2),'s');
    return false;
  }
  if(!pinta()) var id=setInterval(function(){ if(pinta()) clearInterval(id); },1000);
})();
</script>"""
