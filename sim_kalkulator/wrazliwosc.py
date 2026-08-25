"""Sweep udzialu pul, punkt graniczny i ranking parametrow.

Glowny wynik operacyjny narzedzia: przy jakim udziale puli komunalnej calosc
przestaje sie domykac. To jest tresc negocjacji z gmina — gmina chce jak
najwiecej lokali komunalnych, inwestor potrzebuje puli spolecznej, zeby
uciagnac dzwignie kredytowa i wyzszy czynsz.

Wrazliwosc na stope referencyjna liczona jest zawsze, niezaleznie od
konfiguracji: wynik testu rekompensaty jest na nia bardzo wrazliwy, a horyzont
siega 30 lat (rozdz. 7.3 specyfikacji).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .dane import Wejscie
from .silnik import Wynik, WynikNieobliczalny, przelicz_bezpiecznie, przelicz_udzial
from .waluta import ZERO, zl

KROK_SWEEPU = Decimal("0.05")


# ---------------------------------------------------------------------------
# 7.1. Sweep udzialu puli komunalnej
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PunktSweepu:
    udzial: Decimal
    policzalny: bool
    domyka_sie: bool
    werdykty: Tuple[bool, bool, bool]          # test 1, 2, 3
    wiazace_ograniczenie: str
    luki: Tuple[Tuple[str, Decimal, str], ...]  # (opis, kwota, jednostka)
    powod_niepoliczalnosci: str = ""

    @property
    def liczba_zdanych(self) -> int:
        return sum(self.werdykty)


@dataclass(frozen=True)
class Sweep:
    punkty: Tuple[PunktSweepu, ...]

    @property
    def punkty_domykajace(self) -> Tuple[PunktSweepu, ...]:
        return tuple(p for p in self.punkty if p.domyka_sie)

    @property
    def maksymalny_udzial_komunalny(self) -> Optional[Decimal]:
        """Najwiekszy udzial puli komunalnej, przy ktorym przechodza wszystkie trzy testy."""
        domykajace = self.punkty_domykajace
        return max((p.udzial for p in domykajace), default=None)

    @property
    def minimalny_udzial_komunalny(self) -> Optional[Decimal]:
        domykajace = self.punkty_domykajace
        return min((p.udzial for p in domykajace), default=None)

    @property
    def punkt_graniczny(self) -> Optional[Decimal]:
        """Pierwszy udzial powyzej maksimum, przy ktorym montaz juz sie nie domyka."""
        maks = self.maksymalny_udzial_komunalny
        if maks is None:
            return None
        powyzej = [p.udzial for p in self.punkty if p.udzial > maks]
        return min(powyzej) if powyzej else None

    @property
    def test_blokujacy(self) -> Optional[int]:
        """Ktory test blokuje, gdy nie domyka sie przy zadnym udziale."""
        if self.punkty_domykajace:
            return None
        liczniki: Dict[int, int] = {1: 0, 2: 0, 3: 0}
        for punkt in self.punkty:
            if not punkt.policzalny:
                continue
            for numer, zdany in enumerate(punkt.werdykty, start=1):
                if not zdany:
                    liczniki[numer] += 1
        if not any(liczniki.values()):
            return None
        return max(liczniki, key=lambda n: liczniki[n])


def sweep_udzialu(
    w: Wejscie, krok: Decimal = KROK_SWEEPU
) -> Sweep:
    """Przelicza wariant dla udzialu puli komunalnej od 0,0 do 1,0."""
    punkty: List[PunktSweepu] = []
    udzial = ZERO
    while udzial <= Decimal("1.0") + Decimal("1e-9"):
        punkty.append(_punkt(w, udzial))
        udzial += krok
    return Sweep(punkty=tuple(punkty))


def _punkt(w: Wejscie, udzial: Decimal) -> PunktSweepu:
    wynik = przelicz_udzial(w, udzial)
    if isinstance(wynik, WynikNieobliczalny):
        return PunktSweepu(
            udzial=udzial,
            policzalny=False,
            domyka_sie=False,
            werdykty=(False, False, False),
            wiazace_ograniczenie=f"Wariant niepoliczalny ({wynik.typ}).",
            luki=(),
            powod_niepoliczalnosci=wynik.powod,
        )
    werdykty = wynik.werdykty
    return PunktSweepu(
        udzial=udzial,
        policzalny=True,
        domyka_sie=werdykty.domyka_sie,
        werdykty=tuple(t.przechodzi for t in werdykty.wszystkie),
        wiazace_ograniczenie=werdykty.wiazace_ograniczenie,
        luki=tuple(
            (t.luka_opis, t.luka_kwota, t.luka_jednostka)
            for t in werdykty.wszystkie
            if not t.przechodzi
        ),
    )


# ---------------------------------------------------------------------------
# 7.2. Wrazliwosc jednoparametrowa
# ---------------------------------------------------------------------------

def _ustaw(sciezka: Sequence[str]) -> Callable[[Wejscie, Decimal], Wejscie]:
    """Buduje podmieniacz pola zagniezdzonego, np. ('koszty', 'koszt_budowy_na_m2')."""

    def podmien(w: Wejscie, wartosc: Decimal) -> Wejscie:
        wezel = w
        rodzice = []
        for nazwa in sciezka[:-1]:
            rodzice.append((wezel, nazwa))
            wezel = getattr(wezel, nazwa)
        wezel = replace(wezel, **{sciezka[-1]: wartosc})
        for rodzic, nazwa in reversed(rodzice):
            wezel = replace(rodzic, **{nazwa: wezel})
        return wezel

    return podmien


# Parametry z rozdz. 7.2 specyfikacji. Stopa referencyjna jest na koncu i jest
# badana zawsze — patrz rozdz. 7.3.
PARAMETRY_WRAZLIWOSCI: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Koszt budowy na m2", ("koszty", "koszt_budowy_na_m2")),
    ("Oprocentowanie kredytu", ("pula_spoleczna", "kredyt", "oprocentowanie")),
    ("Czynsz w puli spolecznej", ("pula_spoleczna", "czynsz_zakladany_m2_mies")),
    ("Czynsz placony przez gmine", ("pula_komunalna", "czynsz_placony_przez_gmine_m2_mies")),
    ("Pustostany", ("eksploatacja", "pustostany_procent")),
    ("Wartosc gruntu", ("grunt", "wartosc")),
    ("Stopa referencyjna KE", ("parametry_zewnetrzne", "stopa_referencyjna_ke")),
)

ODCHYLENIE = Decimal("0.20")


@dataclass(frozen=True)
class WynikWrazliwosci:
    nazwa: str
    wartosc_bazowa: Decimal
    wartosc_dol: Decimal
    wartosc_gora: Decimal
    domyka_bazowo: bool
    domyka_dol: Optional[bool]     # None = wariant niepoliczalny
    domyka_gora: Optional[bool]
    maks_udzial_bazowo: Optional[Decimal]
    maks_udzial_dol: Optional[Decimal]
    maks_udzial_gora: Optional[Decimal]
    powod_dol: str = ""
    powod_gora: str = ""

    @property
    def przesuniecia(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Przesuniecie punktu granicznego (dol, gora) wzgledem wariantu bazowego."""
        if self.maks_udzial_bazowo is None:
            return (None, None)
        return tuple(
            None if u is None else u - self.maks_udzial_bazowo
            for u in (self.maks_udzial_dol, self.maks_udzial_gora)
        )

    @property
    def przesuniecie_punktu_granicznego(self) -> Optional[Decimal]:
        """Najkorzystniejsze przesuniecie granicy — ktory parametr najtaniej ja podnosi."""
        if self.maks_udzial_bazowo is None:
            kandydaci = [u for u in (self.maks_udzial_dol, self.maks_udzial_gora) if u is not None]
            return max(kandydaci) if kandydaci else None
        realne = [p for p in self.przesuniecia if p is not None]
        return max(realne, default=None)

    @property
    def kierunek_korzystny(self) -> str:
        """W ktora strone trzeba ruszyc parametrem, zeby granica poszla w gore."""
        dol, gora = self.przesuniecia
        if dol is None and gora is None:
            return "nieokreslony"
        najlepszy = self.przesuniecie_punktu_granicznego
        if najlepszy is None or najlepszy <= ZERO:
            return "brak poprawy w badanym zakresie"
        return "-20%" if dol == najlepszy else "+20%"

    @property
    def zmienia_werdykt(self) -> bool:
        return any(
            d is not None and d != self.domyka_bazowo
            for d in (self.domyka_dol, self.domyka_gora)
        )

    @property
    def sila_wplywu(self) -> Decimal:
        """Miara do rankingu: najwieksze przesuniecie granicy w DOWOLNA strone.

        Bierze wartosc bezwzgledna z obu koncow zakresu. Parametr, ktory granice
        wylacznie obniza, jest tak samo istotny jak ten, ktory ja podnosi —
        w negocjacji z gmina liczy sie kazda dzwignia, takze ta w dol.
        """
        realne = [abs(p) for p in self.przesuniecia if p is not None]
        if realne:
            return max(realne)
        # Brak punktu bazowego: parametr, ktory w ogole otwiera jakies pole, ma wplyw.
        kandydaci = [u for u in (self.maks_udzial_dol, self.maks_udzial_gora) if u is not None]
        return max(kandydaci, default=ZERO)


