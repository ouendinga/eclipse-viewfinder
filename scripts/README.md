# scripts

Tareas largas que no caben en el CLI porque tardan horas o dependen de servicios de
fuera. Se ejecutan desde la raíz del repo (`scripts/loquesea.sh`) y todas dan por
hecho que existe `.venv`.

| script | qué hace |
|---|---|
| `night.sh` | Completa de madrugada lo que falta de OpenStreetMap, a una consulta por minuto. Sale solo si no queda nada pendiente. |
| `access.sh` | Añade a cada punto el perfil de acceso: vía más cercana, firme, si hace falta 4x4. |
| `enrich.sh` | Añade árboles y edificios sobre los puntos ya calculados. |
| `limbrun.sh` | Recalcula la totalidad de cada punto con el perfil real del limbo lunar. |
| `recompute.sh` | Rehace la geometría conservando el trabajo de OSM, que son horas. |
| `ogcard.sh` | Genera la tarjeta social de 1200×630. Necesita `PW=` apuntando a Playwright. |
| `redeploy.sh` | Reconstruye el sitio y lo sube. |
| `deploy.sh` | Despliegue completo, incluido asociar el subdominio. |
| `finish.sh`, `finalize.sh` | Encadenan «espera a que acabe lo anterior → reconstruye → despliega». |

## Credenciales

Ninguna vive en el repo. El despliegue las lee del entorno y aborta si faltan:

```bash
export VERCEL_TOKEN=… VERCEL_TEAM=…
scripts/deploy.sh
```

## Dos avisos que costaron caro

- **Overpass limita por coste de consulta, no por número.** Con menos de cien
  peticiones pesadas ya devuelve 429 y «Connection refused». Por eso `night.sh` va
  despacio y aborta en vez de fabricar resultados vacíos.
- **Nunca esperes con `pgrep -f`/`pkill -f` sobre un patrón que aparece en tu propia
  línea de comandos**: el vigilante se encuentra a sí mismo. Se espera sobre una
  marca en el log.
