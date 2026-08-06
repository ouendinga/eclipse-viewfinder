# -*- coding: utf-8 -*-
"""Los eventos de eclipse.

El motor está escrito contra un Event y nunca contra una fecha metida a fuego, así que
añadir otro eclipse es una entrada de configuración y no una reescritura. Hoy sólo hay
uno cableado de punta a punta; el resto de la cadena ya recibe `event` como parámetro.

`search_start_utc` / `search_end_utc` acotan la búsqueda de circunstancias locales.
Tienen que contener el eclipse en toda la región que se quiera servir, y ser lo
bastante estrechos como para que el barrido grueso salga barato. Para un eclipse dado,
la hora del máximo ±90 min cubre la franja entera.
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
    # Región que cubren los datos precalculados: (lat_s, lat_n, lon_w, lon_e)
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

# Declarados pero SIN cablear de punta a punta: no se publica campo precalculado ni
# DEM para estos. Están aquí para que se vea la forma que tiene «añadir un eclipse».
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
READY = {'tse2026'}          # eventos con datos precalculados en este repo
DEFAULT = TSE_2026


def get(key=None):
    if key is None:
        return DEFAULT
    if key not in EVENTS:
        raise KeyError(f'Evento desconocido: {key}. Disponibles: {sorted(EVENTS)}')
    return EVENTS[key]


def is_ready(key):
    return key in READY