def wrazliwosc_jednoparametrowa(
    w: Wejscie, odchylenie: Decimal = ODCHYLENIE, krok: Decimal = KROK_SWEEPU
) -> Tuple[WynikWrazliwosci, ...]:
    """Przelicza kazdy parametr w zakresie +/-20% i podaje wplyw na werdykt zbiorczy."""
    bazowy_sweep = sweep_udzialu(w, krok)
    bazowy_maks = bazowy_sweep.maksymalny_udzial_komunalny
    bazowy_wynik = przelicz_bezpiecznie(w)
    domyka_bazowo = bazowy_wynik.domyka_sie

    wyniki: List[WynikWrazliwosci] = []
    for nazwa, sciezka in PARAMETRY_WRAZLIWOSCI:
        podmien = _ustaw(sciezka)
        wezel = w
        for czlon in sciezka[:-1]:
            wezel = getattr(wezel, czlon)
        bazowa = zl(getattr(wezel, sciezka[-1]))

        warianty = {}
        for etykieta, mnoznik in (("dol", Decimal(1) - odchylenie), ("gora", Decimal(1) + odchylenie)):
            wartosc = bazowa * mnoznik
            try:
                kandydat = podmien(w, wartosc)
                wynik = przelicz_bezpiecznie(kandydat)
                sweep = sweep_udzialu(kandydat, krok)
                warianty[etykieta] = (
                    wartosc,
                    None if isinstance(wynik, WynikNieobliczalny) else wynik.domyka_sie,
                    sweep.maksymalny_udzial_komunalny,
                    wynik.powod if isinstance(wynik, WynikNieobliczalny) else "",
                )
            except Exception as exc:  # walidacja twarda przy skrajnej wartosci
                warianty[etykieta] = (wartosc, None, None, str(exc))

        w_dol, domyka_dol, maks_dol, powod_dol = warianty["dol"]
        w_gora, domyka_gora, maks_gora, powod_gora = warianty["gora"]
        wyniki.append(
            WynikWrazliwosci(
                nazwa=nazwa,
                wartosc_bazowa=bazowa,
                wartosc_dol=w_dol,
                wartosc_gora=w_gora,
                domyka_bazowo=domyka_bazowo,
                domyka_dol=domyka_dol,
                domyka_gora=domyka_gora,
                maks_udzial_bazowo=bazowy_maks,
                maks_udzial_dol=maks_dol,
                maks_udzial_gora=maks_gora,
                powod_dol=powod_dol,
                powod_gora=powod_gora,
            )
        )
    return tuple(wyniki)


