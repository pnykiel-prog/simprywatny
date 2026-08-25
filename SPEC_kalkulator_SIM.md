# Kalkulator montażu finansowego — prywatny SIM z umową z gminą

**Specyfikacja dla Claude Code.** Wersja 1, 25 sierpnia 2026 r.

Dokument jest źródłem prawdy dla implementacji. Każda liczba i reguła ma tu podstawę prawną. Jeżeli implementacja wymaga wartości, której tu nie ma — nie zgaduj, zgłoś brak.

---

## 1. Co narzędzie ma robić

Odpowiadać na pytanie: **czy montaż finansowy się domyka** dla prywatnego SIM realizującego inwestycję na podstawie umowy z gminą — w wariancie czysto społecznym, czysto komunalnym albo hybrydowym.

Odpowiedź nie jest jednym „tak/nie". Projekt musi przejść **trzy niezależne testy** (rozdz. 6). Może przejść dwa i polec na trzecim.

Główny wynik operacyjny: **przy jakim udziale puli komunalnej całość przestaje się domykać.** To jest treść negocjacji z gminą — gmina chce jak najwięcej lokali komunalnych, inwestor potrzebuje puli społecznej, żeby uciągnąć dźwignię kredytową i wyższy czynsz.

### Czego narzędzie NIE robi

- Nie zastępuje wyliczenia BGK. Bank ustala rekompensatę wiążąco.
- Nie ocenia zdolności kredytowej inwestora.
- Nie prowadzi analizy popytu — przyjmuje obłożenie jako parametr wejściowy.
- Nie doradza prawnie.

Te ograniczenia mają być widoczne w interfejsie i w arkuszu, nie tylko w README.

---

## 2. Architektura

### 2.1. Stack

| Warstwa | Technologia | Uzasadnienie |
|---|---|---|
| Silnik obliczeniowy | Python 3.11+ | Jedno źródło prawdy dla UI i arkusza |
| Interfejs | Lokalny serwer HTTP + jednoplikowy HTML | Podgląd na żywo, suwak udziału pul |
| Eksport | `openpyxl` | Arkusz z formułami, nie z wartościami |
| Dane wejściowe | YAML | Wersjonowalne, czytelne w repozytorium |

**Silnik musi być jeden.** Nie wolno duplikować logiki obliczeniowej w JavaScripcie po stronie przeglądarki. UI wywołuje API, API woła silnik. Dwa silniki liczące to samo rozjadą się i nikt tego nie zauważy.

### 2.2. Trzy warstwy domenowe

```
warstwa wspólna       →  koszty, grunt, PUM, alokacja kosztów wspólnych
       ↓                              ↓
silnik społeczny            silnik komunalny
(art. 5 ust. 1 pkt 1)       (art. 5a ust. 1)
       ↓                              ↓
warstwa łączna        →  wkład własny, płynność, test rekompensaty
```

**Warstwa łączna nie jest sumą.** Wkład własny obciąża jeden bilans inwestora. Wartość gruntu limituje grant w obu pulach i musi zostać rozdzielona, a nie policzona dwa razy.

### 2.3. Struktura repozytorium

```
sim_kalkulator/
  prawo.py          # stałe prawne — jedyne miejsce z liczbami z ustaw
  dane.py           # dataclasses wejścia i wyjścia
  alokacja.py       # podział kosztów wspólnych na pule
  grant.py          # wysokość wsparcia, limity, bonus
  kredyt.py         # harmonogram, EDB, obsługa długu
  czynsz.py         # limity czynszu, wybór wiążącego
  projekcja.py      # przepływy 25-30 lat
  rekompensata.py   # KN, RZ, EDB, test nadwyżki
  testy_montazu.py  # trzy werdykty + wiążące ograniczenie
  wrazliwosc.py     # sweep, punkt graniczny
  arkusz.py         # eksport XLSX
serwer.py
web/index.html
przyklady/
tests/
```

### 2.4. Konwencja nazewnicza

