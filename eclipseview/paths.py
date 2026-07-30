"""Where the data lives.

Everything derived (DEM tiles, mosaic, eclipse field, reports) goes under a single
data directory so the repository itself stays small and reproducible. Override with
the EV_DATA environment variable.
"""
import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(PKG_DIR)

DATA_DIR = os.environ.get('EV_DATA') or os.path.join(REPO_DIR, 'data')
DEM_DIR = os.path.join(DATA_DIR, 'dem')
REPORTS_DIR = os.environ.get('EV_REPORTS') or os.path.join(REPO_DIR, 'reports')

MOSAIC_NPY = os.path.join(DATA_DIR, 'mosaic.npy')
MOSAIC_JSON = os.path.join(DATA_DIR, 'mosaic.json')
FIELD_PKL = os.path.join(DATA_DIR, 'field.pkl')
LIMITS_JSON = os.path.join(DATA_DIR, 'limits.json')
MAP_SVG = os.path.join(DATA_DIR, 'map.svg')
SCAN_PKL = os.path.join(DATA_DIR, 'scan.pkl')
ZONES_JSON = os.path.join(DATA_DIR, 'zones.json')

# Skyfield keeps the JPL ephemeris here
EPHEM_DIR = DATA_DIR


def ensure():
    for d in (DATA_DIR, DEM_DIR, REPORTS_DIR):
        os.makedirs(d, exist_ok=True)


def missing():
    """Which prerequisites are absent, so the CLI can tell the user what to run."""
    out = []
    if not os.path.isdir(DEM_DIR) or not os.listdir(DEM_DIR):
        out.append('teselas DEM')
    if not os.path.exists(MOSAIC_NPY):
        out.append('mosaico (mosaic.npy)')
    if not os.path.exists(FIELD_PKL):
        out.append('campo del eclipse (field.pkl)')
    return out