def ranking(wyniki: Sequence[WynikWrazliwosci]) -> Tuple[WynikWrazliwosci, ...]:
    """Parametry uporzadkowane wg sily wplywu — ktory najtaniej przesuwa granice."""
    return tuple(
        sorted(wyniki, key=lambda r: (r.sila_wplywu, r.zmienia_werdykt), reverse=True)
    )


# ---------------------------------------------------------------------------
# Zestaw zbiorczy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Analiza:
    sweep: Sweep
    wrazliwosc: Tuple[WynikWrazliwosci, ...]

    @property
    def ranking(self) -> Tuple[WynikWrazliwosci, ...]:
        return ranking(self.wrazliwosc)

    @property
    def podsumowanie(self) -> str:
        maks = self.sweep.maksymalny_udzial_komunalny
        if maks is not None:
            granica = self.sweep.punkt_graniczny
            tekst = f"Montaz domyka sie do {maks:.0%} udzialu puli komunalnej."
            if granica is not None:
                tekst += f" Powyzej — przy {granica:.0%} — przestaje sie domykac."
            else:
                tekst += " Domyka sie w calym badanym zakresie."
            return tekst
        blokujacy = self.sweep.test_blokujacy
        if blokujacy is None:
            return "Zaden punkt sweepu nie byl policzalny — sprawdz dane wejsciowe."
        return (
            f"Montaz nie domyka sie przy zadnym udziale puli komunalnej. "
            f"Blokuje test {blokujacy}."
        )


def build(w: Wejscie, krok: Decimal = KROK_SWEEPU) -> Analiza:
    return Analiza(
        sweep=sweep_udzialu(w, krok),
        wrazliwosc=wrazliwosc_jednoparametrowa(w, krok=krok),
    )
