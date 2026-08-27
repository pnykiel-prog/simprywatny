# Pytania do BGK — lista skonsolidowana

**Dokument generowany.** Zrodlem jest `sim_kalkulator/zalozenia.py`; po zmianie
katalogu uruchom `python3 scripts/pytania_do_bgk.py`. Recznych poprawek w tym
pliku nie wprowadzac — zostana nadpisane.

Wszystkie pytania dotycza jednego montazu i wzajemnie sie zazebiaja, wiec warto
zadac je jednym pismem. Kolejnosc idzie za waga dla wyniku: najpierw te, ktore
odwracaja werdykt, potem te, ktore przesuwaja kwote.

Kazde pytanie odpowiada jednemu ZALOZENIU w modelu. Dopoki odpowiedzi nie ma,
kalkulator liczy wariant oznaczony jako domyslny i zglasza to ostrzezeniem przy
kazdym przeliczeniu. Po odpowiedzi wystarczy zmienic wskazana wartosc — poza
jednym przypadkiem, w ktorym trzeba wejsc w kod, i ten przypadek jest oznaczony.

| Nr | Pytanie | Co sie zmienia | Priorytet |
|---|---|---|---|
| 1 | Minimalny wskaznik pokrycia obslugi dlugu | wprost przeklada sie na kwote kredytu i wymagany wklad wlasny | 1 |
| 2 | Uzytkowanie wieczyste ustanowione przez gmine jako przychod uslugi | po zawezeniu zakresu jedyna forma gruntu, przy ktorej rozstrzygniecie interpretacyjne istotnie zmienia wynik | 1 |
| 3 | Prog tolerancji nadwyzki przy dotacji i kredycie naraz | odwraca werdykt testu 3 | 1 |
| 4 | Wartosc gruntu w bazie naliczenia wsparcia | kwota dotacji w obu pulach | 2 |
| 5 | Hybryda jako jedno przedsiewziecie czy dwa | struktura wniosku, limit wsparcia, liczba testow nadwyzki | 2 |
| 6 | Dlugosc okresu rozliczeniowego nadwyzki rekompensaty | przesuwa moment, w ktorym nadwyzka jest badana, a z nim werdykt | 2 |
| 7 | Czy bonus +5 pp podnosi takze prog gruntowy | kwota dotacji, gdy wiaze prog gruntowy, a nie limit gorny | 3 |
| 8 | Grunt z trybu 'lokal za grunt' jako przychod uslugi publicznej | dopuszczalna rekompensata w tej formie gruntu | 3 |
| 9 | Bonifikata przy sprzedazy gruntu a pasmo dotacji | gorna granica dotacji przy zakupie z bonifikata | 3 |
| 10 | Ujecie nakladu inwestycyjnego w kosztach netto uslugi | wysokosc kosztow netto, a przez to dopuszczalna rekompensata | 3 |
| 11 | Metoda wyliczenia rozsadnego zysku | skladnik kwoty dopuszczalnej w tescie nadwyzki | 3 |
| 12 | Z ktorej puli pochodza lokale oddawane gminie | ktora pula traci przychod przy zachowaniu pelnego kosztu | 4 |
| 13 | Czy wskaznik pustostanow obciaza pule komunalna | przychod puli komunalnej i jej podloga czynszowa | 4 |

---

## Pytania w pelnym brzmieniu

### 1. Minimalny wskaznik pokrycia obslugi dlugu

> Jakiego minimalnego wskaznika pokrycia obslugi dlugu Bank wymaga przy ocenie zdolnosci w programie SBC? Czy wskaznik liczy sie od nadwyzki operacyjnej do raty, i na ktorym roku projekcji — pierwszym pelnym, sredniej z okresu, czy najgorszym?

| | |
|---|---|
| Podstawa | brak — ani rozp. 766, ani informator BGK nie podaja wymaganego pokrycia |
| Model przyjmuje | 1,20 — poziom typowy dla nieruchomosci przychodowych |
| Odczyt alternatywny | 1,00, czyli finansowanie bez marginesu, albo inna wartosc Banku |
| Co sie zmienia | wprost przeklada sie na kwote kredytu i wymagany wklad wlasny |
| Gdzie to zmienic | `parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu` |
| Kod ostrzezenia | `ZALOZENIE_BUFOR_OBSLUGI_DLUGU` |

