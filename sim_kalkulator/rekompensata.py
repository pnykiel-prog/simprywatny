"""Koszty netto UOIG, rozsadny zysk i test nadwyzki rekompensaty.

Warunek graniczny: RUOIG <= KN + RZ
  art. 5 ust. 5 i 11 ustawy z 8.12.2006; § 6 ust. 2 rozp. Dz.U. 2025 poz. 1897.

Koszty netto:
    KN = SUM[i=1..n] (KUOIG_i - PUOIG_i) / (1 + rb)^(i-1)
gdzie rb to stopa bazowa KE na dzien zawarcia umowy, a n to ostatni rok okresu
powierzenia.

ASYMETRIA GRUNTU — najlatwiejsze miejsce na blad:
  * grunt inwestora, sciezka grantowa  -> KOSZT, bez limitu procentowego
                                          (art. 5 ust. 7 pkt 7 i ust. 8),
  * grunt JST wniesiony aportem,
    sciezka grantowa                   -> PRZYCHOD inwestora, obniza KN
                                          (art. 5 ust. 9 pkt 4),
  * grunt wniesiony aportem,
    sciezka kredytowa                  -> KOSZT, ale tylko do 20% calkowitych
                                          kosztow przedsiewziecia (§ 12 ust. 7 rozp. 766).

Grunt inwestora podnosi podstawe, grunt gminy ja obniza.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from . import prawo
from .alokacja import PulaKosztow
from .dane import (
    Waga,
    MetodaRozsadnegoZysku,
    Ostrzezenie,
    UjecieKosztowInwestycyjnych,
    Wejscie,
)
from .kredyt import Harmonogram, edb_grant
from .projekcja import FinansowaniePuli, ProjekcjaPuli
from .waluta import ZERO, bezpieczny_iloraz

JEDEN = Decimal(1)


@dataclass(frozen=True)
class RokUOIG:
    rok: int
    koszty_biezace: Decimal
    koszty_inwestycyjne: Decimal
    odsetki: Decimal
    grunt_jako_koszt: Decimal
    przychod_czynszowy: Decimal
    grunt_jako_przychod: Decimal
    czynnik_dyskonta: Decimal

    @property
    def kuoig(self) -> Decimal:
        return (
            self.koszty_biezace
            + self.koszty_inwestycyjne
            + self.odsetki
            + self.grunt_jako_koszt
        )

    @property
    def puoig(self) -> Decimal:
        return self.przychod_czynszowy + self.grunt_jako_przychod

    @property
    def netto(self) -> Decimal:
        return self.kuoig - self.puoig

    @property
    def netto_zdyskontowane(self) -> Decimal:
        return self.netto / self.czynnik_dyskonta


@dataclass(frozen=True)
class RekompensataPuli:
    nazwa: str
    sciezka: str                       # "grant" albo "kredyt"
    okres_powierzenia_lat: int
    lata: Tuple[RokUOIG, ...]
    kn: Decimal
    rz: Decimal
    edb_grantu: Decimal
    edb_kredytu: Decimal
    wsparcie_dodatkowe: Decimal        # RFRM + dokumentacja BGK, § 7 ust. 7 rozp. 1897
    prog_tolerancji: Decimal
    grunt_ujecie: str                  # opis zastosowanej reguly gruntowej

    @property
    def ruoig(self) -> Decimal:
        """Rekompensata: EDB grantu + EDB kredytu + wsparcie dodatkowe."""
        return self.edb_grantu + self.edb_kredytu + self.wsparcie_dodatkowe

    @property
    def dopuszczalna(self) -> Decimal:
        return self.kn + self.rz

    @property
    def nadwyzka(self) -> Decimal:
        return max(ZERO, self.ruoig - self.dopuszczalna)

    @property
    def srednia_roczna_rekompensata(self) -> Decimal:
        if self.okres_powierzenia_lat <= 0:
            return ZERO
        return self.ruoig / Decimal(self.okres_powierzenia_lat)

    @property
    def tolerancja_kwotowo(self) -> Decimal:
        """Prog tolerancji jako procent sredniej rocznej rekompensaty."""
        return self.srednia_roczna_rekompensata * self.prog_tolerancji

    @property
    def nadwyzka_wzgledna(self) -> Decimal:
        """Nadwyzka odniesiona do sredniej rocznej rekompensaty."""
        return bezpieczny_iloraz(self.nadwyzka, self.srednia_roczna_rekompensata)

    @property
    def przechodzi(self) -> bool:
        return self.nadwyzka <= self.tolerancja_kwotowo

    @property
    def kwota_do_zwrotu(self) -> Decimal:
        """Kwota podlegajaca zwrotowi do Funduszu Doplat.

        Przekroczenie progu tolerancji uruchamia zwrot calej nadwyzki, a nie tylko
        czesci ponad prog — prog jest granica dopuszczalnosci, nie kwota wolna.
        """
        return self.nadwyzka if not self.przechodzi else ZERO


@dataclass(frozen=True)
class TestRekompensaty:
    spoleczna: Optional[RekompensataPuli]
    komunalna: Optional[RekompensataPuli]
    laczna: Optional[RekompensataPuli]        # tylko przy hybrydzie jako jednym przedsiewzieciu
    ostrzezenia: Tuple[Ostrzezenie, ...]

    @property
    def badane(self) -> Tuple[RekompensataPuli, ...]:
        if self.laczna is not None:
            return (self.laczna,)
        return tuple(p for p in (self.spoleczna, self.komunalna) if p is not None)

    @property
    def przechodzi(self) -> bool:
        return all(p.przechodzi for p in self.badane)

    @property
    def nadwyzka_laczna(self) -> Decimal:
        return sum((p.nadwyzka for p in self.badane), ZERO)

    @property
    def kwota_do_zwrotu(self) -> Decimal:
        return sum((p.kwota_do_zwrotu for p in self.badane), ZERO)


# ---------------------------------------------------------------------------
# Regula gruntowa
# ---------------------------------------------------------------------------

def ujecie_gruntu(
    w: Wejscie, pula: PulaKosztow, sciezka_kredytowa: bool
) -> Tuple[Decimal, Decimal, str]:
    """Zwraca (grunt_jako_koszt, grunt_jako_przychod, opis)."""
    wartosc = pula.grunt
    if wartosc <= ZERO:
        return ZERO, ZERO, "brak pozycji gruntowej"

    if sciezka_kredytowa:
        if w.grunt.forma.wniesiony_aportem:
            # § 12 ust. 7 rozp. 766 — koszt, ale tylko do 20% calkowitych kosztow.
            pulap = pula.koszty_przedsiewziecia * prawo.GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT
            uznany = min(wartosc, pulap)
            opis = (
                f"sciezka kredytowa, grunt z aportu: koszt do "
                f"{prawo.GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT:.0%} kosztow przedsiewziecia "
                f"(§ 12 ust. 7 rozp. 766)"
            )
            if uznany < wartosc:
                opis += f" — obcieto {wartosc - uznany:.2f} zl"
            return uznany, ZERO, opis
        return wartosc, ZERO, "sciezka kredytowa, grunt nie z aportu: koszt bez limitu"

    if w.grunt.forma.pochodzi_od_jst:
        # art. 5 ust. 9 pkt 4 — grunt JST jest PRZYCHODEM inwestora i obniza KN.
        return (
            ZERO,
            wartosc,
            "sciezka grantowa, grunt JST: przychod inwestora, obniza KN (art. 5 ust. 9 pkt 4)",
        )
    # art. 5 ust. 7 pkt 7 i ust. 8 — grunt inwestora jest kosztem, bez limitu procentowego.
    return (
        wartosc,
        ZERO,
        "sciezka grantowa, grunt inwestora: koszt bez limitu (art. 5 ust. 7 pkt 7 i ust. 8)",
    )


# ---------------------------------------------------------------------------
# Rozsadny zysk
# ---------------------------------------------------------------------------

def rozsadny_zysk(
    w: Wejscie, fin: FinansowaniePuli, lat: int, udzial_pum: Decimal
) -> Decimal:
    """Rozsadny zysk (RZ).

    Specyfikacja wskazuje zrodlo stopy — IRS dla kontraktu 20-letniego na bazie
    WIBOR 3M, publikowany przez BGK w BIP przed naborem (§ 6 ust. 5 rozp. 1897;
    § 12 ust. 10 rozp. 766) — ale nie podaje wzoru. Metoda jest przelacznikiem
    z jawnym oznaczeniem zalozenia; patrz LUKI.md.
    """
    if w.przelaczniki.metoda_rozsadnego_zysku is MetodaRozsadnegoZysku.KWOTA_WPROST:
        kwota = w.rekompensata.rozsadny_zysk_kwota or ZERO
        return kwota * udzial_pum

    # ZALOZENIE: godziwy zwrot ze srodkow wlasnych zaangazowanych w przedsiewziecie,
    # naliczany stopa IRS BGK rocznie i dyskontowany stopa bazowa KE — tak samo
    # jak strumien kosztow netto, zeby obie strony nierownosci byly porownywalne.
    kapital = max(ZERO, fin.wklad_wlasny)
    rb = w.parametry_zewnetrzne.stopa_bazowa_ke
    rz = ZERO
    for rok in range(1, lat + 1):
        rz += kapital * w.parametry_zewnetrzne.stopa_irs_bgk / (JEDEN + rb) ** (rok - 1)
    return rz


# ---------------------------------------------------------------------------
# Koszty netto
# ---------------------------------------------------------------------------

def _koszty_inwestycyjne(w: Wejscie, pula: PulaKosztow, rok: int, lat: int) -> Decimal:
    """Naklad inwestycyjny w kosztach UOIG — BEZ pozycji gruntowej.

    Grunt wchodzi do rachunku wlasna regula asymetryczna (patrz `ujecie_gruntu`),
    wiec ujety tutaj po raz drugi trafialby do KN podwojnie.
    """
    ujecie = w.przelaczniki.koszty_inwestycyjne_w_kn
    if ujecie is UjecieKosztowInwestycyjnych.POMINIETE:
        return ZERO
    podstawa = pula.koszty_przedsiewziecia_bez_gruntu
    if ujecie is UjecieKosztowInwestycyjnych.NAKLAD_POCZATKOWY:
        return podstawa if rok == 1 else ZERO
    if ujecie is UjecieKosztowInwestycyjnych.AMORTYZACJA_W_OKRESIE_POWIERZENIA:
        if lat <= 0:
            return ZERO
        return podstawa / Decimal(lat)
    # AMORTYZACJA — roczny odpis wg okresu amortyzacji budynkow z wejscia.
    okres = w.parametry_zewnetrzne.okres_amortyzacji_budynkow_lat
    return podstawa / Decimal(okres)


def _rekompensata_puli(
    w: Wejscie,
    pula: PulaKosztow,
    proj: ProjekcjaPuli,
    fin: FinansowaniePuli,
    h: Optional[Harmonogram],
    edb_kredytu: Decimal,
    wsparcie_dodatkowe: Decimal,
) -> RekompensataPuli:
    sciezka_kredytowa = proj.sciezka == "kredyt"
    lat = proj.okres_powierzenia_lat
    rb = w.parametry_zewnetrzne.stopa_bazowa_ke

    grunt_koszt, grunt_przychod, opis_gruntu = ujecie_gruntu(w, pula, sciezka_kredytowa)

    lata: List[RokUOIG] = []
    for rok_proj in proj.lata:
        i = rok_proj.rok
        # art. 5 ust. 7-8 — koszty biezace swiadczenia uslugi. Koszty stale zarzadu
        # sa w sciezce kredytowej wskazane wprost jako wklad we wspolne koszty stale
        # (§ 12 ust. 3 rozp. 766); model ujmuje je w obu sciezkach.
        koszty_biezace = (
            rok_proj.koszt_eksploatacji
            + rok_proj.odpis_remontowy
            + rok_proj.ubezpieczenie
            + rok_proj.koszty_zarzadu
        )
        odsetki = ZERO
        if h is not None and 1 <= i <= len(h.raty):
            odsetki = h.raty[i - 1].odsetki

        lata.append(
            RokUOIG(
                rok=i,
                koszty_biezace=koszty_biezace,
                koszty_inwestycyjne=_koszty_inwestycyjne(w, pula, i, lat),
                odsetki=odsetki,
                grunt_jako_koszt=grunt_koszt if i == 1 else ZERO,
                przychod_czynszowy=rok_proj.przychod_czynszowy_netto,
                grunt_jako_przychod=grunt_przychod if i == 1 else ZERO,
                czynnik_dyskonta=(JEDEN + rb) ** (i - 1),
            )
        )

    kn = sum((rok.netto_zdyskontowane for rok in lata), ZERO)
    rz = rozsadny_zysk(w, fin, lat, pula.udzial_pum)

    return RekompensataPuli(
        nazwa=pula.nazwa,
        sciezka=proj.sciezka,
        okres_powierzenia_lat=lat,
        lata=tuple(lata),
        kn=kn,
        rz=rz,
        edb_grantu=edb_grant(fin.grant),
        edb_kredytu=edb_kredytu,
        wsparcie_dodatkowe=wsparcie_dodatkowe,
        prog_tolerancji=prawo.prog_tolerancji_nadwyzki(proj.sciezka),
        grunt_ujecie=opis_gruntu,
    )


def build(
    w: Wejscie,
    a,
    fin,
    proj,
    edb_kredytu_spoleczna: Decimal,
) -> TestRekompensaty:
    """Sklada test rekompensaty dla obu pul.

    Domyslnie hybryda to dwa odrebne przedsiewziecia, wiec kazda pula ma wlasny
    okres powierzenia, wlasny prog tolerancji i wlasny test. Przelacznik
    `hybryda_jako_jedno_przedsiewziecie` scala je w jeden rachunek.
    """
    ostrzezenia: List[Ostrzezenie] = []

    # § 7 ust. 7 rozp. 1897 — RFRM i wartosc nieodplatnego prawa do dokumentacji
    # projektowej BGK wliczaja sie do rekompensaty w sciezce grantowej.
    # Dzielone tym samym kluczem PUM co reszta pozycji wspolnych.
    wsparcie_dodatkowe = (
        w.rekompensata.wsparcie_rfrm + w.rekompensata.wartosc_dokumentacji_bgk
    )
    if wsparcie_dodatkowe > ZERO:
        ostrzezenia.append(
            Ostrzezenie(
                kod="WSPARCIE_DODATKOWE_W_REKOMPENSACIE",
                tresc=(
                    f"Do rekompensaty doliczono {wsparcie_dodatkowe:.2f} zl tytulem wsparcia "
                    "z Rzadowego Funduszu Rozwoju Mieszkalnictwa i wartosci nieodplatnego prawa "
                    "do dokumentacji projektowej BGK. Dokumentacja z zasobu Banku nie jest "
                    "darmowa w sensie limitu rekompensaty."
                ),
                podstawa="§ 7 ust. 7 rozp. Dz.U. 2025 poz. 1897",
            
                tresc_potoczna=(
                    "Do limitu pomocy publicznej wlicza sie takze wsparcie z Rzadowego Funduszu "
                    "i wartosc dokumentacji projektowej z zasobu Banku. Nie sa darmowe w sensie limitu."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    spoleczna = None
    if proj.spoleczna.aktywna:
        spoleczna = _rekompensata_puli(
            w,
            a.spoleczna,
            proj.spoleczna,
            fin.spoleczna,
            fin.harmonogram_kredytu if proj.spoleczna.sciezka == "kredyt" else None,
            edb_kredytu_spoleczna,
            wsparcie_dodatkowe * a.spoleczna.udzial_pum,
        )
    komunalna = None
    if proj.komunalna.aktywna:
        komunalna = _rekompensata_puli(
            w,
            a.komunalna,
            proj.komunalna,
            fin.komunalna,
            None,
            ZERO,
            wsparcie_dodatkowe * a.komunalna.udzial_pum,
        )

    laczna = None
    if w.przelaczniki.hybryda_jako_jedno_przedsiewziecie and spoleczna and komunalna:
        laczna = _scal(spoleczna, komunalna)
        ostrzezenia.append(
            Ostrzezenie(
                kod="REKOMPENSATA_JEDEN_TEST",
                tresc=(
                    "Przelacznik 'hybryda_jako_jedno_przedsiewziecie' jest wlaczony, wiec test "
                    "nadwyzki liczony jest raz, lacznie dla obu pul, z progiem tolerancji "
                    f"{laczna.prog_tolerancji:.0%} wlasciwym dla sciezki '{laczna.sciezka}'. "
                    "Przy odczycie domyslnym byly to dwa osobne testy o roznych progach."
                ),
                podstawa="art. 13 ust. 1a ustawy z 8.12.2006 — kwestia otwarta 10.1",
            
                tresc_potoczna=(
                    "Limit pomocy publicznej liczony jest raz, lacznie dla obu pul. Przy odczycie "
                    "domyslnym byly to dwa osobne rachunki o roznych progach."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    for pula in (spoleczna, komunalna):
        if pula is not None and pula.kn < ZERO:
            ostrzezenia.append(
                Ostrzezenie(
                    kod="KOSZTY_NETTO_UJEMNE",
                    tresc=(
                        f"Koszty netto puli {pula.nazwa} wyszly ujemne ({pula.kn:.2f} zl), "
                        "czyli zdyskontowane przychody UOIG przewyzszaja koszty. Kazda zlotowka "
                        "rekompensaty jest wtedy nadwyzka. Sprawdz czynsz, ujecie nakladu "
                        "inwestycyjnego i pozycje gruntowa."
                    ),
                    podstawa="art. 5 ust. 5 i 11 ustawy z 8.12.2006",
                
                tresc_potoczna=(
                    "Wedlug modelu inwestycja zarabia wiecej, niz kosztuje utrzymanie uslugi. Kazda "
                    "zlotowka dotacji jest wtedy nadwyzka — sprawdz czynsz i sposob rozliczenia nakladu."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
            )

    return TestRekompensaty(
        spoleczna=spoleczna,
        komunalna=komunalna,
        laczna=laczna,
        ostrzezenia=tuple(ostrzezenia),
    )


def _scal(a: RekompensataPuli, b: RekompensataPuli) -> RekompensataPuli:
    """Laczy dwie pule w jeden rachunek rekompensaty.

    Prog tolerancji bierze sie ze sciezki kredytowej, jezeli ktorakolwiek pula
    z niej korzysta — jedno przedsiewziecie ma jeden rezim.
    """
    sciezka = "kredyt" if "kredyt" in (a.sciezka, b.sciezka) else "grant"
    lat = max(a.okres_powierzenia_lat, b.okres_powierzenia_lat)
    lata: List[RokUOIG] = []
    for rok in range(1, lat + 1):
        czesci = [p.lata[rok - 1] for p in (a, b) if rok <= len(p.lata)]
        lata.append(
            RokUOIG(
                rok=rok,
                koszty_biezace=sum((c.koszty_biezace for c in czesci), ZERO),
                koszty_inwestycyjne=sum((c.koszty_inwestycyjne for c in czesci), ZERO),
                odsetki=sum((c.odsetki for c in czesci), ZERO),
                grunt_jako_koszt=sum((c.grunt_jako_koszt for c in czesci), ZERO),
                przychod_czynszowy=sum((c.przychod_czynszowy for c in czesci), ZERO),
                grunt_jako_przychod=sum((c.grunt_jako_przychod for c in czesci), ZERO),
                czynnik_dyskonta=czesci[0].czynnik_dyskonta,
            )
        )
    return RekompensataPuli(
        nazwa="laczna",
        sciezka=sciezka,
        okres_powierzenia_lat=lat,
        lata=tuple(lata),
        kn=a.kn + b.kn,
        rz=a.rz + b.rz,
        edb_grantu=a.edb_grantu + b.edb_grantu,
        edb_kredytu=a.edb_kredytu + b.edb_kredytu,
        wsparcie_dodatkowe=a.wsparcie_dodatkowe + b.wsparcie_dodatkowe,
        prog_tolerancji=prawo.prog_tolerancji_nadwyzki(sciezka),
        grunt_ujecie=f"spoleczna: {a.grunt_ujecie}; komunalna: {b.grunt_ujecie}",
    )
