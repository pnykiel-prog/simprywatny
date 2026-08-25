# Kalkulator montażu finansowego — prywatny SIM z umową z gminą

Narzędzie odpowiada na jedno pytanie: **czy montaż finansowy się domyka** dla
prywatnego SIM realizującego inwestycję na podstawie umowy z gminą — w wariancie
czysto społecznym, czysto komunalnym albo hybrydowym.

Odpowiedź nie jest jednym „tak/nie". Projekt musi przejść **trzy niezależne
testy** i może przejść dwa, a polec na trzecim.

Główny wynik operacyjny: **przy jakim udziale puli komunalnej całość przestaje
się domykać.** To jest treść negocjacji z gminą — gmina chce jak najwięcej
lokali komunalnych, inwestor potrzebuje puli społecznej, żeby uciągnąć dźwignię
kredytową i wyższy czynsz.

---

## Zastrzeżenia

Przeczytaj przed użyciem wyniku do czegokolwiek.

- Narzędzie wspiera **odsiewanie wariantów** przed złożeniem wniosku i rozmowę
  z gminą o proporcji pul. **Nie zastępuje wyliczenia BGK**, opinii prawnej ani
  doradztwa podatkowego. Rekompensatę ustala wiążąco Bank.
- Stałe prawne odczytano z tekstów jednolitych obowiązujących w **sierpniu
  2026 r.** Przed każdym naborem sprawdź aktualność: parametry programów
  zmieniają się między edycjami, a stopy zewnętrzne w ogóle nie są elementem
  prawa.
- **Kwestie otwarte pozostają nierozstrzygnięte i mają wpływ na wynik.**
  Wszystkie są w [`LUKI.md`](LUKI.md) i wszystkie siedzą na przełącznikach z
  jawnym oznaczeniem założenia. Pozycja 3 — ujęcie nakładu inwestycyjnego w
  kosztach netto — potrafi odwrócić werdykt testu 3.
- Narzędzie nie ocenia zdolności kredytowej inwestora i nie prowadzi analizy
  popytu — obłożenie jest parametrem wejściowym.
- Silnik powstał na **wartościach przykładowych**. Oba pliki w `przyklady/` to
  dane wymyślone, nie projekt rzeczywisty.

---

## Szybki start

```bash
pip install openpyxl pyyaml pytest        # zależności
python3 serwer.py --wejscie przyklady/domykajacy_sie.yaml
```

Otworzy się `http://127.0.0.1:8000/` — suwak udziału puli komunalnej, pod nim
trzy werdykty przeliczane na żywo, obok wykres z punktem granicznym.

Bez serwera:

```bash
python3 -m pytest -q                      # 347 testów
python3 -m pytest -q -m "not wolne"       # bez LibreOffice
```

---

## Wdrożenie (Vercel)

Repozytorium jest gotowe do wdrożenia bez konfiguracji w panelu — wystarczy
podpiąć projekt do repo. Vercel wykryje funkcje w `api/` i `requirements.txt`.

```
api/index.py       →  /              (rewrite z vercel.json) — podaje web/index.html
api/przelicz.py    →  /api/przelicz
api/sweep.py       →  /api/sweep
api/parametry.py   →  /api/parametry
api/arkusz.py      →  /api/arkusz
api/diag.py        →  /api/diag      funkcja serwisowa — stan paczki funkcji
```

### Konfiguracja `vercel.json` — runtime wymuszony, nie wykrywany

Konfiguracja używa `builds` z `@vercel/python`, a nie nowszego bloku
`functions`. Powód jest konkretny: `functions` polega na tym, że platforma sama
rozpozna `api/*.py` jako funkcje. W tym projekcie tego nie robiła i build
kończył się błędem:

```
The pattern "api/*.py" defined in `functions` doesn't match any
Serverless Functions inside the `api` directory
```

`builds` wskazuje runtime wprost, więc wykrywanie nie jest potrzebne.
`config.includeFiles` dokłada do paczki trzy katalogi spoza `api/`, których
funkcje potrzebują: `sim_kalkulator/`, `przyklady/` i `web/`.

`routes` odwzorowuje `/api/<nazwa>` na `api/<nazwa>.py`, a wszystko pozostałe
na `api/index.py`. Kolejność ma znaczenie — gdyby łapacz był pierwszy, każde
wywołanie API zwracałoby stronę HTML zamiast JSON-a. Pilnują tego testy
`test_kazda_trasa_z_ui_trafia_w_istniejacy_plik_funkcji`
i `test_trasa_api_ma_pierwszenstwo_przed_lapaczem`.