Terminy dziedzinowe **po polsku** — `czynsz`, `partycypacja`, `rekompensata`, `wartosc_odtworzeniowa`. Nie tłumacz na angielski: „rekompensata" to termin ustawowy o precyzyjnym znaczeniu, a `compensation` je gubi. Elementy strukturalne (`build`, `run`, `export`) po angielsku.

---

## 3. Stałe prawne

**Wszystkie do modułu `prawo.py`, każda z podstawą w komentarzu.** Nigdzie indziej w kodzie nie może pojawić się liczba pochodząca z ustawy.

### 3.1. Wysokość wsparcia

| Stała | Wartość | Podstawa |
|---|---|---|
| Grant społeczny — limit podstawowy | 45% kosztów przedsięwzięcia | art. 13 ust. 1 pkt 1 ustawy z 8.12.2006 |
| Grant społeczny — próg gruntowy | 35% kosztów | art. 13 ust. 1 pkt 1 |
| Grant komunalny | 80% kosztów | art. 13 ust. 1 pkt 3 lit. c w zw. z art. 5a ust. 1 |
| Bonus rewitalizacyjny / „Za życiem" | +5 punktów procentowych | art. 13 ust. 4 |

**Reguła gruntowa (krytyczna).** Grant społeczny nie jest po prostu 45% kosztów:

```
grant_spoleczny = min(
    0.45 * koszty_kwalifikowane,
    0.35 * koszty_kwalifikowane + wartosc_gruntu_inwestora
)
```

Część przekraczająca 35% jest pokrywana wyłącznie do wysokości wartości prawa własności albo użytkowania wieczystego gruntu **będącego we władaniu inwestora**. Bez gruntu inwestora realna stawka wynosi 35%.

**Bonus +5 pp** przysługuje wyłącznie przy braku finansowania zwrotnego (art. 13 ust. 4, wyłączenie wprost). Praktycznie: dostępny w puli komunalnej, niedostępny w społecznej z kredytem SBC.

**VAT w podstawie.** Koszty stanowiące podstawę wsparcia uwzględniają VAT tylko wtedy, gdy inwestorowi nie przysługuje prawo do odliczenia lub zwrotu (art. 13 ust. 3). Status VAT musi być parametrem wejściowym, bo zmienia podstawę naliczenia grantu, a nie tylko rozliczenia bieżące.

### 3.2. Finansowanie zwrotne

| Stała | Wartość | Podstawa |
|---|---|---|
| Maksymalny udział kredytu | 80% kosztów przedsięwzięcia | art. 15b ust. 2 ustawy z 26.10.1995 |
| Maksymalny okres kredytowania | 30 lat wliczając karencję | art. 15b ust. 3 |
| Wykluczenie w puli komunalnej | brak możliwości łączenia | art. 5a ust. 3 ustawy z 8.12.2006 |

**Art. 5a ust. 3 jest rozłącznością konstrukcyjną, nie limitem.** Silnik komunalny nie może przyjąć kredytu jako parametru. Próba ustawienia kredytu w tej puli to błąd walidacji, nie ostrzeżenie.

### 3.3. Limity czynszu

Na ten sam lokal nakładają się **dwa niezależne limity**. Wiąże niższy.

**Limit z art. 7c ustawy z 8.12.2006** — procent wartości odtworzeniowej lokalu rocznie, zależny od udziału wsparcia w kosztach:

| Udział wsparcia | Limit roczny |
|---|---|
| poniżej 45% | 4,0% |
| co najmniej 45% | 3,5% |
| co najmniej 60% | 3,0% |
| co najmniej 75% | 2,5% |
| co najmniej 90% | 2,0% |
| remont i przebudowa (art. 5 ust. 1 pkt 2) | 5,0% |

**Limit z art. 28 ust. 2 pkt 2 ustawy z 26.10.1995** — 5% wartości odtworzeniowej rocznie dla lokali wybudowanych przy wykorzystaniu finansowania zwrotnego.

