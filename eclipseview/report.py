# -*- coding: utf-8 -*-
"""HTML reports. Every figure shown is computed at render time.

There is deliberately no number typed into the prose: the templates take values from
the evaluated sites, from `verify.run_all()` and from `sources`, so the text and the
tables cannot drift apart. External statistics (cloud climatology) are rendered with
their attribution attached, never inline as if they were ours.
"""
import html

from . import i18n, sources
from .analysis import km
from .style import CSS

SUN_DIAMETER_DEG = 0.53


def esc(s):
    return html.escape(str(s), quote=True)


def _num(k, v, cls=''):
    return (f'<div class="num {cls}"><div class="k">{k}</div>'
            f'<div class="v">{v}</div></div>')


def _margin_class(clear, min_clear=1.5):
    return 'ok' if clear >= max(min_clear, 2.0) else ('no' if clear < min_clear
                                                      else 'w')


def _td_class(clear):
    return 'g' if clear >= 2 else ('w' if clear >= 0 else 'b')


# --------------------------------------------------------------------- notes

def site_note(row, lang, min_clear=1.5):
    """Explain the verdict in words, from this row's own numbers."""
    d = lambda v, s=False: i18n.deg(lang, v, 2, s)          # noqa: E731
    if row['clear'] < 0:
        note = i18n.t(lang, 'note_blocked',
                      set_time=(row.get('set_local') or '—')[:5],
                      max_time=row['max_local'][:5],
                      horizon=d(row['horizon'], True), alt=d(row['alt']))
    elif row['clear'] < 2.0:
        note = i18n.t(lang, 'note_tight', margin=d(row['clear'], True),
                      times=row['clear'] / SUN_DIAMETER_DEG,
                      blocker=f"{i18n.number(lang, row['blocker_km'], 1)} km")
    else:
        note = i18n.t(lang, 'note_ok', margin=d(row['clear'], True),
                      times=row['clear'] / SUN_DIAMETER_DEG,
                      blocker=f"{i18n.number(lang, row['blocker_km'], 1)} km",
                      horizon=d(row['horizon'], True))
    if row['total']:
        dur = f"{i18n.number(lang, row['dur'], 0)} s"
        note += i18n.t(lang, 'note_total' if row['dur'] >= 45 else 'note_total_edge',
                       dur=dur)
    else:
        note += i18n.t(lang, 'note_partial',
                       obsc=f"{i18n.number(lang, row['obsc'], 2)}%")
    return note


# --------------------------------------------------------------- place report