Jeśli build nadal nie widzi funkcji, sprawdź w ustawieniach projektu na Vercelu
**Root Directory** — musi wskazywać korzeń repozytorium, nie podkatalog.
Konfiguracja w repozytorium tego nie nadpisze.

### Kształt funkcji w `api/` — dwie reguły

**1. `handler` musi być definicją klasy na najwyższym poziomie modułu.**
Platforma szuka go analizą składni, przeglądając wyłącznie ciało modułu.
Przypisanie schowane w bloku `try` jest dla niej niewidoczne i build kończy się
błędem `Could not find a top-level "app", "application", or "handler"`.

**2. Silnik importowany jest leniwie, przy obsłudze żądania.** Import przy
ładowaniu modułu wywróciłby funkcję, zanim jakikolwiek kod obsługi błędów
zdążyłby zadziałać — a wtedy platforma zwraca nieczytelne 500 bez wskazówki.
Przy nieudanym imporcie strażnik zwraca JSON z powodem, śladem, zawartością
korzenia i informacją, których katalogów brakuje.

Obie reguły działają przeciw sobie tylko pozornie: klasa `handler` powstaje
zawsze, a import zawodzi dopiero w środku żądania, gdzie da się go obsłużyć.
Pilnują tego testy `test_handler_jest_widoczny_dla_analizy_skladni`
i `test_import_silnika_jest_leniwy`.

### Gdy wdrożenie nie działa — `/api/diag`

Endpoint diagnostyczny mówi wprost, czego brakuje: wersję Pythona, katalog
roboczy, obecność pakietu silnika, interfejsu i parametrów, wersje zależności
oraz wynik próbnego przeliczenia. `"ok": true` znaczy, że środowisko jest
kompletne. Nie ujawnia zmiennych środowiskowych ani zawartości plików.

Działa w obu środowiskach, żeby dało się je porównać:

| Gdzie | Adres |
|---|---|
| Wdrożenie | adres Twojej aplikacji + `/api/diag`, np. `https://nazwa-projektu.vercel.app/api/diag` |
| Lokalnie | `http://127.0.0.1:8000/api/diag` po `python3 serwer.py` |

Adres wdrożenia znajdziesz w panelu Vercela: projekt → zakładka **Deployments**
→ przycisk **Visit** przy ostatnim udanym wdrożeniu. To ten sam adres, pod
którym aplikacja nie działa — wystarczy dopisać `/api/diag`.

Gdy build w ogóle się nie powiódł, nie ma czego otwierać: w panelu wejdź
w nieudane wdrożenie i przeczytaj **Build Logs** — tam jest przyczyna.

Każda funkcja to kilka linijek — cała mechanika siedzi w
`sim_kalkulator/serverless.py`, a obliczenia w `sim_kalkulator/api.py`, z którego
korzysta też serwer lokalny. **Jeden silnik obsługuje oba środowiska.**

Wariant startowy zmienia się zmienną środowiskową `SIM_WEJSCIE` (ścieżka
względem korzenia repozytorium, domyślnie `przyklady/domykajacy_sie.yaml`).

### Czym wdrożenie różni się od uruchomienia lokalnego

Środowisko serverless jest bezstanowe i ma system plików tylko do odczytu, więc:

- **Arkusz wraca strumieniem do przeglądarki**, zamiast być zapisywany w
  `wyniki/`. Przycisk pobiera parę plików — `.xlsx` oraz `.yaml` z użytym
  zestawem parametrów, żeby dało się odtworzyć, na czym liczono. Lokalnie
  serwer dodatkowo odkłada tę parę na dysk.
- **Nic nie jest pamiętane między żądaniami.** Każde wywołanie dostaje komplet
  parametrów bazowych i własny zestaw zmian; UI trzyma stan suwaka u siebie.

Pełny sweep z rankingiem parametrów liczy się w ok. 0,5 s, więc mieści się
w limitach czasu funkcji z dużym zapasem.

---

## Główne pytanie: ile kapitału trzeba dołożyć

Narzędzie nie pyta „mam tyle kapitału, czy się spina", tylko odpowiada **„ile
kapitału muszę dołożyć, żeby się spięło"**. Wkład własny jest domknięciem
montażu, więc liczy się go jako resztę:

```
wkład własny = koszty przedsięwzięcia − dotacja − kredyt − partycypacja
```

