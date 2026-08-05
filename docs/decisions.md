# Decisiones y por qué

Fechadas. Lo marcado ✅ está verificado con evidencia; lo demás es criterio.

## 2026-08-05 — Los puntos se precalculan; la búsqueda es un filtro
La respuesta a «¿dónde voy desde X?» no depende de X: es siempre el mismo conjunto de
buenos miradores, y X y el radio solo deciden cuáles caen cerca. Por eso el dataset se
calcula una vez (`recommend.py`) y el buscador filtra en el navegador. Sin backend,
respuesta instantánea, y encaja con que una consulta en vivo necesita ~700 MB de
elevación y decenas de segundos de CPU, que ningún serverless da.
**Radio máximo 100 km**: más lejos deja de ser una recomendación para ser un listado.

## 2026-08-05 — Selección por celdas, no por ranking global ✅
Ordenar globalmente parecía sensato y era falso: la totalidad gana siempre, el cupo
entero caía dentro de la franja y un pueblo fuera de ella recibía **cero** resultados.
Se elige el mejor punto **por celda** (14 km en totalidad, 25 km en parcial) y el
recorte es **por categoría**, nunca global.
Verificado: Malgrat 21 miradores en 100 km, Barcelona 37, Menorca 4, Sevilla 0 (correcto).

## 2026-08-05 — Árboles y edificios desde OSM ✅
El IGN dice en su visualizador que ignora «edificaciones y arbolado» y usa relieve
GMTED2010 a ~300 m. Aquí el relieve va a 30 m y encima se consulta a OpenStreetMap qué
hay plantado en la línea de visión.
Verificado: de 1067 puntos comprobados, 136 tienen algo delante (mediana +2,87°) y
**109 dejaron de ser recomendables** — no empeoraban, es que el barrido elige la mejor
celda de *terreno* y el terreno no sabe que encima hay un pueblo (Cornellà: +2,23° →
−32° por un bloque de 30 m a 44 m).

## 2026-08-05 — Un dato que falta nunca se disfraza de dato bueno
Los puntos sin comprobar conservan el margen del terreno y se marcan **«sin
comprobar»**, jamás «limpio». Mismo criterio en el informe general: si falta el barrido
de la franja, `overview.build()` **lanza error** en vez de renderizar rayas, que se leen
como decisión de diseño y no como dato ausente.

## 2026-08-05 — Street View solo si hay carretera asfaltada a <60 m ✅
Un enlace publicado abría una pantalla negra: el punto estaba en pleno campo. Street
View se graba desde la vía, así que sin vía no hay foto.
Verificado: en 41,28/1,68 lo más cercano es un sendero a 66 m → sin enlace.

## 2026-08-05 — La ficha recomienda un PUNTO, no un pueblo
El municipio iba en el titular y las coordenadas en pequeño, así que se leía como «ve a
ese pueblo» — y el centro del pueblo es justo donde el horizonte suele estar tapado.
Ahora el titular son las coordenadas, el municipio es contexto y hay «Cómo llegar» a la
coordenada exacta.

## 2026-08-05 — Riesgo de borde visible, sin cambiar el orden
La totalidad sigue primero porque es categóricamente otra cosa. Pero por debajo de 30 s
se marca **«AL BORDE · RIESGO ALTO»** con tooltip: sesgo de ±3 s, no se modela el limbo
lunar, podrían ser 0 s; para un cazador de eclipses compensa, para un plan en familia
suele ser mejor un parcial casi seguro.

## 2026-08-05 — Analítica: Vercel, no Google ni Cloudflare
Google Analytics pone cookies → banner de consentimiento en la UE sobre una web
informativa, y su legalidad está cuestionada por transferencias a EE.UU.
Cloudflare Web Analytics es ilimitada, pero su única ventaja aplicable es un límite que
no se va a rozar (Vercel Hobby da **50.000 eventos/mes**, verificado en su
documentación) y sus datos de borde requieren proxy, que aquí va en gris.
**Ninguna de las dos da «qué localidades se buscaron» gratis**: Vercel lo tiene solo en
Pro (20 $/mes) y Cloudflare no lo tiene.
