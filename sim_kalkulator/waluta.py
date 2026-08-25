"""Pomocnicze operacje na kwotach.

Modul celowo nie zawiera zadnej liczby pochodzacej z przepisow — te sa
wylacznie w `prawo.py`. Tutaj mieszka tylko arytmetyka pieniadza.

Zasada projektu: kwoty sa typu Decimal (model operuje na pieniadzach przez
30 lat), stopy i wskazniki moga byc typu float. Mnozenie Decimal przez float
jest w Pythonie bledem typu, wiec kazde przejscie miedzy swiatami przechodzi
przez jawna konwersje w `mnoz`.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Union

Liczba = Union[int, float, str, Decimal]

ZERO = Decimal("0")
GROSZ = Decimal("0.01")


def zl(wartosc: Liczba) -> Decimal:
    """Zamienia wartosc na kwote w PLN jako Decimal.

    Konwersja z float idzie przez `repr`, zeby 1234.56 nie stalo sie
    1234.5599999999999... — to jest jedyne miejsce, w ktorym float dotyka kwoty.
    """
    if isinstance(wartosc, Decimal):
        return wartosc
    if isinstance(wartosc, float):
        return Decimal(repr(wartosc))
    return Decimal(wartosc)


def stopa(wartosc: Liczba) -> Decimal:
    """Zamienia stope/wskaznik na Decimal, zeby mogl mnozyc kwote."""
    return zl(wartosc)


def mnoz(kwota: Decimal, wskaznik: Liczba) -> Decimal:
    """Mnozy kwote przez wskaznik podany jako float, int albo Decimal."""
    return zl(kwota) * stopa(wskaznik)


def grosze(kwota: Decimal) -> Decimal:
    """Zaokragla kwote do pelnych groszy — wylacznie do prezentacji i eksportu."""
    return zl(kwota).quantize(GROSZ, rounding=ROUND_HALF_UP)


def pelne_zlote_w_dol(kwota: Decimal) -> Decimal:
    """Zaokragla kwote w dol do pelnych zlotych.

    Uzywane tam, gdzie kwota jest wynikiem dzielenia i zasila warunek progowy.
    Bank i tak udziela kredytu w kwotach zaokraglonych, a zaokraglenie w dol
    zostawia po wlasciwej stronie progu — bez tego wskaznik pokrycia potrafi
    wyjsc 0,999...8 i przewrocic werdykt na dwudziestym osmym miejscu po przecinku.
    """
    return zl(kwota).quantize(Decimal("1"), rounding=ROUND_DOWN)


def na_m2(kwota: Decimal, pum: Decimal) -> Decimal:
    """Wskaznik na m2 PUM. Metodyka projektu wymaga liczenia na metr, nie na lokal."""
    pum = zl(pum)
    if pum == ZERO:
        return ZERO
    return zl(kwota) / pum


def bezpieczny_iloraz(licznik: Decimal, mianownik: Decimal, gdy_zero: Decimal = ZERO) -> Decimal:
    mianownik = zl(mianownik)
    if mianownik == ZERO:
        return gdy_zero
    return zl(licznik) / mianownik