W praktyce dla modelu bazowego: pula społeczna z grantem 45% → wiąże 3,5%. Pula komunalna z grantem 80% → wiąże 2,5%. Silnik ma to wyliczać, nie zakładać.

**Podstawa naliczenia — art. 28 ust. 2b.** Gdy wartość odtworzeniowa lokalu jest niższa niż koszt budowy uwzględniający wartość nieruchomości, podstawą maksymalnej stawki jest **koszt budowy**. Przy drogim gruncie działa to na korzyść inwestora. Silnik liczy obie podstawy i bierze wyższą.

**Opłaty poza czynszem — art. 28 ust. 4–5.** Koszty OZE, termomodernizacji, dostępności i rewitalizacji pobiera się obok czynszu, łącznie do 1% wartości odtworzeniowej rocznie. Osobna pozycja w modelu, nie doliczana do czynszu.

### 3.4. Partycypacja

| Próg | Skutek | Podstawa |
|---|---|---|
| co najmniej 10% kosztów budowy lokalu | umowa najmu na czas nieoznaczony albo najem instytucjonalny z dojściem do własności | art. 29a ust. 2b ustawy z 26.10.1995 |
| co najmniej 15% | nie stosuje się art. 7b ust. 1 (wymóg czasu oznaczonego min. 5 lat) | art. 29a ust. 2a |
| maksimum 30% | górny limit dla osoby fizycznej przy finansowaniu zwrotnym | art. 29a ust. 2 |

**Ostrzeżenie do zaimplementowania.** W przedziale od 10% do poniżej 15% art. 29a ust. 2b i art. 7b ust. 1 prowadzą do sprzecznych wniosków co do typu umowy. Silnik ma w tym przedziale zwracać ostrzeżenie, nie werdykt.

**Zwrot partycypacji** jest wymagalny nie później niż 12 miesięcy od opróżnienia lokalu i podlega ustawowej waloryzacji wskaźnikiem ceny 1 m² GUS (art. 29a ust. 3). W projekcji to zobowiązanie rosnące, niezależne od ponownego zasiedlenia — musi być ujęte w przepływach przy założonej rotacji.

**Partycypacja nie występuje w puli komunalnej** — najemcą jest gmina.

### 3.5. Rekompensata

| Element | Reguła | Podstawa |
|---|---|---|
| Warunek graniczny | `RUOIG ≤ KN + RZ` | art. 5 ust. 5 i 11 ustawy z 8.12.2006; § 6 ust. 2 rozp. Dz.U. 2025 poz. 1897 |
| Okres powierzenia — grant | 25 lat | art. 5 ust. 10 pkt 1 |
| Okres powierzenia — kredyt | równy okresowi finansowania, nie dłużej niż okres amortyzacji budynków | § 11 rozp. t.j. Dz.U. 2021 poz. 766 |
| Katalog kosztów UOIG | art. 5 ust. 7–8 ustawy | — |
| Katalog przychodów UOIG | art. 5 ust. 9 ustawy | — |
| Próg tolerancji nadwyżki — grant | 10% średniej rocznej rekompensaty | § 7 ust. 9 rozp. Dz.U. 2025 poz. 1897 |
| Próg tolerancji nadwyżki — kredyt | 20% | § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766 |

**Koszty netto:**

```
KN = Σ (KUOIG_i − PUOIG_i) / (1 + rb)^(i−1)     dla i = 1..n
```

gdzie `rb` to stopa bazowa Komisji Europejskiej obowiązująca na dzień zawarcia umowy, a `n` to ostatni rok okresu powierzenia. W ścieżce kredytowej wzór zawiera dodatkowo wkład we wspólne koszty stałe (§ 12 ust. 3 rozp. 766).

**Pozycja gruntu w rekompensacie — asymetria do zaimplementowania wprost:**