def render_place(origin, radius_km, rows, min_clear, lang='es', event=None,
                 verification=None):
    """Report for "the best viewpoints within R km of X"."""
    from . import events
    ev = event or events.DEFAULT
    tz = ev.tz_label
    place = origin['label']
    dd = lambda v, s=True: i18n.deg(lang, v, 2, s)          # noqa: E731

    if not rows:
        body = (f'<section><div class="note warn">'
                f'{i18n.t(lang, "no_results", radius=radius_km, min_clear=dd(min_clear))}'
                f'</div></section>')
        return _shell(i18n.t(lang, 'report_title', place=esc(place)),
                      _header(lang, ev, place, radius_km, min_clear) + body, lang, ev,
                      verification)

    trs = []
    for r in rows:
        label = esc(r.get('label') or r.get('place') or '—')
        trs.append(
            f'<tr><td>{label}</td>'
            f'<td>{i18n.number(lang, r["lat"], 4)}, {i18n.number(lang, r["lon"], 4)}</td>'
            f'<td>{r["elev"]}</td>'
            f'<td>{i18n.number(lang, r["dist"], 1)}</td>'
            f'<td>{i18n.number(lang, r["obsc"], 2)}%</td>'
            f'<td>{"—" if not r["total"] else i18n.number(lang, r["dur"], 0) + " s"}</td>'
            f'<td>{i18n.deg(lang, r["alt"], 2)}</td>'
            f'<td>{dd(r["horizon"])}</td>'
            f'<td class="{_td_class(r["clear"])}">{dd(r["clear"])}</td></tr>')

    cards = []
    for r in rows:
        badge = (i18n.t(lang, 'badge_total') if r['total']
                 else i18n.t(lang, 'badge_partial',
                             pct=f'{i18n.number(lang, r["obsc"], 1)}%'))
        bcls = 'g' if r['total'] else ('w' if r['clear'] >= 2 else 'b')
        head = esc(r.get('label') or r.get('place') or
                   f'{r["lat"]:.4f}, {r["lon"]:.4f}')
        nums = [
            _num(i18n.t(lang, 'n_coords'),
                 f'{i18n.number(lang, r["lat"], 4)}, {i18n.number(lang, r["lon"], 4)}'),
            _num(i18n.t(lang, 'n_elev'), f'{r["elev"]} m'),
            _num(i18n.t(lang, 'n_dist'), f'{i18n.number(lang, r["dist"], 1)} km'),
            _num(i18n.t(lang, 'n_obsc'), f'{i18n.number(lang, r["obsc"], 1)}%', 'hi'),
        ]
        if r['total']:
            nums.append(_num(i18n.t(lang, 'n_dur'),
                             f'{i18n.number(lang, r["dur"], 0)} s', 'hi'))
        nums += [
            _num(i18n.t(lang, 'n_alt'), i18n.deg(lang, r['alt'], 2)),
            _num(i18n.t(lang, 'n_az'), i18n.deg(lang, r['az'], 1)),
            _num(i18n.t(lang, 'n_horizon'), dd(r['horizon'])),
            _num(i18n.t(lang, 'n_margin'), dd(r['clear']),
                 _margin_class(r['clear'], min_clear)),
            _num(i18n.t(lang, 'n_max', tz=tz.split()[0]), r['max_local'][:5]),
            _num(i18n.t(lang, 'n_blocker'),
                 f'{i18n.number(lang, r["blocker_km"], 1)} km'),
        ]
        cards.append(f'''
<article class="site{' bad' if r['clear'] < 0 else ''}">
  <div class="site-h">
    <h3>{head}</h3>
    <span class="place">{esc(r.get('place') or '')}</span>
    <span class="badge {bcls}">{badge}</span>
  </div>
  <div class="nums">{''.join(nums)}</div>
  <div class="panowrap">{r['svg']}</div>
  <div class="why">{site_note(r, lang, min_clear)}</div>
</article>''')

    how = (f'<section><h2>{i18n.t(lang, "how_title")}</h2><ul class="prose">'
           f'<li>{i18n.t(lang, "how_1")}</li><li>{i18n.t(lang, "how_2")}</li>'
           f'<li>{i18n.t(lang, "how_3")}</li>'
           f'<li>{i18n.t(lang, "how_4", min_clear=dd(min_clear))}</li></ul></section>')

    body = _header(lang, ev, place, radius_km, min_clear) + f'''
<section>
  <h2>{i18n.t(lang, 'summary')}</h2>
  <div class="tablewrap"><table><thead><tr>
    <th>{i18n.t(lang, 'col_site')}</th><th>{i18n.t(lang, 'col_coords')}</th>
    <th>{i18n.t(lang, 'col_elev')}</th><th>{i18n.t(lang, 'col_dist')}</th>
    <th>{i18n.t(lang, 'col_obsc')}</th><th>{i18n.t(lang, 'col_dur')}</th>
    <th>{i18n.t(lang, 'col_alt')}</th><th>{i18n.t(lang, 'col_horizon')}</th>
    <th>{i18n.t(lang, 'col_margin')}</th>
  </tr></thead><tbody>{''.join(trs)}</tbody></table></div>
  <p class="caption">{i18n.t(lang, 'origin_note', place=esc(place),
                             lat=origin['lat'], lon=origin['lon'],
                             gazetteer=sources.cite('osm'))}</p>
</section>
{how}
<section>{''.join(cards)}</section>'''
    return _shell(i18n.t(lang, 'report_title', place=esc(place)), body, lang, ev,
                  verification)


def _header(lang, ev, place, radius_km, min_clear):
    return f'''
<header class="top">
  <p class="eyebrow">{i18n.t(lang, 'eyebrow', event=esc(ev.label))}</p>
  <h1>{i18n.t(lang, 'h1', radius=radius_km, place=esc(place))}</h1>
  <p class="lede">{i18n.t(lang, 'lede',
                          min_clear=i18n.deg(lang, min_clear, 1, True))}</p>
</header>'''


def _shell(title, body, lang, ev, verification=None):
    ver = ''
    if verification:
        s = verification
        ver = ('<br>' + i18n.t(lang, 'verified', passed=s['passed'],
                               total=s['total']))
    foot = i18n.t(lang, 'footer', de421=sources.cite('de421'),
                  srtm=sources.cite('srtm'), osm=sources.cite('osm'),
                  tz=esc(ev.tz_label))
    return f'''<title>{title}</title>
<style>{CSS}</style>
<div class="wrap">
{body}
<footer><p>{foot}{ver}</p></footer>
</div>'''
