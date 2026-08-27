# Luki w specyfikacji i przyjęte założenia

Zasada nadrzędna projektu brzmi: **nie zgaduj liczb pochodzących z przepisów.**
Ten plik jest listą miejsc, w których specyfikacja nie dała wartości albo
rozstrzygnięcia, a implementacja i tak musiała się jakoś zachować.

Każda pozycja jest zrealizowana jako **przełącznik z jawnym oznaczeniem
założenia**, a nie jako zaszyta reguła. Silnik emituje dla nich ostrzeżenie,
które trafia do UI, do arkusza i do wyniku API.

Kolejność odpowiada temu, jak mocno pozycja przesuwa wynik.

---

## 1. Brak wzoru na rozsądny zysk (RZ) — **luka, nie kwestia otwarta**

**Czego brakuje.** Rozdz. 3.5 specyfikacji wskazuje źródło stopy: IRS dla
kontraktu 20-letniego na bazie WIBOR 3M, publikowany przez BGK w BIP przed
naborem (§ 6 ust. 5 rozp. Dz.U. 2025 poz. 1897; § 12 ust. 10 rozp. Dz.U. 2021
poz. 766). Nie podaje jednak **wzoru** — do czego tę stopę przyłożyć.

**Co zrobiono.** Przełącznik `przelaczniki.metoda_rozsadnego_zysku`:

| Wartość | Znaczenie |
|---|---|
| `kapital_zaangazowany` (domyślna) | RZ = zdyskontowany stopą bazową KE strumień `stopa_irs_bgk × wkład własny puli` przez okres powierzenia |
| `kwota_wprost` | RZ podany wprost w `rekompensata.rozsadny_zysk_kwota`, dzielony kluczem PUM |

**Dlaczego tak.** Wariant domyślny mierzy godziwy zwrot ze środków własnych
faktycznie zaangażowanych w przedsięwzięcie i dyskontuje go tą samą stopą co
strumień kosztów netto, żeby obie strony nierówności `RUOIG ≤ KN + RZ` były
porównywalne. Wariant `kwota_wprost` istnieje po to, żeby po potwierdzeniu w
BGK dało się wpisać liczbę z Banku bez zmiany kodu.

**Do potwierdzenia w BGK.** Podstawa naliczenia (kapitał własny czy całość
zaangażowanego kapitału), sposób dyskontowania, moment ustalenia stopy.

---

## 2. Katalog kosztów UOIG nie jest przytoczony

**Czego brakuje.** Rozdz. 3.5 odsyła do art. 5 ust. 7–8 ustawy z 8.12.2006
("Katalog kosztów UOIG") i art. 5 ust. 9 ("Katalog przychodów UOIG"), ale ich
nie przytacza. Wyliczona jest wyłącznie pozycja gruntowa (asymetria) oraz
wkład we wspólne koszty stałe w ścieżce kredytowej (§ 12 ust. 3 rozp. 766).

**Co zrobiono.** Do kosztów bieżących UOIG weszły pozycje, które specyfikacja
podaje wprost w danych wejściowych: eksploatacja, odpis remontowy,
ubezpieczenie, koszty stałe zarządu, odsetki od kredytu. Do przychodów —
czynsz netto po pustostanach. Grunt wchodzi wyłącznie własną regułą asymetrii.

**Czego świadomie NIE ujęto.** Partycypacji ani rezerwy na jej zwrot. Jest to
kapitał zwrotny, nie przychód i nie koszt świadczenia usługi; ujęcie jej po
jednej stronie bez drugiej zniekształcałoby KN. **Do potwierdzenia w BGK.**

---

## 3. Ujęcie nakładu inwestycyjnego w kosztach netto — **przesuwa wynik o rząd wielkości**

**Czego brakuje.** Skoro katalog z pkt 2 nie jest przytoczony, nie wiadomo, czy
i jak nakład inwestycyjny wchodzi do KUOIG. To jest najsilniejsza dźwignia w
całym teście 3.

**Co zrobiono.** Przełącznik `przelaczniki.koszty_inwestycyjne_w_kn`:

| Wartość | Znaczenie |
|---|---|
| `amortyzacja` (domyślna) | roczny odpis wg `okres_amortyzacji_budynkow_lat` |
| `amortyzacja_w_okresie_powierzenia` | nakład rozłożony równo na lata okresu powierzenia |
| `naklad_poczatkowy` | cały nakład w roku pierwszym |
| `pominiete` | wyłącznie koszty bieżące |

Podstawą jest zawsze koszt przedsięwzięcia **bez gruntu** — grunt ma własną
regułę i ujęty dodatkowo w nakładzie trafiałby do KN dwa razy.

**Skala wpływu.** Na przykładzie wzorcowym (3000 m² PUM, koszty 29,05 mln zł)
różnica między `amortyzacja` przy 100-letnim okresie a `naklad_poczatkowy`
decyduje o tym, czy test 3 przechodzi, czy kończy się wielomilionowym zwrotem
do Funduszu Dopłat. Oba przykłady w `przyklady/` różnią się m.in. tym
ustawieniem i dają przeciwne werdykty.

**Do potwierdzenia w BGK — priorytet najwyższy.**

---

## 4. Hybryda: jedno przedsięwzięcie czy dwa (kwestia otwarta 10.1 specyfikacji)

**Co zrobiono.** Przełącznik `przelaczniki.hybryda_jako_jedno_przedsiewziecie`,
domyślnie `false` — dwa odrębne przedsięwzięcia, dwa wnioski, dwa okresy
powierzenia, dwa testy rekompensaty o różnych progach tolerancji (20% w
ścieżce kredytowej, 10% w grantowej). Przy `true` łączne wsparcie ściągane
jest do 45% kosztów (art. 13 ust. 1a), a test nadwyżki liczony jest raz.

Zgodnie ze wskazaniem specyfikacji, za odczytem domyślnym przemawia art. 5a
ust. 3: kredyt SBC udzielany jest na przedsięwzięcie, nie na wydzieloną pulę
lokali, więc wspólne przedsięwzięcie z kredytem byłoby wewnętrznie sprzeczne.

---

## 5. Grunt JST a limit gruntowy grantu

**Czego brakuje.** Art. 13 ust. 1 pkt 1 mówi o gruncie „będącym we władaniu
inwestora". Grunt wniesiony aportem przez gminę jest po wniesieniu we władaniu
inwestora, ale nie pochodzi z jego majątku. Specyfikacja tego nie rozstrzyga —
rozstrzyga jedynie ujęcie gruntu JST w **rekompensacie** (przychód).

