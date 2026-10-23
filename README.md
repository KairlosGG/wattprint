# Wattprint

**¿Cuánto carbono, energía y agua consume tu IA?** Wattprint lo calcula en un minuto para un entrenamiento, un ajuste fino o un servicio de inferencia. Sin registro y sin enviar datos a ningún servidor: todo se calcula en tu navegador.

**Pruébala:** https://neocortech-kohl.vercel.app/tool/wattprint/

![Resultados de Wattprint](docs/resultados.png)

## Qué hace

1. Eliges el tipo de carga (entrenamiento, ajuste fino, inferencia), la GPU, cuántas unidades y cuántas horas, la región y el tipo de centro de datos.
2. Te da los kg de CO₂e, los kWh y los litros de agua, con equivalencias fáciles de entender (km en coche, cargas de móvil, duchas).
3. Te propone retos de optimización (región más limpia, cloud hyperscale, ajuste de capacidad, cuantización, planificación según la red) y recalcula al momento.
4. Puedes compartir el resultado con un enlace o descargarlo como imagen.

## Cómo calcula

| Magnitud | Fórmula | Fuente de los datos |
|---|---|---|
| Energía | `kWh = TDP (W) × unidades × horas × utilización ÷ 1000 × PUE` | TDP del fabricante (NVIDIA). PUE: media del sector 1,54 (Uptime Institute, 2025); hyperscale 1,12 |
| Carbono | `kg CO₂e = kWh × intensidad de la red ÷ 1000` + parte de fabricación del hardware | Intensidad por país de [Ember](https://ember-energy.org/) (CC BY 4.0). Fabricación: ≈300 kg CO₂e por acelerador amortizados en 6 años (Luccioni et al., 2022; Semiconductor Climate Consortium, 2025) |
| Agua | `litros = kWh de IT × WUE` | Media del sector ≈1,9 L/kWh (EESI, 2024); hyperscale 0,65 L/kWh (media de Google y Microsoft, 2024) |

El marco es la especificación SCI (ISO/IEC 21031) de la Green Software Foundation. Son **estimaciones de orden de magnitud, no una medición certificada**. La metodología completa está dentro de la herramienta, en «Metodología».

## Cómo usarla en local

Es un único archivo HTML sin dependencias ni proceso de compilación:

```bash
git clone https://github.com/KairlosGG/wattprint.git
cd wattprint
python3 -m http.server 8000   # o abre index.html directamente
```

Los datos (regiones, PUE, WUE, equivalencias) están en el objeto `DATA` de `index.html`, en un solo sitio, para que sea fácil revisarlos o actualizarlos. El formulario de newsletter se configura en el objeto `CONFIG`.

## Licencias y créditos

- Código: [MIT](LICENSE) © 2026 Carlos Gallego Galán.
- Datos de intensidad de carbono: Ember, CC BY 4.0.
- Tipografías Space Grotesk, Inter y JetBrains Mono: SIL Open Font License 1.1.
- Proyecto independiente, sin relación con la Green Software Foundation ni con los proveedores citados.

Hecha por [Carlos Gallego Galán](https://neocortech-kohl.vercel.app/). Si te interesa medir y reducir la huella de la IA, escribo sobre ello en la newsletter [Neocortech](https://neocortech-kohl.vercel.app/newsletter).

---

## English

**How much carbon, energy and water does your AI use?** Wattprint estimates it in about a minute for a training run, a fine-tune or an inference service. No sign-up, nothing is sent to a server: everything runs in your browser.

- **Try it:** https://neocortech-kohl.vercel.app/tool/wattprint/ (interface in Spanish).
- **Method:** energy from GPU TDP × units × hours × utilisation × PUE; carbon from Ember grid intensity plus amortised embodied emissions; water from IT energy × WUE. Based on the SCI specification (ISO/IEC 21031). Order-of-magnitude estimates, not certified measurement.
- **Run locally:** it is a single HTML file; serve the folder with any static server.
- **License:** MIT for the code; Ember data under CC BY 4.0; fonts under SIL OFL 1.1.