| Sytuacja | Ujęcie | Podstawa |
|---|---|---|
| Grunt inwestora, ścieżka grantowa | koszt, bez limitu procentowego | art. 5 ust. 7 pkt 7 i ust. 8 |
| Grunt JST wniesiony aportem, ścieżka grantowa | **przychód** inwestora — obniża KN | art. 5 ust. 9 pkt 4 |
| Grunt wniesiony aportem, ścieżka kredytowa | koszt, ale tylko do 20% całkowitych kosztów przedsięwzięcia | § 12 ust. 7 rozp. 766 |

To jest miejsce, w którym najłatwiej o błąd: grunt inwestora podnosi podstawę, grunt gminy ją obniża.

**Do rekompensaty w ścieżce grantowej wlicza się dodatkowo** wsparcie z Rządowego Funduszu Rozwoju Mieszkalnictwa oraz wartość nieodpłatnego prawa do korzystania z dokumentacji projektowych BGK (§ 7 ust. 7 rozp. 1897). Dokumentacja z zasobu Banku nie jest darmowa w sensie limitu.

**Rozsądny zysk** liczony wzorem opartym na stopie IRS dla kontraktu 20-letniego na bazie WIBOR 3M, publikowanej przez BGK w BIP dla każdej edycji programu przed naborem (§ 6 ust. 5 rozp. 1897; § 12 ust. 10 rozp. 766). **Parametr zewnętrzny — wejście, nie stała.**

### 3.6. Ekwiwalent dotacji brutto

Podstawa: rozporządzenie RM z 11.08.2004, t.j. Dz.U. 2018 poz. 461.

**Ścieżka grantowa — § 4 pkt 1:** dla dotacji EDB jest równy kwocie dotacji. Bez dyskontowania, bez parametrów.

```python
edb_grant = kwota_grantu
```

**Ścieżka kredytowa — § 4 pkt 5 lit. e** (kredyt spłacany w systemie równej raty z karencją spłaty kapitału — wariant wskazany przez rozporządzenie o finansowaniu zwrotnym):

```
EDB = Σ[i=1..T]  (S·r − S·rp) / (1+rd)^i
    + Σ[i=T+1..N]  [ S·r·(1+r)^(N−T) / ((1+r)^(N−T) − 1)
                    − S·rp·(1+rp)^(N−T) / ((1+rp)^(N−T) − 1) ] / (1+rd)^i
```

| Symbol | Znaczenie |
|---|---|
| `S` | kwota kredytu |
| `N` | liczba okresów płatności i karencji łącznie |
| `T` | liczba okresów karencji |
| `r` | stopa referencyjna KE, ułamek dziesiętny |
| `rp` | preferencyjna stopa kredytu, ułamek dziesiętny |
| `rd` | stopa dyskontowa, ułamek dziesiętny |

**Asercja obowiązkowa:** `0 < EDB < S`. Wynik ujemny oznacza, że `rp > r` — silnik ma wtedy przerwać z komunikatem, a nie zwrócić liczbę.

### 3.7. Standardy techniczne

Podstawa: rozporządzenie MIiR z 4.03.2019, Dz.U. 2019 poz. 457.

| Parametr | Wymóg |
|---|---|
| PUM pojedynczego lokalu | 25–80 m²; powyżej 80 m² wyłącznie dla rodzin wielodzietnych |
| Dźwigi osobowe | obowiązkowe od 3 kondygnacji naziemnych |
| Minimalna szerokość drogi publicznej | 6 m |

Silnik traktuje to jako **walidację wejścia**, nie jako element obliczeń. Średnie PUM lokalu poza przedziałem → ostrzeżenie z odesłaniem do przepisu. Liczba kondygnacji ≥ 3 bez pozycji kosztowej na dźwigi → ostrzeżenie o prawdopodobnym niedoszacowaniu kosztów.

---

## 4. Dane wejściowe

Plik YAML. Wszystkie kwoty w PLN, powierzchnie w m², stopy jako ułamki dziesiętne (0,035 nie 3,5).

### 4.1. Warstwa wspólna

