# -*- coding: utf-8 -*-
"""Eclipse events.

The engine is written against an Event, never against a hard-coded date, so adding
another eclipse is a config entry rather than a rewrite. Today only one event is
wired up end to end; the rest of the pipeline already takes `event` as a parameter.

`search_start_utc` / `search_end_utc` bracket the local circumstances hunt. They must
contain the eclipse everywhere in the region you intend to serve, and be tight enough
that the coarse scan is cheap. For a given eclipse, greatest-eclipse time +/- 90 min
covers the whole path.
"""
from dataclasses import dataclass, field as _field


@dataclass(frozen=True)
class Event:
    key: str
    date: tuple                 # (year, month, day) in UTC
    label: str
    kind: str                   # 'total' | 'annular' | 'partial' | 'hybrid'
    search_start_utc: tuple     # (h, m) UTC
    search_end_utc: tuple
    tz_offset_h: float          # local clock offset used in reports
    tz_label: str
    # Region this event's precomputed data covers: (lat_s, lat_n, lon_w, lon_e)
    region: tuple
    notes: str = ''
    extra: dict = _field(default_factory=dict)

    @property
    def iso_date(self):
        return '%04d-%02d-%02d' % self.date


TSE_2026 = Event(
    key='tse2026',
    date=(2026, 8, 12),
    label='Eclipse total de Sol del 12 de agosto de 2026',
    kind='total',
    search_start_utc=(17, 30),
    search_end_utc=(19, 30),
    tz_offset_h=2, tz_label='CEST (hora peninsular)',
    region=(38.0, 45.0, -10.0, 4.5),
    notes='Franja de totalidad sobre el norte de España, con el Sol muy bajo.',
)

# Declared but NOT yet wired end to end: no precomputed field or DEM ships for these.
# Kept here so the shape of "add an eclipse" is obvious.
TSE_2027 = Event(
    key='tse2027', date=(2027, 8, 2),
    label='Eclipse total de Sol del 2 de agosto de 2027',
    kind='total', search_start_utc=(7, 30), search_end_utc=(12, 0),
    tz_offset_h=2, tz_label='CEST',
    region=(27.0, 42.0, -12.0, 40.0),
    notes='Andalucía, Ceuta y norte de África, por la mañana y con el Sol alto.',
)

ASE_2028 = Event(
    key='ase2028', date=(2028, 1, 26),
    label='Eclipse anular de Sol del 26 de enero de 2028',
    kind='annular', search_start_utc=(14, 0), search_end_utc=(17, 30),
    tz_offset_h=1, tz_label='CET',
    region=(35.0, 44.0, -10.0, 5.0),
    notes='Anular sobre la península, de suroeste a noreste.',
)

EVENTS = {e.key: e for e in (TSE_2026, TSE_2027, ASE_2028)}
READY = {'tse2026'}          # events with precomputed data in this repo
DEFAULT = TSE_2026


def get(key=None):
    if key is None:
        return DEFAULT
    if key not in EVENTS:
        raise KeyError(f'Evento desconocido: {key}. Disponibles: {sorted(EVENTS)}')
    return EVENTS[key]


def is_ready(key):
    return key in READY
