# Wattprint

**¿Cuánto carbono, energía y agua consume tu IA?** Wattprint lo calcula en un minuto para un entrenamiento, un ajuste fino o un servicio de inferencia, también por petición. Sin registro y sin enviar datos a ningún servidor: todo se calcula en tu navegador. En español e inglés.

**Pruébala:** https://wattprint-kappa.vercel.app/ · [English version](https://wattprint-kappa.vercel.app/?lang=en)

![Resultados de Wattprint](docs/resultados.png)

## Qué hace

1. Eliges el tipo de carga, la GPU, cuántas unidades y cuántas horas, la región y el tipo de centro de datos. Si ya has medido el consumo (CodeCarbon, nvidia-smi, DCGM), puedes meter los kWh medidos en vez de estimarlos.
2. Por defecto estima de forma prudente (GPU al 100 % de su TDP más el resto del servidor) y puedes ajustar la utilización. Te da los kg de CO₂e, los kWh y los litros de agua, con un desglose visual de dónde sale cada cifra:
   - carbono de la electricidad y de la fabricación del hardware;
   - energía de los servidores y consumo extra del centro de datos (PUE);
   - agua de refrigeración y agua usada para generar la electricidad.
3. Si es un servicio de inferencia, calcula la huella **por petición** (la unidad funcional R de SCI). Si se repite, da la **vista anual**.
4. Todo cabe en una pantalla: a la izquierda la tarea, en el centro las tres cifras y un **mapa** con la misma tarea en cada red eléctrica (CO₂e, agua o energía, con detalle al pasar el cursor y clic para elegir la región), y a la derecha las formas de reducirla (región más limpia, gran nube, horas de red más limpia, optimización propia) con su efecto en las tres cifras, incluidos los efectos contrarios: pasar a una red con mucha hidráulica baja el carbono pero sube el agua. El mapa cubre unos 200 países: el carbono de todos sale de Ember y el agua de la central solo se colorea donde el WRI tiene dato propio. La metodología incluye la lista completa de referencias y, para cada región, la fuente de cada dato. Tiene modo claro y oscuro, y una guía de cinco pasos la primera vez. La energía no cambia de país a país; su pestaña compara tipos de centro de datos y de dónde salen los kWh. Un paso a paso explica de dónde sale cada cifra.
5. Exporta un **informe en PDF** (con las hipótesis y las fuentes, pensado para pasárselo a dirección o al área de sostenibilidad), los **datos en CSV**, una tarjeta para redes y un enlace con el resultado.

## Cómo calcula

Marco: basada en la especificación **Software Carbon Intensity (SCI)** de la Green Software Foundation, publicada como **ISO/IEC 21031:2024**: `SCI = ((E × I) + M) por R`. SCI define I como intensidad marginal; aquí se usa la media anual de la red. El agua se calcula aparte.

