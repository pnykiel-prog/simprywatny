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
from .dane import Ostrzezenie, Wejscie, Waga
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
    pasmo_45: bool = True            # kanal A — czy forma gruntu odblokowuje pasmo
    forma_gruntu: str = ""

    @property
    def udzial_wsparcia(self) -> Decimal:
        """Udzial wsparcia w kosztach przedsiewziecia — wejscie do tabeli art. 7c."""
        return bezpieczny_iloraz(self.kwota, self.podstawa_kosztowa)

    @property
    def grant_maksymalny_ustawowy(self) -> Decimal:
        """Ile wynioslby grant, gdyby nic go nie ograniczalo poza stawka."""
        return self.podstawa_kosztowa * self.stawka_nominalna

    @property
    def grant_utracony(self) -> Decimal:
        """Roznica miedzy stawka a kwota faktyczna — szary slupek "utracone".

        Rozdz. 7.3 uzupelnienia nr 2. Liczona na tej samej podstawie kosztowej,
        wiec pokazuje skutek ograniczenia, a nie skutek zmiany calego montazu;
        porownanie miedzy formami gruntu daje osobny widok porownawczy.
        """
        return max(ZERO, self.grant_maksymalny_ustawowy - self.kwota)

    @property
    def utracony_przez_forme_gruntu(self) -> bool:
        return not self.pasmo_45 and self.grant_utracony > ZERO


@dataclass(frozen=True)
class Granty:
    spoleczna: GrantPuli
    komunalna: GrantPuli
    ograniczony_limitem_hybrydy: bool
    ostrzezenia: Tuple[Ostrzezenie, ...]

    @property
    def kwota_laczna(self) -> Decimal:
        return self.spoleczna.kwota + self.komunalna.kwota


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
                    "Dodatkowe 5% dotacji naliczono przy założeniu, że nie podnosi ono progu "
                    "gruntowego. Odczyt alternatywny dałby wyższą dotację — do potwierdzenia w Banku."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    # Kanal A. art. 13 ust. 1 pkt 1 pokrywa czesc ponad prog gruntowy wylacznie
    # do wysokosci wartosci prawa wlasnosci albo uzytkowania wieczystego gruntu
    # bedacego we wladaniu inwestora. Forma, ktora zadnego z tych praw nie daje,
    # zatrzymuje wsparcie na progu — i to niezaleznie od wartosci dzialki, bo
    # wartosci, ktorej inwestor nie wlada, przepis nie pozwala uwzglednic.
    pasmo_45 = w.grunt.forma.daje_pasmo_45
    grunt_wliczany = pula.grunt_do_pasma_w_podstawie if pasmo_45 else ZERO
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
        pasmo_45=pasmo_45,
        forma_gruntu=w.grunt.forma.value,
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
        forma_gruntu=w.grunt.forma.value,
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
                    "Łączna dotacja została ściągnięta do 45% kosztów, bo obie pule potraktowano "
                    "jako jedną inwestycję. Przy odczycie przeciwnym dotacja byłaby istotnie wyższa."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
            )

    # Kwestia otwarta: czy wartosc gruntu wchodzi do bazy naliczania dotacji.
    # Model przyjmuje, ze TAK — specyfikacja wymienia grunt wsrod kosztow wspolnych
    # dzielonych kluczem PUM i domyka montaz wzgledem kosztow przedsiewziecia
    # zawierajacych te pozycje. Przepis mowi o "kosztach przedsiewziecia", nie
    # definiujac ich katalogu, a formularz rozliczenia wykazuje koszt przedsiewziecia
    # i wartosc gruntu w osobnych pozycjach — co czyta sie tez odwrotnie.
    # To ZALOZENIE, nie rozstrzygniecie. Patrz LUKI.md, rozdz. 13.
    grunt_w_bazie = a.spoleczna.grunt_w_podstawie + a.komunalna.grunt_w_podstawie
    if grunt_w_bazie > ZERO:
        roznica = _roznica_bazy_bez_gruntu(w, a, spoleczna, komunalna)
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_GRUNT_W_BAZIE_DOTACJI",
                tresc=(
                    f"Wartosc gruntu ({grunt_w_bazie:.2f} zl) wchodzi do bazy naliczania "
                    "dotacji w obu pulach. Odczyt alternatywny — baza liczona bez gruntu, "
                    "przy zachowaniu gruntu jako limitu pasma ponad prog gruntowy — daje "
                    f"dotacje nizsza o {roznica:.2f} zl. ZALOZENIE do potwierdzenia w BGK."
                ),
                podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
                tresc_potoczna=(
                    f"Dotacja liczona jest od kosztów zawierających wartość działki. Przy odczycie "
                    f"przeciwnym byłaby o {_zl(roznica)} niższa. To założenie — potwierdź w Banku, "
                    "bo zmienia wynik."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    if a.spoleczna.aktywna and spoleczna.utracony_przez_forme_gruntu:
        ostrzezenia.append(
            Ostrzezenie(
                kod="PASMO_SCIETE_FORMA_GRUNTU",
                tresc=(
                    f"Forma gruntu '{spoleczna.forma_gruntu}' scina wsparcie w puli spolecznej "
                    f"z {spoleczna.stawka_nominalna:.0%} do "
                    f"{prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} kosztow przedsiewziecia. "
                    f"Na tej podstawie kosztowej to {spoleczna.grant_utracony:.2f} zl mniej."
                ),
                podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
                tresc_potoczna=(
                    f"Wybrana forma gruntu kosztuje Cię {_zl(spoleczna.grant_utracony)} dotacji — "
                    "dotacja zatrzymuje się na 35% zamiast 45% kosztów."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    if a.spoleczna.aktywna and spoleczna.ograniczony_gruntem and spoleczna.pasmo_45:
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
                    "Dotacja wyszła niższa niż 45%, bo część powyżej 35% jest ograniczona wartością "
                    "Twojego gruntu. Droższy grunt oznacza wyższą dotację."
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


def _roznica_bazy_bez_gruntu(
    w: Wejscie, a: Alokacja, spoleczna: GrantPuli, komunalna: GrantPuli
) -> Decimal:
    """O ile nizsza bylaby dotacja, gdyby baze liczyc bez wartosci gruntu.

    Odczyt alternatywny zostawia grunt tam, gdzie przepis mowi o nim wprost —
    jako limit czesci ponad prog gruntowy — ale wyjmuje go z samej podstawy.
    Liczone wylacznie do komunikatu; implementacja pozostaje bez zmian.
    """
    roznica = ZERO
    if a.spoleczna.aktywna:
        bez = a.spoleczna.koszty_przedsiewziecia - a.spoleczna.grunt_w_podstawie
        alternatywny = min(
            bez * spoleczna.stawka_nominalna,
            bez * prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY
            + (a.spoleczna.grunt_do_pasma_w_podstawie if spoleczna.pasmo_45 else ZERO),
        )
        roznica += spoleczna.kwota - alternatywny
    if a.komunalna.aktywna:
        bez = a.komunalna.koszty_przedsiewziecia - a.komunalna.grunt_w_podstawie
        roznica += komunalna.kwota - bez * komunalna.stawka_nominalna
    return max(ZERO, roznica)


def _zl(kwota: Decimal) -> str:
    return f"{kwota:,.0f} zł".replace(",", "\u00a0")


def _przeskaluj(g: GrantPuli, wspolczynnik: Decimal) -> GrantPuli:
    from dataclasses import replace

    return replace(g, kwota=g.kwota * wspolczynnik)