```yaml
projekt:
  nazwa: str
  gmina: str
  wojewodztwo: str            # dla wskaźnika wartości odtworzeniowej

powierzchnie:
  pum_laczne: float           # m²
  liczba_lokali: int
  liczba_kondygnacji: int
  udzial_puli_komunalnej: float   # 0.0–1.0 — GŁÓWNE POKRĘTŁO

koszty:
  koszt_budowy_na_m2: float
  infrastruktura: float
  projekt_i_nadzor: float
  koszty_ogolne: float
  rezerwa: float
  vat_odliczalny: bool        # wpływa na podstawę grantu, art. 13 ust. 3

grunt:
  wartosc: float              # z operatu
  forma: enum                 # wlasnosc_inwestora | aport_inwestora | aport_jst | nabycie | lokal_za_grunt
  obciazony_hipoteka: bool    # przy aporcie w ścieżce kredytowej — dyskwalifikuje
```

### 4.2. Pula społeczna

```yaml
pula_spoleczna:
  kredyt:
    oprocentowanie: float           # rp
    okres_lat: int                  # N, max 30 wliczając karencję
    karencja_lat: int               # T
    udzial_docelowy: float          # 0.0–0.80, art. 15b ust. 2
  partycypacja:
    stawka_procent_kosztu_lokalu: float   # 0.0–0.30
    rotacja_roczna: float                 # do rezerwy na zwrot
  czynsz_zakladany_m2_mies: float
  bonus_rewitalizacyjny: bool             # tylko gdy brak kredytu
```

### 4.3. Pula komunalna

```yaml
pula_komunalna:
  czynsz_placony_przez_gmine_m2_mies: float
  bonus_rewitalizacyjny: bool
  # kredyt i partycypacja NIEDOPUSZCZALNE — walidacja twarda
```

### 4.4. Parametry eksploatacyjne i rynkowe

```yaml
eksploatacja:
  koszt_eksploatacji_m2_rok: float
  odpis_remontowy_m2_rok: float
  ubezpieczenie_rocznie: float
  koszty_stale_zarzadu_rocznie: float
  pustostany_procent: float
  indeksacja_kosztow_rocznie: float
  indeksacja_czynszu_rocznie: float

parametry_zewnetrzne:
  wartosc_odtworzeniowa_m2: float   # obwieszczenie wojewody
  stopa_bazowa_ke: float            # rb
  stopa_referencyjna_ke: float      # r
  stopa_dyskontowa: float           # rd
  stopa_irs_bgk: float              # do rozsądnego zysku, z BIP BGK
  data_parametrow: date             # obowiązkowa — parametry się starzeją

inwestor:
  dostepny_wklad_wlasny: float
```

**Każdy parametr zewnętrzny musi mieć w YAML komentarz ze źródłem i datą.** Silnik ostrzega, gdy `data_parametrow` jest starsza niż 6 miesięcy.

---

## 5. Alokacja kosztów wspólnych

Koszty wspólne (grunt, infrastruktura, projekt, nadzór, koszty ogólne, rezerwa) dzielone są między pule **proporcjonalnie do PUM**, chyba że wejście wskazuje inny klucz.

Metodyka projektu wymaga liczenia **na m² PUM, nie na lokal** — inaczej porównania między wariantami o różnej strukturze mieszkań są zniekształcone. Wszystkie wskaźniki wyjściowe podawać per m² PUM.

Wartość gruntu przy wyliczaniu limitu grantu z art. 13 ust. 1 pkt 1 dzieli się tym samym kluczem. **Nie wolno przypisać pełnej wartości gruntu obu pulom.**

---

## 6. Trzy testy

### Test 1 — montaż

```
grant + kredyt + partycypacja + wkład_własny = koszty_przedsięwzięcia
```

Werdykt: **przechodzi**, gdy wymagany wkład własny ≤ `inwestor.dostepny_wklad_wlasny`.
Wynik liczbowy przy porażce: luka kapitałowa w PLN.

### Test 2 — zdolność czynszowa

