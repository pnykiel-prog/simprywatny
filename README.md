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

### Czego w `vercel.json` być nie może

Konfiguracja jest celowo minimalna — same `rewrites`. Dwa ustawienia, które
wyglądają rozsądnie, a wywalają build:

- **`outputDirectory`** przesuwa katalog, w którym platforma szuka funkcji.
  Katalog `api/` w korzeniu przestaje być widoczny i build kończy się błędem
  `The pattern "api/*.py" defined in functions doesn't match any Serverless
  Functions inside the api directory`.
- **Własny blok `functions`** dokłada ryzyka bez zysku: wykrywanie zero-config
  samo znajduje `api/*.py`.

Pilnują tego testy `test_konfiguracja_nie_przestawia_katalogu_wyjsciowego`
i `test_konfiguracja_nie_zawezaja_wzorca_funkcji`.

Funkcje potrzebują trzech rzeczy spoza `api/`: pakietu `sim_kalkulator/`,
pliku `web/index.html` i katalogu `przyklady/`. Gdyby któraś nie trafiła do
paczki funkcji, `/api/diag` powie to wprost.

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

## Trzy testy

| Test | Warunek | Wynik przy porażce |
|---|---|---|
| **1. Montaż** | `grant + kredyt + partycypacja + wkład własny = koszty` przy wkładzie ≤ dostępny | luka kapitałowa w zł |
| **2. Zdolność czynszowa** | `przychód netto ≥ eksploatacja + odpis + rata`, DSCR ≥ 1,0 w **każdym** roku | luka czynszowa w zł/m²/mies. + rok pierwszego naruszenia |
| **3. Rekompensata** | `EDB_grant + EDB_kredyt ≤ KN + RZ` przez cały okres powierzenia | nadwyżka w zł + kwota do zwrotu do Funduszu Dopłat |

Projekt domyka się **wyłącznie gdy przechodzą wszystkie trzy**. Wynik zawsze
wskazuje **wiążące ograniczenie** — który test i który parametr w nim decyduje.

Czynsz zakładany ponad limit ustawowy to **twardy błąd walidacji**, nie porażka
testu 2. Silnik nie liczy scenariusza bezprawnego.

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