**Co zrobiono.** Przełącznik `przelaczniki.grunt_jst_liczy_sie_do_limitu_grantu`,
domyślnie `true` (odczyt literalny). Niezależnie od jego ustawienia w ścieżce
grantowej grunt JST pozostaje **przychodem** inwestora i obniża KN
(art. 5 ust. 9 pkt 4) — te dwie reguły są rozłączne.

---

## 6. Bonus +5 pp a próg gruntowy

**Czego brakuje.** Art. 13 ust. 4 dodaje 5 punktów procentowych, ale nie mówi,
czy podnosi tylko limit górny (45% → 50%), czy oba progi konstrukcji z art. 13
ust. 1 pkt 1 (35% → 40% i 45% → 50%).

**Co zrobiono.** Przyjęto odczyt literalny: bonus podnosi wyłącznie limit
górny, próg gruntowy zostaje na 35%. Silnik emituje ostrzeżenie
`ZALOZENIE_BONUS_A_PROG_GRUNTOWY` **tylko wtedy, gdy przypadek faktycznie
wystąpi** — czyli przy bonusie w puli społecznej bez kredytu. W puli komunalnej
kwestia nie powstaje, bo art. 13 ust. 1 pkt 3 lit. c nie zawiera warunku
gruntowego.

---

## 7. Pustostany w puli komunalnej

**Czego brakuje.** Specyfikacja daje jeden wskaźnik `pustostany_procent` i nie
mówi, czy obciąża on pulę, której najemcą jest gmina.

**Co zrobiono.** Przełącznik `przelaczniki.pustostany_takze_w_puli_komunalnej`,
domyślnie `false` — ryzyko pustostanu zostaje po stronie gminy. To założenie
modelowe, nie przepis; sprawdź, co mówi projekt umowy z gminą.

---

## 8. Parametry zewnętrzne dodane ponad szkic YAML ze specyfikacji

Trzy wartości są konieczne do policzenia tego, czego specyfikacja wymaga, a nie
ma ich w szkicu z rozdz. 4. Silnik **nie podstawia dla nich wartości domyślnych** —
ich brak zatrzymuje obliczenie:

| Parametr | Do czego | Podstawa |
|---|---|---|
| `waloryzacja_partycypacji_rocznie` | rezerwa na zwrot partycypacji rośnie wskaźnikiem ceny 1 m² GUS | art. 29a ust. 3 ustawy z 26.10.1995 |
| `okres_amortyzacji_budynkow_lat` | limituje okres powierzenia w ścieżce kredytowej; podstawa ujęcia `amortyzacja` | § 11 rozp. Dz.U. 2021 poz. 766 |
| `koszty.stawka_vat` | podstawa grantu przy VAT nieodliczalnym | art. 13 ust. 3 ustawy z 8.12.2006 |

Dodano też `rekompensata.wsparcie_rfrm` i `rekompensata.wartosc_dokumentacji_bgk`
(§ 7 ust. 7 rozp. 1897) — muszą być podane jawnie, choćby zerem.

---

## 9. Uproszczenia, o których trzeba wiedzieć

- **VAT** stosowany jest jedną stawką do wszystkich pozycji kosztowych, bo
  wejście podaje jedną `stawka_vat`. Realne przedsięwzięcie ma różne stawki na
  gruncie, robotach i usługach.
- **Partycypacja** liczona jest od kosztu przedsięwzięcia przypadającego na
  lokale puli społecznej (z udziałem w kosztach wspólnych), zgodnie z metodyką
  „wszystko per m² PUM". Art. 29a ust. 2 mówi o „koszcie budowy lokalu" —
  do potwierdzenia, czy chodzi o koszt pełny czy sam koszt budowy.
- **Zakładka `Wrazliwosc`** w arkuszu jest migawką z silnika, nie żywymi
  formułami. Każdy punkt sweepu to osobne przeliczenie całego modelu — nie da
  się go złożyć z formuł jednej zakładki. Żywy model siedzi w zakładkach
  `Alokacja`, `Pula_*`, `Rekompensata` i `Werdykty`; te przeliczają się w całości
  po zmianie dowolnego założenia.
- **Kwota do zwrotu** przy przekroczeniu progu tolerancji to cała nadwyżka, nie
  tylko część ponad próg. Próg czytany jest jako granica dopuszczalności, nie
  jako kwota wolna. **Do potwierdzenia w BGK.**

---

## 10. Kwestia otwarta 10.3 specyfikacji — poza zakresem silnika

Wymóg umowy z gminą przy kredycie SBC dla prywatnego SIM (Informator BGK wiąże
go z SIM, w których gminy mają ponad 50% głosów) nie jest parametrem
obliczeniowym i nie został zaimplementowany. Jest to warunek dopuszczalności
do sprawdzenia przed złożeniem wniosku, nie element montażu finansowego.

---

## 11. Grunt — cztery kanały, trzy pytania do BGK i trzy założenia modelowe

Uzupełnienie nr 2 do specyfikacji rozbiło grunt na dwa poziomy (pochodzenie ×
forma) i cztery kanały oddziaływania. Matryca skutków siedzi w
`prawo.MATRYCA_GRUNTU`, po jednym wierszu na formę, z oznaczeniem pewności
każdego skutku: **Z** — odczytane w przepisie, **W** — wniosek z odczytanych
przepisów, **?** — wymaga potwierdzenia w BGK.

### 11.1. Trzy kwestie oznaczone [?] — przełączniki z jawnym założeniem

| Nr | Przełącznik | Domyślnie | Czego dotyczy |
|---|---|---|---|
| 9.1 | `lokal_za_grunt_jest_przychodem_uoig` | `false` | Czy grunt nabyty w trybie „lokal za grunt" jest przychodem usługi publicznej. Przyjęto, że **nie** — to nabycie, a nie wniesienie przez JST. |
| 9.2 | `uzytkowanie_wieczyste_jest_przychodem_uoig` | `true` | Czy wartość prawa użytkowania wieczystego ustanowionego przez gminę jest przychodem. Przyjęto wariant **ostrożniejszy**: jest. |
| 9.3 | `pasmo_liczone_od_wartosci_z_operatu` | `true` | Czy bonifikata przy sprzedaży przez gminę obniża wartość przyjmowaną do pasma dotacji. Przyjęto, że **nie** — art. 13 ust. 1 pkt 1 mówi o wartości prawa, nie o cenie nabycia. |

Odczyt alternatywny kwestii 9.3 wymaga podania `grunt.cena_nabycia`. Silnik nie
zgaduje wysokości bonifikaty — jej brak przy wyłączonym przełączniku zatrzymuje
obliczenie.

### 11.2. Limit z § 12 ust. 7 rozp. 766 jest samozwrotny

