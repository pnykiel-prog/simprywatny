"""Podzial kosztow wspolnych miedzy pule.

Koszty wspolne — grunt, infrastruktura, projekt i nadzor, koszty ogolne, rezerwa,
dzwigi — dziela sie miedzy pule proporcjonalnie do PUM. Koszt budowy przypisuje
sie kazdej puli wprost, wg jej wlasnej powierzchni.

Wartosc gruntu dzieli sie tym samym kluczem co reszta kosztow wspolnych.
Przypisanie pelnej wartosci gruntu obu pulom byloby policzeniem jej dwa razy.

Modul nie zawiera zadnej liczby z ustawy — VAT-owy wymog z art. 13 ust. 3
realizowany jest przez flage wejsciowa `koszty.vat_odliczalny`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator, Tuple

from .dane import Wejscie
from .waluta import ZERO, bezpieczny_iloraz, na_m2, zl


@dataclass(frozen=True)
class PulaKosztow:
    """Koszty przypisane jednej puli. Wszystkie kwoty netto, bez VAT."""

    nazwa: str
    pum: Decimal
    udzial_pum: Decimal              # klucz alokacji kosztow wspolnych
    koszt_budowy: Decimal            # bezposredni, wg wlasnego PUM
    grunt: Decimal                   # udzial w wartosci gruntu, klucz PUM
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
        """Wartosc gruntu w tym samym ujeciu VAT co koszty — do limitu z art. 13 ust. 1 pkt 1."""
        if self.vat_odliczalny:
            return self.grunt
        return self.grunt * (Decimal(1) + self.stawka_vat)

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
    pum_laczne: Decimal

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
        return self.spoleczna.grunt + self.komunalna.grunt

    def __iter__(self) -> Iterator[PulaKosztow]:
        return iter((self.spoleczna, self.komunalna))


def build(w: Wejscie) -> Alokacja:
    """Dzieli koszty przedsiewziecia na pule kluczem PUM."""
    p = w.powierzchnie
    k = w.koszty

    udzial_komunalny = p.udzial_puli_komunalnej
    udzial_spoleczny = Decimal(1) - udzial_komunalny

    def pula(nazwa: str, pum: Decimal, udzial: Decimal) -> PulaKosztow:
        return PulaKosztow(
            nazwa=nazwa,
            pum=pum,
            udzial_pum=udzial,
            koszt_budowy=k.koszt_budowy_na_m2 * pum,
            grunt=w.grunt.wartosc * udzial,
            infrastruktura=k.infrastruktura * udzial,
            projekt_i_nadzor=k.projekt_i_nadzor * udzial,
            koszty_ogolne=k.koszty_ogolne * udzial,
            rezerwa=k.rezerwa * udzial,
            dzwigi=k.dzwigi * udzial,
            vat_odliczalny=k.vat_odliczalny,
            stawka_vat=k.stawka_vat,
        )

    alokacja = Alokacja(
        spoleczna=pula("spoleczna", p.pum_spoleczne, udzial_spoleczny),
        komunalna=pula("komunalna", p.pum_komunalne, udzial_komunalny),
        pum_laczne=p.pum_laczne,
    )

    # Kontrola zamkniecia: klucz PUM ma rozdzielic koszty wspolne bez reszty.
    koszty_wspolne_wejsciowe = (
        w.grunt.wartosc + k.infrastruktura + k.projekt_i_nadzor + k.koszty_ogolne + k.rezerwa + k.dzwigi
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
