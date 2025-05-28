# Kreator długodystansowych tras rowerowych​

Przestrzenne Bazy Danych - projekt - realizacja 25L

Krzysztof Fijałowski

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

Wyznaczanie trasy oparte jest o dwukierunkowy algorytm A* oraz jego implementację w rozszerzeniu `pgrouting` dla PostgreSQL. Pozwala on wyznaczyć (w przybliżeniu) najtańszą ścieżkę między dwoma punktami. Uruchomienie algorytmu wymaga podania:

- Treści zapytania wydobywającego krawędzie grafu z bazy danych
- Identyfikatora wierzchołka startowego
- Identyfikatora wierzchołka końcowego

#### Pobranie danych

#### Algorytm A*

#### Dodatkowe przetwarzanie

### Użytkowanie 