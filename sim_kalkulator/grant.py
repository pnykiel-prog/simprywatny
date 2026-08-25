"""Wysokosc wsparcia bezzwrotnego, limity i bonus.

Grant spoleczny nie jest po prostu 45% kosztow. Czesc przekraczajaca prog
gruntowy pokrywana jest wylacznie do wysokosci wartosci prawa wlasnosci albo
uzytkowania wieczystego gruntu bedacego we wladaniu inwestora — art. 13 ust. 1
pkt 1 ustawy z 8.12.2006. Bez gruntu inwestora realna stawka to prog gruntowy.

Wszystkie progi pochodza z `prawo.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from . import prawo
from .alokacja import Alokacja, PulaKosztow
from .dane import FormaGruntu, Ostrzezenie, Wejscie, Waga
from .waluta import ZERO, bezpieczny_iloraz


@dataclass(frozen=True)
class GrantPuli:
    nazwa: str
    kwota: Decimal
    stawka_nominalna: Decimal        # limit procentowy zastosowany do kosztow
    limit_bez_gruntu: Decimal        # 0.35 * K + G_inwestora, albo brak (None -> Decimal max)
    ograniczony_gruntem: bool
    bonus_zastosowany: bool
    podstawa_kosztowa: Decimal
    podstawa_prawna: str

    @property
    def udzial_wsparcia(self) -> Decimal:
        """Udzial wsparcia w kosztach przedsiewziecia — wejscie do tabeli art. 7c."""
        return bezpieczny_iloraz(self.kwota, self.podstawa_kosztowa)


@dataclass(frozen=True)
class Granty:
    spoleczna: GrantPuli
    komunalna: GrantPuli
    ograniczony_limitem_hybrydy: bool
    ostrzezenia: Tuple[Ostrzezenie, ...]

    @property
    def kwota_laczna(self) -> Decimal:
        return self.spoleczna.kwota + self.komunalna.kwota


def grunt_liczy_sie_do_limitu(w: Wejscie) -> bool:
    """Czy wartosc gruntu podnosi limit grantu spolecznego ponad prog gruntowy.

    art. 13 ust. 1 pkt 1: liczy sie grunt "bedacy we wladaniu inwestora".
    Grunt pochodzacy od JST jest po wniesieniu we wladaniu inwestora, ale nie
    pochodzi z jego majatku — odczyt jest sporny, wiec siedzi na przelaczniku
    `grunt_jst_liczy_sie_do_limitu_grantu` z jawnym oznaczeniem zalozenia.
    """
    if w.grunt.forma.pochodzi_od_jst:
        return w.przelaczniki.grunt_jst_liczy_sie_do_limitu_grantu
    return True


def _grant_spoleczny(w: Wejscie, pula: PulaKosztow, ostrzezenia: List[Ostrzezenie]) -> GrantPuli:
    koszty = pula.koszty_przedsiewziecia
    if not pula.aktywna:
        return GrantPuli(
            nazwa="spoleczna",
            kwota=ZERO,
            stawka_nominalna=ZERO,
            limit_bez_gruntu=ZERO,
            ograniczony_gruntem=False,
            bonus_zastosowany=False,
            podstawa_kosztowa=koszty,
            podstawa_prawna="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
        )

    bonus = w.pula_spoleczna.bonus_rewitalizacyjny and not w.pula_spoleczna.kredyt.aktywny
    stawka = prawo.GRANT_SPOLECZNY_LIMIT_PODSTAWOWY
    if bonus:
        # art. 13 ust. 4 — +5 pp; wylaczony przy finansowaniu zwrotnym (walidacja w dane.py).
        stawka += prawo.BONUS_REWITALIZACYJNY_PP
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_BONUS_A_PROG_GRUNTOWY",
                tresc=(
                    "Bonus +5 pp zastosowany w puli spolecznej. Przyjeto, ze bonus podnosi "
                    "wylacznie limit gorny, a prog gruntowy pozostaje na poziomie "
                    f"{prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%}. Odczyt alternatywny podnosilby "
                    "oba progi o 5 pp i dawal wyzszy grant przy skromnym gruncie. "
                    "ZALOZENIE do potwierdzenia w BGK — patrz LUKI.md."
                ),
                podstawa="art. 13 ust. 1 pkt 1 w zw. z art. 13 ust. 4 ustawy z 8.12.2006",
            
                tresc_potoczna=(
                    "Dodatkowe 5% dotacji naliczono przy zalozeniu, ze nie podnosi ono progu "
                    "gruntowego. Odczyt alternatywny dalby wyzsza dotacje — do potwierdzenia w Banku."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    grunt_wliczany = pula.grunt_w_podstawie if grunt_liczy_sie_do_limitu(w) else ZERO
    limit_gorny = koszty * stawka
    limit_gruntowy = koszty * prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY + grunt_wliczany

    kwota = min(limit_gorny, limit_gruntowy)
    return GrantPuli(
        nazwa="spoleczna",
        kwota=kwota,
        stawka_nominalna=stawka,
        limit_bez_gruntu=limit_gruntowy,
        ograniczony_gruntem=limit_gruntowy < limit_gorny,
        bonus_zastosowany=bonus,
        podstawa_kosztowa=koszty,
        podstawa_prawna="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
    )


def _grant_komunalny(w: Wejscie, pula: PulaKosztow) -> GrantPuli:
    koszty = pula.koszty_przedsiewziecia
    if not pula.aktywna:
        return GrantPuli(
            nazwa="komunalna",
            kwota=ZERO,
            stawka_nominalna=ZERO,
            limit_bez_gruntu=ZERO,
            ograniczony_gruntem=False,
            bonus_zastosowany=False,
            podstawa_kosztowa=koszty,
            podstawa_prawna="art. 13 ust. 1 pkt 3 lit. c w zw. z art. 5a ust. 1 ustawy z 8.12.2006",
        )

    # W puli komunalnej kredytu nie ma z definicji (art. 5a ust. 3), wiec bonus
    # z art. 13 ust. 4 jest tu dostepny bez dodatkowego warunku.
    stawka = prawo.GRANT_KOMUNALNY
    bonus = w.pula_komunalna.bonus_rewitalizacyjny
    if bonus:
        stawka += prawo.BONUS_REWITALIZACYJNY_PP

    # art. 13 ust. 1 pkt 3 lit. c nie zawiera warunku gruntowego z pkt 1.
    return GrantPuli(
        nazwa="komunalna",
        kwota=koszty * stawka,
        stawka_nominalna=stawka,
        limit_bez_gruntu=koszty * stawka,
        ograniczony_gruntem=False,
        bonus_zastosowany=bonus,
        podstawa_kosztowa=koszty,
        podstawa_prawna="art. 13 ust. 1 pkt 3 lit. c w zw. z art. 5a ust. 1 ustawy z 8.12.2006",
    )


def build(w: Wejscie, a: Alokacja) -> Granty:
    ostrzezenia: List[Ostrzezenie] = []
    spoleczna = _grant_spoleczny(w, a.spoleczna, ostrzezenia)
    komunalna = _grant_komunalny(w, a.komunalna)
    ograniczony_hybryda = False

    if w.przelaczniki.hybryda_jako_jedno_przedsiewziecie and spoleczna.kwota + komunalna.kwota > 0:
        # Kwestia otwarta 10.1, odczyt drugi: hybryda to jedno przedsiewziecie,
        # wiec laczne wsparcie podlega limitowi z art. 13 ust. 1a.
        limit_laczny = a.koszty_laczne * prawo.GRANT_HYBRYDA_LIMIT_LACZNY
        laczny = spoleczna.kwota + komunalna.kwota
        if laczny > limit_laczny:
            wspolczynnik = bezpieczny_iloraz(limit_laczny, laczny)
            spoleczna = _przeskaluj(spoleczna, wspolczynnik)
            komunalna = _przeskaluj(komunalna, wspolczynnik)
            ograniczony_hybryda = True
            ostrzezenia.append(
                Ostrzezenie(
                    kod="HYBRYDA_SCIAGNIETA_DO_LIMITU",
                    tresc=(
                        "Przelacznik 'hybryda_jako_jedno_przedsiewziecie' jest wlaczony, wiec "
                        f"laczne wsparcie sciagnieto do {prawo.GRANT_HYBRYDA_LIMIT_LACZNY:.0%} "
                        "kosztow przedsiewziecia. Odczyt przeciwny — dwa odrebne przedsiewziecia — "
                        "daje istotnie wyzszy grant. Kwestia otwarta 10.1."
                    ),
                    podstawa="art. 13 ust. 1a ustawy z 8.12.2006",
                
                tresc_potoczna=(
                    "Laczna dotacja zostala sciagnieta do 45% kosztow, bo obie pule potraktowano "
                    "jako jedna inwestycje. Przy odczycie przeciwnym dotacja bylaby istotnie wyzsza."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
            )

    if a.spoleczna.aktywna and spoleczna.ograniczony_gruntem:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GRANT_OGRANICZONY_GRUNTEM",
                tresc=(
                    "Grant spoleczny ograniczony wartoscia gruntu: zamiast "
                    f"{spoleczna.stawka_nominalna:.0%} kosztow wychodzi "
                    f"{spoleczna.udzial_wsparcia:.1%}. Czesc ponad "
                    f"{prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} kosztow pokrywana jest wylacznie "
                    "do wysokosci wartosci gruntu we wladaniu inwestora."
                ),
                podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
            
                tresc_potoczna=(
                    "Dotacja wyszla nizsza niz 45%, bo czesc powyzej 35% jest ograniczona wartoscia "
                    "Twojego gruntu. Drozszy grunt oznacza wyzsza dotacje."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    return Granty(
        spoleczna=spoleczna,
        komunalna=komunalna,
        ograniczony_limitem_hybrydy=ograniczony_hybryda,
        ostrzezenia=tuple(ostrzezenia),
    )


def _przeskaluj(g: GrantPuli, wspolczynnik: Decimal) -> GrantPuli:
    from dataclasses import replace

    return replace(g, kwota=g.kwota * wspolczynnik)
