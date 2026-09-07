# Kontrola szczelności powłoki

```
blender --background --factory-startup --python tools/kontrola/szczelnosc.py -- <plik.blend>
```

Strzela 900 promieni na punkt, z ośmiu miejsc wewnątrz pokoju, we wszystkie
strony. Każdy promień, który nie trafi w nic w zasięgu 12 m, to dziura
w powłoce. Wypisuje JSON.

## Dlaczego akurat tak

Pierwsza wersja testu strzelała prostopadle do ścian prostopadłościanu
i zgłosiła 49% „dziur" w ścianie kolankowej oraz 40% w suficie. Obie liczby
były fałszywe: tam granicą pokoju jest skos, więc promień poziomy z wysokości
1,5 m rzeczywiście nic nie trafiał, bo leciał już poza pokojem. Test
zakładał kształt, którego model nie ma.

Strzelanie we wszystkie strony z punktu wewnątrz nie zakłada niczego.
Jeśli powłoka jest zamknięta, każdy promień musi coś trafić — niezależnie
od tego, czy pokój jest pudełkiem, czy ma skosy, wnęki i lukarny.

## Czego ten test NIE wykryje

**Ścian o zerowej grubości.** Promień trafia w płaszczyznę tak samo dobrze
jak w mur, więc test pokaże 0% dziur. A w Unrealu jednostronna płaszczyzna
nie ma czego zapisać w cache powierzchni Lumena i słońce przechodzi przez
nią wprost. W `Room-attic-v05.blend` tak właśnie było z dwiema z czterech
ścian — test szczelności był czysty, a światło wchodziło w narożniki.

Dlatego skrypt liczy osobno listę `zerowa_grubosc`: obiekty, których
najmniejszy wymiar jest poniżej 4 mm, a największy powyżej 0,8 m. Szyba
w drzwiach i tło fotograficzne mają prawo tam być. Ściana nie.

**Styków bez zakładki.** Dwie bryły stykające się dokładnie, bez wspólnej
objętości, przepuszczą światło przy najmniejszym błędzie zaokrąglenia.
Tego nie widać ani promieniem, ani w Blenderze — dopiero w silniku.
Zasada przy składaniu powłoki z prostopadłościanów: sąsiedzi mają zachodzić
na siebie o kilka milimetrów, a wszystkie naddatki idą na zewnątrz i w dół,
żeby żadne lico od strony wnętrza się nie ruszyło.