To jest **główna liczba wyjściowa**. Zadeklarowany kapitał inwestora jest
opcjonalnym punktem odniesienia i nigdy nie blokuje obliczenia.

### Kredyt liczony, nie wpisywany

Domyślnie silnik wyznacza **największy kredyt, który uniesie zakładany czynsz**,
ograniczony trzema rzeczami: zdolnością czynszu w każdym roku projekcji,
ustawowym udziałem 80% oraz tym, ile kredytu w ogóle potrzeba po dotacji
i partycypacji. Dzięki temu wskaźnik pokrycia obsługi długu nigdy nie schodzi
poniżej 1,0, a całe napięcie montażu przenosi się do jednej liczby.

Przełącznik „ustal kredyt samodzielnie" wraca do trybu ręcznego — tam wskaźnik
pokrycia znów bywa mniejszy od jedności i test 2 może oblać.

## Trzy testy

| Test | Warunek | Wynik przy porażce |
|---|---|---|
| **1. Kapitał** | wymagany wkład ≤ zadeklarowany kapitał (gdy podany) | brakujący kapitał w zł |
| **2. Zdolność czynszowa** | `przychód netto ≥ koszty bieżące + rata`, wskaźnik pokrycia ≥ 1,0 w **każdym** roku | luka czynszowa w zł/m²/mies. + rok pierwszego naruszenia |
| **3. Rekompensata** | `EDB_grant + EDB_kredyt ≤ KN + RZ` przez cały okres powierzenia | nadwyżka w zł + kwota do zwrotu do Funduszu Dopłat |

Projekt domyka się **wyłącznie gdy przechodzą wszystkie trzy**. Wynik zawsze
wskazuje **wiążące ograniczenie** — jednym zdaniem, bez numeru przepisu.

### Ograniczenia ustawowe są wbudowane w sterowanie

Suwak czynszu kończy się na limicie ustawowym dla danego poziomu dotacji.
Limit zależy od udziału mieszkań komunalnych, więc przy ruchu głównego pokrętła
przelicza się na żywo; stawka ponad nowy limit zostaje ściągnięta i **jest to
komunikowane** — to jedyne miejsce, gdzie narzędzie zmienia wartość za
użytkownika.

Ściąganie dzieje się po stronie API, bo przeglądarka nie może znać limitu,
zanim przesunie pokrętło. Sam silnik pozostaje twardy: czynszu ponad limit nie
policzy, kto by go nie podał.

---

## Architektura

```
warstwa wspólna       →  koszty, grunt, PUM, alokacja kosztów wspólnych
       ↓                              ↓
silnik społeczny            silnik komunalny
(art. 5 ust. 1 pkt 1)       (art. 5a ust. 1)
       ↓                              ↓
warstwa łączna        →  wkład własny, płynność, test rekompensaty
```

**Warstwa łączna nie jest sumą.** Wkład własny obciąża jeden bilans inwestora.
Wartość gruntu limituje grant w obu pulach i dzieli się kluczem PUM, zamiast być
liczona dwa razy.

**Jeden silnik.** Logika obliczeniowa wyłącznie w Pythonie. UI wywołuje API, API
woła silnik. Przeglądarka nie liczy niczego poza formatowaniem wyświetlania —
pilnuje tego test `test_ui_nie_liczy_niczego_poza_formatowaniem`.

### Moduły

| Plik | Zawartość |
|---|---|
| `sim_kalkulator/prawo.py` | **jedyne miejsce z liczbami z ustaw**, każda z podstawą w komentarzu |
| `sim_kalkulator/waluta.py` | arytmetyka pieniądza (`Decimal`), bez żadnej stałej prawnej |
| `sim_kalkulator/dane.py` | dataclasses wejścia, parser YAML, komplet walidacji |
| `sim_kalkulator/alokacja.py` | podział kosztów wspólnych kluczem PUM + wysokość wsparcia |
| `sim_kalkulator/grant.py` | limity grantu, reguła gruntowa, bonus |
| `sim_kalkulator/kredyt.py` | harmonogram równej raty z karencją, EDB |
| `sim_kalkulator/czynsz.py` | dwa limity czynszu, wybór wiążącego, opłaty poza czynszem |
| `sim_kalkulator/projekcja.py` | struktura finansowania, przepływy rok po rok |
| `sim_kalkulator/rekompensata.py` | KN, RZ, EDB, test nadwyżki, asymetria gruntu |
| `sim_kalkulator/testy_montazu.py` | trzy werdykty, wiążące ograniczenie, luki |
| `sim_kalkulator/wrazliwosc.py` | sweep udziału pul, punkt graniczny, ranking |
| `sim_kalkulator/arkusz.py` | eksport XLSX z formułami |
| `sim_kalkulator/silnik.py` | orkiestrator — jedno pełne przeliczenie |
| `sim_kalkulator/api.py` | warstwa API bez HTTP — wspólna dla obu środowisk |
| `sim_kalkulator/serverless.py` | adapter funkcji serverless |
| `serwer.py`, `web/index.html` | lokalny serwer HTTP i jednoplikowy UI |
| `api/*.py`, `vercel.json` | funkcje i trasowanie wdrożenia |
| `scripts/recalc.py` | przeliczenie arkusza i kontrola błędów formuł |