```
przychód_czynszowy_netto ≥ koszty_eksploatacji + odpis_remontowy + rata_kredytu
```

Przychód liczony przy założonym obłożeniu, z czynszem **nie wyższym niż limit wiążący** (rozdz. 3.3). Jeżeli czynsz zakładany przekracza limit — twardy błąd walidacji, nie porażka testu.

Werdykt: **przechodzi**, gdy wskaźnik pokrycia obsługi długu ≥ 1,0 w każdym roku projekcji.
Wynik liczbowy przy porażce: luka czynszowa w zł/m²/mies. oraz rok pierwszego naruszenia.

**Dodatkowo raportować:** czynsz wymagany do domknięcia vs limit ustawowy vs czynsz rynkowy, jeśli podany. Rozjazd między limitem a poziomem potrzebnym do domknięcia montażu to centralne napięcie tego modelu i ma być widoczne wprost.

### Test 3 — rekompensata

```
EDB_grant + EDB_kredyt ≤ KN + RZ
```

Liczone przez cały okres powierzenia, z dyskontowaniem. Przy hybrydzie — zgodnie z rozstrzygnięciem kwestii otwartej z rozdz. 10.

Werdykt: **przechodzi**, gdy nadwyżka nie przekracza progu tolerancji (10% grant / 20% kredyt).
Wynik liczbowy przy porażce: nadwyżka w PLN oraz kwota podlegająca zwrotowi do Funduszu Dopłat.

### Werdykt zbiorczy

Projekt domyka się **wyłącznie gdy przechodzą wszystkie trzy**. Wynik ma zawsze wskazywać **wiążące ograniczenie** — który test i który parametr w nim decyduje.

---

## 7. Wrażliwość i punkt graniczny

### 7.1. Sweep udziału puli komunalnej

Przeliczenie dla `udzial_puli_komunalnej` od 0,0 do 1,0 z krokiem 0,05. Dla każdego punktu: trzy werdykty i wiążące ograniczenie.

**Wynik główny:** największy udział puli komunalnej, przy którym wszystkie trzy testy przechodzą. Jeżeli nie przechodzą przy żadnym udziale — wskazać, który test blokuje i przy jakiej wartości parametru wejściowego zacząłby przechodzić.

### 7.2. Wrażliwość jednoparametrowa

Dla każdego z parametrów: koszt budowy na m², oprocentowanie kredytu, czynsz w puli społecznej, czynsz płacony przez gminę, pustostany, wartość gruntu, stopa referencyjna — przeliczyć w zakresie ±20% i podać wpływ na werdykt zbiorczy.

Wynik: ranking parametrów według siły wpływu. Który parametr najtaniej przesuwa punkt graniczny.

### 7.3. Uwaga obliczeniowa

Wynik testu rekompensaty jest bardzo wrażliwy na stopę referencyjną, a horyzont sięga 30 lat. Wrażliwość na `r` liczyć zawsze, niezależnie od konfiguracji.

---

## 8. Arkusz wyjściowy

### 8.1. Zasada nadrzędna

**Formuły, nie wartości.** Arkusz z wklejonymi liczbami jest nieweryfikowalny. Każda komórka wynikowa ma być formułą odwołującą się do komórek założeń. Sprawdzian: zmiana założenia w zakładce wejściowej musi przeliczyć cały arkusz.

### 8.2. Zakładki

| Zakładka | Zawartość |
|---|---|
| `Zalozenia` | Wszystkie parametry wejściowe, każdy w osobnej komórce, z podaniem źródła i daty |
| `Alokacja` | Podział kosztów wspólnych na pule, klucz PUM |
| `Pula_spoleczna` | Projekcja rok po rok: przychody, koszty, rata, saldo |
| `Pula_komunalna` | To samo bez pozycji kredytowych |
| `Rekompensata` | KUOIG, PUOIG, dyskonto, KN, RZ, EDB, test nadwyżki — osobno dla każdej ścieżki |
| `Werdykty` | Trzy testy, wiążące ograniczenie, luki liczbowe |
| `Wrazliwosc` | Sweep udziału pul, punkt graniczny, ranking parametrów |
| `Podstawy_prawne` | Wykaz stałych z artykułami — żeby czytający mógł zweryfikować |

