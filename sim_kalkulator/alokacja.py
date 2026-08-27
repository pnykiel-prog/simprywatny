"""Podzial kosztow wspolnych miedzy pule.

Koszty wspolne — grunt, infrastruktura, projekt i nadzor, koszty ogolne, rezerwa,
dzwigi — dziela sie miedzy pule proporcjonalnie do PUM. Koszt budowy przypisuje
sie kazdej puli wprost, wg jej wlasnej powierzchni.

Wartosc gruntu dzieli sie tym samym kluczem co reszta kosztow wspolnych.
Przypisanie pelnej wartosci gruntu obu pulom byloby policzeniem jej dwa razy.

Pozycja gruntowa wchodzi tu wylacznie kanalem B (wartosc w kosztach) — o tym,
ile jej wchodzi, rozstrzyga `grunt.rozstrzygnij`. Kanal A (wartosc do pasma
dotacji) jedzie osobna kolumna, bo limit z § 12 ust. 7 rozp. 766 dotyczy
kosztow, a nie wartosci prawa z art. 13 ust. 1 pkt 1.

Powierzchnia przychodowa jest osobna od powierzchni kosztowej: w wariancie
"lokal za grunt" czesc lokali trafia do gminy, wiec nie przynosi czynszu, ale
trzeba ja wybudowac.

Modul nie zawiera zadnej liczby z ustawy — VAT-owy wymog z art. 13 ust. 3
realizowany jest przez flage wejsciowa `koszty.vat_odliczalny`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Iterator, Optional, Tuple

from . import prawo
from .dane import Wejscie, ZrodloLokaliDlaGminy
from .grunt import UjecieGruntu, rozstrzygnij
from .waluta import ZERO, bezpieczny_iloraz, na_m2, zl


@dataclass(frozen=True)
class PulaKosztow:
    """Koszty przypisane jednej puli. Wszystkie kwoty netto, bez VAT."""

    nazwa: str
    pum: Decimal                     # powierzchnia wybudowana — podstawa kosztow
    pum_przychodowe: Decimal         # powierzchnia przynoszaca czynsz SIM
    udzial_pum: Decimal              # klucz alokacji kosztow wspolnych
    koszt_budowy: Decimal            # bezposredni, wg wlasnego PUM
    grunt: Decimal                   # kanal B — wartosc gruntu w kosztach, po limicie
    grunt_do_pasma: Decimal          # kanal A — wartosc prawa do limitu art. 13 ust. 1 pkt 1
    grunt_obciety_limitem: Decimal   # ile scial § 12 ust. 7 rozp. 766
    infrastruktura: Decimal
    projekt_i_nadzor: Decimal
    koszty_ogolne: Decimal
    rezerwa: Decimal
    dzwigi: Decimal
    vat_odliczalny: bool
    stawka_vat: Decimal

    @property
    def koszty_wspolne(self) -> Decimal:
        return (
            self.grunt
            + self.infrastruktura
            + self.projekt_i_nadzor
            + self.koszty_ogolne
            + self.rezerwa
            + self.dzwigi
        )

    @property
    def koszty_przedsiewziecia_netto(self) -> Decimal:
        return self.koszt_budowy + self.koszty_wspolne

    @property
    def koszty_przedsiewziecia(self) -> Decimal:
        """Koszty przedsiewziecia w ujeciu, w ktorym obciazaja inwestora.

        art. 13 ust. 3 ustawy z 8.12.2006: VAT wchodzi do podstawy wsparcia tylko
        wtedy, gdy inwestorowi nie przysluguje prawo do odliczenia lub zwrotu.
        Gdy VAT jest nieodliczalny, jest realnym wydatkiem — stad ta sama kwota
        sluzy za podstawe grantu i za kwote do sfinansowania w montazu.
        """
        if self.vat_odliczalny:
            return self.koszty_przedsiewziecia_netto
        return self.koszty_przedsiewziecia_netto * (Decimal(1) + self.stawka_vat)

    @property
    def koszty_przedsiewziecia_bez_gruntu(self) -> Decimal:
        """Koszty przedsiewziecia z wylaczeniem pozycji gruntowej.

        Grunt ma w rachunku kosztow netto wlasna, asymetryczna regule (raz koszt,
        raz przychod, raz koszt limitowany), wiec nie moze siedziec dodatkowo
        w nakladzie inwestycyjnym — inaczej trafia do KN dwa razy.
        """
        return self.koszty_przedsiewziecia - self.grunt_w_podstawie

    @property
    def grunt_w_podstawie(self) -> Decimal:
        """Wartosc gruntu w kosztach, w tym samym ujeciu VAT co reszta pozycji."""
        return self._w_ujeciu_vat(self.grunt)

    @property
    def grunt_do_pasma_w_podstawie(self) -> Decimal:
        """Wartosc prawa do limitu z art. 13 ust. 1 pkt 1, w ujeciu VAT kosztow.

        Rozni sie od `grunt_w_podstawie` przy aporcie w sciezce kredytowej: limit
        z § 12 ust. 7 rozp. 766 obcina wartosc w KOSZTACH, ale art. 13 ust. 1 pkt 1
        mowi o wartosci PRAWA i zadnego limitu procentowego nie zawiera.
        """
        return self._w_ujeciu_vat(self.grunt_do_pasma)

    def _w_ujeciu_vat(self, kwota: Decimal) -> Decimal:
        if self.vat_odliczalny:
            return kwota
        return kwota * (Decimal(1) + self.stawka_vat)

    @property
    def pum_oddane_gminie(self) -> Decimal:
        """Powierzchnia wybudowana, ktora nie przyniesie czynszu — lokal za grunt."""
        return self.pum - self.pum_przychodowe

    @property
    def przynosi_przychod(self) -> bool:
        return self.pum_przychodowe > ZERO

    @property
    def koszt_budowy_lokalu_na_m2(self) -> Decimal:
        """Koszt przedsiewziecia na m2 PUM, z wartoscia nieruchomosci.

        Podstawa alternatywna dla limitu czynszu — art. 28 ust. 2b ustawy z 26.10.1995.
        """
        return na_m2(self.koszty_przedsiewziecia, self.pum)

    @property
    def aktywna(self) -> bool:
        return self.pum > ZERO

    def pozycje(self) -> Tuple[Tuple[str, Decimal], ...]:
        """Rozbicie do arkusza i UI."""
        return (
            ("Koszt budowy", self.koszt_budowy),
            ("Grunt", self.grunt),
            ("Infrastruktura", self.infrastruktura),
            ("Projekt i nadzor", self.projekt_i_nadzor),
            ("Koszty ogolne", self.koszty_ogolne),
            ("Rezerwa", self.rezerwa),
            ("Dzwigi", self.dzwigi),
        )


@dataclass(frozen=True)
class Alokacja:
    spoleczna: PulaKosztow
    komunalna: PulaKosztow
    pum_laczne: Decimal                    # powierzchnia wybudowana
    pum_przychodowe_laczne: Decimal        # powierzchnia przynoszaca czynsz SIM
    grunt_obciety_limitem: Decimal         # laczna kwota scieta § 12 ust. 7 rozp. 766

    @property
    def koszty_laczne_netto(self) -> Decimal:
        return (
            self.spoleczna.koszty_przedsiewziecia_netto
            + self.komunalna.koszty_przedsiewziecia_netto
        )

    @property
    def koszty_laczne(self) -> Decimal:
        return self.spoleczna.koszty_przedsiewziecia + self.komunalna.koszty_przedsiewziecia

    @property
    def grunt_laczny(self) -> Decimal:
        """Wartosc gruntu faktycznie uznana w kosztach obu pul — kanal B."""
        return self.spoleczna.grunt + self.komunalna.grunt

    @property
    def grunt_do_pasma_laczny(self) -> Decimal:
        """Wartosc prawa wchodzaca do limitu z art. 13 ust. 1 pkt 1 — kanal A."""
        return self.spoleczna.grunt_do_pasma + self.komunalna.grunt_do_pasma

    @property
    def pum_oddane_gminie(self) -> Decimal:
        return self.pum_laczne - self.pum_przychodowe_laczne

    def __iter__(self) -> Iterator[PulaKosztow]:
        return iter((self.spoleczna, self.komunalna))


def _udzial_po_oddaniu(pum_puli: Decimal, pum_dla_gminy: Decimal) -> Decimal:
    """Udzial powierzchni przychodowej puli, ktora oddaje gminie caly pakiet.

    Gdy lokale dla gminy nie miesza sie w puli, udzial schodzi do zera, a reszta
    zostaje nierozliczona. Model nie przerzuca nadwyzki na druga pule po cichu —
    to byloby ciche wybranie trzeciej interpretacji zamiast tej, ktora wskazano.
    Sytuacje zglasza `grunt.rozstrzygnij` osobnym ostrzezeniem.
    """
    if pum_puli <= ZERO:
        return Decimal(1)
    return max(ZERO, (pum_puli - pum_dla_gminy) / pum_puli)


def build(w: Wejscie, u: Optional[UjecieGruntu] = None) -> Alokacja:
    """Dzieli koszty przedsiewziecia na pule kluczem PUM.

    `u` to rozstrzygniecie kanalow gruntowych. Pominiete — liczone tu na miejscu,
    zeby wywolania spoza silnika nie musialy o nim wiedziec.
    """
    p = w.powierzchnie
    k = w.koszty
    if u is None:
        u = rozstrzygnij(w)

    udzial_komunalny = p.udzial_puli_komunalnej
    udzial_spoleczny = Decimal(1) - udzial_komunalny

    # Lokale oddawane gminie w trybie "lokal za grunt" trzeba wybudowac, ale nie
    # przyniosa czynszu. Specyfikacja nie wskazuje puli, z ktorej pochodza, wiec
    # model scina powierzchnie przychodowa obu pul tym samym kluczem PUM —
    # ZALOZENIE zglaszane przez `grunt.rozstrzygnij`.
    # Wersja domyslna — obie pule oddaja proporcjonalnie. Przelacznik
    # `lokale_dla_gminy_z_puli` pozwala obciazyc jedna z nich w calosci; wybor
    # nie jest obojetny, bo pula, ktora oddaje, traci przychod przy pelnym koszcie.
    udzial_przychodowy_spoleczna = Decimal(1)
    udzial_przychodowy_komunalna = Decimal(1)
    if u.pum_dla_gminy > ZERO and p.pum_laczne > ZERO:
        zrodlo = w.przelaczniki.lokale_dla_gminy_z_puli
        if zrodlo is ZrodloLokaliDlaGminy.PROPORCJONALNIE:
            wspolny = (p.pum_laczne - u.pum_dla_gminy) / p.pum_laczne
            udzial_przychodowy_spoleczna = wspolny
            udzial_przychodowy_komunalna = wspolny
        elif zrodlo is ZrodloLokaliDlaGminy.SPOLECZNA:
            udzial_przychodowy_spoleczna = _udzial_po_oddaniu(
                p.pum_spoleczne, u.pum_dla_gminy
            )
        else:
            udzial_przychodowy_komunalna = _udzial_po_oddaniu(
                p.pum_komunalne, u.pum_dla_gminy
            )

    # § 12 ust. 7 rozp. 766 dotyczy przedsiewziecia finansowanego zwrotnie.
    # Domyslnie hybryda to dwa odrebne przedsiewziecia, wiec limit siega tylko
    # tej puli, ktora korzysta z kredytu.
    kredyt_aktywny = w.pula_spoleczna.kredyt.aktywny

    def pula(
        nazwa: str, pum: Decimal, udzial: Decimal, kredytowa: bool,
        udzial_przychodowy: Decimal,
    ) -> PulaKosztow:
        koszty_bez_gruntu = (
            k.koszt_budowy_na_m2 * pum
            + (k.infrastruktura + k.projekt_i_nadzor + k.koszty_ogolne + k.rezerwa + k.dzwigi)
            * udzial
        )
        grunt_pelny = u.wartosc_w_kosztach * udzial
        grunt_uznany = grunt_pelny
        if u.limit_aportowy_dotyczy and kredytowa:
            grunt_uznany = min(
                grunt_pelny, prawo.grunt_aport_maksymalny_w_kosztach(koszty_bez_gruntu)
            )
        return PulaKosztow(
            nazwa=nazwa,
            pum=pum,
            pum_przychodowe=pum * udzial_przychodowy,
            udzial_pum=udzial,
            koszt_budowy=k.koszt_budowy_na_m2 * pum,
            grunt=grunt_uznany,
            grunt_do_pasma=u.wartosc_do_pasma * udzial,
            grunt_obciety_limitem=grunt_pelny - grunt_uznany,
            infrastruktura=k.infrastruktura * udzial,
            projekt_i_nadzor=k.projekt_i_nadzor * udzial,
            koszty_ogolne=k.koszty_ogolne * udzial,
            rezerwa=k.rezerwa * udzial,
            dzwigi=k.dzwigi * udzial,
            vat_odliczalny=k.vat_odliczalny,
            stawka_vat=k.stawka_vat,
        )

    alokacja = Alokacja(
        spoleczna=pula(
            "spoleczna", p.pum_spoleczne, udzial_spoleczny, kredyt_aktywny,
            udzial_przychodowy_spoleczna,
        ),
        komunalna=pula(
            "komunalna", p.pum_komunalne, udzial_komunalny, False,
            udzial_przychodowy_komunalna,
        ),
        pum_laczne=p.pum_laczne,
        pum_przychodowe_laczne=p.pum_laczne - u.pum_dla_gminy,
        grunt_obciety_limitem=ZERO,
    )
    alokacja = replace(
        alokacja,
        grunt_obciety_limitem=(
            alokacja.spoleczna.grunt_obciety_limitem + alokacja.komunalna.grunt_obciety_limitem
        ),
    )

    # Kontrola zamkniecia: klucz PUM ma rozdzielic koszty wspolne bez reszty.
    # Grunt wchodzi do kontroli w kwocie faktycznie uznanej, bo limit aportowy
    # obcina go zanim trafi do kosztow.
    koszty_wspolne_wejsciowe = (
        alokacja.grunt_laczny
        + k.infrastruktura
        + k.projekt_i_nadzor
        + k.koszty_ogolne
        + k.rezerwa
        + k.dzwigi
    )
    rozjazd = (
        alokacja.spoleczna.koszty_wspolne + alokacja.komunalna.koszty_wspolne
    ) - koszty_wspolne_wejsciowe
    assert abs(rozjazd) < Decimal("0.01"), (
        f"Alokacja kosztow wspolnych nie zamyka sie: rozjazd {rozjazd}. "
        "Wartosc gruntu albo innej pozycji wspolnej zostala policzona podwojnie."
    )
    return alokacja


def udzial_wsparcia(grant: Decimal, koszty_przedsiewziecia: Decimal) -> Decimal:
    """Udzial wsparcia w kosztach przedsiewziecia — wejscie do tabeli art. 7c."""
    return bezpieczny_iloraz(zl(grant), zl(koszty_przedsiewziecia))
