# Wdrożenie MVP
Najpierw lokalny build, potem hosting jednej sesji GPU. Nie uruchomiono usług płatnych.
1. Zanotuj zgodne wersje Unreal, pluginu i infrastruktury.
2. Zbuduj aplikację, przeprowadź lokalny test sceny i sterowania.
3. Wybierz usługę zarządzaną lub serwer GPU na podstawie testu i wyceny.
4. Skonfiguruj HTTPS, sygnalizację i w razie potrzeby TURN; nie eksponuj sekretów.
5. Ustaw maksymalną liczbę sesji, czas bezczynności, limit budżetu i zwalnianie zasobów.
6. Sprawdź stream z zewnętrznych sieci oraz zachowanie po zerwaniu połączenia.
7. Dopiero po tym osadź odtwarzacz na stronie.
Koszt sesji = czas rozliczany GPU + transfer/TURN + magazyn danych + AI + stałe opłaty przypadające na sesję.
Uwzględnij rozruch i bezczynność, nie tylko czas oglądania. Porównaj aktualne oferty przed zakupem.
Skrypty infrastruktury dodajemy po wyborze dostawcy, bez pozornych konfiguracji produkcyjnych.