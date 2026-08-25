"""Limity czynszu i wybor limitu wiazacego.

Na ten sam lokal nakladaja sie dwa niezalezne limity — wiaze nizszy:
  * art. 7c ustawy z 8.12.2006 — procent wartosci odtworzeniowej rocznie,
    zalezny od udzialu wsparcia w kosztach przedsiewziecia,
  * art. 28 ust. 2 pkt 2 ustawy z 26.10.1995 — 5% wartosci odtworzeniowej
    rocznie dla lokali wybudowanych przy wykorzystaniu finansowania zwrotnego.

Podstawa naliczenia — art. 28 ust. 2b: gdy wartosc odtworzeniowa lokalu jest
nizsza niz koszt budowy uwzgledniajacy wartosc nieruchomosci, podstawa jest
koszt budowy. Silnik liczy obie i bierze wyzsza.

Oplaty z art. 28 ust. 4-5 sa osobnym strumieniem z wlasnym limitem — nigdy nie
sa doliczane do czynszu.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from . import prawo
from .alokacja import PulaKosztow
from .dane import BladWalidacji, Wejscie
from .grant import GrantPuli
from .waluta import ZERO, na_m2

MIESIECY_W_ROKU = Decimal(12)


@dataclass(frozen=True)
class LimityCzynszu:
    nazwa_puli: str
    podstawa_wartosc_odtworzeniowa_m2: Decimal
    podstawa_koszt_budowy_m2: Decimal
    podstawa_wiazaca_m2: Decimal
    podstawa_wiazaca_zrodlo: str
    udzial_wsparcia: Decimal
    stawka_art_7c: Decimal
    limit_art_7c_m2_mies: Decimal
    stawka_art_28: Optional[Decimal]
    limit_art_28_m2_mies: Optional[Decimal]
    limit_wiazacy_m2_mies: Decimal
    limit_wiazacy_zrodlo: str
    czynsz_zakladany_m2_mies: Decimal
    limit_oplat_poza_czynszem_m2_mies: Decimal

    @property
    def limit_wiazacy_m2_rok(self) -> Decimal:
        return self.limit_wiazacy_m2_mies * MIESIECY_W_ROKU

    @property
    def zapas_do_limitu_m2_mies(self) -> Decimal:
        return self.limit_wiazacy_m2_mies - self.czynsz_zakladany_m2_mies


def _limit_miesieczny(podstawa_m2: Decimal, stawka_roczna: Decimal) -> Decimal:
    return podstawa_m2 * stawka_roczna / MIESIECY_W_ROKU


def build(
    w: Wejscie,
    pula: PulaKosztow,
    g: GrantPuli,
    czynsz_zakladany_m2_mies: Decimal,
    finansowanie_zwrotne: bool,
) -> LimityCzynszu:
    """Liczy limity dla jednej puli i sprawdza, czy zakladany czynsz sie w nich miesci."""
    wartosc_odtworzeniowa_m2 = w.parametry_zewnetrzne.wartosc_odtworzeniowa_m2
    koszt_budowy_m2 = pula.koszt_budowy_lokalu_na_m2 if pula.aktywna else ZERO

    # art. 28 ust. 2b — podstawa wyzsza z dwoch. Przy drogim gruncie dziala na
    # korzysc inwestora, bo koszt budowy z wartoscia nieruchomosci przebija
    # wskaznik wojewody.
    if koszt_budowy_m2 > wartosc_odtworzeniowa_m2:
        podstawa_m2 = koszt_budowy_m2
        podstawa_zrodlo = "koszt budowy z wartoscia nieruchomosci (art. 28 ust. 2b)"
    else:
        podstawa_m2 = wartosc_odtworzeniowa_m2
        podstawa_zrodlo = "wartosc odtworzeniowa lokalu (obwieszczenie wojewody)"

    udzial = g.udzial_wsparcia
    stawka_7c = prawo.limit_czynszu_art_7c(
        udzial, remont_i_przebudowa=w.przelaczniki.remont_i_przebudowa
    )
    limit_7c = _limit_miesieczny(podstawa_m2, stawka_7c)

    stawka_28: Optional[Decimal] = None
    limit_28: Optional[Decimal] = None
    if finansowanie_zwrotne:
        stawka_28 = prawo.LIMIT_CZYNSZU_FINANSOWANIE_ZWROTNE
        limit_28 = _limit_miesieczny(podstawa_m2, stawka_28)

    if limit_28 is not None and limit_28 < limit_7c:
        limit_wiazacy = limit_28
        zrodlo = "art. 28 ust. 2 pkt 2 ustawy z 26.10.1995"
    else:
        limit_wiazacy = limit_7c
        zrodlo = "art. 7c ustawy z 8.12.2006"

    # art. 28 ust. 4-5 — osobny strumien, wlasny limit, nigdy nie doliczany do czynszu.
    limit_oplat = _limit_miesieczny(
        wartosc_odtworzeniowa_m2, prawo.LIMIT_OPLAT_POZA_CZYNSZEM
    )

    limity = LimityCzynszu(
        nazwa_puli=pula.nazwa,
        podstawa_wartosc_odtworzeniowa_m2=wartosc_odtworzeniowa_m2,
        podstawa_koszt_budowy_m2=koszt_budowy_m2,
        podstawa_wiazaca_m2=podstawa_m2,
        podstawa_wiazaca_zrodlo=podstawa_zrodlo,
        udzial_wsparcia=udzial,
        stawka_art_7c=stawka_7c,
        limit_art_7c_m2_mies=limit_7c,
        stawka_art_28=stawka_28,
        limit_art_28_m2_mies=limit_28,
        limit_wiazacy_m2_mies=limit_wiazacy,
        limit_wiazacy_zrodlo=zrodlo,
        czynsz_zakladany_m2_mies=czynsz_zakladany_m2_mies,
        limit_oplat_poza_czynszem_m2_mies=limit_oplat,
    )

    if pula.aktywna and czynsz_zakladany_m2_mies > limit_wiazacy:
        # Specyfikacja, rozdz. 6 test 2: przekroczenie limitu to twardy blad
        # walidacji, nie porazka testu. Model nie liczy scenariusza bezprawnego.
        raise BladWalidacji(
            f"Czynsz zakladany w puli {pula.nazwa} wynosi "
            f"{czynsz_zakladany_m2_mies:.2f} zl/m2/mies. i przekracza limit wiazacy "
            f"{limit_wiazacy:.2f} zl/m2/mies. ({zrodlo}, stawka {stawka_7c:.1%} rocznie od "
            f"podstawy {podstawa_m2:.2f} zl/m2 — {podstawa_zrodlo}). "
            "Obnizz czynsz albo zmien montaz; silnik nie liczy scenariusza ponad limit."
        )

    return limity


def czynsz_wymagany_do_domkniecia(
    potrzeba_roczna: Decimal, pum: Decimal, obloznosc: Decimal
) -> Decimal:
    """Stawka czynszu, przy ktorej przychod pokrywa podana potrzebe roczna.

    Zwraca zl/m2/mies. przy zadanym obłozeniu (1 - pustostany).
    """
    if pum <= ZERO or obloznosc <= ZERO:
        return ZERO
    return potrzeba_roczna / (pum * obloznosc * MIESIECY_W_ROKU)


def oplaty_poza_czynszem_rocznie(w: Wejscie, pum: Decimal) -> Decimal:
    """Gorny pulap oplat z art. 28 ust. 4-5 dla danej powierzchni, rocznie.

    Osobna pozycja modelu. Nie wchodzi do przychodu czynszowego w tescie 2.
    """
    return (
        w.parametry_zewnetrzne.wartosc_odtworzeniowa_m2
        * prawo.LIMIT_OPLAT_POZA_CZYNSZEM
        * pum
    )