### 2. Uzytkowanie wieczyste ustanowione przez gmine jako przychod uslugi

> Czy wartosc prawa uzytkowania wieczystego ustanowionego przez gmine na rzecz spolki stanowi przychod uslugi publicznej w rozumieniu art. 5 ust. 9 pkt 4, czy pozostaje kosztem inwestora rozlozonym na oplaty roczne?

| | |
|---|---|
| Podstawa | art. 5 ust. 9 pkt 4 ustawy z 8.12.2006 |
| Model przyjmuje | JEST przychodem — wariant ostrozniejszy |
| Odczyt alternatywny | NIE jest; wtedy forma staje sie wyraznie najlepsza z gminnych |
| Co sie zmienia | po zawezeniu zakresu jedyna forma gruntu, przy ktorej rozstrzygniecie interpretacyjne istotnie zmienia wynik |
| Gdzie to zmienic | `przelaczniki.uzytkowanie_wieczyste_jest_przychodem_uoig` |
| Kod ostrzezenia | `ZALOZENIE_GRUNT_9_2` |

### 3. Prog tolerancji nadwyzki przy dotacji i kredycie naraz

> Ktory prog tolerancji nadwyzki rekompensaty obowiazuje przedsiewziecie laczace finansowe wsparcie z Funduszu Doplat z finansowaniem zwrotnym: 10% z § 7 ust. 9 rozp. 1897, 20% z § 13 ust. 8 rozp. 766, czy kazdy do czesci pomocy pochodzacej z danego instrumentu?

| | |
|---|---|
| Podstawa | § 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766 |
| Model przyjmuje | nizszy z dwoch progow, czyli 10% |
| Odczyt alternatywny | wyzszy, czyli 20%, albo prog instrumentu dominujacego |
| Co sie zmienia | odwraca werdykt testu 3 |
| Gdzie to zmienic | `przelaczniki.prog_tolerancji_przy_dwoch_instrumentach` |
| Kod ostrzezenia | `ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY` |

### 4. Wartosc gruntu w bazie naliczenia wsparcia

> Czy wartosc gruntu wchodzi do podstawy naliczenia finansowego wsparcia, czy pozostaje poza nia jako srodek wlasny inwestora w strukturze finansowania przedsiewziecia?

| | |
|---|---|
| Podstawa | art. 13 ust. 1 pkt 1 ustawy z 8.12.2006 |
| Model przyjmuje | grunt WCHODZI do podstawy kosztowej obu pul |
| Odczyt alternatywny | baza bez gruntu, przy zachowaniu gruntu jako limitu pasma ponad prog gruntowy; silnik podaje roznice obu odczytow w ostrzezeniu |
| Co sie zmienia | kwota dotacji w obu pulach |
| Gdzie to zmienic | `brak przelacznika — patrz stopka` |
| Kod ostrzezenia | `ZALOZENIE_GRUNT_W_BAZIE_DOTACJI` |

### 5. Hybryda jako jedno przedsiewziecie czy dwa

> Czy przedsiewziecie obejmujace lokale na wynajem i lokale komunalne stanowi jedno przedsiewziecie, czy dwa odrebne wnioski? Od tego zalezy liczba okresow powierzenia i stosowanie limitu lacznego z art. 13 ust. 1a.

| | |
|---|---|
| Podstawa | art. 13 ust. 1a w zw. z art. 5a ust. 1 ustawy z 8.12.2006 |
| Model przyjmuje | DWA odrebne przedsiewziecia — wlasny okres powierzenia i prog kazde |
| Odczyt alternatywny | jedno, z limitem lacznym 45% (art. 13 ust. 1a) i jednym testem nadwyzki |
| Co sie zmienia | struktura wniosku, limit wsparcia, liczba testow nadwyzki |
| Gdzie to zmienic | `przelaczniki.hybryda_jako_jedno_przedsiewziecie` |
| Kod ostrzezenia | `ZALOZENIE_HYBRYDA` |

### 6. Dlugosc okresu rozliczeniowego nadwyzki rekompensaty