| Magnitud | Fórmula | Fuente de los datos |
|---|---|---|
| Energía (E) | `kWh = TDP × unidades × horas × (utilización + 0,41) ÷ 1000 × PUE`, o kWh medidos × PUE | Método de [Green Algorithms](https://arxiv.org/abs/2007.07610) (Lannelongue et al., 2021): utilización por defecto 100 % del TDP, ajustable ([Patel et al., ASPLOS 2024](https://homes.cs.washington.edu/~patelp1/papers/llmpower-asplos24.pdf): en inferencia la media es menor). Resto del servidor: 0,41 × TDP como consumo fijo (el nodo completo consumió 1,41 veces el TDP de sus GPU), medido en un nodo de 8 H100 SXM ([Latif et al., IEEE Access 2025](https://eta-publications.lbl.gov/sites/default/files/2026-07/single-node_power_demand_during_ai_training.pdf)). TDP de NVIDIA. PUE: media del sector 1,54 (Uptime Institute, 2025); grandes nubes 1,13 (Google 1,09 y Microsoft 1,17, 2025) |
| Carbono (I) | `kg CO₂e = kWh × intensidad de la red ÷ 1000` | Intensidad de ciclo de vida por país de [Ember](https://ember-energy.org/data/yearly-electricity-data/) (CC BY 4.0), vía [Our World in Data](https://github.com/owid/energy-data); estados de EE. UU. de [Ember US Electricity Data](https://ember-energy.org/data/us-electricity-data/). Método location-based |
| Fabricación (M) | ≈460 kg CO₂e por acelerador ÷ vida útil (4–6 años) | 150 kg de la GPU + parte de un servidor de 2.500 kg con 8 GPU ([Luccioni et al., JMLR 2023](https://jmlr.org/papers/v24/23-0069.html)); la parte de la GPU es coherente con el [PCF de NVIDIA HGX H100](https://images.nvidia.com/aem-dam/Solutions/documents/HGX-H100-PCF-Summary.pdf) (164 kg por GPU) y el total queda en la zona baja de [Schneider et al., 2025](https://arxiv.org/abs/2502.01671) (TPU de Google) |
| Agua de refrigeración | `litros = kWh de servidores × WUE` | Centro medio 0,36 L/kWh: media de los centros de EE. UU. en 2023 ([Shehabi et al., LBNL 2024](https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf)); grandes nubes 0,27 L/kWh ([Microsoft, año fiscal 2025](https://datacenters.microsoft.com/sustainability/efficiency/); AWS informa 0,12 de agua extraída en 2025 ([Amazon Sustainability](https://sustainability.aboutamazon.com/products-services/aws-cloud))) |
| Agua de generación eléctrica | `litros = kWh totales × factor de agua de la red` | [WRI, Reig et al. (2020)](https://www.wri.org/research/guidance-calculating-water-use-embedded-purchased-electricity), apéndice 2 (49 países) y apéndice 1 (subregiones eGRID de EE. UU.: SRVC para Virginia, NWPP para Oregón), en gal/kWh × 3,785 L/gal; los países sin factor propio usan la media mundial ponderada por generación de la tabla 4 (1,27 gal/kWh = 4,81 L/kWh) y se marcan como aproximados. Atribuyen a la electricidad toda la evaporación de los embalses; mismo marco que [Li et al., *Making AI Less "Thirsty"*](https://arxiv.org/abs/2304.03271) |

Opciones para reducirla: carbon-aware scheduling con la referencia de [Dodge et al., FAccT 2022](https://arxiv.org/abs/2206.05229) (medias de 16 regiones de Azure con intensidad marginal de 2020: −26,4 % hasta 1 h y −14,5 % hasta 6 h retrasando el inicio; −11 % en cargas más largas pausando y reanudando), que el usuario puede sustituir por su propio dato. Para otras optimizaciones (auto-scaling, cuantización) no hay un porcentaje general fiable, así que el usuario introduce su ahorro. Todos los supuestos de cada cálculo se muestran en los resultados y en el informe.

Equivalencias: coche de gasolina en la UE en uso real, 166 g CO₂/km ([JRC, 2025](https://publications.jrc.ec.europa.eu/repository/handle/JRC142808)); carga de móvil, 0,019 kWh (EPA); agua que usa en casa una persona en España, 128 L al día ([INE, 2022](https://www.ine.es/dyngs/Prensa/ESSA2022.htm)). Para entrenamientos, genera un texto de partida para la documentación técnica que la Ley de IA exige a los proveedores de modelos de propósito general (anexo XI, consumo energético conocido o estimado).

**Límites y referencias.** No existe ninguna norma que limite la huella de una carga de IA. Por eso la herramienta no da notas: compara la misma tarea entre regiones. Como referencia legal real se muestra el PUE frente a la ley de eficiencia energética de Alemania ([EnEfG § 11](https://www.gesetze-im-internet.de/enefg/__11.html), centros de 300 kW o más: ≤ 1,5 desde 2027 y ≤ 1,3 desde 2030 para los existentes, ≤ 1,2 para los nuevos; una reforma en tramitación subiría los dos primeros a 1,6 y 1,4). La Comisión Europea adoptó el 21 de septiembre de 2026 una [calificación A–G para centros de más de 500 kW](https://ec.europa.eu/commission/presscorner/api/files/document/print/en/ip_26_1667/IP_26_1667_EN.pdf), basada en PUE y WUE, con las primeras etiquetas previstas para 2027.

Son **estimaciones de orden de magnitud, no una medición certificada**. La metodología completa y la tabla de factores por región están dentro de la herramienta, en «Metodología».

## Datos siempre al día

La intensidad de carbono se actualiza sola. Los datos de Ember son anuales; una GitHub Action ([`update-data.yml`](.github/workflows/update-data.yml)) ejecuta [`scripts/update-data.mjs`](scripts/update-data.mjs) el día 2 de cada mes: descarga los últimos datos de Ember, comprueba que los valores son plausibles, actualiza `index.html` y guarda el cambio con la fecha. Si una fuente falla, se conservan los valores anteriores. También se puede lanzar a mano desde la pestaña *Actions*.

Los factores de agua de la electricidad (WRI, 2020) y los valores de PUE y WUE no tienen una publicación periódica en formato abierto; se revisan a mano cuando sale una edición nueva.

## Cómo usarla en local

Es un único archivo HTML sin dependencias ni proceso de compilación:

```bash
git clone https://github.com/KairlosGG/wattprint.git
cd wattprint
python3 -m http.server 8000   # o abre index.html directamente
```

Los datos (regiones, PUE, WUE, factores de agua, equivalencias) están en el objeto `DATA` de `index.html`, en un solo sitio, para que sea fácil revisarlos o actualizarlos. Los textos en los dos idiomas están en `I18N`.

## Licencias y créditos

- Código: [MIT](LICENSE) © 2026 Carlos Gallego Galán.
- Datos de intensidad de carbono: Ember, CC BY 4.0.
- Factores de agua de la electricidad: World Resources Institute (2020).
- Tipografías Space Grotesk, Inter y JetBrains Mono: SIL Open Font License 1.1.
- Proyecto independiente, sin relación con la Green Software Foundation, Ember, WRI ni los proveedores citados.

Hecha por [Carlos Gallego Galán](https://neocortech-kohl.vercel.app/). Escribo sobre gobernanza de IA en la newsletter [Neocortech](https://neocortech-kohl.vercel.app/newsletter).

---

## English

**How much carbon, energy and water does your AI use?** Wattprint estimates it in about a minute for a training run, a fine-tune or an inference service, per request too. No sign-up, nothing is sent to a server: everything runs in your browser.

- **Try it:** https://wattprint-kappa.vercel.app/?lang=en
- **Method:** based on Software Carbon Intensity (SCI, ISO/IEC 21031), using annual average rather than marginal grid intensity. Energy from GPU TDP and utilisation plus a fixed share for the rest of the server, or your measured kWh, times PUE. Carbon from Ember grid intensity (location-based) plus amortised embodied emissions. Water = cooling (WUE, LBNL 2024 / Microsoft 2025) + electricity generation (WRI country factors, as in Li et al.).
- **Outputs:** single-screen dashboard with a choropleth map of the same task on every grid, visual breakdowns, per-request (SCI functional unit) and annual views, reduction options with their effect on CO₂e, energy and water, PDF report, CSV data, share card and link.
- **Limits:** order-of-magnitude estimates, not certified measurement.
- **Run locally:** a single HTML file; serve the folder with any static server.
- **License:** MIT for the code; Ember data under CC BY 4.0; fonts under SIL OFL 1.1.
