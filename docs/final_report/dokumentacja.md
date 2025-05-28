# Kreator długodystansowych tras rowerowych​

Przestrzenne Bazy Danych - projekt - realizacja 25L

Krzysztof Fijałkowski

Tomasz Owienko

Jakub Woźniak

## Cel projektu

Celem projektu była implementacja aplikacji pozwalającej na planowanie wielodniowych tras rowerowych.

## Wymagania funkcjonalne

- Interaktywne wyznaczanie tras rowerowych przebiegającej przez zadane punkty na mapie
- Uwzględnienie typu roweru oraz rodzajów dróg i ich nawierzchni w wyznaczaniu przebiegu trasy
- Sugerowanie miejsc wartych odwiedzenia oraz noclegów na podstawie przebiegu trasy
- Wspieranie równomiernego rozkładu się w poszczególnych dniach
- Wizualizacja przebiegu trasy
- Eksport wygenerowanych tras do formatu GPX

## Architektura rozwiązania

### Model danych

<!-- Topologia sieci reprezentowana jest w dwóch tabelach: jedna przechowuje krawędzie grafu, a druga jego wierzchołki. Graf  -->

### Ładowanie danych

Ładowanie danych odbywa się w kilku etapach:

1. Pobranie danych z bazy OpenStreetMap
  - Mapy poszczególnych województw pobierane są z serwisu `geofabrik.de` w formacie PBD. Następnie każdy plik konwertowany jest do formatu XML (`.osm`) za pomocą narzędzia `osmconvert` i usuwane są z niego niektóre tagi nieprzydatne z punktu widzenia projektu - w szczególności tagi `author` i `version`.
2. Budowa topologii sieci
  - Dla każdego pliku zawierającego mapę danego województwa wykonywane są następujące akcje:
    - Za pomocą narzędzia `osmfilter` usuwane są tagi nieprzydatne z punktu widzenia projektu, w wyniku czego w pliku pozostają jedynie dane dotyczące dróg - pozwala to zmniejszyć rozmiar pliku o około 65%. 
    - Plik ładowany jest do bazy danych i jednocześnie budowana jest topologia sieci, za co odpowiada narzędzie `osm2pgrouting`. Tym samym, drogi obecne w oryginalnych danych z OpenStreetMap mogą być dzielone na mniejsze odcinki lub scalane, przez co niektóre drogi z OSM nie posiadają odwzorowania w bazie, a innym odpowiada kilka krawędzi grafu. Na tym etapie pomijane jest tworzenie indeksów. Dane umieszczane są w tabelach `ways` i `ways_vertices_pgr`. Należy zaznaczyć, że struktura tabeli zdefiniowana jest przez narzędzie `osm2pgrouting`, w związku z czym niektóre wymagane kolumny muszą zostać dodane później.
    - Ten sam plik jest dodatkowo filtrowany narzędziem `osmfilter` aby wyodrębnić z niego poszczególne typy dróg, a następnie ładowany jest do tabeli `planet_osm_line` za pomocą narzędzia `osm2pgsql`
    - Na podstawie idektyfikatorów obiektów w OSM obecnych w obu tabelach uzupełniane są informacje o klasie drogi w tabeli `ways`
3. Analiza danych i optymalizacja modelu
  - Graf jest analizowany pod kątem obecności izolowanych podgrafów, następnie wszystkie izolowane podgrafy poza największym są usuwane (przy ładowaniu mapy całej Polski wiąże się to z usunięciem około 150.000 z 11.000.000 krawędzi)
  - Dla każdej krawędzi grafu wyznaczany jest jej środek dla szybszego wyszukiwania
  - Tworzone są indeksy
  - Aktualizowane są statystyki optymalizatora


### 

### Wyznaczanie trasy

#### Pobranie danych

#### Algorytm A*

Wyznaczanie trasy oparte jest o dwukierunkowy algorytm A* oraz jego implementację w rozszerzeniu `pgrouting` dla PostgreSQL. Pozwala on wyznaczyć (w przybliżeniu) najtańszą ścieżkę między dwoma punktami. Zastosowanie wariantu  dwukierunkowego pozwala poprawić wydajność w przypadku długich tras o ok. $15-25\%$. Uruchomienie algorytmu wymaga podania:

- Treści zapytania wydobywającego krawędzie grafu z bazy danych
  - Zapytanie powinno zwrócić m.in. współrzędne początków i końców krawędzi oraz koszt ich pokonania w obie strony (ujemny koszt oznacza możliwość przebycia krawędzi tylko w jednym kierunku)
- Identyfikatora wierzchołka startowego
- Identyfikatora wierzchołka końcowego
- Jednej z predefiniowanych funkcji heurystycznych

