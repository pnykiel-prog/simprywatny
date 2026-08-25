"""Jeden silnik — pelne przeliczenie wariantu.

UI i arkusz wolaja to samo. Logika obliczeniowa nie ma prawa istniec nigdzie
indziej: dwa silniki liczace to samo rozjada sie i nikt tego nie zauwazy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from . import alokacja as _alokacja
from . import czynsz as _czynsz
from . import grant as _grant
from . import kredyt as _kredyt
from . import projekcja as _projekcja
from . import rekompensata as _rekompensata
from . import testy_montazu as _testy
from .alokacja import Alokacja
from .czynsz import LimityCzynszu
from .dane import BladWalidacji, Ostrzezenie, Wejscie
from .grant import Granty
from .projekcja import Finansowanie, Projekcja
from .rekompensata import TestRekompensaty
from .testy_montazu import Werdykty
from .waluta import ZERO, na_m2


@dataclass(frozen=True)
class Wynik:
    """Komplet wyniku dla jednego wariantu wejsciowego."""

    wejscie: Wejscie
    alokacja: Alokacja
    granty: Granty
    limity_spoleczna: LimityCzynszu
    limity_komunalna: LimityCzynszu
    finansowanie: Finansowanie
    projekcja: Projekcja
    edb_kredytu: Decimal
    rekompensata: TestRekompensaty
    werdykty: Werdykty

    @property
    def ostrzezenia(self) -> Tuple[Ostrzezenie, ...]:
        return tuple(self.wejscie.ostrzezenia) + self.granty.ostrzezenia + self.rekompensata.ostrzezenia

    @property
    def domyka_sie(self) -> bool:
        return self.werdykty.domyka_sie

    # --- wskazniki per m2 PUM — metodyka projektu wymaga metra, nie lokalu ---

    @property
    def koszt_na_m2(self) -> Decimal:
        return na_m2(self.alokacja.koszty_laczne, self.wejscie.powierzchnie.pum_laczne)

    @property
    def grant_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.grant_laczny, self.wejscie.powierzchnie.pum_laczne)

    @property
    def kredyt_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.kredyt_laczny, self.wejscie.powierzchnie.pum_laczne)

    @property
    def partycypacja_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.partycypacja_laczna, self.wejscie.powierzchnie.pum_laczne)

    @property
    def wklad_wlasny_na_m2(self) -> Decimal:
        return na_m2(
            self.finansowanie.wklad_wlasny_wymagany, self.wejscie.powierzchnie.pum_laczne
        )

    @property
    def luka_kapitalowa_na_m2(self) -> Decimal:
        return na_m2(self.werdykty.montaz.luka_kwota, self.wejscie.powierzchnie.pum_laczne)


@dataclass(frozen=True)
class WynikNieobliczalny:
    """Wariant, ktorego silnik nie policzyl — z powodem, nie z liczba."""

    powod: str
    typ: str

    @property
    def domyka_sie(self) -> bool:
        return False


def przelicz(w: Wejscie) -> Wynik:
    """Pelne przeliczenie. Podnosi BladWalidacji / BladObliczenia zamiast zgadywac."""
    a = _alokacja.build(w)
    g = _grant.build(w, a)

    kredyt_aktywny = w.pula_spoleczna.kredyt.aktywny and a.spoleczna.aktywna

    limity_spoleczna = _czynsz.build(
        w, a.spoleczna, g.spoleczna,
        w.pula_spoleczna.czynsz_zakladany_m2_mies,
        finansowanie_zwrotne=kredyt_aktywny,
    )
    limity_komunalna = _czynsz.build(
        w, a.komunalna, g.komunalna,
        w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies,
        finansowanie_zwrotne=False,
    )

    fin = _projekcja.zbuduj_finansowanie(w, a, g)
    proj = _projekcja.build(w, a, fin, limity_spoleczna, limity_komunalna)
    edb_kredytu = _kredyt.edb_dla_harmonogramu(fin.harmonogram_kredytu, w.parametry_zewnetrzne)
    rek = _rekompensata.build(w, a, fin, proj, edb_kredytu)
    werdykty = _testy.build(w, fin, proj, limity_spoleczna, limity_komunalna, rek)

    return Wynik(
        wejscie=w,
        alokacja=a,
        granty=g,
        limity_spoleczna=limity_spoleczna,
        limity_komunalna=limity_komunalna,
        finansowanie=fin,
        projekcja=proj,
        edb_kredytu=edb_kredytu,
        rekompensata=rek,
        werdykty=werdykty,
    )


def przelicz_udzial(w: Wejscie, udzial: Decimal):
    """Przelicza wariant przy zadanym udziale puli komunalnej, bezpiecznie.

    Przesuniecie pokretla przechodzi pelna walidacje, wiec punkt sprzeczny
    z przepisem (np. kredyt SBC przy 100% puli komunalnej) wraca jako
    `WynikNieobliczalny` z podana przyczyna, a nie jako cicha porazka testu.
    """
    from .dane import BladObliczenia

    try:
        wariant = w.z_udzialem_komunalnym(udzial)
    except BladWalidacji as exc:
        return WynikNieobliczalny(powod=str(exc), typ="walidacja")
    return przelicz_bezpiecznie(wariant)


def przelicz_bezpiecznie(w: Wejscie):
    """Jak `przelicz`, ale zwraca `WynikNieobliczalny` zamiast wyjatku.

    Uzywane w sweepie, gdzie pojedynczy niepoliczalny punkt nie moze przerwac
    calej analizy — ale musi zostac widoczny jako niepoliczalny, nie jako porazka.
    """
    from .dane import BladObliczenia

    try:
        return przelicz(w)
    except BladWalidacji as exc:
        return WynikNieobliczalny(powod=str(exc), typ="walidacja")
    except BladObliczenia as exc:
        return WynikNieobliczalny(powod=str(exc), typ="obliczenie")