Przepis ogranicza zaliczenie wartości gruntu wniesionego jako wkład niepieniężny
do 20% **całkowitych kosztów przedsięwzięcia** — a wartość gruntu jest składnikiem
tych kosztów. Model rozwiązuje warunek tak, żeby udział gruntu w podstawie
faktycznie przyjętej wyszedł dokładnie na limicie:

    u = K_bez_gruntu × limit / (1 − limit)

**Odczyt alternatywny:** 20% kosztów liczonych z pełną, nieobciętą wartością
gruntu. Daje kwotę wyższą, a udział w podstawie faktycznie przyjętej — poniżej
limitu. Do potwierdzenia w BGK.

### 11.3. Kanały B i C wykluczają się

Grunt, za który inwestor nie zapłacił, nie jest kosztem świadczenia usługi;
grunt, który kupił, nie jest jego przychodem. Model nigdy nie ujmuje tej samej
wartości po obu stronach rachunku kosztów netto — gdyby to robił, efekt netto
byłby zerowy i asymetria z art. 5 ust. 9 pkt 4 zniknęłaby z wyniku. Dotyczy to
także ścieżki kredytowej: aport gminy pozostaje tam przychodem, a nie kosztem
limitowanym.

### 11.4. „Lokal za grunt" — z której puli pochodzą lokale dla gminy

Specyfikacja mówi, że PUM dostępne na wynajem maleje o powierzchnię lokali
przekazywanych gminie, ale **nie wskazuje puli**, z której pochodzą. Model
pomniejsza powierzchnię przychodową obu pul proporcjonalnie, kluczem PUM — tym
samym, którym dzieli koszty wspólne. **ZAŁOŻENIE modelowe**, sygnalizowane
ostrzeżeniem `ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM`.

Konsekwencje przyjęte razem z nim:

- koszt przedsięwzięcia pozostaje pełny — te lokale trzeba wybudować,
- lokale oddane gminie nie obciążają SIM kosztem eksploatacji ani odpisem
  remontowym, bo nie są już jej lokalami; ubezpieczenie i koszty zarządu zostają
  na kluczu PUM, bo są kosztem spółki, nie lokalu,
- podstawa alternatywna limitu czynszu z art. 28 ust. 2b liczona jest od **pełnej**
  powierzchni wybudowanej. Dzielenie pełnego kosztu przez zmniejszoną powierzchnię
  podniosłoby limit czynszu, a przepis mówi o koszcie budowy lokalu, nie o koszcie
  projektu rozłożonym na lokale pozostałe.

### 11.5. Hipoteka na nieruchomości wnoszonej aportem

§ 12 ust. 6 rozp. 766 zakazuje wnoszenia aportem nieruchomości obciążonej
hipoteką — przepis dotyczy wprost ścieżki finansowania zwrotnego. Kalkulator
blokuje ten wariant **także poza tą ścieżką**, bo hipoteka na gruncie wniesionym
do spółki obciąża majątek SIM niezależnie od źródła finansowania. To jest
rozszerzenie zakresu przepisu, przyjęte świadomie i zgodnie z rozdz. 5
uzupełnienia nr 2, które każe traktować ten warunek zerojedynkowo.

### 11.6. Kanał D nie ma podstawy w przepisie

Podział wkładu na część rzeczową i pieniężną jest klasyfikacją modelu, nie
kategorią ustawową. Wynika z prostej obserwacji: grunt wniesiony aportem siedzi
w kosztach przedsięwzięcia, ale nikt za niego nie płaci gotówką, więc test
kapitałowy — pytający o pieniądze — nie może go do tych pieniędzy doliczać.
Aport gminy trafia do osobnej pozycji, bo nie jest kapitałem inwestora i nie
nalicza się od niego rozsądnego zysku.

### 11.7. Wkład rzeczowy potrafi przewyższyć zapotrzebowanie

Dotacja 80% w puli komunalnej (art. 13 ust. 1 pkt 3 lit. c) plus wniesiony grunt
domykają tę pulę z zapasem, jeżeli działka jest droga. Wymagana gotówka wychodzi
wtedy ujemna, co nic nie znaczy dla inwestora — nie da się „wyjąć" wartości
gruntu z montażu. Test kapitałowy podaje w takim wypadku zero i nazywa zapas
osobno, zamiast pokazywać ujemną kwotę.

Kredyt ograniczany jest wkładem rzeczowym **tej samej puli**, nie obu. Przy
odczycie domyślnym hybryda to dwa odrębne przedsięwzięcia, a kredyt finansuje
przedsięwzięcie społeczne — grunt wniesiony do puli komunalnej domyka pulę
komunalną i nie zwalnia zdolności kredytowej po stronie społecznej. Przy
włączonym przełączniku `hybryda_jako_jedno_przedsiewziecie` to rozróżnienie
traci sens i jest kandydatem do przeglądu.

---

## 12. Czynsz rynkowy — sufit, którego silnik nie policzy

Errata nr 1 do specyfikacji interakcji. Poprzednia wersja narzędzia pokazywała
na wykresie „stawkę rynkową 34,00 zł/m²" — liczbę wpisaną ręcznie w pliku
przykładowym, bez źródła, bez daty i bez możliwości zmiany w interfejsie.
Wyglądała jak dana. **Usunięta.**

### 12.1. Dlaczego nie da się jej wyliczyć

Narzędzie nie pyta o lokalizację w stopniu pozwalającym cokolwiek wywnioskować,
a czynsze najmu różnią się między miejscowościami wielokrotnie. Każde
oszacowanie byłoby zgadywaniem, a liczba bez źródła wchodzi do rozmowy z gminą
jako argument. Stawka jest więc **parametrem wejściowym** — sekcja `rynek`,
pole opcjonalne, `zrodlo` obowiązkowe gdy podano wartość.

Przy pustym polu narzędzie **zadaje pytanie zamiast podawać liczbę**. To jest
uczciwsze i bardziej użyteczne: zamienia brakującą daną w decyzję, którą
użytkownik i tak musi podjąć — a on tę odpowiedź zna, tylko nie ma jej w arkuszu.

### 12.2. Podłoga czynszowa liczona osobno dla każdej puli

Model odpowiada na pytanie „czy podłoga mieści się pod najniższym z sufitów",
a podłoga znaczy co innego w każdej puli, bo każda ma inne instrumenty:

- **pula społeczna** — stawka, przy której kredyt uniesie całą lukę kapitałową
  przedsięwzięcia, czyli przy której inwestor nie musi dokładać kapitału;
- **pula komunalna** — stawka pokrywająca koszty bieżące. Zerowego wkładu
  własnego nie da się w niej osiągnąć **żadną stawką**: kredyt jest wykluczony
  (art. 5a ust. 3), więc nie ma czym zamienić przyszłego czynszu na kapitał
  początkowy. 20% kosztów poza dotacją to luka strukturalna, którą pokrywa
  kapitał — i tak jest to nazwane w podpisie wykresu.

