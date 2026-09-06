# Katalog

`products.json` opisuje meble, których generator używa do umeblowania sceny.
Każdy wpis ma pole `kind` i to ono decyduje, co wolno powiedzieć klientowi.

## Dwa rodzaje wpisów

**`kind: "real"` — rzeczywisty produkt handlowy.** Ma znanego producenta, adres
karty produktu, wymiary przepisane z karty katalogowej i osobno rozstrzygnięte
prawo do użycia modelu 3D. Tylko taki wpis wolno pokazać jako „to jest ten mebel".

**`kind: "placeholder"` — bryła zastępcza.** Wymiary są wiarygodne, ale przyjęte
przez nas, nie pochodzą od producenta. Model jest poglądowy. Pokazuje skalę
i układ funkcjonalny — odpowiada na pytanie „czy sofa się tu zmieści", a nie
„która to sofa". Nie wolno jej przedstawiać jako konkretnego mebla do kupienia.

Scena ze statusem `approved` **nie może** zawierać brył zastępczych. Walidator
to blokuje. Powód jest prosty: „wymiary sprawdzone" i mebel przyjęty na oko nie
mogą stać obok siebie w jednej ofercie.

## Co musi mieć wpis rzeczywisty

    {
      "product_id": "sofa-modell-x",
      "kind": "real",
      "name": "Sofa Modell X",
      "manufacturer": "Nazwa producenta",
      "product_url": "https://... karta produktu",
      "price": {"net": 4200, "currency": "PLN", "checked": "2026-09-06"},
      "model_path": "catalog/models/producent/sofa-modell-x.glb",
      "model_author": "kto wykonał model 3D",
      "license": "na jakiej podstawie wolno użyć TEGO MODELU",
      "dimensions_m": {"x": 2.20, "y": 0.95, "z": 0.82},
      "dimensions_source": "Karta katalogowa producenta, wydanie 2026",
      "materials": ["tkanina", "drewno"]
    }

Bez `manufacturer`, `product_url` i `dimensions_source` walidator odrzuca wpis
oznaczony jako `real` — bo bez nich nie da się mebla ani zamówić, ani sprawdzić.

## Prawo do modelu to nie to samo, co produkt

Kupienie sofy nie daje prawa do jej modelu 3D. Link do produktu nie daje prawa
do niczego. `license` opisuje wyłącznie podstawę użycia pliku i musi być
wypełnione niezależnie od tego, czy produkt jest realny.

## Co jest w katalogu dzisiaj

Trzydzieści wpisów `placeholder` na modelach z paczki Kenney Furniture Kit
(CC0, komercyjnie, bez atrybucji). Wymiary są typowymi wymiarami rynkowymi,
które przyjęliśmy sami. Modele nie odwzorowują żadnego produktu i są w stylu
low-poly. Zero wpisów `real` — pozyskanie ich to osobna praca: rozmowa
z producentem albo zakup licencjonowanej biblioteki.

## Skala modeli

Modele z bibliotek zwykle nie są w skali rzeczywistej — w paczkach growych
łóżko dwuosobowe potrafi mieć metr długości. **Katalog jest źródłem prawdy
o wymiarach**: generator skaluje wczytany plik do `dimensions_m`, jednolicie,
licząc z rzutu i pomijając osie cieńsze niż 12 cm. Dlatego `dimensions_m`
musi być prawdziwe, nawet gdy model jest poglądowy.

`mount_height_m` podnosi rzeczy wieszane (lustro, okap, telewizor, szafki górne)
na wysokość montażu nad podłogą.
