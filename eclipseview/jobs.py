# -*- coding: utf-8 -*-
"""Staged progress reporting, so a caller can show a loading state that is true.

The point is that the percentage means something. Stage weights are derived from the
work actually queued -- how many tiles must be downloaded, how many sites will be
re-checked at 30 m -- rather than from a fixed script. A request that needs no new
elevation data skips that stage entirely and says so, instead of animating a fake bar.

Emits newline-delimited JSON when `stream` is set, which is what an HTTP endpoint or
a CLI spinner can consume directly.
"""
import json
import os
import sys
import time

from .paths import DATA_DIR

# Measured on a 16-core laptop; used only to turn queued work into weights, never
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
    """A unit of work with weighted stages and honest progress."""

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
        """Seconds remaining.

        Stage weights are already calibrated in seconds, so the remaining weight IS a
        first estimate -- available immediately, unlike a throughput figure, which is
        meaningless until a decent share of the work is done. Once past 20 % we
        rescale by what this machine is actually achieving.
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
        """Begin a stage. Closing the previous one credits its full weight."""
        if self.current is not None:
            self.done += self.plan.get(self.current, 0.0) - self._credited
        self.current = key
        self._credited = 0.0
        self._stage_started = time.time()
        return self._emit('stage', message=message, eta=self.eta())

    def step(self, done, total, message=None):
        """Partial progress inside the current stage."""
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
    """Weights for a "best viewpoints near X" request, from the queued work."""
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
    """A callback that prints a readable one-line progress bar to stderr."""
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
