"""Trzy niezalezne testy montazu, wiazace ograniczenie i luki liczbowe.

Projekt domyka sie WYLACZNIE gdy przechodza wszystkie trzy. Kazdy werdykt
negatywny podaje wiazace ograniczenie i luke w liczbach — "nie spina sie"
bez podania luki jest bezuzyteczne w negocjacji z gmina.

Test 1 — montaz:      grant + kredyt + partycypacja + wklad wlasny = koszty
Test 2 — zdolnosc czynszowa: przychod netto >= eksploatacja + odpis + rata, DSCR >= 1,0
Test 3 — rekompensata:       EDB_grant + EDB_kredyt <= KN + RZ
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from .alokacja import Alokacja
from .czynsz import LimityCzynszu, czynsz_wymagany_do_domkniecia
from .dane import Ostrzezenie, Wejscie
from .grant import Granty
from .projekcja import Finansowanie, Projekcja
from .rekompensata import TestRekompensaty
from .waluta import ZERO, bezpieczny_iloraz, na_m2


def _zl(kwota: Decimal) -> str:
    """Kwota w zapisie, ktory czyta sie bez wysilku."""
    return f"{kwota:,.0f} zl".replace(",", " ")

JEDEN = Decimal(1)


@dataclass(frozen=True)
class Werdykt:
    numer: int
    nazwa: str
    przechodzi: bool
    wiazace_ograniczenie: str
    luka_opis: str
    luka_kwota: Decimal
    luka_jednostka: str
    szczegoly: Dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "przechodzi" if self.przechodzi else "nie przechodzi"


# ---------------------------------------------------------------------------
# Test 1 — montaz
# ---------------------------------------------------------------------------

def test_montazu(w: Wejscie, fin: Finansowanie) -> Werdykt:
    """Test 1 — montaz. Wklad wlasny jest WYNIKIEM, nie wejsciem.

    Zamiast pytac "mam tyle kapitalu, czy sie spina", narzedzie odpowiada
    "ile kapitalu trzeba dolozyc, zeby sie spielo". Zadeklarowana zdolnosc
    inwestora jest opcjonalnym punktem odniesienia i nigdy nie blokuje
    obliczenia — brak deklaracji nie jest porazka testu.
    """
    wymagany = fin.wklad_wlasny_wymagany
    udzial = bezpieczny_iloraz(wymagany, fin.koszty_laczne)
    dostepny = w.inwestor.dostepny_wklad_wlasny

    szczegoly = {
        "Koszty przedsiewziecia": _zl(fin.koszty_laczne),
        "Dotacja": _zl(fin.grant_laczny),
        "Kredyt SBC": _zl(fin.kredyt_laczny),
        "Partycypacja": _zl(fin.partycypacja_laczna),
        "Wymagany wklad wlasny": _zl(wymagany),
        "Udzial wkladu w kosztach": f"{udzial:.1%}",
    }

    if dostepny is None:
        return Werdykt(
            numer=1,
            nazwa="Kapital",
            przechodzi=True,
            wiazace_ograniczenie=(
                f"Zeby zrealizowac te inwestycje, trzeba wylozyc wlasnych "
                f"{_zl(wymagany)}, czyli {udzial:.0%} kosztow."
            ),
            luka_opis="Wymagany wklad wlasny",
            luka_kwota=wymagany,
            luka_jednostka="zl",
            szczegoly=szczegoly,
        )

    szczegoly["Zadeklarowany kapital"] = _zl(dostepny)
    luka = max(ZERO, wymagany - dostepny)
    if luka > ZERO:
        ograniczenie = (
            f"Brakuje {_zl(luka)}. Inwestycja wymaga {_zl(wymagany)}, "
            f"a zadeklarowany kapital to {_zl(dostepny)}."
        )
    else:
        ograniczenie = (
            f"Zostaje zapas {_zl(dostepny - wymagany)}. Inwestycja wymaga "
            f"{_zl(wymagany)} przy zadeklarowanych {_zl(dostepny)}."
        )

    return Werdykt(
        numer=1,
        nazwa="Kapital",
        przechodzi=luka == ZERO,
        wiazace_ograniczenie=ograniczenie,
        luka_opis="Brakujacy kapital" if luka > ZERO else "Wymagany wklad wlasny",
        luka_kwota=luka if luka > ZERO else wymagany,
        luka_jednostka="zl",
        szczegoly=szczegoly,
    )


# ---------------------------------------------------------------------------
# Test 2 — zdolnosc czynszowa
# ---------------------------------------------------------------------------

def test_zdolnosci_czynszowej(
    w: Wejscie,
    proj: Projekcja,
    limity_spoleczna: LimityCzynszu,
    limity_komunalna: LimityCzynszu,
) -> Werdykt:
    naruszenia: List[Tuple[str, int, Decimal]] = []
    szczegoly: Dict[str, str] = {}
    luka_stawki = ZERO
    wiazaca_pula = ""

    pary = (
        (proj.spoleczna, limity_spoleczna, w.pula_spoleczna.czynsz_zakladany_m2_mies),
        (proj.komunalna, limity_komunalna, w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies),
    )
    for pula, limity, czynsz_zakladany in pary:
        if not pula.aktywna:
            continue
        rok = pula.pierwszy_rok_naruszenia
        min_dscr = pula.minimalny_dscr
        szczegoly[f"Min. DSCR — pula {pula.nazwa}"] = (
            f"{min_dscr:.3f}" if min_dscr is not None else "brak obslugi dlugu"
        )
        szczegoly[f"Limit czynszu — pula {pula.nazwa}"] = (
            f"{limity.limit_wiazacy_m2_mies:.2f} zl/m2/mies. ({limity.limit_wiazacy_zrodlo})"
        )
        szczegoly[f"Czynsz zakladany — pula {pula.nazwa}"] = (
            f"{czynsz_zakladany:.2f} zl/m2/mies."
        )
        if rok is None:
            continue

        naruszenia.append((pula.nazwa, rok, min_dscr or ZERO))
        # Luka czynszowa: o ile trzeba podniesc stawke w roku naruszenia,
        # zeby przychod pokryl wymagane obciazenia.
        rok_naruszenia = pula.lata[rok - 1]
        obloznosc = JEDEN - (
            rok_naruszenia.strata_na_pustostanach
            / rok_naruszenia.przychod_czynszowy_potencjalny
            if rok_naruszenia.przychod_czynszowy_potencjalny > ZERO
            else ZERO
        )
        potrzebny = czynsz_wymagany_do_domkniecia(
            rok_naruszenia.wymagane_pokrycie, pula.pum, obloznosc
        )
        # Sprowadzenie do stawki bazowej roku 1 — indeksacja czynszu juz w niej siedzi.
        indeks = (
            rok_naruszenia.czynsz_m2_mies / czynsz_zakladany
            if czynsz_zakladany > ZERO
            else JEDEN
        )
        potrzebny_bazowo = potrzebny / indeks if indeks > ZERO else potrzebny
        luka_pula = potrzebny_bazowo - czynsz_zakladany
        szczegoly[f"Czynsz wymagany do domkniecia — pula {pula.nazwa}"] = (
            f"{potrzebny_bazowo:.2f} zl/m2/mies. (stawka bazowa roku 1)"
        )
        if luka_pula > luka_stawki:
            luka_stawki = luka_pula
            wiazaca_pula = pula.nazwa

        if potrzebny_bazowo > limity.limit_wiazacy_m2_mies:
            szczegoly[f"Rozjazd limit-potrzeba — pula {pula.nazwa}"] = (
                f"Do domkniecia trzeba {potrzebny_bazowo:.2f} zl/m2/mies., a limit ustawowy "
                f"konczy sie na {limity.limit_wiazacy_m2_mies:.2f} zl/m2/mies. "
                f"({limity.limit_wiazacy_zrodlo}). Montazu nie da sie domknac samym czynszem."
            )

    for limity, czynsz_rynkowy in (
        (limity_spoleczna, w.pula_spoleczna.czynsz_rynkowy_m2_mies),
    ):
        if czynsz_rynkowy is not None:
            szczegoly["Czynsz rynkowy — pula spoleczna"] = f"{czynsz_rynkowy:.2f} zl/m2/mies."
            szczegoly["Dyskonto do rynku — pula spoleczna"] = (
                f"{(JEDEN - limity.limit_wiazacy_m2_mies / czynsz_rynkowy):.1%} "
                "ponizej stawki rynkowej wynosi limit ustawowy"
            )

    if not naruszenia:
        najslabsza = min(
            (p for p in proj.pule if p.minimalny_dscr is not None),
            key=lambda p: p.minimalny_dscr,
            default=None,
        )
        ograniczenie = (
            f"Najciasniej w puli {najslabsza.nazwa}: DSCR {najslabsza.minimalny_dscr:.3f}."
            if najslabsza is not None
            else "Brak obslugi dlugu — test przechodzi trywialnie."
        )
        return Werdykt(
            numer=2,
            nazwa="Zdolnosc czynszowa",
            przechodzi=True,
            wiazace_ograniczenie=ograniczenie,
            luka_opis="Luka czynszowa",
            luka_kwota=ZERO,
            luka_jednostka="zl/m2/mies.",
            szczegoly=szczegoly,
        )

    pula, rok, dscr = min(naruszenia, key=lambda n: n[1])
    return Werdykt(
        numer=2,
        nazwa="Zdolnosc czynszowa",
        przechodzi=False,
        wiazace_ograniczenie=(
            f"Obsluga dlugu i koszty w puli {pula}. Pierwsze naruszenie w roku {rok}, "
            f"najnizszy DSCR {dscr:.3f}."
        ),
        luka_opis=f"Luka czynszowa (pula {wiazaca_pula}, stawka bazowa)",
        luka_kwota=luka_stawki,
        luka_jednostka="zl/m2/mies.",
        szczegoly={**szczegoly, "Rok pierwszego naruszenia": str(rok)},
    )


# ---------------------------------------------------------------------------
# Test 3 — rekompensata
# ---------------------------------------------------------------------------

def test_rekompensaty(rek: TestRekompensaty) -> Werdykt:
    szczegoly: Dict[str, str] = {}
    for pula in rek.badane:
        szczegoly[f"KN — {pula.nazwa}"] = f"{pula.kn:,.0f} zl".replace(",", " ")
        szczegoly[f"RZ — {pula.nazwa}"] = f"{pula.rz:,.0f} zl".replace(",", " ")
        szczegoly[f"Rekompensata (RUOIG) — {pula.nazwa}"] = (
            f"{pula.ruoig:,.0f} zl".replace(",", " ")
        )
        szczegoly[f"Prog tolerancji — {pula.nazwa}"] = (
            f"{pula.prog_tolerancji:.0%} sredniej rocznej "
            f"({pula.tolerancja_kwotowo:,.0f} zl)".replace(",", " ")
        )
        szczegoly[f"Ujecie gruntu — {pula.nazwa}"] = pula.grunt_ujecie

    if rek.przechodzi:
        najciasniej = max(rek.badane, key=lambda p: p.nadwyzka_wzgledna, default=None)
        ograniczenie = (
            f"Najciasniej w puli {najciasniej.nazwa}: nadwyzka "
            f"{najciasniej.nadwyzka_wzgledna:.1%} przy progu "
            f"{najciasniej.prog_tolerancji:.0%}."
            if najciasniej is not None
            else "Brak pul do zbadania."
        )
        return Werdykt(
            numer=3,
            nazwa="Rekompensata",
            przechodzi=True,
            wiazace_ograniczenie=ograniczenie,
            luka_opis="Nadwyzka rekompensaty",
            luka_kwota=rek.nadwyzka_laczna,
            luka_jednostka="zl",
            szczegoly=szczegoly,
        )

    winne = [p for p in rek.badane if not p.przechodzi]
    najgorsza = max(winne, key=lambda p: p.nadwyzka_wzgledna)
    szczegoly["Kwota podlegajaca zwrotowi do Funduszu Doplat"] = (
        f"{rek.kwota_do_zwrotu:,.0f} zl".replace(",", " ")
    )
    return Werdykt(
        numer=3,
        nazwa="Rekompensata",
        przechodzi=False,
        wiazace_ograniczenie=(
            f"Nadwyzka rekompensaty w puli {najgorsza.nazwa}: "
            f"{najgorsza.nadwyzka_wzgledna:.1%} sredniej rocznej przy progu "
            f"{najgorsza.prog_tolerancji:.0%} (sciezka {najgorsza.sciezka})."
        ),
        luka_opis="Nadwyzka rekompensaty",
        luka_kwota=rek.nadwyzka_laczna,
        luka_jednostka="zl",
        szczegoly=szczegoly,
    )


# ---------------------------------------------------------------------------
# Werdykt zbiorczy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Werdykty:
    montaz: Werdykt              # Test 1 — Kapital
    zdolnosc_czynszowa: Werdykt  # Test 2 — Czynsz
    rekompensata: Werdykt        # Test 3 — Rekompensata

    @property
    def wszystkie(self) -> Tuple[Werdykt, ...]:
        return (self.montaz, self.zdolnosc_czynszowa, self.rekompensata)

    @property
    def domyka_sie(self) -> bool:
        """Projekt domyka sie wylacznie gdy przechodza wszystkie trzy testy."""
        return all(t.przechodzi for t in self.wszystkie)

    @property
    def blokujace(self) -> Tuple[Werdykt, ...]:
        return tuple(t for t in self.wszystkie if not t.przechodzi)

    @property
    def wiazace_ograniczenie(self) -> str:
        """Ktory test i ktory parametr w nim decyduje."""
        if self.domyka_sie:
            najciasniejszy = min(
                self.wszystkie, key=lambda t: _zapas_wzgledny(t)
            )
            return f"Test {najciasniejszy.numer} ({najciasniejszy.nazwa}). {najciasniejszy.wiazace_ograniczenie}"
        pierwszy = self.blokujace[0]
        return f"Test {pierwszy.numer} ({pierwszy.nazwa}). {pierwszy.wiazace_ograniczenie}"


def _zapas_wzgledny(t: Werdykt) -> Decimal:
    """Pomocnicze uporzadkowanie testow, ktore przeszly, wg ciasnoty."""
    return t.luka_kwota if not t.przechodzi else ZERO


def build(
    w: Wejscie,
    fin: Finansowanie,
    proj: Projekcja,
    limity_spoleczna: LimityCzynszu,
    limity_komunalna: LimityCzynszu,
    rek: TestRekompensaty,
) -> Werdykty:
    return Werdykty(
        montaz=test_montazu(w, fin),
        zdolnosc_czynszowa=test_zdolnosci_czynszowej(w, proj, limity_spoleczna, limity_komunalna),
        rekompensata=test_rekompensaty(rek),
    )