> Jaka jest dlugosc okresu rozliczeniowego dla progu nadwyzki rekompensaty i czy weryfikacja obejmuje pojedynczy okres, czy stan narastajacy od poczatku okresu powierzenia?

| | |
|---|---|
| Podstawa | § 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766 |
| Model przyjmuje | okres roczny — kontrola w kazdym roku, wariant najostrozniejszy |
| Odczyt alternatywny | okres dluzszy; rzadsza siatka kontrolna daje lagodniejszy wynik |
| Co sie zmienia | przesuwa moment, w ktorym nadwyzka jest badana, a z nim werdykt |
| Gdzie to zmienic | `przelaczniki.okres_rozliczeniowy_nadwyzki_lat` |
| Kod ostrzezenia | `ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI` |

### 7. Czy bonus +5 pp podnosi takze prog gruntowy

> Czy zwiekszenie wsparcia o 5 punktow procentowych z art. 13 ust. 4 podnosi takze prog, powyzej ktorego wsparcie jest limitowane wartoscia gruntu we wladaniu inwestora, czy wylacznie limit gorny?

| | |
|---|---|
| Podstawa | art. 13 ust. 1 pkt 1 w zw. z art. 13 ust. 4 ustawy z 8.12.2006 |
| Model przyjmuje | NIE — bonus podnosi wylacznie limit gorny |
| Odczyt alternatywny | TAK — oba progi ida w gore o 5 pp |
| Co sie zmienia | kwota dotacji, gdy wiaze prog gruntowy, a nie limit gorny |
| Gdzie to zmienic | `przelaczniki.bonus_podnosi_prog_gruntowy` |
| Kod ostrzezenia | `ZALOZENIE_BONUS_A_PROG_GRUNTOWY` |

### 8. Grunt z trybu 'lokal za grunt' jako przychod uslugi publicznej

> Czy grunt nabyty od gminy w trybie ustawy z 16.12.2020 (lokale w zamian za nieruchomosc) jest wartoscia wniesiona przez jednostke samorzadu terytorialnego w rozumieniu art. 5 ust. 9 pkt 4, czy zwyklym nabyciem?

| | |
|---|---|
| Podstawa | art. 5 ust. 9 pkt 4 ustawy z 8.12.2006 |
| Model przyjmuje | NIE jest — transakcja jest nabyciem, nie wniesieniem przez gmine |
| Odczyt alternatywny | JEST; obniza dopuszczalna rekompensate o wartosc dzialki |
| Co sie zmienia | dopuszczalna rekompensata w tej formie gruntu |
| Gdzie to zmienic | `przelaczniki.lokal_za_grunt_jest_przychodem_uoig` |
| Kod ostrzezenia | `ZALOZENIE_GRUNT_9_1` |

### 9. Bonifikata przy sprzedazy gruntu a pasmo dotacji

> Przy nabyciu gruntu od gminy z bonifikata — czy pasmo wsparcia ponad prog gruntowy liczy sie od wartosci prawa z operatu, czy od ceny faktycznie zaplaconej?

| | |
|---|---|
| Podstawa | art. 13 ust. 1 pkt 1 ustawy z 8.12.2006 |
| Model przyjmuje | pasmo liczone od wartosci z operatu, nie od ceny po bonifikacie |
| Odczyt alternatywny | od ceny zaplaconej; bonifikata scina wtedy pasmo dotacji |
| Co sie zmienia | gorna granica dotacji przy zakupie z bonifikata |
| Gdzie to zmienic | `przelaczniki.pasmo_liczone_od_wartosci_z_operatu` |
| Kod ostrzezenia | `ZALOZENIE_GRUNT_9_3` |

### 10. Ujecie nakladu inwestycyjnego w kosztach netto uslugi

> W jaki sposob naklad inwestycyjny wchodzi do kosztow netto uslugi publicznej: jednorazowo w roku poniesienia, przez odpisy amortyzacyjne, czy proporcjonalnie do okresu powierzenia?

| | |
|---|---|
| Podstawa | art. 5 ust. 7-8 ustawy z 8.12.2006 |
| Model przyjmuje | amortyzacja wg okresu amortyzacji budynkow |
| Odczyt alternatywny | naklad w roku pierwszym, amortyzacja w okresie powierzenia albo pominiecie |
| Co sie zmienia | wysokosc kosztow netto, a przez to dopuszczalna rekompensata |
| Gdzie to zmienic | `przelaczniki.koszty_inwestycyjne_w_kn` |
| Kod ostrzezenia | `ZALOZENIE_KOSZTY_INWESTYCYJNE_W_KN` |