### 12.3. Hybryda — dwie niewiadome, jedno równanie

Rozstrzygnięcie: **czynsz komunalny zadany, społeczny domyka.** Uzasadnienie jest
praktyczne, nie matematyczne — stawkę komunalną negocjuje się z gminą i zapisuje
w umowie, a limit przy dotacji 80% i tak przyciska ją do 2,5% wartości
odtworzeniowej rocznie.

Konsekwencja, którą trzeba przyjąć razem z tym rozstrzygnięciem: czynsz społeczny
domyka **całe przedsięwzięcie**, nie samą pulę społeczną. Kredyt jest jedynym
instrumentem zamieniającym przyszły czynsz na kapitał początkowy i przysługuje
wyłącznie puli społecznej, więc ciężar obu pul spada na najemców społecznych.
Stąd monotoniczny wzrost wymaganej stawki wraz z udziałem puli komunalnej.

Skutek uboczny wart odnotowania: **stawka komunalna nie wpływa na wymagany czynsz
społeczny.** Czynsz komunalny nie zamienia się w kapitał początkowy, więc luka,
którą musi pokryć kredyt, od niego nie zależy. To wynika wprost z przyjętego
rozstrzygnięcia, ale bywa zaskakujące.

### 12.4. Rozbieżność w samej erracie

Rozdz. 3.3 podaje jako jedną z dźwigni przy zbyt wysokim czynszu „większy udział
mieszkań komunalnych". Rozdz. 5.2 tej samej erraty mówi coś przeciwnego i to on
jest zgodny z modelem: wzrost udziału puli komunalnej **wypycha czynsz społeczny
w górę**, bo pula komunalna wnosi mniej. Na przykładzie z repozytorium wymagana
stawka rośnie z 21,31 zł przy zerowym udziale do 33,48 zł przy 60%.

W komunikacie zaimplementowano wersję zgodną z rozdz. 5.2 i z liczbami —
narzędzie podpowiada **mniejszy** udział mieszkań komunalnych.

### 12.5. Brak stawki domykającej to ograniczenie kapitałowe, nie rynkowe

Gdy potrzebny kredyt przebija ustawowe 80% kosztów, montażu nie domknie żadna
stawka czynszu. Model **nie raportuje tego jako przebicia sufitu rynkowego** —
to inne ograniczenie i inne dźwignie. Test rynkowy jest wtedy nierozstrzygnięty
(`None`), a nie negatywny.

### 12.6. Stawka akceptowana przez gminę — świadomie niewdrożona

Errata rozdz. 6.4 przewiduje opcjonalny parametr
`czynsz_akceptowany_przez_gmine_m2_mies` jako drugą linię przerywaną w wierszu
komunalnym, z **priorytetem niskim** i wskazówką „wdrożyć po uruchomieniu
mechanizmu dla puli społecznej — bez sygnału z negocjacji nie wiadomo, czy
parametr jest w praktyce potrzebny". Zgodnie z tym nie został wdrożony.
Konstrukcja jest identyczna jak dla stawki rynkowej, więc dołożenie będzie proste.

---

## 13. Baza naliczania dotacji — grunt w podstawie czy poza nią

**Kwestia otwarta, nierozstrzygnięta. Implementacja przyjmuje jeden odczyt i go
oznacza; wymaga potwierdzenia w BGK.**

Model liczy dotację od kosztów przedsięwzięcia **zawierających wartość gruntu**.
Na scenariuszu odniesienia (PUM 3000 m², grunt 2,8 mln zł, udział komunalny 30%)
daje to bazę 29,05 mln zł i dotację 16,05 mln zł. Odczyt alternatywny — baza bez
gruntu, przy zachowaniu gruntu jako limitu części ponad próg gruntowy — dałby
dotację o **1,48 mln zł niższą**.

### 13.1. Skąd wziął się przyjęty odczyt

Nie z przepisu i nie z osobnego rozstrzygnięcia przy implementacji, tylko
z katalogu kosztów w specyfikacji: rozdz. 8 wymienia grunt wśród kosztów
wspólnych dzielonych kluczem PUM, a tożsamość domykająca montaż brzmi
`grant + kredyt + partycypacja + wkład_własny = koszty_przedsięwzięcia`.
Specyfikacja posługuje się nazwą `koszty_kwalifikowane`, ale nigdzie jej nie
definiuje — a testy odbiorcze nie rozstrzygają, bo sprawdzają wariant bez gruntu
inwestora, w którym obie bazy są identyczne.

Innymi słowy: implementacja poszła za katalogiem kosztów, a niejednoznaczność
nie została wtedy odnotowana. To jest luka w tym dokumencie, którą trzeba było
opisać przy etapie 3.

### 13.2. Argument za odczytem przeciwnym

Formularz rozliczenia z rozp. Dz.U. 2025 poz. 1897 wykazuje osobno „faktyczny
koszt przedsięwzięcia" i osobno „wartość gruntu stanowiącego własność inwestora",
a w strukturze finansowania zalicza wartość gruntu do środków własnych inwestora.
Czyta się to tak, że grunt jest **wkładem i limitem pasma ponad próg gruntowy**,
a nie pozycją bazy.

Uwaga metodyczna: to argument z formularza, nie z brzmienia przepisu — a formularz
może odzwierciedlać sposób wykazywania, nie definicję podstawy. Rozstrzygnięcia
nie da się oprzeć na samym układzie rubryk.

### 13.3. Napięcie wewnątrz odczytu przeciwnego

Gdyby grunt wypadł z bazy, tożsamość domykająca montaż przestałaby się zgadzać:
działkę trzeba sfinansować, więc pozostaje po stronie kosztów, choć dotacja jej
nie obejmuje. To samo w sobie nie jest sprzeczne — znaczy tylko, że grunt pokrywa
inwestor — ale wymaga rozdzielenia „kosztów przedsięwzięcia" na potrzeby dotacji
i na potrzeby montażu. Model dziś tego rozdziału nie ma.

**Do rozstrzygnięcia w BGK przed użyciem wyniku w rozmowie o finansowaniu.**
Wynik niesie ostrzeżenie `ZALOZENIE_GRUNT_W_BAZIE_DOTACJI` z kwotą różnicy.

---

## 14. Nadwyżka rekompensaty — okres, do którego odnosi się próg

Próg tolerancji (10% w ścieżce grantowej, 20% w kredytowej) odnosi się do
**średniej rocznej** rekompensaty. RUOIG i koszty netto są wielkościami całego
okresu powierzenia, więc nadwyżka też jest wieloletnia.

