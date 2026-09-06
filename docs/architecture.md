# Kontrakty MVP

## Dane sceny
scene.json: schema_version, scene_id, units=m, coordinate_system=right_handed_z_up, status, sources, rooms, furniture, variants.
Pomieszczenie: id, polygon_xy_m, height_m, openings, evidence, review_notes.
Otwór: wall_index, offset_m od początku ściany, width_m, sill_m, height_m, kind.
Mebel: id, product_id, position_m, rotation_deg; skala wynika z katalogu.
Wariant: id, nazwa i lista dozwolonych podmian materiałów/produktów.
Przed importem do Unreal jawnie przeliczyć metry na centymetry oraz orientację układu współrzędnych.

## Walidacja przed generowaniem
Wielokąt prosty, dodatnie wymiary, otwory mieszczące się w ścianie, brak powtórzonych identyfikatorów, istniejące produkty i pliki modeli.
Brakujące dane blokują status approved. Status approved nadaje operator po porównaniu z materiałami.
Przechowywać wynik AI oddzielnie od zatwierdzonego JSON; nie nadpisywać poprawek operatora.
Biblioteka produktów przechowuje licencję, producenta, URL i rzeczywiste gabaryty.

## Backend: proponowane granice, jeszcze niezaimplementowane
POST /projects — rejestracja materiałów; pliki prywatne, limity wielkości i typu.
POST /projects/{id}/extract — zadanie analizy, nie synchroniczny długi request.
GET /jobs/{id} — queued / running / needs_review / succeeded / failed.
POST /projects/{id}/approve — zatwierdzenie wersji przez operatora.
POST /sessions — sesja przypisana do zatwierdzonej sceny.
DELETE /sessions/{id} — zwolnienie GPU.
Na start pojedynczy worker i pliki JSON; bazę i kolejkę dodać gdy pojawi się realna potrzeba.

## Polecenia wnętrzarskie, etap późniejszy
Tekst → AI → komenda z listy, np. set_variant lub replace_product → walidacja → Unreal → potwierdzenie.
Bez dowolnego kodu, ścieżek plików lub komend systemowych. Zmiany geometrii wymagają osobnego zadania i przeglądu.

## Rendering
Unreal działa na GPU, a przeglądarka odbiera media przez WebRTC.
Sygnalizacja zestawia połączenie; STUN/TURN zależą od sieci i dostawcy.
Klucze hostingu pozostają po stronie serwera. Sesje mają autoryzację, limit czasu i bezczynności.