### Zasady, których kod pilnuje

- **Stałe tylko w `prawo.py`.** Liczba z ustawy w innym module to błąd, nawet
  gdy wynik jest poprawny. Testy sprawdzają, że stałe nie są `float`.
- **Kwoty jako `Decimal`.** Model operuje na pieniądzach przez 30 lat.
- **Wszystko per m² PUM**, nie na lokal — inaczej warianty o różnej strukturze
  mieszkań nie są porównywalne.
- **Żadnych milczących wartości domyślnych** dla parametrów zewnętrznych. Brak
  stopy referencyjnej zatrzymuje obliczenie, nie podstawia ostatniej znanej.
- **Pule nie są uśredniane.** Pula komunalna nie może mieć kredytu (art. 5a
  ust. 3), więc średnia ważona dałaby wynik pozornie poprawny i całkowicie fałszywy.

---

## Dane wejściowe

Plik YAML — patrz `przyklady/wzorcowy.yaml` z komentarzem przy każdej pozycji.
Wszystkie kwoty w PLN, powierzchnie w m², **stopy jako ułamki dziesiętne**
(0,035 nie 3,5; silnik odrzuca wartości wyglądające na procenty).

Każdy parametr zewnętrzny ma mieć w YAML źródło i datę. Silnik ostrzega, gdy
`data_parametrow` jest starsza niż 6 miesięcy, i gdy któryś parametr nie ma
wskazanego źródła.

### Dwa przykłady

| Plik | Werdykt | Po co |
|---|---|---|
| `przyklady/wzorcowy.yaml` | nie domyka się, wiąże test 2 | pokazuje raportowanie luk i wiążącego ograniczenia |
| `przyklady/domykajacy_sie.yaml` | domyka się do 55% udziału komunalnego | pokazuje punkt graniczny wewnątrz zakresu |

Oba mają **identyczne koszty** (29,05 mln zł) i różnią się wyłącznie strukturą
finansowania. To jest teza narzędzia: o werdykcie decyduje montaż, nie skala.

---

## Ranking parametrów — dwa tryby

Kolumna „Dźwignia" odpowiada na inne pytanie w zależności od tego, czy wariant
bazowy w ogóle się domyka:

| Sytuacja | Co pokazuje ranking |
|---|---|
| Montaż domyka się przy jakimś udziale | o ile parametr przesuwa punkt graniczny (`-20%` znaczy: obniż o jedną piątą, a granica pójdzie w górę) |
| Nie domyka się przy żadnym udziale | przy jakiej wartości parametru **zacząłby** się domykać i do jakiego udziału komunalnego |

Drugi tryb realizuje wymóg z rozdz. 7.1 specyfikacji. Silnik przeszukuje zakres
±60% wartości bazowej, zaczynając od zmian najmniejszych — pierwsza znaleziona
jest zarazem najtańsza. Ranking porządkuje wtedy parametry wg kosztu
przełamania, nie wg siły przesunięcia.

Gdy żaden parametr nie przełamuje w tym zakresie, wiersze mówią to wprost.
Wtedy problemem nie jest pojedyncze założenie, tylko cała konstrukcja montażu.

---

## Arkusz

```bash
# z UI: przycisk „Generuj arkusz i zapisz parametry"
# albo z Pythona:
python3 -c "
from sim_kalkulator.dane import wczytaj_yaml
from sim_kalkulator.silnik import przelicz
from sim_kalkulator import arkusz, wrazliwosc
w = wczytaj_yaml('przyklady/domykajacy_sie.yaml')
arkusz.eksportuj(przelicz(w), 'wynik.xlsx', wrazliwosc.build(w))"

python3 scripts/recalc.py wynik.xlsx --porownaj-z-silnikiem przyklady/domykajacy_sie.yaml
```

