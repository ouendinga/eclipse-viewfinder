# -*- coding: utf-8 -*-
"""Progreso por fases, para que quien llame pueda enseñar una espera que sea verdad.

La gracia es que el porcentaje signifique algo. El peso de cada fase sale del trabajo
que de verdad está encolado —cuántas teselas hay que bajar, cuántos sitios se van a
recomprobar a 30 m— y no de un guion fijo. Una consulta que no necesita elevación
nueva se salta esa fase entera y lo dice, en vez de animar una barra falsa.

Con `stream` puesto emite JSON por líneas, que es lo que un endpoint HTTP o un
indicador de la consola pueden consumir directamente.
"""
import json
import os
import sys
import time

from .paths import DATA_DIR

# Medido en un portátil de 16 núcleos; sólo sirve para convertir trabajo encolado en
# pesos, nunca
# presented as a promise.
COST = {
    'resolve': 1.5,          # gazetteer lookup (throttled to 1 req/s)
    'coverage': 0.5,
    'download_per_tile': 6.0,
    'mosaic': 25.0,
    'field': 0.0,            # precomputed for ready events
    'scan': 35.0,            # coarse ranking pass
    'refine_per_site': 2.5,  # 30 m re-check
    'label_per_site': 1.2,   # reverse geocode (throttled)
    'render': 1.0,
}


class Job:
    """Una unidad de trabajo con fases pesadas y progreso honrado."""

    def __init__(self, name, plan, on_event=None, stream=None, state_path=None):
        """`plan` maps stage key -> weight (seconds of expected work)."""
        self.name = name
        self.plan = dict(plan)
        self.total = sum(self.plan.values()) or 1.0
        self.done = 0.0
        self.current = None
        self.started = time.time()
        self.on_event = on_event
        self.stream = stream
        self.state_path = state_path or os.path.join(DATA_DIR, f'job_{name}.json')
        self.log = []
        self._stage_started = None
        self._credited = 0.0

    # ---------------------------------------------------------------- emitting
    def _emit(self, kind, **kw):
        ev = dict(job=self.name, kind=kind, stage=self.current,
                  progress=round(min(self.done / self.total, 1.0), 4),
                  elapsed=round(time.time() - self.started, 2), **kw)
        self.log.append(ev)
        if self.on_event:
            self.on_event(ev)
        if self.stream:
            self.stream.write(json.dumps(ev, ensure_ascii=False) + '\n')
            self.stream.flush()
        try:
            with open(self.state_path, 'w') as f:
                json.dump(dict(current=ev, log=self.log[-40:]), f,
                          ensure_ascii=False)
        except OSError:
            pass
        return ev

    def eta(self):
        """Segundos que quedan.

        El peso de las fases ya está calibrado en segundos, así que el peso restante ES una
        primera estimación, disponible desde el principio. Un dato de rendimiento no sirve
        hasta que se ha hecho una parte decente del trabajo. Pasado el 20 % se reescala con
        lo que esta máquina está consiguiendo de verdad.
        """
        remaining = max(0.0, self.total - self.done)
        if self.done > 0.2 * self.total:
            el = time.time() - self.started
            speed = self.done / el if el > 0 else 0
            if speed > 0:
                return remaining / speed
        return remaining

    # ---------------------------------------------------------------- stages
    def stage(self, key, message):
        """Empieza una fase. Cerrar la anterior le abona su peso entero."""
        if self.current is not None:
            self.done += self.plan.get(self.current, 0.0) - self._credited
        self.current = key
        self._credited = 0.0
        self._stage_started = time.time()
        return self._emit('stage', message=message, eta=self.eta())

    def step(self, done, total, message=None):
        """Progreso parcial dentro de la fase actual."""
        w = self.plan.get(self.current, 0.0)
        want = w * (done / total if total else 1.0)
        self.done += want - self._credited
        self._credited = want
        return self._emit('step', message=message, done=done, total=total,
                          eta=self.eta())

    def info(self, message, **kw):
        return self._emit('info', message=message, **kw)

    def finish(self, **kw):
        if self.current is not None:
            self.done += self.plan.get(self.current, 0.0) - self._credited
        self.current = None
        self.done = self.total
        return self._emit('done', **kw)

    def fail(self, message):
        return self._emit('error', message=message)


def plan_for_place(missing_tiles, n_sites, needs_mosaic):
    """Pesos de una consulta «mejores miradores cerca de X», sacados del trabajo encolado."""
    plan = {'resolve': COST['resolve'], 'coverage': COST['coverage']}
    if missing_tiles:
        plan['download'] = COST['download_per_tile'] * missing_tiles
    if needs_mosaic:
        plan['mosaic'] = COST['mosaic']
    plan['scan'] = COST['scan']
    plan['refine'] = COST['refine_per_site'] * max(n_sites, 1)
    plan['label'] = COST['label_per_site'] * max(n_sites, 1)
    plan['render'] = COST['render']
    return plan


def cli_reporter(verbose=True):
    """Un callback que pinta en stderr una barra de progreso de una línea."""
    def report(ev):
        if not verbose:
            return
        pct = int(ev['progress'] * 100)
        bar = '#' * (pct // 4) + '.' * (25 - pct // 4)
        eta = ev.get('eta')
        tail = f" ~{int(eta)}s" if eta else ''
        msg = ev.get('message') or ev.get('stage') or ''
        if ev['kind'] in ('step',) and ev.get('total'):
            msg = f"{msg or ev['stage']} {ev['done']}/{ev['total']}"
        sys.stderr.write(f'\r[{bar}] {pct:3d}%{tail}  {msg[:58]:58s}')
        sys.stderr.flush()
        if ev['kind'] in ('done', 'error'):
            sys.stderr.write('\n')
    return report