Poprzednia wersja porównywała nadwyżkę z 25–30 lat z progiem opartym na jednym
roku, co zawyżało wskaźnik dwudziestopięcio- do trzydziestokrotnie: na scenariuszu
odniesienia banner podawał „378% średniej rocznej" przy przekroczeniu limitu
o 14,4%. Po naprawie wskaźnik wynosi 12,6%.

Werdykt w tym scenariuszu się nie zmienił — pula komunalna ma 12,5% przy progu
10% i nadal nie przechodzi — ale przy nadwyżce granicznej poprzednia wersja
dawała fałszywy alarm.

**Kwestia otwarta:** przepis odnosi próg do **okresu rozliczeniowego**, a model
nie odwzorowuje jego długości — liczy jeden strumień dla całego okresu
powierzenia. Annualizacja jest przybliżeniem: gdyby nadwyżka rozłożyła się
nierówno, w pojedynczym okresie rozliczeniowym mogłaby przekroczyć próg mimo
poprawnego wyniku w skali całego okresu. Wynik niesie ostrzeżenie
`ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI`.

---

## 15. Podział udziałów przy aporcie gminy

Aport gminy nie jest tylko pozycją finansowania — za wniesiony grunt gmina
obejmuje udziały. O proporcji nie decyduje niczyja wola, tylko relacja wartości
działki do kapitału, który musi wyłożyć inwestor.

Na scenariuszu odniesienia gmina wnosi 2,8 mln zł przy 903 tys. zł od inwestora,
czyli obejmuje **75,6% kapitału spółki** — większość na zgromadzeniu wspólników,
z prawem decydowania między innymi o stawkach czynszu. Komunikat „gmina obejmie
udziały i stanie się wspólnikiem" był prawdziwy, ale nie oddawał skali.

**Uproszczenia przyjęte w tym wyliczeniu:**

- kapitał spółki utożsamiony jest z wkładem domykającym montaż (gotówka inwestora
  plus wkłady rzeczowe). Realna umowa spółki może część aportu odnieść na agio,
  a wtedy udział będzie inny;
- aport wyceniony jest wartością z operatu. Wycena na potrzeby objęcia udziałów
  bywa niższa;
- model nie zna umowy spółki, więc nie uwzględnia uprzywilejowania udziałów ani
  progów kwalifikowanych. Próg 50% to zwykła większość z prawa spółek, nie
  z ustaw o wsparciu mieszkalnictwa.

Wynik traktować jako **rząd wielkości i sygnał ostrzegawczy**, nie jako ustalenie
korporacyjne.

---

## 16. Co ogranicza kwotę kredytu — i dlaczego czynsz przestaje być dźwignią

Kredyt liczony jest jako **największy, jaki uniesie założony czynsz** (rozdz. 2.2
uzupełnienia UI), a nie z `pula_spoleczna.kredyt.udzial_docelowy`. Tryb
automatyczny jest domyślny i to on obsługuje interfejs; przełącznik „ustal kredyt
samodzielnie" jest wyłączony.

Kwota jest ścinana przez **trzy ograniczenia, z których wiąże najniższe**. Na
scenariuszu odniesienia (aport gminy, czynsz 22 zł):

| Ograniczenie | Kwota |
|---|---|
| udźwig czynszowy — ile uniesie 22 zł | 7 536 580 zł |
| limit ustawowy 80% kosztów puli społecznej | 16 268 000 zł |
| **potrzeba — ile kredytu w ogóle brakuje** | **5 230 750 zł** |

Wiąże potrzeba. Dotacja 16,05 mln zł, partycypacja 4,07 mln zł i aport 2,8 mln zł
pokrywają razem 79% kosztów 29,05 mln zł — nikt nie zaciąga kredytu większego niż
brakująca reszta. Stąd 18% kosztów, a nie 80%: to nie jest ograniczenie ustawowe
ani czynszowe, tylko brak zapotrzebowania.

### 16.1. Zależność czynsz → wkład własny jest NIEROSNĄCA, nie ściśle malejąca

Podniesienie czynszu obniża wymagany wkład **dopóki wiąże udźwig czynszowy**.
Gdy zaczyna wiązać potrzeba, dalsze podnoszenie stawki nic nie daje — kredyt już
pokrywa całą brakującą resztę puli społecznej. Na scenariuszu odniesienia:

| Czynsz | Kredyt | Wkład gotówkowy |
|---|---|---|
| 8 zł | 186 660 zł | 5 947 090 zł |
| 12 zł | 2 525 867 zł | 3 607 883 zł |
| 16 zł | 4 530 152 zł | 1 603 598 zł |
| 20 zł | 5 230 750 zł | 903 000 zł |
| 22–32 zł | 5 230 750 zł | **903 000 zł (bez zmian)** |

Plateau nie jest błędem. Zostaje na nim dokładnie
`Wynik.luka_poza_zasiegiem_czynszu` — luka puli komunalnej, której żaden czynsz
nie domknie, bo pula komunalna nie ma kredytu (art. 5a ust. 3), a tylko kredyt
zamienia przyszły czynsz na kapitał początkowy.

Test regresji sprawdza **nierosnącość** w całym zakresie oraz ścisły spadek
w części, gdzie wiąże udźwig. Test wymagający ścisłego spadku wszędzie byłby
błędny — wymuszałby zaciąganie kredytu ponad potrzebę.

### 16.2. „Czynsz wymagany" znaczy co innego w każdym wierszu

- **pula społeczna** — stawka, przy której kredyt uniósłby lukę kapitałową całego
  przedsięwzięcia (errata nr 1, rozdz. 5: czynsz społeczny domyka całość);
- **pula komunalna** — stawka pokrywająca koszty bieżące. Zerowego wkładu nie da
  się tam osiągnąć żadną stawką.

Nawet w trybie automatycznym stawka domykająca **nie sprowadza wkładu do zera** —
zostaje `luka_poza_zasiegiem_czynszu`. W trybie ręcznym jest dodatkowo
hipotetyczna: kwotę kredytu ustawia użytkownik, więc podniesienie czynszu jej nie
zmieni. Oba zastrzeżenia są teraz wypisane pod wykresem.

### 16.3. Naprawiony błąd: kredyt bez obsługi

Przy `udzial_docelowy = 0` w trybie automatycznym silnik przyjmował kredyt
5 230 750 zł, ale `kredyt_aktywny` szedł za `udzial_docelowy`, więc projekcja
liczyła ścieżkę **grantową**: bez raty, z 25-letnim okresem powierzenia, bez
limitu z art. 28 ust. 2 pkt 2 i z progiem tolerancji 10% zamiast 20%. Kredyt
obniżał wymagany wkład, a nikt go nie spłacał — wkład wychodził 903 tys. zł
zamiast 6,13 mln zł.

