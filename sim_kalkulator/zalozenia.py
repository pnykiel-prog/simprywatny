"""Katalog zalozen modelu — pakiet naprawczy nr 2, rozdz. 7 i 9.

Kazde miejsce, w ktorym model przyjmuje odczyt przepisu zamiast go odczytac,
ma tu wpis. Wpis mowi trzy rzeczy: gdzie siedzi przelacznik, jaki jest odczyt
alternatywny i jak brzmi pytanie, ktore rozstrzyga sprawe w BGK.

Po co osobny modul, skoro ostrzezenia i tak niosa te tresc w wyniku:

1.  Ostrzezenie widzi wylacznie ten, kto uruchomil scenariusz, w ktorym zalozenie
    w ogole zadzialalo. Katalog widac zawsze.
2.  Test `test_zalozenia.py` porownuje ten katalog z kodami faktycznie emitowanymi
    przez silnik. Nowe zalozenie bez wpisu — i bez scenariusza rozstrzygajacego —
    nie przejdzie zestawu testowego.
3.  Pismo do BGK (`PYTANIA_DO_BGK.md`) jest generowane stad, wiec nie da sie go
    rozjechac z kodem: zmiana rozstrzygniecia zmienia jedno miejsce.

CZEGO TU NIE MA. Wpis nie zawiera liczb — te zaleza od scenariusza i licza sie
w tescie. Katalog opisuje strukture pytania, nie jego odpowiedz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# Jak model dochodzi do odczytu alternatywnego. Rozroznienie jest istotne przy
# odpowiedzi Banku: przy przelaczniku wystarczy zmienic wartosc domyslna,
# bez niego trzeba wejsc w kod.
PRZEZ_PRZELACZNIK = "przelacznik"      # wartosc do podmiany w `dane.Przelaczniki`
PRZEZ_PARAMETR = "parametr"            # wartosc w `parametry_zewnetrzne`
OBLICZANY_OBOK = "obliczany_obok"      # brak przelacznika; silnik liczy obie wartosci


@dataclass(frozen=True)
class Zalozenie:
    """Jedno zalozenie modelu wraz z odczytem alternatywnym."""

    kod: str                      # kod ostrzezenia emitowanego przez silnik
    tytul: str
    sciezka: Optional[str]        # sciezka w YAML, None gdy brak przelacznika
    mechanizm: str                # PRZEZ_PRZELACZNIK / PRZEZ_PARAMETR / OBLICZANY_OBOK
    domyslnie: str                # przyjety odczyt, slowami
    alternatywa: str              # odczyt przeciwny, slowami
    podstawa: str                 # przepis, ktorego dotyczy watpliwosc
    pytanie_do_bgk: str           # gotowe zdanie do pisma
    waga_dla_wyniku: str          # co konkretnie sie zmienia
    priorytet: int                # 1 = pytac najpierw
    # Gdy dwa kody opisuja te sama watpliwosc — po jednym na kazdy odczyt — ten
    # wtorny wskazuje tu kod glowny. Do Banku idzie wtedy jedno pytanie, a nie
    # dwa identyczne; katalog i tak wymienia oba, bo oba kody istnieja w wyniku.
    duplikat_pytania: Optional[str] = None

    @property
    def ma_przelacznik(self) -> bool:
        return self.mechanizm in (PRZEZ_PRZELACZNIK, PRZEZ_PARAMETR)

    @property
    def idzie_do_pisma(self) -> bool:
        return self.duplikat_pytania is None


KATALOG: Tuple[Zalozenie, ...] = (
    Zalozenie(
        kod="ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY",
        tytul="Prog tolerancji nadwyzki przy dotacji i kredycie naraz",
        sciezka="przelaczniki.prog_tolerancji_przy_dwoch_instrumentach",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="nizszy z dwoch progow, czyli 10%",
        alternatywa="wyzszy, czyli 20%, albo prog instrumentu dominujacego",
        podstawa="§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766",
        pytanie_do_bgk=(
            "Ktory prog tolerancji nadwyzki rekompensaty obowiazuje przedsiewziecie "
            "laczace finansowe wsparcie z Funduszu Doplat z finansowaniem zwrotnym: "
            "10% z § 7 ust. 9 rozp. 1897, 20% z § 13 ust. 8 rozp. 766, czy kazdy do "
            "czesci pomocy pochodzacej z danego instrumentu?"
        ),
        waga_dla_wyniku="odwraca werdykt testu 3",
        priorytet=1,
    ),
    Zalozenie(
        kod="ZALOZENIE_BUFOR_OBSLUGI_DLUGU",
        tytul="Minimalny wskaznik pokrycia obslugi dlugu",
        sciezka="parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu",
        mechanizm=PRZEZ_PARAMETR,
        domyslnie="1,20 — poziom typowy dla nieruchomosci przychodowych",
        alternatywa="1,00, czyli finansowanie bez marginesu, albo inna wartosc Banku",
        podstawa="brak — ani rozp. 766, ani informator BGK nie podaja wymaganego pokrycia",
        pytanie_do_bgk=(
            "Jakiego minimalnego wskaznika pokrycia obslugi dlugu Bank wymaga przy "
            "ocenie zdolnosci w programie SBC? Czy wskaznik liczy sie od nadwyzki "
            "operacyjnej do raty, i na ktorym roku projekcji — pierwszym pelnym, "
            "sredniej z okresu, czy najgorszym?"
        ),
        waga_dla_wyniku="wprost przeklada sie na kwote kredytu i wymagany wklad wlasny",
        priorytet=1,
    ),
    Zalozenie(
        kod="ZALOZENIE_GRUNT_9_2",
        tytul="Uzytkowanie wieczyste ustanowione przez gmine jako przychod uslugi",
        sciezka="przelaczniki.uzytkowanie_wieczyste_jest_przychodem_uoig",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="JEST przychodem — wariant ostrozniejszy",
        alternatywa="NIE jest; wtedy forma staje sie wyraznie najlepsza z gminnych",
        podstawa="art. 5 ust. 9 pkt 4 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Czy wartosc prawa uzytkowania wieczystego ustanowionego przez gmine na "
            "rzecz spolki stanowi przychod uslugi publicznej w rozumieniu art. 5 ust. 9 "
            "pkt 4, czy pozostaje kosztem inwestora rozlozonym na oplaty roczne?"
        ),
        waga_dla_wyniku=(
            "po zawezeniu zakresu jedyna forma gruntu, przy ktorej rozstrzygniecie "
            "interpretacyjne istotnie zmienia wynik"
        ),
        priorytet=1,
    ),
    Zalozenie(
        kod="ZALOZENIE_GRUNT_W_BAZIE_DOTACJI",
        tytul="Wartosc gruntu w bazie naliczenia wsparcia",
        sciezka=None,
        mechanizm=OBLICZANY_OBOK,
        domyslnie="grunt WCHODZI do podstawy kosztowej obu pul",
        alternatywa=(
            "baza bez gruntu, przy zachowaniu gruntu jako limitu pasma ponad prog "
            "gruntowy; silnik podaje roznice obu odczytow w ostrzezeniu"
        ),
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Czy wartosc gruntu wchodzi do podstawy naliczenia finansowego wsparcia, "
            "czy pozostaje poza nia jako srodek wlasny inwestora w strukturze "
            "finansowania przedsiewziecia?"
        ),
        waga_dla_wyniku="kwota dotacji w obu pulach",
        priorytet=2,
    ),
    Zalozenie(
        kod="ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI",
        tytul="Dlugosc okresu rozliczeniowego nadwyzki rekompensaty",
        sciezka="przelaczniki.okres_rozliczeniowy_nadwyzki_lat",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="okres roczny — kontrola w kazdym roku, wariant najostrozniejszy",
        alternatywa="okres dluzszy; rzadsza siatka kontrolna daje lagodniejszy wynik",
        podstawa="§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766",
        pytanie_do_bgk=(
            "Jaka jest dlugosc okresu rozliczeniowego dla progu nadwyzki rekompensaty "
            "i czy weryfikacja obejmuje pojedynczy okres, czy stan narastajacy od "
            "poczatku okresu powierzenia?"
        ),
        waga_dla_wyniku="przesuwa moment, w ktorym nadwyzka jest badana, a z nim werdykt",
        priorytet=2,
    ),
    Zalozenie(
        kod="ZALOZENIE_HYBRYDA",
        tytul="Hybryda jako jedno przedsiewziecie czy dwa",
        sciezka="przelaczniki.hybryda_jako_jedno_przedsiewziecie",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="DWA odrebne przedsiewziecia — wlasny okres powierzenia i prog kazde",
        alternatywa="jedno, z limitem lacznym 45% (art. 13 ust. 1a) i jednym testem nadwyzki",
        podstawa="art. 13 ust. 1a w zw. z art. 5a ust. 1 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Czy przedsiewziecie obejmujace lokale na wynajem i lokale komunalne "
            "stanowi jedno przedsiewziecie, czy dwa odrebne wnioski? Od tego zalezy "
            "liczba okresow powierzenia i stosowanie limitu lacznego z art. 13 ust. 1a."
        ),
        waga_dla_wyniku="struktura wniosku, limit wsparcia, liczba testow nadwyzki",
        priorytet=2,
    ),
    Zalozenie(
        kod="ZALOZENIE_GRUNT_9_1",
        tytul="Grunt z trybu 'lokal za grunt' jako przychod uslugi publicznej",
        sciezka="przelaczniki.lokal_za_grunt_jest_przychodem_uoig",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="NIE jest — transakcja jest nabyciem, nie wniesieniem przez gmine",
        alternatywa="JEST; obniza dopuszczalna rekompensate o wartosc dzialki",
        podstawa="art. 5 ust. 9 pkt 4 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Czy grunt nabyty od gminy w trybie ustawy z 16.12.2020 (lokale w zamian "
            "za nieruchomosc) jest wartoscia wniesiona przez jednostke samorzadu "
            "terytorialnego w rozumieniu art. 5 ust. 9 pkt 4, czy zwyklym nabyciem?"
        ),
        waga_dla_wyniku="dopuszczalna rekompensata w tej formie gruntu",
        priorytet=3,
    ),
    Zalozenie(
        kod="ZALOZENIE_GRUNT_9_3",
        tytul="Bonifikata przy sprzedazy gruntu a pasmo dotacji",
        sciezka="przelaczniki.pasmo_liczone_od_wartosci_z_operatu",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="pasmo liczone od wartosci z operatu, nie od ceny po bonifikacie",
        alternatywa="od ceny zaplaconej; bonifikata scina wtedy pasmo dotacji",
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Przy nabyciu gruntu od gminy z bonifikata — czy pasmo wsparcia ponad prog "
            "gruntowy liczy sie od wartosci prawa z operatu, czy od ceny faktycznie "
            "zaplaconej?"
        ),
        waga_dla_wyniku="gorna granica dotacji przy zakupie z bonifikata",
        priorytet=3,
    ),
    Zalozenie(
        kod="ZALOZENIE_BONUS_A_PROG_GRUNTOWY",
        tytul="Czy bonus +5 pp podnosi takze prog gruntowy",
        sciezka="przelaczniki.bonus_podnosi_prog_gruntowy",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="NIE — bonus podnosi wylacznie limit gorny",
        alternatywa="TAK — oba progi ida w gore o 5 pp",
        podstawa="art. 13 ust. 1 pkt 1 w zw. z art. 13 ust. 4 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Czy zwiekszenie wsparcia o 5 punktow procentowych z art. 13 ust. 4 podnosi "
            "takze prog, powyzej ktorego wsparcie jest limitowane wartoscia gruntu "
            "we wladaniu inwestora, czy wylacznie limit gorny?"
        ),
        waga_dla_wyniku="kwota dotacji, gdy wiaze prog gruntowy, a nie limit gorny",
        priorytet=3,
    ),
    Zalozenie(
        kod="ZALOZENIE_KOSZTY_INWESTYCYJNE_W_KN",
        tytul="Ujecie nakladu inwestycyjnego w kosztach netto uslugi",
        sciezka="przelaczniki.koszty_inwestycyjne_w_kn",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="amortyzacja wg okresu amortyzacji budynkow",
        alternatywa="naklad w roku pierwszym, amortyzacja w okresie powierzenia albo pominiecie",
        podstawa="art. 5 ust. 7-8 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "W jaki sposob naklad inwestycyjny wchodzi do kosztow netto uslugi "
            "publicznej: jednorazowo w roku poniesienia, przez odpisy amortyzacyjne, "
            "czy proporcjonalnie do okresu powierzenia?"
        ),
        waga_dla_wyniku="wysokosc kosztow netto, a przez to dopuszczalna rekompensata",
        priorytet=3,
    ),
    Zalozenie(
        kod="ZALOZENIE_ROZSADNY_ZYSK",
        tytul="Metoda wyliczenia rozsadnego zysku",
        sciezka="przelaczniki.metoda_rozsadnego_zysku",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="stopa IRS BGK od kapitalu zaangazowanego, dyskontowana stopa bazowa",
        alternatywa="kwota podana wprost przez uzytkownika",
        podstawa="§ 6 ust. 5 rozp. Dz.U. 2025 poz. 1897; § 12 ust. 10 rozp. t.j. Dz.U. 2021 poz. 766",
        pytanie_do_bgk=(
            "Przepisy wskazuja stope IRS dla kontraktu 20-letniego na bazie WIBOR 3M "
            "jako podstawe rozsadnego zysku, ale nie podaja wzoru. Od jakiej podstawy "
            "nalicza sie te stope i czy wynik podlega dyskontowaniu?"
        ),
        waga_dla_wyniku="skladnik kwoty dopuszczalnej w tescie nadwyzki",
        priorytet=3,
    ),
    Zalozenie(
        kod="ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM",
        tytul="Z ktorej puli pochodza lokale oddawane gminie",
        sciezka="przelaczniki.lokale_dla_gminy_z_puli",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="proporcjonalnie z obu pul, kluczem PUM",
        alternatywa="w calosci z puli komunalnej albo w calosci ze spolecznej",
        podstawa="ustawa z 16.12.2020, Dz.U. 2021 poz. 223",
        pytanie_do_bgk=(
            "Przy rozliczeniu 'lokal za grunt' — czy lokale przekazywane gminie moga "
            "pochodzic z dowolnej czesci przedsiewziecia, czy musza byc wskazane "
            "w konkretnej puli? Pytanie kierowane rownolegle do gminy jako strony umowy."
        ),
        waga_dla_wyniku="ktora pula traci przychod przy zachowaniu pelnego kosztu",
        priorytet=4,
    ),
    Zalozenie(
        kod="ZALOZENIE_PASMO_OD_CENY",
        tytul="Pasmo dotacji liczone od ceny po bonifikacie",
        sciezka="przelaczniki.pasmo_liczone_od_wartosci_z_operatu",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="pasmo od wartosci z operatu",
        alternatywa="pasmo od ceny nabycia — wariant wlaczony tym samym przelacznikiem",
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
        pytanie_do_bgk=(
            "Przy nabyciu gruntu od gminy z bonifikata — czy pasmo wsparcia ponad prog "
            "gruntowy liczy sie od wartosci prawa z operatu, czy od ceny faktycznie "
            "zaplaconej?"
        ),
        waga_dla_wyniku="gorna granica dotacji przy zakupie z bonifikata",
        priorytet=4,
        duplikat_pytania="ZALOZENIE_GRUNT_9_3",
    ),
    Zalozenie(
        kod="ZALOZENIE_PUSTOSTANY_KOMUNALNE",
        tytul="Czy wskaznik pustostanow obciaza pule komunalna",
        sciezka="przelaczniki.pustostany_takze_w_puli_komunalnej",
        mechanizm=PRZEZ_PRZELACZNIK,
        domyslnie="NIE — najemca calej puli jest gmina, ryzyko zostaje po jej stronie",
        alternatywa="TAK — pula komunalna traci przychod tak samo jak spoleczna",
        podstawa="poza przepisem — rozstrzygniecie umowne miedzy spolka a gmina",
        pytanie_do_bgk=(
            "Pytanie nie do Banku, tylko do gminy: czy umowa najmu calej puli komunalnej "
            "przewiduje czynsz niezalezny od zasiedlenia lokali?"
        ),
        waga_dla_wyniku="przychod puli komunalnej i jej podloga czynszowa",
        priorytet=4,
    ),
)

WEDLUG_KODU = {z.kod: z for z in KATALOG}


def zalozenie(kod: str) -> Zalozenie:
    try:
        return WEDLUG_KODU[kod]
    except KeyError as exc:
        raise KeyError(
            f"Kod {kod!r} nie ma wpisu w katalogu zalozen. Kazde ostrzezenie "
            "ZALOZENIE_* musi miec wpis wraz ze scenariuszem rozstrzygajacym."
        ) from exc


def wedlug_priorytetu() -> Tuple[Zalozenie, ...]:
    """Katalog w kolejnosci, w jakiej pytania maja isc do Banku."""
    return tuple(sorted(KATALOG, key=lambda z: (z.priorytet, z.kod)))


def do_pisma() -> Tuple[Zalozenie, ...]:
    """Pytania bez powtorzen — jedno na watpliwosc, nie jedno na kod."""
    return tuple(z for z in wedlug_priorytetu() if z.idzie_do_pisma)
