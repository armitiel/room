# Katalog

`products.json` jest pusty celowo: nie pozyskano jeszcze produktów ani licencji.

## Kształt wpisu

    {
      "schema_version": "0.1",
      "products": [
        {
          "product_id": "sofa-001",
          "name": "Nazwa handlowa",
          "manufacturer": "Producent",
          "product_url": "https://...",
          "model_path": "catalog/models/sofa-001.glb",
          "dimensions_m": {"x": 2.10, "y": 0.95, "z": 0.82},
          "license": "opis prawa do użycia modelu",
          "source": "skąd pochodzi model",
          "materials": ["tkanina", "drewno"]
        }
      ]
    }

`product_id` musi być unikalny — walidator odrzuca powtórzenia.
`model_path` liczy się względem katalogu głównego repozytorium.
`dimensions_m` służy do wykrywania przenikających się mebli, więc podawaj
rzeczywiste gabaryty, a nie zaokrąglenia z karty produktu.

## Co blokuje użycie produktu

Walidator zgłasza błąd, gdy scena odwołuje się do produktu, który nie ma
zapisanej licencji albo którego plik modelu nie istnieje. Link do produktu
nie oznacza prawa do użycia jego modelu.

Cenę i dostępność dodamy później wraz z datą aktualizacji.