W trybie automatycznym `udzial_docelowy` nie wyznacza kwoty, ale nadal
rozstrzyga, **czy kredyt w ogóle wchodzi w grę**. Zero znaczy teraz „bez
kredytu", spójnie z resztą modelu. Test pilnuje, że każdy przyjęty kredyt jest
obsługiwany w projekcji.


---

## 17. Zawężenie zakresu — aport działki przez gminę usunięty

**Pakiet naprawczy nr 2, rozdz. 11. Rozstrzygnięcie zakresu narzędzia, nie poprawka błędu.**

Kalkulator odpowiada na pytanie prywatnego inwestora. Przy aporcie działki przez
gminę wychodziło jej 75,6% udziałów — a wraz z przekroczeniem progu
większościowego przestaje obowiązywać kilka założeń modelu naraz: stawki czynszu
ustala zgromadzenie wspólników (art. 28 ust. 1 ustawy z 26.10.1995), więc suwak
czynszu przestaje być dźwignią inwestora; główna liczba wyjściowa — wymagany
wkład inwestora — traci sens, bo przedsięwzięcie przestaje być jego; wykres
negocjacyjny nie ma z kim negocjować. Narzędzie odpowiadało poprawnie na pytanie,
którego nikt nie zadał.

Usunięte wraz z wariantem: moduł liczenia podziału udziałów (z trzema
uproszczeniami, które go obciążały), klasa ostrzeżeń o utracie kontroli
korporacyjnej, próg większości z prawa spółek, pytanie o wycenę aportu na
potrzeby objęcia udziałów.

### 17.1. Czego zawężenie nie naprawia

- **Reguła gruntu jako przychodu usługi publicznej zostaje.** Art. 5 ust. 9 pkt 4
  obejmuje nieruchomość wniesioną przez jednostkę samorządu, a przy użytkowaniu
  wieczystym ustanowionym przez gminę przyjęto ostrożnie, że to wniesienie.
  Gałąź obliczeniowa żyje, tylko rzadziej się uruchamia.
- **Rozjazd nazewnictwa wkładu zostaje w całości** — wynika z aportu inwestora,
  nie gminnego.
- **Logika i testy aportu zostają**, bo aport inwestora nadal istnieje: limit 20%
  w ścieżce kredytowej i zakaz obciążenia hipoteką.

### 17.2. Aport mniejszościowy — świadomie pomijany

Gmina mogłaby objąć pakiet mniejszościowy i byłby to nadal prywatny SIM. Nie
modelujemy: wada finansowa zostaje w całości (grunt nadal obniża dopuszczalną
rekompensatę), korzyść jest relacyjna, a rozstrzygnięcie, czy pakiet jest
mniejszościowy, wymagałoby modelowania struktury kapitałowej spółki.

### 17.3. Usunięte, ale nie przemilczane

W sekcji „działka należy do gminy" stoi zdanie wyjaśniające z alternatywą. Powód
jest praktyczny: gmina zaproponuje aport, bo dla niej to najprostsze rozwiązanie,
więc inwestor przy stole ma dostać gotową odpowiedź, a nie puste miejsce
w interfejsie.

### 17.4. Skutek uboczny — użytkowanie wieczyste zyskuje na wadze

Zostają cztery formy działki gminnej, a jedna zyskuje. Użytkowanie wieczyste jest
dziś liczone jako przychód usługi publicznej wyłącznie dlatego, że przy braku
rozstrzygnięcia przyjęto wariant ostrożniejszy (kwestia 9.2). Jeżeli BGK
potwierdzi, że nim nie jest, staje się wariantem wyraźnie najlepszym: pełne pasmo
dotacji, brak wydatku kapitałowego, brak skutków ustrojowych, wyłącznie opłaty
roczne w kosztach bieżących.

**Po usunięciu aportu jest to jedyna forma gruntu, przy której rozstrzygnięcie
interpretacyjne istotnie zmienia wynik** — pytanie do BGK awansuje w kolejności.

---

## 18. Wymagany zapas na obsługę kredytu — liczba, której nie ma w dokumentach

**Status: założenie, wartość domyślna 1,20. Do potwierdzenia w BGK.**

### 18.1. Czego szukano i czego nie znaleziono

Kredyt maksymalny liczony był dotąd przy pokryciu obsługi długu równym 1,0 —
cała nadwyżka operacyjna szła na ratę. Przy takim wymiarowaniu pierwsze
odchylenie od założeń (pustostan ponad plan, awaria, skok kosztów energii)
daje niedobór na racie w tym samym roku.

Wymaganego pokrycia **nie podaje ani rozporządzenie o finansowaniu zwrotnym
(t.j. Dz.U. 2021 poz. 766), ani informator BGK o programie SBC**. Jest to
element polityki kredytowej banku, a nie parametr programu.

### 18.2. Co przyjęto

`parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu`, domyślnie
**1,20**. Poziom typowy dla kredytowania nieruchomości przychodowych. Silnik
oznacza go ostrzeżeniem `ZALOZENIE_BUFOR_OBSLUGI_DLUGU` przy każdym przeliczeniu
ze ścieżką kredytową, a arkusz — żółtą komórką z adnotacją o źródle.

Jest to **jedyny parametr zewnętrzny z wartością domyślną**. Odstępstwo od reguły
„brak danej daje jawny stan »nie podano«" jest świadome i idzie w stronę
ostrożniejszą: brak wpisu daje bufor, a nie jego brak. Milcząco nie przechodzi
nigdy — ostrzeżenie towarzyszy także wartości domyślnej.

Ustawienie 1,00 pozostaje dopuszczalne i daje osobne ostrzeżenie
`BUFOR_OBSLUGI_DLUGU_ZEROWY`. Wartości poniżej 1,00 są błędem walidacji.

### 18.3. Ile to zmienia w scenariuszu odniesienia

| | bez bufora (1,00) | z buforem (1,20) |
|---|---|---|
| Kredyt puli społecznej | 7 190 750 zł | 6 338 861 zł |
| Wymagany wkład własny | 1 743 000 zł | 2 594 889 zł |
| Granica udziału komunalnego (przykład domykający się) | 75% | 70% |

Przed zmianą kredyt wiązała **potrzeba** — koszty po dotacji i partycypacji.
Po zmianie wiąże **udźwig czynszowy**. Cały ubytek kredytu przechodzi na wkład
własny, bo nic innego tej pozycji nie zastąpi.

### 18.4. Dwie miary pokrycia, które łatwo pomylić

Model liczy dwa wskaźniki i obu potrzebuje:

- **pokrycie wypływów** (`dscr`, próg testu 2 = 1,00) — przychód netto podzielony
  przez wszystkie wypływy bieżące razem z ratą;