### 11. Metoda wyliczenia rozsadnego zysku

> Przepisy wskazuja stope IRS dla kontraktu 20-letniego na bazie WIBOR 3M jako podstawe rozsadnego zysku, ale nie podaja wzoru. Od jakiej podstawy nalicza sie te stope i czy wynik podlega dyskontowaniu?

| | |
|---|---|
| Podstawa | § 6 ust. 5 rozp. Dz.U. 2025 poz. 1897; § 12 ust. 10 rozp. t.j. Dz.U. 2021 poz. 766 |
| Model przyjmuje | stopa IRS BGK od kapitalu zaangazowanego, dyskontowana stopa bazowa |
| Odczyt alternatywny | kwota podana wprost przez uzytkownika |
| Co sie zmienia | skladnik kwoty dopuszczalnej w tescie nadwyzki |
| Gdzie to zmienic | `przelaczniki.metoda_rozsadnego_zysku` |
| Kod ostrzezenia | `ZALOZENIE_ROZSADNY_ZYSK` |

### 12. Z ktorej puli pochodza lokale oddawane gminie

> Przy rozliczeniu 'lokal za grunt' — czy lokale przekazywane gminie moga pochodzic z dowolnej czesci przedsiewziecia, czy musza byc wskazane w konkretnej puli? Pytanie kierowane rownolegle do gminy jako strony umowy.

| | |
|---|---|
| Podstawa | ustawa z 16.12.2020, Dz.U. 2021 poz. 223 |
| Model przyjmuje | proporcjonalnie z obu pul, kluczem PUM |
| Odczyt alternatywny | w calosci z puli komunalnej albo w calosci ze spolecznej |
| Co sie zmienia | ktora pula traci przychod przy zachowaniu pelnego kosztu |
| Gdzie to zmienic | `przelaczniki.lokale_dla_gminy_z_puli` |
| Kod ostrzezenia | `ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM` |

### 13. Czy wskaznik pustostanow obciaza pule komunalna

> Pytanie nie do Banku, tylko do gminy: czy umowa najmu calej puli komunalnej przewiduje czynsz niezalezny od zasiedlenia lokali?

| | |
|---|---|
| Podstawa | poza przepisem — rozstrzygniecie umowne miedzy spolka a gmina |
| Model przyjmuje | NIE — najemca calej puli jest gmina, ryzyko zostaje po jej stronie |
| Odczyt alternatywny | TAK — pula komunalna traci przychod tak samo jak spoleczna |
| Co sie zmienia | przychod puli komunalnej i jej podloga czynszowa |
| Gdzie to zmienic | `przelaczniki.pustostany_takze_w_puli_komunalnej` |
| Kod ostrzezenia | `ZALOZENIE_PUSTOSTANY_KOMUNALNE` |

---

## Jak czytac kolumne „gdzie to zmienic"

Sciezka wskazuje pole w pliku YAML z zalozeniami. Zmiana wartosci i ponowne
przeliczenie wystarcza — silnik, arkusz i interfejs ida za nia razem.

`brak przelacznika` znaczy, ze odczyt alternatywny nie jest wpiety w wejscie.
Silnik liczy wtedy obie wartosci i podaje roznice w ostrzezeniu, ale przyjecie
odczytu przeciwnego wymaga zmiany w kodzie.

## Kody bez osobnego pytania

Niektore watpliwosci maja w modelu dwa kody ostrzezen — po jednym na kazdy
odczyt. Do Banku idzie wtedy jedno pytanie. Kody wtorne:

- `ZALOZENIE_PASMO_OD_CENY` — patrz pytanie o: Bonifikata przy sprzedazy gruntu a pasmo dotacji

## Czego na tej liscie nie ma

Pytanie o wycene aportu na potrzeby objecia udzialow przez gmine zostalo
skreslone wraz z usunieciem tego wariantu z zakresu narzedzia — patrz LUKI.md
rozdz. 17.