W aplikacji przyjęto funkcję heurystyczną będącą odległością w linii prostej między dwoma punktami: $h(P) = \sqrt{lat(P)^2 + lon(P)^2}$. 

##### Pobranie danych

Zapytanie pobierające dane dla algorytmu A* zwraca wszystkie krawędzie spełniające łącznie podane kryteria:

- Ich środki znajdują się w ramce mbb zawierającej punkt początkowy i startowy poszerzonej o pewien margines
- Odległość między ich środkami a odcinkiem od punktu startowego do końcowego mieści się z marginesie

Margines wyliczany jest w oparciu o odległość między punktem startowym i końcowym wg następującego wzoru (współczynniki dobrane eksperymentalnie):

$$
m = min(max(4.3 - \frac{4}{1 + e^{-3.5 d + 1}}, 0.5d), 3d)
$$

gdzie $m$ to margines, a $d$ to odległość między punktem startowym i końcowym w stopniach. W ten sposób dla krótszych tras margines jest szerszy (wyznaczenie stosunkowo prostej drogi na krótkim dystansie jest trudniejsze niż na długim) i stopniowo maleje wraz z długością trasy. Jednocześnie wprowadzono minimalny i maksymalne wartości marginesu w odniesieniu do $d$ ($0.5d, 3d$) dla poprawy stabilności algorytmu.

Odległość między środkami krawędzi grafu a odcinkiem łączącym początek i koniec wytyczanej ścieżki *nie* jest obliczana w oparciu o predykaty przestrzenne PostGIS, gdyż takie rozwiązanie nie zapewniało oczekiwanej wydajności - w przypadku wyznaczania trasy długości ok. 200km pobieranie krawędzi grafu trwało blisko dwukrotnie dłużej, niż faktyczne działanie algorytmu A*. Zamiast tego odległości obliczane są w sposób bezpośredni z wykorzystaniem odpowiednio przekształconego równania odległości punktu od prostej przebiegającej przez dwa punktu, gdzie większość współczynników równania obliczana jest przez aplikację i podawana jako parametry zapytani. Wykorzystywane są współrzędne geograficzne środków punktów zapisane uprzednio jako typ `numeric` w PostgreSQL, po pozwala ograniczyć narzut na konwersję typów. Takie podejście pozwala ograniczyć liczbę zwracanych krawędzi przy pomijalnie niskim koszcie obliczenia predykatów (pod warunkiem założenia indeksu typu B-drzewo na kolumny z współrzędnymi geograficznymi środków krawędzi grafu).

#### Wyznaczanie wag krawędzi

Ponieważ na koszta krawędzi wpływa wybrany typ roweru, muszą być one obliczone w trakcie zapytania. Koszt każdej krawędzi obliczana jest jako iloczyn jej długości i współczynnika kary zależnego od wybranego typu roweru i rodzaju drogi. Przykładowo, dla roweru szosowego współczynnik będzie wynosił $1$ dla dróg utwardzonych niebędących drogami krajowymi i wojewódzkimi, ale jego wartość dla dróg nieutwardzonych wyniesie $3$, w związku z czym algorytm będzie je wybierał tylko w zupełnej ostateczności. Współczynniki dobierane były eksperymentalnie dla każdego typu roweru wg następujących preferencji:

- Rower szosowy - silnie preferowane drogi utwardzone, niewielka kara za wybór dróg o dużym natężeniu ruchu
- Rower gravelowy / crossowy - koszt dróg nieutwardzonych niewiele większy niż utwardzonych, stosunkowo duża kara za wybór ruchliwych dróg
- Rower trekkingowy - tak samo jak w przypadku gravelowego, ale duża kara za wybór drogi o wysokim natężeniu ruchu
- Rower górski - koszt dróg nieutwardzonych niższy niż utwardzonych, duża kara za wybór drogi o wysokim natężeniu ruchu
- Rower elektryczny - wagi takie same, jak dla roweru trekkingowego (przyjęto założenie, że mają taką samą zdolność do pokonywania poszczególnych rodzajów nawierzchni, za to różnią się osiąganą prędkością)

Koszta przejazdu drogi w obie strony są równe dla dróg dwukierunkowych, a przypadku dróg jednokierunkowych koszt przejazdu w przeciwną stronę przemnażany jest przez $-1$ (droga nieprzejezdna).

#### Dodatkowe przetwarzanie

Funkcja `pgr_bdastar` zwraca kolejne krawędzi wchodzące w skład najkrótszej ścieżki (lub nie zwraca nic jeśli nie udało się znaleźć ścieżki). W ramach zapytania obliczane i przekazywane do aplikacji są następujące dane:

- Złączenie geometrii wszystkich krawędzi grafu w jedną ścieżkę zapisane w formacie GeoJSON
- Łączna długość trasy
- Łączny dystans pokonywany drogami każdego z typów

### Użytkowanie 