### 8.3. Konwencja formatowania

Wejścia i dźwignie scenariuszowe — tekst niebieski. Formuły — czarny. Odwołania międzyzakładkowe — zielony. Kluczowe założenia do uzupełnienia — żółte wypełnienie.

Kwoty `# ##0 zł`, procenty `0,0%` przechowywane jako ułamki, stawki czynszu z dwoma miejscami, lata jako tekst.

### 8.4. Weryfikacja przed wydaniem

Arkusz zawiera formuły, więc **obowiązkowo** przeliczyć przez `scripts/recalc.py` i zażądać zera błędów. Zielony przebieg dowodzi, że formuły się liczą, nie że są poprawne — dodatkowo sprawdzić ręcznie 2–3 formuły w każdej zakładce projekcji.

Unikać funkcji spoza standardu Excel 2007. Do wyszukiwań `INDEX`/`MATCH`, nie `XLOOKUP`.

---

## 9. Interfejs

### 9.1. Zakres

Jeden plik HTML serwowany lokalnie. Bez frameworków i bez zależności zewnętrznych z sieci.

**Widok główny:** suwak udziału puli komunalnej jako element centralny, pod nim trzy wskaźniki werdyktów przeliczane na żywo, obok wykres pokazujący położenie punktu granicznego.

**Widok parametrów:** pola edycyjne pogrupowane jak sekcje YAML, z walidacją na bieżąco.

**Zatwierdzenie:** przycisk generujący arkusz i zapisujący użyty zestaw parametrów jako YAML z datą — żeby dało się odtworzyć, na czym liczono.

### 9.2. Czego w UI nie robić

Nie chować wiążącego ograniczenia za kliknięciem. Gdy montaż się nie domyka, powód ma być widoczny od razu.

Nie pokazywać werdyktu bez liczby. „Nie spina się" bez podania luki jest bezużyteczne w negocjacji.

Nie wyświetlać wyniku testu rekompensaty bez zastrzeżenia, że wiążące jest wyliczenie Banku.

---

## 10. Kwestie otwarte — nie rozstrzygać w kodzie

Poniższe wymagają potwierdzenia w BGK. Implementacja ma je obsłużyć jako **przełącznik konfiguracyjny z jawnym oznaczeniem, że wartość domyślna jest założeniem**, a nie zaszywać jedno rozwiązanie.

**10.1. Czy hybryda to jedno przedsięwzięcie, czy dwa.** Art. 13 ust. 1a przewiduje, że gdy przedsięwzięcie obejmuje koszty objęte różnymi limitami, wsparcie nie może przekroczyć 45% — z wyraźnym wyjątkiem dla przypadków z art. 5a ust. 1. Konstrukcja wyjątku daje się czytać dwojako: albo pula 80% jest wyłączona spod ściągnięcia do 45%, albo ma być odrębnym przedsięwzięciem.

Domyślnie przyjąć **dwa odrębne przedsięwzięcia** — dwa wnioski, dwa okresy powierzenia, dwa testy rekompensaty. Za tym czytaniem przemawia art. 5a ust. 3: kredyt SBC udzielany jest na przedsięwzięcie, nie na wydzieloną pulę lokali, więc wspólne przedsięwzięcie z kredytem byłoby wewnętrznie sprzeczne.

Przełącznik: `hybryda_jako_jedno_przedsiewziecie: false`.

**10.2. Zbieg progów partycypacyjnych 10–15%.** Patrz rozdz. 3.4. Silnik zwraca ostrzeżenie, nie werdykt.

**10.3. Wymóg umowy z gminą przy kredycie SBC dla prywatnego SIM.** Informator BGK wiąże ten wymóg z SIM, w których gminy dysponują ponad 50% głosów. Zakres dla prywatnego SIM do potwierdzenia.

