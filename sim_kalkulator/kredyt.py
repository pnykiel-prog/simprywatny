"""Harmonogram splat kredytu SBC i ekwiwalent dotacji brutto.

Kredyt splacany w systemie rownej raty z karencja splaty kapitalu — wariant
wskazany przez rozporzadzenie o finansowaniu zwrotnym. W okresie karencji placone
sa same odsetki, potem annuita liczona na pozostale okresy.

EDB wg § 4 pkt 5 lit. e rozporzadzenia RM z 11.08.2004 (t.j. Dz.U. 2018 poz. 461):

    EDB = SUM[i=1..T]  (S*r - S*rp) / (1+rd)^i
        + SUM[i=T+1..N] [ S*r *(1+r )^(N-T) / ((1+r )^(N-T) - 1)
                        - S*rp*(1+rp)^(N-T) / ((1+rp)^(N-T) - 1) ] / (1+rd)^i

Asercja obowiazkowa: 0 < EDB < S. Wynik ujemny oznacza rp > r — silnik przerywa
z komunikatem zamiast zwrocic liczbe. Przypadek rp = r daje dokladnie zero i jest
dopuszczalna granica, a nie bledem.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from .dane import BladObliczenia, Kredyt, ParametryZewnetrzne
from .waluta import ZERO, zl

JEDEN = Decimal(1)


@dataclass(frozen=True)
class RataRoczna:
    rok: int
    saldo_poczatkowe: Decimal
    odsetki: Decimal
    kapital: Decimal
    saldo_koncowe: Decimal
    karencja: bool

    @property
    def rata(self) -> Decimal:
        return self.odsetki + self.kapital


@dataclass(frozen=True)
class Harmonogram:
    kwota: Decimal                  # S
    oprocentowanie: Decimal         # rp
    okres_lat: int                  # N
    karencja_lat: int               # T
    raty: Tuple[RataRoczna, ...]

    @property
    def aktywny(self) -> bool:
        return self.kwota > ZERO and self.okres_lat > 0

    @property
    def rata_annuitetowa(self) -> Decimal:
        """Rata w okresie splaty kapitalu (po karencji)."""
        for rata in self.raty:
            if not rata.karencja:
                return rata.rata
        return ZERO

    def obsluga_dlugu(self, rok: int) -> Decimal:
        """Laczna rata w danym roku projekcji (1-indeksowany). Poza okresem: zero."""
        if 1 <= rok <= len(self.raty):
            return self.raty[rok - 1].rata
        return ZERO

    @property
    def suma_odsetek(self) -> Decimal:
        return sum((r.odsetki for r in self.raty), ZERO)


def _annuita(kwota: Decimal, stopa: Decimal, okresy: int) -> Decimal:
    """Rata rowna dla kwoty, stopy i liczby okresow."""
    if okresy <= 0:
        return ZERO
    if stopa == ZERO:
        # Granica wzoru annuitetowego przy stopie zerowej — sam kapital.
        return kwota / Decimal(okresy)
    czynnik = (JEDEN + stopa) ** okresy
    return kwota * stopa * czynnik / (czynnik - JEDEN)


def wartosc_biezaca_rat(
    rata: Decimal, stopa: Decimal, okresy_splaty: int, karencja_lat: int
) -> Decimal:
    """Kwota kredytu, ktora przy danej stopie da dokladnie taka rate roczna.

    Odwrocenie wzoru annuitetowego. W okresie karencji placone sa same odsetki,
    wiec karencja nie zmienia zdolnosci do udzwigniecia kapitalu — wplywa na
    harmonogram, nie na wysokosc raty po karencji.

    Sluzy jako pierwsze przyblizenie przy szukaniu maksymalnego kredytu
    obslugiwalnego; wiazacy jest rachunek na pelnej projekcji, bo ta uwzglednia
    indeksacje kosztow i czynszu przez caly okres.
    """
    if rata <= ZERO or okresy_splaty <= 0:
        return ZERO
    if stopa == ZERO:
        return rata * Decimal(okresy_splaty)
    czynnik = (JEDEN + stopa) ** okresy_splaty
    return rata * (czynnik - JEDEN) / (stopa * czynnik)


def harmonogram(k: Kredyt, kwota: Decimal) -> Harmonogram:
    """Buduje harmonogram splat rownej raty z karencja splaty kapitalu."""
    kwota = zl(kwota)
    if kwota <= ZERO or not k.aktywny:
        return Harmonogram(
            kwota=ZERO,
            oprocentowanie=k.oprocentowanie,
            okres_lat=k.okres_lat,
            karencja_lat=k.karencja_lat,
            raty=(),
        )

    okresy_splaty = k.okres_lat - k.karencja_lat
    rata = _annuita(kwota, k.oprocentowanie, okresy_splaty)

    raty: List[RataRoczna] = []
    saldo = kwota
    for rok in range(1, k.okres_lat + 1):
        odsetki = saldo * k.oprocentowanie
        if rok <= k.karencja_lat:
            kapital = ZERO
        else:
            kapital = rata - odsetki
            if rok == k.okres_lat:
                # Ostatni rok domyka saldo co do grosza — annuita zostawia resztke.
                kapital = saldo
        saldo_koncowe = saldo - kapital
        raty.append(
            RataRoczna(
                rok=rok,
                saldo_poczatkowe=saldo,
                odsetki=odsetki,
                kapital=kapital,
                saldo_koncowe=saldo_koncowe,
                karencja=rok <= k.karencja_lat,
            )
        )
        saldo = saldo_koncowe

    if abs(saldo) > Decimal("0.01"):
        raise BladObliczenia(
            f"Harmonogram nie domyka salda kredytu: pozostalo {saldo}. "
            "Sprawdz okres, karencje i oprocentowanie."
        )
    return Harmonogram(
        kwota=kwota,
        oprocentowanie=k.oprocentowanie,
        okres_lat=k.okres_lat,
        karencja_lat=k.karencja_lat,
        raty=tuple(raty),
    )


# ---------------------------------------------------------------------------
# Ekwiwalent dotacji brutto
# ---------------------------------------------------------------------------

def edb_grant(kwota_grantu: Decimal) -> Decimal:
    """§ 4 pkt 1 rozp. Dz.U. 2018 poz. 461 — dla dotacji EDB rowna sie kwocie dotacji.

    Bez dyskontowania i bez parametrow.
    """
    return zl(kwota_grantu)


def edb_kredyt(
    kwota: Decimal,
    oprocentowanie_preferencyjne: Decimal,
    okres_lat: int,
    karencja_lat: int,
    stopa_referencyjna: Decimal,
    stopa_dyskontowa: Decimal,
) -> Decimal:
    """§ 4 pkt 5 lit. e rozp. Dz.U. 2018 poz. 461.

    S  — kwota kredytu
    N  — liczba okresow platnosci i karencji lacznie
    T  — liczba okresow karencji
    r  — stopa referencyjna KE
    rp — preferencyjna stopa kredytu
    rd — stopa dyskontowa
    """
    S = zl(kwota)
    rp = zl(oprocentowanie_preferencyjne)
    r = zl(stopa_referencyjna)
    rd = zl(stopa_dyskontowa)
    N = int(okres_lat)
    T = int(karencja_lat)

    if S <= ZERO:
        return ZERO
    if N <= 0:
        raise BladObliczenia("EDB kredytu wymaga dodatniej liczby okresow N.")
    if not (0 <= T < N):
        raise BladObliczenia(
            f"Liczba okresow karencji T={T} musi miescic sie w przedziale [0, N) dla N={N}."
        )
    if rd <= Decimal("-1"):
        raise BladObliczenia("Stopa dyskontowa rd musi byc wieksza niz -100%.")

    okresy_splaty = N - T

    # Czlon pierwszy — okres karencji, splacane sa same odsetki.
    czlon_karencji = ZERO
    for i in range(1, T + 1):
        czlon_karencji += (S * r - S * rp) / (JEDEN + rd) ** i

    # Czlon drugi — okres splaty kapitalu, roznica annuit liczonych stopa
    # referencyjna i preferencyjna.
    annuita_referencyjna = _annuita(S, r, okresy_splaty)
    annuita_preferencyjna = _annuita(S, rp, okresy_splaty)
    roznica_rat = annuita_referencyjna - annuita_preferencyjna

    czlon_splaty = ZERO
    for i in range(T + 1, N + 1):
        czlon_splaty += roznica_rat / (JEDEN + rd) ** i

    edb = czlon_karencji + czlon_splaty

    # Asercja obowiazkowa z rozdz. 3.6 specyfikacji.
    if edb < ZERO:
        raise BladObliczenia(
            f"EDB kredytu wyszlo ujemne ({edb:.2f} zl). Oznacza to, ze oprocentowanie "
            f"preferencyjne rp = {rp} przewyzsza stope referencyjna KE r = {r}, czyli kredyt "
            "nie zawiera pomocy publicznej i nie jest preferencyjny. Sprawdz obie stopy — "
            "silnik nie zwraca liczby dla takiej konfiguracji."
        )
    if edb >= S:
        raise BladObliczenia(
            f"EDB kredytu ({edb:.2f} zl) nie jest mniejsze od kwoty kredytu ({S:.2f} zl). "
            "Wzor z § 4 pkt 5 lit. e nie moze dac takiego wyniku dla poprawnych danych — "
            "sprawdz stopy r, rp, rd oraz okresy N i T."
        )
    return edb


def edb_dla_harmonogramu(h: Harmonogram, p: ParametryZewnetrzne) -> Decimal:
    """EDB dla zbudowanego harmonogramu, przy parametrach zewnetrznych wejscia."""
    if not h.aktywny:
        return ZERO
    return edb_kredyt(
        kwota=h.kwota,
        oprocentowanie_preferencyjne=h.oprocentowanie,
        okres_lat=h.okres_lat,
        karencja_lat=h.karencja_lat,
        stopa_referencyjna=p.stopa_referencyjna_ke,
        stopa_dyskontowa=p.stopa_dyskontowa,
    )
