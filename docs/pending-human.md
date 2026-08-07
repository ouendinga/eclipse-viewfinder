# Tareas que requieren acción humana — eclipse-viewfinder

Actualizado: 2026-08-06

## Decisiones pendientes

- [x] **Analítica: decidida y puesta.** Vercel Web Analytics (sin cookies, sin banner,
      50.000 eventos/mes). El `<script defer src="/_vercel/insights/script.js">` ya va en
      la página (`overview.py`). Descartadas: Google Analytics (cookies + banner + dudas
      legales por transferencias) y Cloudflare Web Analytics (su única ventaja es un
      límite que no se va a rozar).

- [x] **Web Analytics del eclipse: ACTIVA y contando** (6 visitantes, 7 páginas vistas
      al 2026-08-06). Hizo falta pulsar Enable en el panel **y** volver a desplegar: la
      ruta `/_vercel/insights/*` no se provisiona hasta el primer despliegue posterior.
      Y ojo al comprobarlo: el script de Vercel se apaga solo en navegadores
      automatizados (mira `navigator.webdriver`), así que con Playwright headless parece
      que no funciona. Hay que probarlo con navegador de verdad.

- [x] **Web Analytics del portfolio (alvarosolis.dev)**: activada, el endpoint responde
      200. Y sus 6 vulnerabilidades de dependencias, resueltas en otra conversación
      (`npm audit --omit=dev` da 0).

- [x] **Los 50.000 eventos/mes: la pregunta era irrelevante, medido el 2026-08-06.**
      No se puede resolver desde la API —el endpoint de uso agregado responde que es
      sólo para Pro/Enterprise— pero da igual, porque el consumo real está a tres
      órdenes de magnitud del tope:

      | proyecto | páginas vistas |
      |---|---:|
      | `eclipse-viewfinder` | 20 |
      | `alvarosolis` | 7 |
      | `kynex-web`, `kynex-construccion`, `folio-doctor` | analítica **no activada** |

      Aun suponiendo lo peor (cuota compartida de cuenta), 27 eventos contra 50.000
      dejan sitio para unas 1.800 veces el tráfico actual. Deja de ser una decisión.

- [ ] **Los otros tres proyectos NO tienen la analítica activa**, aunque en el listado
      de proyectos aparezca el registro `webAnalytics`. La API responde
      `web_analytics_not_enabled`. Es el mismo tropiezo de siempre: hace falta pulsar
      Enable en el panel **y volver a desplegar**. Si se quiere medirlos, hay que
      redesplegarlos; si no, no hay nada que hacer.

- [ ] **¿Registrar las localidades buscadas?** Requiere Vercel Pro (20 $/mes) o el truco
      de leer la query string (`?n=Malgrat+de+Mar`), que está **sin verificar**. Además
      implica que nombres de pueblo acaben en la analítica: es una decisión, no un
      detalle técnico.

## Credenciales

- [ ] **Permiso `Web Analytics` en el token de Cloudflare**, si algún día se quiere esa
      opción. El token de `services.md` es correcto (lee y escribe DNS, ve la cuenta
      `3450cb7a…`), pero el endpoint RUM devuelve **403 código 10000**.
      Se añade en `+ Add policy` eligiendo **la cuenta**, no «All Domains» — Web
      Analytics es permiso de cuenta, por eso buscando «web» en el selector de dominios
      solo sale «Web3 Hostnames».
      **No hace falta** si se va con Vercel.

## Hecho, no repetir

- [x] Registro `A eclipse 76.76.21.21` con proxy desactivado (2026-08-05).
- [x] Token de Cloudflare renovado: **funciona** para DNS (probado creando y borrando un
      TXT temporal).
- [x] Certificado TLS: **no salió solo**, hubo que forzarlo con `POST /v3/certs`.
      Recordarlo si se añade otro subdominio.

## Comprobaciones que solo puede hacer una persona

- [ ] **Ir a un punto candidato el 10 de agosto a las 20:30.** El Sol estará casi en el
      mismo sitio. Es lo único que valida lo que ningún modelo puede: el pino, la nave,
      el poste y si de verdad se llega.
