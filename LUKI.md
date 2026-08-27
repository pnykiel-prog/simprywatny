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