**Formuły, nie wartości.** Każda komórka wynikowa odwołuje się do komórek
założeń; zmiana dowolnego założenia w zakładce `Zalozenia` przelicza cały
skoroszyt. Osiem zakładek: `Zalozenia`, `Alokacja`, `Pula_spoleczna`,
`Pula_komunalna`, `Rekompensata`, `Werdykty`, `Wrazliwosc`, `Podstawy_prawne`.

Konwencja kolorów: wejścia i dźwignie scenariuszowe — **niebieskie**, formuły —
czarne, odwołania międzyzakładkowe — **zielone**, kluczowe założenia do
uzupełnienia — **żółte wypełnienie**. Funkcje ograniczone do standardu Excel
2007; do wyszukiwań `INDEX`/`MATCH`, nie `XLOOKUP`.

`scripts/recalc.py` wymaga LibreOffice (`apt install libreoffice-calc`) i żąda
zera błędów formuł. Z flagą `--porownaj-z-silnikiem` porównuje dodatkowo
kluczowe komórki arkusza z wynikiem silnika.

> Zielony przebieg dowodzi, że formuły się liczą — nie że są poprawne.
> Sprawdź ręcznie 2–3 formuły w każdej zakładce projekcji.
> Klasa `TestRecznaKontrolaFormul` robi część tej roboty automatycznie.

Przycisk w UI zapisuje obok arkusza **zestaw użytych parametrów jako YAML z
datą**, żeby dało się odtworzyć, na czym liczono.

---

## Znane ograniczenia implementacji

- Komunikaty silnika (ostrzeżenia, opisy werdyktów, etykiety w arkuszu) są
  pisane **bez polskich znaków diakrytycznych**. Statyczny tekst UI i
  dokumentacja mają je normalnie. Ujednolicenie to mechaniczny przegląd
  kilkudziesięciu łańcuchów znaków — nie zostało zrobione.
- Zakładka `Wrazliwosc` w arkuszu jest migawką, nie żywymi formułami — patrz
  [`LUKI.md`](LUKI.md) pkt 9.
- Kalibracja na przypadkach rzeczywistych nie została wykonana. Silnik ma
  komplet zamrożonych testów regresji dla obu przykładów (`TestRegresjaPrzykladow`),
  gotowych do rozszerzenia o projekty realne.

---

## Kolejny krok — kalibracja

Silnik powstał na wartościach przykładowych. Następny krok to wprowadzenie
realnych projektów jako przypadków kalibracyjnych, każdy z zamrożonym wynikiem
jako testem regresji. Dla każdego zapisz: komplet parametrów w YAML, oczekiwany
werdykt, źródło danych rzeczywistych oraz — jeżeli dostępne — wyliczenie BGK do
porównania.

**Rozbieżność z wyliczeniem Banku traktuj jako błąd krytyczny w silniku**, nie w
Banku, i wyjaśnij przed dalszym rozwojem.

---

## Wykaz podstaw prawnych

- Ustawa z 26 października 1995 r. o społecznych formach rozwoju mieszkalnictwa
  — t.j. Dz.U. 2025 poz. 1273, ze zm. Dz.U. 2026 poz. 39 i poz. 986
- Ustawa z 8 grudnia 2006 r. o finansowym wsparciu niektórych przedsięwzięć
  mieszkaniowych — t.j. Dz.U. 2026 poz. 511
- Ustawa z 25 lipca 2025 r. o zmianie ustawy o społecznych formach rozwoju
  mieszkalnictwa — Dz.U. 2025 poz. 1077
- Rozporządzenie RM z 20 października 2015 r. o warunkach finansowania
  zwrotnego — t.j. Dz.U. 2021 poz. 766, ze zm. Dz.U. 2024 poz. 1732
- Rozporządzenie MFiG z 29 grudnia 2025 r. o finansowym wsparciu — Dz.U. 2025 poz. 1897
- Rozporządzenie RM z 11 sierpnia 2004 r. o obliczaniu wartości pomocy
  publicznej — t.j. Dz.U. 2018 poz. 461
- Rozporządzenie MIiR z 4 marca 2019 r. o standardach — Dz.U. 2019 poz. 457

Pełny wykaz stałych z podstawami jest w `sim_kalkulator/prawo.py` oraz w
zakładce `Podstawy_prawne` każdego wygenerowanego arkusza.
