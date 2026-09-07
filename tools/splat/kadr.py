"""Wycina z ortofoto sam prostokat lezanki - to jest tekstura do modelu.

Ortofoto obejmuje 2,192 x 1,809 m, czyli narzute razem z kawalkiem podlogi
i ramy. Do modelu potrzebny jest sam blat 1,987 x 1,578 m, wyciety
symetrycznie ze srodka, zeby piksele nadal odpowiadaly metrom.
"""

import json
import sys

from PIL import Image

PX_NA_M = 250
CEL_M = (1.987, 1.578)

obraz = Image.open(sys.argv[1])
szer, wys = obraz.size
cel_px = (round(CEL_M[0] * PX_NA_M), round(CEL_M[1] * PX_NA_M))
lewo = (szer - cel_px[0]) // 2
gora = (wys - cel_px[1]) // 2
wycinek = obraz.crop((lewo, gora, lewo + cel_px[0], gora + cel_px[1]))
wycinek = wycinek.resize((cel_px[0] * 2, cel_px[1] * 2), Image.LANCZOS)
wycinek.save(sys.argv[2])
print(json.dumps({
    "plik": sys.argv[2],
    "piksele": list(wycinek.size),
    "wymiar_m": list(CEL_M),
    "pikseli_na_metr_po_powiekszeniu": PX_NA_M * 2,
}, ensure_ascii=False))
