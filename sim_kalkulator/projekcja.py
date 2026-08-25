"""Struktura finansowania i przeplywy rok po rok przez okres powierzenia.

Warstwa laczna nie jest suma pul. Wklad wlasny obciaza jeden bilans inwestora,
wiec zapotrzebowanie liczone jest lacznie, choc kazda pula ma wlasne zrodla.

Okres powierzenia:
  * sciezka grantowa — 25 lat (art. 5 ust. 10 pkt 1 ustawy z 8.12.2006),
  * sciezka kredytowa — rowny okresowi finansowania, nie dluzej niz okres
    amortyzacji budynkow (§ 11 rozp. t.j. Dz.U. 2021 poz. 766).

Zadna liczba z ustawy nie pada w tym module — wszystkie pochodza z `prawo.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from . import prawo
from .alokacja import Alokacja, PulaKosztow
from .czynsz import LimityCzynszu, oplaty_poza_czynszem_rocznie
from .dane import Wejscie
from .grant import GrantPuli, Granty
from .kredyt import Harmonogram, harmonogram
from .waluta import ZERO, bezpieczny_iloraz, na_m2, zl

JEDEN = Decimal(1)
MIESIECY_W_ROKU = Decimal(12)


# ---------------------------------------------------------------------------
# Struktura finansowania
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FinansowaniePuli:
    nazwa: str
    koszty_przedsiewziecia: Decimal
    grant: Decimal
    kredyt: Decimal
    partycypacja: Decimal
    wklad_wlasny: Decimal

    @property
    def zrodla_obce(self) -> Decimal:
        return self.grant + self.kredyt + self.partycypacja


@dataclass(frozen=True)
class Finansowanie:
    spoleczna: FinansowaniePuli
    komunalna: FinansowaniePuli
    harmonogram_kredytu: Harmonogram

    @property
    def koszty_laczne(self) -> Decimal:
        return self.spoleczna.koszty_przedsiewziecia + self.komunalna.koszty_przedsiewziecia

    @property
    def grant_laczny(self) -> Decimal:
        return self.spoleczna.grant + self.komunalna.grant

    @property
    def kredyt_laczny(self) -> Decimal:
        return self.spoleczna.kredyt + self.komunalna.kredyt

    @property
    def partycypacja_laczna(self) -> Decimal:
        return self.spoleczna.partycypacja + self.komunalna.partycypacja

    @property
    def wklad_wlasny_wymagany(self) -> Decimal:
        """Jeden bilans inwestora — obie pule skladaja sie na to samo zapotrzebowanie."""
        return self.spoleczna.wklad_wlasny + self.komunalna.wklad_wlasny


def zbuduj_finansowanie(
    w: Wejscie, a: Alokacja, g: Granty, kwota_kredytu: Optional[Decimal] = None
) -> Finansowanie:
    """Sklada zrodla finansowania kazdej puli; wklad wlasny domyka reszte.

    `kwota_kredytu` podana wprost pochodzi z wyliczenia maksymalnego kredytu
    obslugiwalnego (tryb automatyczny). Pominieta — kwote wyznacza udzial
    docelowy z wejscia (tryb reczny).
    """
    # Pula spoleczna — grant, kredyt SBC, partycypacja, wklad wlasny.
    if kwota_kredytu is None:
        kwota_kredytu = (
            a.spoleczna.koszty_przedsiewziecia * w.pula_spoleczna.kredyt.udzial_docelowy
        )
    # art. 29a ust. 2 ustawy z 26.10.1995 mowi o koszcie budowy lokalu; model liczy
    # go jako koszt przedsiewziecia przypadajacy na lokale tej puli (z udzialem
    # w kosztach wspolnych), zgodnie z metodyka "wszystko per m2 PUM".
    kwota_partycypacji = (
        a.spoleczna.koszty_przedsiewziecia
        * w.pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu
    )
    spoleczna = FinansowaniePuli(
        nazwa="spoleczna",
        koszty_przedsiewziecia=a.spoleczna.koszty_przedsiewziecia,
        grant=g.spoleczna.kwota,
        kredyt=kwota_kredytu,
        partycypacja=kwota_partycypacji,
        wklad_wlasny=(
            a.spoleczna.koszty_przedsiewziecia
            - g.spoleczna.kwota
            - kwota_kredytu
            - kwota_partycypacji
        ),
    )

    # Pula komunalna — wylacznie grant i wklad wlasny. Kredyt wykluczony
    # (art. 5a ust. 3), partycypacji nie ma, bo najemca jest gmina.
    komunalna = FinansowaniePuli(
        nazwa="komunalna",
        koszty_przedsiewziecia=a.komunalna.koszty_przedsiewziecia,
        grant=g.komunalna.kwota,
        kredyt=ZERO,
        partycypacja=ZERO,
        wklad_wlasny=a.komunalna.koszty_przedsiewziecia - g.komunalna.kwota,
    )

    return Finansowanie(
        spoleczna=spoleczna,
        komunalna=komunalna,
        harmonogram_kredytu=harmonogram(w.pula_spoleczna.kredyt, kwota_kredytu),
    )


# ---------------------------------------------------------------------------
# Okres powierzenia
# ---------------------------------------------------------------------------

def okres_powierzenia(w: Wejscie, sciezka_kredytowa: bool) -> int:
    """Dlugosc okresu powierzenia w latach dla danej sciezki."""
    if not sciezka_kredytowa:
        return prawo.OKRES_POWIERZENIA_GRANT_LAT
    # § 11 rozp. 766 — rowny okresowi finansowania, nie dluzej niz okres amortyzacji.
    return min(
        w.pula_spoleczna.kredyt.okres_lat,
        w.parametry_zewnetrzne.okres_amortyzacji_budynkow_lat,
    )


# ---------------------------------------------------------------------------
# Przeplywy roczne
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RokProjekcji:
    rok: int
    czynsz_m2_mies: Decimal
    przychod_czynszowy_potencjalny: Decimal
    strata_na_pustostanach: Decimal
    przychod_czynszowy_netto: Decimal
    koszt_eksploatacji: Decimal
    odpis_remontowy: Decimal
    ubezpieczenie: Decimal
    koszty_zarzadu: Decimal
    obsluga_dlugu: Decimal
    rezerwa_zwrot_partycypacji: Decimal
    pulap_oplat_poza_czynszem: Decimal   # art. 28 ust. 4-5, osobny strumien

    @property
    def koszty_operacyjne(self) -> Decimal:
        return self.koszt_eksploatacji + self.odpis_remontowy + self.ubezpieczenie + self.koszty_zarzadu

    @property
    def wymagane_pokrycie(self) -> Decimal:
        """Mianownik testu 2: koszty eksploatacji + odpis remontowy + rata kredytu."""
        return self.koszty_operacyjne + self.obsluga_dlugu

    @property
    def dscr(self) -> Optional[Decimal]:
        """Wskaznik pokrycia obslugi dlugu. None, gdy nie ma czego pokrywac."""
        if self.wymagane_pokrycie == ZERO:
            return None
        return self.przychod_czynszowy_netto / self.wymagane_pokrycie

    @property
    def luka_roczna(self) -> Decimal:
        """Ile brakuje przychodu do pokrycia. Zero, gdy pokrycie wystarcza."""
        return max(ZERO, self.wymagane_pokrycie - self.przychod_czynszowy_netto)

    @property
    def saldo(self) -> Decimal:
        """Przeplyw po obsludze dlugu i rezerwie na zwrot partycypacji."""
        return (
            self.przychod_czynszowy_netto
            - self.wymagane_pokrycie
            - self.rezerwa_zwrot_partycypacji
        )


@dataclass(frozen=True)
class ProjekcjaPuli:
    nazwa: str
    pum: Decimal
    lata: Tuple[RokProjekcji, ...]
    okres_powierzenia_lat: int
    sciezka: str                       # "grant" albo "kredyt"

    @property
    def aktywna(self) -> bool:
        return self.pum > ZERO and bool(self.lata)

    @property
    def pierwszy_rok_naruszenia(self) -> Optional[int]:
        for rok in self.lata:
            dscr = rok.dscr
            if dscr is not None and dscr < JEDEN:
                return rok.rok
        return None

    @property
    def minimalny_dscr(self) -> Optional[Decimal]:
        wartosci = [r.dscr for r in self.lata if r.dscr is not None]
        return min(wartosci) if wartosci else None

    @property
    def maksymalna_luka_roczna(self) -> Decimal:
        return max((r.luka_roczna for r in self.lata), default=ZERO)

    @property
    def rok_maksymalnej_luki(self) -> Optional[int]:
        naruszenia = [r for r in self.lata if r.luka_roczna > ZERO]
        if not naruszenia:
            return None
        return max(naruszenia, key=lambda r: r.luka_roczna).rok


@dataclass(frozen=True)
class Projekcja:
    spoleczna: ProjekcjaPuli
    komunalna: ProjekcjaPuli

    @property
    def pule(self) -> Tuple[ProjekcjaPuli, ...]:
        return tuple(p for p in (self.spoleczna, self.komunalna) if p.aktywna)

    @property
    def horyzont_lat(self) -> int:
        return max((p.okres_powierzenia_lat for p in self.pule), default=0)


def _projekcja_puli(
    w: Wejscie,
    pula: PulaKosztow,
    limity: LimityCzynszu,
    czynsz_bazowy_m2_mies: Decimal,
    fin: FinansowaniePuli,
    h: Optional[Harmonogram],
    pustostany: Decimal,
    lat: int,
    sciezka: str,
) -> ProjekcjaPuli:
    e = w.eksploatacja
    p = w.parametry_zewnetrzne
    lata = []

    if not pula.aktywna:
        return ProjekcjaPuli(
            nazwa=pula.nazwa, pum=pula.pum, lata=(), okres_powierzenia_lat=lat, sciezka=sciezka
        )

    for rok in range(1, lat + 1):
        indeks_czynszu = (JEDEN + e.indeksacja_czynszu_rocznie) ** (rok - 1)
        indeks_kosztow = (JEDEN + e.indeksacja_kosztow_rocznie) ** (rok - 1)

        czynsz_m2 = czynsz_bazowy_m2_mies * indeks_czynszu
        potencjalny = czynsz_m2 * MIESIECY_W_ROKU * pula.pum
        strata = potencjalny * pustostany

        # Rezerwa na zwrot partycypacji — art. 29a ust. 3. Zobowiazanie rosnie
        # wskaznikiem GUS i jest wymagalne niezaleznie od ponownego zasiedlenia,
        # wiec model traktuje je jako wyplyw, a nie jako pozycje netto.
        if fin.partycypacja > ZERO and w.pula_spoleczna.partycypacja.rotacja_roczna > ZERO:
            waloryzacja = (JEDEN + p.waloryzacja_partycypacji_rocznie) ** rok
            rezerwa = fin.partycypacja * w.pula_spoleczna.partycypacja.rotacja_roczna * waloryzacja
        else:
            rezerwa = ZERO

        lata.append(
            RokProjekcji(
                rok=rok,
                czynsz_m2_mies=czynsz_m2,
                przychod_czynszowy_potencjalny=potencjalny,
                strata_na_pustostanach=strata,
                przychod_czynszowy_netto=potencjalny - strata,
                koszt_eksploatacji=e.koszt_eksploatacji_m2_rok * pula.pum * indeks_kosztow,
                odpis_remontowy=e.odpis_remontowy_m2_rok * pula.pum * indeks_kosztow,
                ubezpieczenie=e.ubezpieczenie_rocznie * pula.udzial_pum * indeks_kosztow,
                koszty_zarzadu=e.koszty_stale_zarzadu_rocznie * pula.udzial_pum * indeks_kosztow,
                obsluga_dlugu=h.obsluga_dlugu(rok) if h is not None else ZERO,
                rezerwa_zwrot_partycypacji=rezerwa,
                pulap_oplat_poza_czynszem=oplaty_poza_czynszem_rocznie(w, pula.pum),
            )
        )

    return ProjekcjaPuli(
        nazwa=pula.nazwa,
        pum=pula.pum,
        lata=tuple(lata),
        okres_powierzenia_lat=lat,
        sciezka=sciezka,
    )


def build(
    w: Wejscie,
    a: Alokacja,
    fin: Finansowanie,
    limity_spoleczna: LimityCzynszu,
    limity_komunalna: LimityCzynszu,
) -> Projekcja:
    kredyt_aktywny = fin.harmonogram_kredytu.aktywny
    sciezka_spoleczna = "kredyt" if kredyt_aktywny else "grant"

    pustostany_komunalne = (
        w.eksploatacja.pustostany_procent
        if w.przelaczniki.pustostany_takze_w_puli_komunalnej
        else ZERO
    )

    return Projekcja(
        spoleczna=_projekcja_puli(
            w,
            a.spoleczna,
            limity_spoleczna,
            w.pula_spoleczna.czynsz_zakladany_m2_mies,
            fin.spoleczna,
            fin.harmonogram_kredytu if kredyt_aktywny else None,
            w.eksploatacja.pustostany_procent,
            okres_powierzenia(w, sciezka_kredytowa=kredyt_aktywny),
            sciezka_spoleczna,
        ),
        komunalna=_projekcja_puli(
            w,
            a.komunalna,
            limity_komunalna,
            w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies,
            fin.komunalna,
            None,
            pustostany_komunalne,
            okres_powierzenia(w, sciezka_kredytowa=False),
            "grant",
        ),
    )