---

## 11. Testy jednostkowe — minimum

Silnik operuje na pieniądzach i przepisach, więc testy nie są opcjonalne.

**Przypadki brzegowe stałych prawnych:**
- grant społeczny bez gruntu inwestora → dokładnie 35% kosztów
- grant społeczny przy gruncie wartym ponad 10% kosztów → dokładnie 45%
- kredyt w puli komunalnej → wyjątek walidacyjny
- bonus +5 pp przy aktywnym kredycie → wyjątek walidacyjny
- udział wsparcia 44,9% → limit czynszu 4,0%; 45,0% → 3,5%; 75,0% → 2,5%

**EDB:**
- dotacja → EDB równy kwocie
- kredyt z `rp = r` → EDB równy zeru
- kredyt z `rp > r` → wyjątek
- kredyt z `T = 0` → wzór redukuje się do samego drugiego członu

**Rekompensata:**
- grunt JST jako przychód obniża KN względem identycznego wariantu z gruntem inwestora
- nadwyżka 9,9% w ścieżce grantowej → przechodzi; 10,1% → zwrot

**Regresyjne:** dla każdego realnego przypadku wprowadzonego do kalibracji — zamrożony wynik jako test regresji. Zmiana silnika, która przesuwa wynik zweryfikowanego przypadku, ma wysypać testy.

---

## 12. Kalibracja na przypadkach realnych

Silnik powstaje na wartościach przykładowych. Po zbudowaniu wprowadzane są realne projekty jako testy weryfikacyjne.

Dla każdego przypadku kalibracyjnego zapisać: komplet parametrów wejściowych w YAML, oczekiwany werdykt, źródło danych rzeczywistych oraz — jeżeli dostępne — wyliczenie BGK do porównania.

Rozbieżność z wyliczeniem Banku jest sygnałem błędu w silniku, nie w Banku. Traktować jako błąd krytyczny do wyjaśnienia przed dalszym rozwojem.

---

## 13. Zastrzeżenia do umieszczenia w README, UI i arkuszu

Narzędzie wspiera odsiewanie wariantów przed złożeniem wniosku i rozmowę z gminą o proporcji pul. Nie zastępuje wyliczenia BGK, opinii prawnej ani doradztwa podatkowego.

Stałe prawne odczytano z tekstów jednolitych obowiązujących w sierpniu 2026 r. Przed każdym naborem sprawdzić aktualność: parametry programów zmieniają się między edycjami, a stopy zewnętrzne w ogóle nie są elementem prawa.

Kwestie z rozdziału 10 pozostają nierozstrzygnięte i mają wpływ na wynik.

---

## Wykaz podstaw prawnych

- Ustawa z 26 października 1995 r. o społecznych formach rozwoju mieszkalnictwa — t.j. Dz.U. 2025 poz. 1273, ze zm. Dz.U. 2026 poz. 39 i poz. 986
- Ustawa z 8 grudnia 2006 r. o finansowym wsparciu niektórych przedsięwzięć mieszkaniowych — t.j. Dz.U. 2026 poz. 511
- Ustawa z 25 lipca 2025 r. o zmianie ustawy o społecznych formach rozwoju mieszkalnictwa — Dz.U. 2025 poz. 1077
- Rozporządzenie RM z 20 października 2015 r. o warunkach finansowania zwrotnego — t.j. Dz.U. 2021 poz. 766, ze zm. Dz.U. 2024 poz. 1732
- Rozporządzenie MFiG z 29 grudnia 2025 r. o finansowym wsparciu — Dz.U. 2025 poz. 1897
- Rozporządzenie RM z 11 sierpnia 2004 r. o obliczaniu wartości pomocy publicznej — t.j. Dz.U. 2018 poz. 461
- Rozporządzenie MIiR z 4 marca 2019 r. o standardach — Dz.U. 2019 poz. 457