- **pokrycie obsługi długu** (`pokrycie_obslugi_dlugu`) — nadwyżka operacyjna
  podzielona przez samą ratę. To ta wielkość, którą ustawia bufor, i to ona
  odpowiada bankowemu DSCR.

Przy racie wymierzonej na pokrycie bankowe 1,20 pierwszy wskaźnik wychodzi około
1,09. Zamiana ich miejscami przewróciłaby werdykt testu 2, dlatego arkusz
i interfejs pokazują obie pod pełnymi nazwami — słowo „DSCR" bez dopowiedzenia
zostało z nich usunięte.

### 18.5. Na którym roku liczony jest udźwig

Na **najgorszym roku okresu kredytowania**, nie na pierwszym i nie na średniej —
`min(pulapy)` po wszystkich latach kredytu. Przy czynszu i kosztach indeksowanych
różnymi stawkami te trzy wielkości się rozjeżdżają, a bank patrzy na rok
najgorszy.

Przy okazji naprawiono błąd, który ten wybór wcześniej unieważniał: projekcja
bez kredytu idzie ścieżką grantową, czyli 25 lat, więc lata 26–30 nie były
w ogóle badane. Przy kosztach indeksowanych szybciej od czynszu to właśnie one
są najciaśniejsze. Silnik wymusza teraz horyzont równy okresowi kredytu
(`projekcja.build(..., horyzont_spoleczna=...)`). W scenariuszu odniesienia
(koszty 3,5%, czynsz 3,0%) nie zmienia to nic, bo wiążący rok mieści się
w dwudziestu pięciu; przy indeksacji kosztów 4,5% wobec czynszu 2,0% kredyt
spada z 5 968 765 zł na 5 485 629 zł.

### 18.6. Pytanie do BGK

> Jakiego minimalnego wskaźnika pokrycia obsługi długu wymaga BGK przy
> finansowaniu zwrotnym w programie SBC? Czy wskaźnik liczony jest od nadwyżki
> operacyjnej do raty, czy inaczej, i na którym roku projekcji — pierwszym pełnym,
> średniej, czy najgorszym?

---

## 19. Zbieg progów tolerancji — dotacja i kredyt w jednej puli

**Status: założenie, wartość domyślna `nizszy` (10%). Do potwierdzenia w BGK.
Pierwszy przypadek, w którym samo założenie przesądza o werdykcie.**

### 19.1. Na czym polega zbieg

Próg tolerancji nadwyżki rekompensaty przypisany był ścieżce: 10% dla puli
grantowej (§ 7 ust. 9 rozp. 1897), 20% dla kredytowej (§ 13 ust. 8 rozp. 766).
Przypisanie jest zrozumiałe, ale niepełne — **pula społeczna ma oba instrumenty
naraz**: dotację do 45% kosztów i kredyt SBC.

Dotacja podlega rozporządzeniu o wsparciu finansowym, kredyt rozporządzeniu
o finansowaniu zwrotnym. Żaden z dwóch przepisów nie mówi, co dzieje się, gdy
to samo przedsięwzięcie korzysta z obu. Jeżeli oba obowiązują równolegle, wiąże
niższy.

### 19.2. Co przyjęto

`przelaczniki.prog_tolerancji_przy_dwoch_instrumentach`, trzy wartości:

| wartość | próg | uzasadnienie |
|---|---|---|
| `nizszy` (domyślna) | 10% | oba rozporządzenia obowiązują równolegle, wiąże niższy |
| `wyzszy` | 20% | przedsięwzięcie z finansowaniem zwrotnym podlega reżimowi rozp. 766 w całości |
| `wedlug_instrumentu_dominujacego` | 10% albo 20% | rozstrzyga ten instrument, który niesie większe EDB |

Domyślnie `nizszy`, jako ostrożniejszy. Pula z jednym instrumentem zbiegowi nie
podlega i odczyt pozostaje jednoznaczny — dotyczy to całej puli komunalnej,
w której kredyt SBC jest niedopuszczalny (art. 5a ust. 3).

### 19.3. To założenie odwraca werdykt

Dotąd żadne założenie nie decydowało samo o odpowiedzi „spina się / nie spina" —
przesuwały kwoty, nie werdykty. To decyduje. Scenariusz testowy
(`tests/test_audyt.py`, `MIEDZY_PROGAMI`) daje nadwyżkę **19,21%**:

| założenie | próg | test 3 |
|---|---|---|
| `nizszy` | 10% | **nie przechodzi** |
| `wyzszy` | 20% | **przechodzi** |

Te same dane, ten sam rachunek, przeciwne odpowiedzi. Dlatego wynik niesie to
jawnie w trzech miejscach naraz: ostrzeżenie `ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY`
o wadze „zmienia werdykt", zdanie przy liczbie w kafelku testu 3 (nie dopiero
w liście uwag), oraz żółta komórka progu w zakładce `Rekompensata` arkusza,
którą można podmienić i przeliczyć.

### 19.4. Pytanie do BGK

> Przedsięwzięcie korzysta jednocześnie z finansowego wsparcia z Funduszu Dopłat
> i z finansowania zwrotnego. Który próg tolerancji nadwyżki rekompensaty ma
> zastosowanie — 10% z § 7 ust. 9 rozp. 1897, 20% z § 13 ust. 8 rozp. 766, czy
> każdy do części pomocy pochodzącej z danego instrumentu?

---

## 20. Rozkład nadwyżki rekompensaty w czasie

**Status: naprawa. Werdykt liczony na najgorszym okresie, nie na średniej.**

### 20.1. Co było nie tak

Nadwyżka była annualizowana przez podzielenie przez liczbę lat okresu
powierzenia. To zakłada rozkład równomierny, a rzeczywisty taki nie jest:
dotacja spływa jednorazowo na etapie inwestycji, nakład wchodzi według wybranego
ujęcia, a przychody czynszowe rozkładają się przez cały okres. Nadwyżka
przesuwa się więc ku jednemu albo drugiemu końcowi okresu, zależnie od ujęcia
nakładu.

Przy wyniku granicznym średnia pokazuje zapas, którego w najciaśniejszym roku
rozliczenia nie ma.

### 20.2. Co przyjęto

Profil narastający rok po rok: rekompensata otrzymana do roku *t* wobec kwoty
dopuszczalnej należnej do roku *t*. Werdykt bierze rok najgorszy.

Nadkompensata jest pytaniem o to, ile pomocy podmiot **już** dostał wobec tego,
ile mu się **już** należało — dlatego obie strony są narastające, a nie roczne.
Pojedynczy rok nic o stanie rozliczenia nie mówi.

Żadna pozycja nie jest rozdzielana założeniem, którego model wcześniej nie miał:

- **EDB kredytu** — wzór § 4 pkt 5 lit. e jest sumą po okresach, więc składnik
  *i*-ty jest korzyścią roku *i*-tego. Rozkład jest odczytem, nie szacunkiem;
  jego suma równa się całości co do grosza (`kredyt.edb_kredyt_lata`).
- **Koszty netto** — liczone rok po roku od początku, bez zmian.
- **Rozsądny zysk** przy metodzie kapitałowej — ze wzoru.
- **EDB grantu i wsparcie dodatkowe** — rok 1: dotacja jest wypłacana na etapie
  inwestycji, nie rozkładana na okres powierzenia.

Jeden wyjątek: **rozsądny zysk podany kwotą wprost** nie ma własnego profilu
czasowego, więc rozkład równy jest tam dodatkowym założeniem. Zaznaczone
w `rozsadny_zysk_lata`.

Ostatni punkt profilu jest z definicji równy wielkości całookresowej, więc nowa
miara nigdy nie jest łagodniejsza od poprzedniej — może być tylko ostrzejsza.

### 20.3. Ile to zmienia

W scenariuszu wzorcowym pula komunalna: średnia **74,7%**, najgorszy rok (rok 1)
**86,8%**. Kierunek zależy od ujęcia nakładu:

| ujęcie nakładu w KN | gdzie wypada najgorszy rok | dlaczego |
|---|---|---|
| `amortyzacja` | rok 1 | kwota dopuszczalna narasta powoli, a dotacja spłynęła w całości |
| `naklad_poczatkowy` | ostatni rok | ogromna kwota dopuszczalna na starcie, którą przychody czynszowe zjadają przez cały okres |

Gdy najgorszy rok odbiega od średniej o więcej niż 0,05 punktu procentowego,
wynik niesie ostrzeżenie `NADWYZKA_ROZLOZONA_NIEROWNO` o wadze „zmienia werdykt",
z podaniem roku i obu liczb.

### 20.4. Czego to nie rozwiązuje

Przepis odnosi próg do **okresu rozliczeniowego**, a model nadal nie zna jego
długości — nie ma jej w żadnym dokumencie wejściowym. Profil roczny jest
najbliższym przybliżeniem, jakie da się zbudować bez tej danej: gdyby okres
rozliczeniowy był dwuletni albo pięcioletni, punkty pomiaru byłyby rzadsze,
a wynik nieco łagodniejszy. Ostrzeżenie `ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI`
zostaje.

---

## 21. Trzy uzupełnienia warstwy prezentacji

**Status: uzupełnienia, nie luki. Żadne nie zmienia liczby — zmieniają to, czy
z liczby da się coś wyczytać.**

### 21.1. Co ogranicza kwotę kredytu

Kredyt jest minimum z trzech wielkości: udźwigu czynszowego, limitu 80%
(art. 15b ust. 2) i faktycznej potrzeby po dotacji, partycypacji i wkładzie
rzeczowym. Czynsz rusza tylko jedną z nich. Gdy wiąże potrzeba, podnoszenie
stawki niczego nie zmienia — bez podania przyczyny zachowanie narzędzia wygląda
na awarię.

Silnik zwraca teraz `OgraniczenieKredytu` z nazwą wiążącej wielkości i wszystkimi
trzema pułapami. Kaskada niesie wskaźnik przy słupku kredytu, arkusz — sekcję
„CO OGRANICZA KWOTĘ KREDYTU" z własną formułą rozstrzygającą (test sprawdza, że
obie warstwy nazywają to samo).

Kolejność rozstrzygania przy remisie: potrzeba, limit, udźwig. Gdy dwie
wielkości wypadają równo, uczciwiej powiedzieć „nie ma czego więcej finansować"
niż „podnieś czynsz" — druga rada nic by nie dała.

### 21.2. Próg bezskuteczności czynszu

Stawka, powyżej której wkład własny przestaje reagować na czynsz. Liczona jako
odwrócenie wymiarowania kredytu przy pułapie równym `min(limit, potrzeba)` —
czyli stawka, przy której udźwig dorównuje temu, co i tak ogranicza kwotę.

W scenariuszu wzorcowym wynosi **24,01 zł**. Powyżej niej wkład stoi na
**1,7 mln zł** — to `luka_poza_zasiegiem_czynszu`, część, której żaden czynsz nie
domknie, bo pula komunalna nie ma kredytu (art. 5a ust. 3), a tylko kredyt
zamienia przyszły czynsz na kapitał początkowy.

Uwaga redakcyjna: próg i tak zwana luka poza zasięgiem mówią o tym samym
plateau, więc idą **jednym** zdaniem pod wykresem, nie dwoma akapitami z tą samą
kwotą. Na wykresie zostaje znacznik z podpowiedzią po najechaniu.

**Most między dwoma wykresami.** Wielkość plateau rośnie wprost z udziałem puli
komunalnej: przy 0% wynosi zero, przy 100% pochłania cały wkład. Wykres
negocjacyjny pokazuje to jako zacieniowaną warstwę pod linią wkładu — odstęp
między nią a linią to część, którą da się zdjąć podnosząc stawkę.

| udział komunalny | wkład wymagany | z tego poza zasięgiem czynszu |
|---|---|---|
| 0% | 1 216 984 zł | 0 zł |
| 40% | 3 054 191 zł | 2 324 000 zł |
| 100% | 5 810 000 zł | 5 810 000 zł |

### 21.3. Wkład rzeczowy inwestora

Rozstrzygnięcie na rzecz `wklad_gotowkowy_wymagany` (luka nr 1 audytu) było
słuszne i zostaje: gdy działkę wnosi gmina, inwestor faktycznie nie wykłada tych
pieniędzy. Ale przy formie **„inwestor wnosi aportem"** ten sam mechanizm
pokazywał samą gotówkę, przemilczając działkę oddaną do spółki.

Kaskada rozróżnia teraz, **kto** wnosi grunt rzeczowo. Przy aporcie inwestora
nagłówek podaje dwie liczby i sumę:

> Twój wkład: 903 tys. zł w gotówce plus działka warta 2,8 mln zł. Łącznie
> 3,7 mln zł, czyli 13% kosztów.

Kafelek testu 1 pokazuje wtedy kwotę łączną z rozbiciem w podpisie. Grunt
wniesiony przez gminę do tej sumy nie wchodzi — to nie jest wkład inwestora.

**Uwaga do testu z pakietu.** Pakiet proponował porównać dwa scenariusze różniące
się wyłącznie formą aportu — inwestora i gminy. Aport gminy został usunięty
z zakresu (rozdz. 17), więc test porównuje aport inwestora z nabyciem od gminy
i z dzierżawą: te same koszty, ta sama kwota gotówkowa tam, gdzie ma być ta sama,
i wkład łączny większy wyłącznie przy aporcie inwestora.
