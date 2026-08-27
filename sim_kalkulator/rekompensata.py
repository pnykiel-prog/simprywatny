"""Koszty netto UOIG, rozsadny zysk i test nadwyzki rekompensaty.

Warunek graniczny: RUOIG <= KN + RZ
  art. 5 ust. 5 i 11 ustawy z 8.12.2006; § 6 ust. 2 rozp. Dz.U. 2025 poz. 1897.

Koszty netto:
    KN = SUM[i=1..n] (KUOIG_i - PUOIG_i) / (1 + rb)^(i-1)
gdzie rb to stopa bazowa KE na dzien zawarcia umowy, a n to ostatni rok okresu
powierzenia.

ASYMETRIA GRUNTU — najlatwiejsze miejsce na blad:
  * grunt, za ktory inwestor zaplacil albo ktory wniosl z wlasnego majatku
                                       -> KOSZT (art. 5 ust. 7 pkt 7 i ust. 8),
                                          w sciezce kredytowej ograniczony do
                                          20% kosztow, gdy wniesiono go aportem
                                          (§ 12 ust. 7 rozp. 766),
  * grunt wniesiony przez gmine        -> PRZYCHOD uslugi publicznej, obniza KN
                                          (art. 5 ust. 9 pkt 4),
  * grunt wydzierzawiony               -> poza podstawa; obciaza koszty biezace
                                          czynszem dzierzawnym.

Ten sam grunt o tej samej wartosci PODNOSI podstawe, gdy pochodzi od inwestora,
i OBNIZA dopuszczalna pomoc, gdy pochodzi od gminy. O tym, ktora regula dziala,
rozstrzyga forma wniesienia — patrz `grunt.py`.
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
from .grunt import rozstrzygnij
from .kredyt import Harmonogram, edb_dla_harmonogramu_lata, edb_grant
from .projekcja import FinansowaniePuli, ProjekcjaPuli
from .waluta import ZERO, bezpieczny_iloraz

JEDEN = Decimal(1)

# Ponizej tej roznicy nierownomiernosc profilu nie jest ustaleniem, tylko szumem
# ostatniej cyfry — patrz `RekompensataPuli.profil_zaostrza_werdykt`.
ISTOTNA_ROZNICA_PROFILU = Decimal("0.0005")


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
class OkresNadwyzki:
    """Stan rozliczenia nadwyzki na koniec roku `rok` — narastajaco od poczatku.

    Nadkompensata jest pytaniem o to, ile pomocy podmiot JUZ dostal wobec tego,
    ile mu sie JUZ nalezalo. Dlatego obie strony sa narastajace, a nie roczne:
    dotacja splywa na poczatku, koszty netto tez sa skoncentrowane na poczatku,
    a przychody czynszowe rozkladaja sie przez caly okres — pojedynczy rok nie
    mowi nic o stanie rozliczenia.
    """

    rok: int
    ruoig_narastajaco: Decimal
    dopuszczalna_narastajaco: Decimal

    @property
    def nadwyzka(self) -> Decimal:
        return max(ZERO, self.ruoig_narastajaco - self.dopuszczalna_narastajaco)

    @property
    def nadwyzka_wzgledna(self) -> Decimal:
        """Nadwyzka odniesiona do rekompensaty otrzymanej do tego roku.

        Ta sama miara co dla calego okresu — nadwyzka do rekompensaty — wiec
        porownuje sie wprost z progiem tolerancji. W ostatnim roku wartosc jest
        rowna wielkosci calookresowej co do grosza; strzeze tego test.
        """
        return bezpieczny_iloraz(self.nadwyzka, self.ruoig_narastajaco)


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
    # Rozklady roczne — potrzebne do profilu nadwyzki (pakiet nr 2, rozdz. 3).
    edb_kredytu_lata: Tuple[Decimal, ...] = ()
    rz_lata: Tuple[Decimal, ...] = ()
    # Zbieg progow (pakiet nr 2, rozdz. 2). `prog_tolerancji_alternatywny` jest
    # ustawiony TYLKO wtedy, gdy pula ma oba instrumenty i istnieje drugi odczyt.
    prog_tolerancji_uzasadnienie: str = ""
    prog_tolerancji_alternatywny: Optional[Decimal] = None

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
    def nadwyzka_roczna(self) -> Decimal:
        """Nadwyzka sprowadzona do jednego roku okresu powierzenia.

        RUOIG i koszty netto liczone sa dla calego okresu powierzenia, wiec
        nadwyzka tez jest wielkoscia wieloletnia. Prog tolerancji odnosi sie do
        SREDNIEJ ROCZNEJ rekompensaty, wiec zeby porownywac wielkosci tego samego
        rzedu, nadwyzka musi zostac zannualizowana. Porownanie sumy z 25 lat
        z progiem opartym na jednym roku zawyzalo wynik dwudziestopieciokrotnie.
        """
        if self.okres_powierzenia_lat <= 0:
            return ZERO
        return self.nadwyzka / Decimal(self.okres_powierzenia_lat)

    @property
    def tolerancja_kwotowo(self) -> Decimal:
        """Prog tolerancji jako procent sredniej rocznej rekompensaty."""
        return self.srednia_roczna_rekompensata * self.prog_tolerancji

    @property
    def nadwyzka_wzgledna(self) -> Decimal:
        """Nadwyzka roczna odniesiona do sredniej rocznej rekompensaty.

        Oba skladniki dotycza jednego roku, wiec iloraz jest porownywalny wprost
        z progiem tolerancji. Rownowaznie: nadwyzka calego okresu odniesiona do
        rekompensaty calego okresu — okres skraca sie po obu stronach.
        """
        return bezpieczny_iloraz(self.nadwyzka_roczna, self.srednia_roczna_rekompensata)

    # ------------------------------------------------------------------
    # Profil nadwyzki w czasie — pakiet naprawczy nr 2, rozdz. 3
    # ------------------------------------------------------------------

    @property
    def profil(self) -> Tuple[OkresNadwyzki, ...]:
        """Stan rozliczenia nadwyzki na koniec kazdego roku okresu powierzenia.

        Annualizacja przez podzielenie nadwyzki przez liczbe lat zakladala
        rozklad rowny. Rzeczywisty przebieg taki nie jest: dotacja splywa
        jednorazowo na poczatku, naklad inwestycyjny wchodzi wedlug wybranego
        ujecia, a przychody czynszowe rozkladaja sie przez caly okres — wiec
        nadwyzka przesuwa sie ku latom pozniejszym albo wczesniejszym zaleznie
        od ujecia nakladu.

        Zadna pozycja nie jest tu rozdzielana zalozeniem, ktorego model wczesniej
        nie mial. EDB kredytu ma rozklad wprost ze wzoru (§ 4 pkt 5 lit. e jest
        suma po okresach), koszty netto sa liczone rok po roku od poczatku,
        rozsadny zysk przy metodzie kapitalowej rowniez. Jedyny wyjatek to RZ
        podany kwota wprost — patrz `rozsadny_zysk_lata`.

        EDB grantu i wsparcie dodatkowe przypisane sa do roku 1: dotacja jest
        wyplacana na etapie inwestycji, a nie rozkladana na okres powierzenia.
        """
        lat = self.okres_powierzenia_lat
        if lat <= 0 or not self.lata:
            # Bez rozkladu rocznego profilu nie da sie zbudowac. Zwracamy pustke,
            # a werdykt spada z powrotem na miare calookresowa — zamiast na
            # rachunek, w ktorym cala rekompensata stoi naprzeciw zera kosztow.
            return ()
        okresy: List[OkresNadwyzki] = []
        ruoig_nar = ZERO
        dopuszczalna_nar = ZERO
        for i in range(1, lat + 1):
            if i == 1:
                ruoig_nar += self.edb_grantu + self.wsparcie_dodatkowe
            if i <= len(self.edb_kredytu_lata):
                ruoig_nar += self.edb_kredytu_lata[i - 1]
            if i <= len(self.lata):
                dopuszczalna_nar += self.lata[i - 1].netto_zdyskontowane
            if i <= len(self.rz_lata):
                dopuszczalna_nar += self.rz_lata[i - 1]
            okresy.append(
                OkresNadwyzki(
                    rok=i,
                    ruoig_narastajaco=ruoig_nar,
                    dopuszczalna_narastajaco=dopuszczalna_nar,
                )
            )
        return tuple(okresy)

    @property
    def okres_najgorszy(self) -> Optional[OkresNadwyzki]:
        """Rok o najwyzszej nadwyzce wzglednej. To on rozstrzyga werdykt."""
        profil = self.profil
        if not profil:
            return None
        return max(profil, key=lambda o: o.nadwyzka_wzgledna)

    @property
    def nadwyzka_wzgledna_najgorsza(self) -> Decimal:
        """Nadwyzka wzgledna w najciasniejszym roku rozliczenia.

        Bez profilu wraca miara calookresowa — nie zero. Zero znaczyloby "brak
        nadwyzki", a to nie to samo co "nie wiadomo, jak sie rozklada".
        """
        najgorszy = self.okres_najgorszy
        if najgorszy is None:
            return self.nadwyzka_wzgledna
        return najgorszy.nadwyzka_wzgledna

    @property
    def profil_zaostrza_werdykt(self) -> bool:
        """Czy najgorszy rok wypada zauwazalnie gorzej niz srednia calookresowa.

        Prawda znaczy, ze nadwyzka nie jest rozlozona rowno i ze rachunek
        usredniony pokazywalby wynik lepszy niz stan faktyczny w najciasniejszym
        momencie rozliczenia.

        Prog istotnosci nie jest kosmetyka. Ostatni punkt profilu jest z definicji
        rowny miary calookresowej, wiec przy rownym rozkladzie roznica wychodzi
        zerowa co do arytmetyki dziesietnej, ale nie co do ostatniej cyfry
        `Decimal`. Bez progu kazdy wariant dostawalby ostrzezenie o nierownym
        rozkladzie — takze ten, w ktorym rozklad jest rowny.
        """
        return (
            self.nadwyzka_wzgledna_najgorsza - self.nadwyzka_wzgledna
            > ISTOTNA_ROZNICA_PROFILU
        )

    @property
    def przechodzi(self) -> bool:
        """Werdykt na NAJGORSZYM okresie rozliczenia, nie na sredniej.

        Ostatni punkt profilu jest rowny wielkosci calookresowej, wiec ta miara
        nigdy nie jest lagodniejsza od poprzedniej — moze byc tylko ostrzejsza.
        """
        return self.nadwyzka_wzgledna_najgorsza <= self.prog_tolerancji

    @property
    def przechodzi_przy_alternatywnym_progu(self) -> Optional[bool]:
        """Werdykt przy drugim odczycie zbiegu progow. None, gdy zbiegu nie ma."""
        if self.prog_tolerancji_alternatywny is None:
            return None
        return self.nadwyzka_wzgledna_najgorsza <= self.prog_tolerancji_alternatywny

    @property
    def werdykt_zalezy_od_zalozenia(self) -> bool:
        """Czy o wyniku przesadza samo zalozenie o progu, a nie dane."""
        alternatywny = self.przechodzi_przy_alternatywnym_progu
        return alternatywny is not None and alternatywny != self.przechodzi

    @property
    def kwota_do_zwrotu(self) -> Decimal:
        """Kwota podlegajaca zwrotowi do Funduszu Doplat.

        Przekroczenie progu tolerancji uruchamia zwrot calej nadwyzki, a nie tylko
        czesci ponad prog — prog jest granica dopuszczalnosci, nie kwota wolna.
        Zwrotowi podlega nadwyzka CALEGO okresu, nie jej roczna czesc; annualizacja
        sluzy wylacznie porownaniu z progiem.
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
    """Kanal C — zwraca (grunt_jako_koszt, grunt_jako_przychod, opis).

    Kanaly B i C nie moga zadzialac naraz. Grunt, ktorego inwestor nie kupil,
    nie jest kosztem swiadczenia uslugi; grunt, ktory kupil, nie jest jego
    przychodem. Gdyby ta sama wartosc weszla po obu stronach, wynik netto bylby
    zerowy i asymetria z art. 5 ust. 9 pkt 4 — dla ktorej ten modul istnieje —
    zniknelaby z rachunku.

    Wartosc gruntu w kosztach jest juz po limicie z § 12 ust. 7 rozp. 766, bo
    limit dziala na podstawe kosztowa i nakladany jest w `alokacja.build`.
    Przychod z art. 5 ust. 9 pkt 4 zadnego limitu nie ma — mowa w nim o wartosci
    nieruchomosci wniesionej, a nie o kwocie zaliczonej do kosztow.
    """
    u = rozstrzygnij(w)

    if u.przychod_uoig:
        wartosc = u.wartosc_operatu * pula.udzial_pum
        if wartosc <= ZERO:
            return ZERO, ZERO, "brak pozycji gruntowej"
        return (
            ZERO,
            wartosc,
            f"grunt od gminy w formie '{u.forma.value}': przychod uslugi publicznej, "
            "obniza KN (art. 5 ust. 9 pkt 4)",
        )

    wartosc = pula.grunt
    if wartosc <= ZERO:
        if u.oplata_roczna > ZERO:
            return (
                ZERO,
                ZERO,
                f"forma '{u.forma.value}': wartosc gruntu poza kosztami, "
                "oplata roczna obciaza koszty biezace",
            )
        return ZERO, ZERO, "brak pozycji gruntowej"

    if sciezka_kredytowa and u.limit_aportowy_dotyczy:
        opis = (
            f"sciezka kredytowa, grunt z aportu: koszt do "
            f"{prawo.GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT:.0%} kosztow przedsiewziecia "
            f"(§ 12 ust. 7 rozp. 766)"
        )
        if pula.grunt_obciety_limitem > ZERO:
            opis += f" — obcieto {pula.grunt_obciety_limitem:.2f} zl"
        return wartosc, ZERO, opis

    # art. 5 ust. 7 pkt 7 i ust. 8 — grunt inwestora jest kosztem, bez limitu.
    return (
        wartosc,
        ZERO,
        f"forma '{u.forma.value}': koszt bez limitu procentowego "
        "(art. 5 ust. 7 pkt 7 i ust. 8)",
    )


# ---------------------------------------------------------------------------
# Rozsadny zysk
# ---------------------------------------------------------------------------

def rozsadny_zysk_lata(
    w: Wejscie, fin: FinansowaniePuli, lat: int, udzial_pum: Decimal
) -> Tuple[Decimal, ...]:
    """Rozsadny zysk (RZ) rozlozony na lata okresu powierzenia.

    Specyfikacja wskazuje zrodlo stopy — IRS dla kontraktu 20-letniego na bazie
    WIBOR 3M, publikowany przez BGK w BIP przed naborem (§ 6 ust. 5 rozp. 1897;
    § 12 ust. 10 rozp. 766) — ale nie podaje wzoru. Metoda jest przelacznikiem
    z jawnym oznaczeniem zalozenia; patrz LUKI.md.

    Przy metodzie KWOTA_WPROST uzytkownik podaje jedna liczbe dla calego okresu.
    Rozklad rowny jest wtedy DODATKOWYM zalozeniem — kwota wprost nie ma wlasnego
    profilu czasowego. Przy metodzie kapitalowej rozklad wynika wprost ze wzoru.
    """
    if lat <= 0:
        return ()
    if w.przelaczniki.metoda_rozsadnego_zysku is MetodaRozsadnegoZysku.KWOTA_WPROST:
        kwota = (w.rekompensata.rozsadny_zysk_kwota or ZERO) * udzial_pum
        rata = kwota / Decimal(lat)
        return tuple(rata for _ in range(lat))

    # ZALOZENIE: godziwy zwrot ze srodkow wlasnych zaangazowanych w przedsiewziecie,
    # naliczany stopa IRS BGK rocznie i dyskontowany stopa bazowa KE — tak samo
    # jak strumien kosztow netto, zeby obie strony nierownosci byly porownywalne.
    kapital = max(ZERO, fin.kapital_inwestora)
    rb = w.parametry_zewnetrzne.stopa_bazowa_ke
    return tuple(
        kapital * w.parametry_zewnetrzne.stopa_irs_bgk / (JEDEN + rb) ** (rok - 1)
        for rok in range(1, lat + 1)
    )


def rozsadny_zysk(
    w: Wejscie, fin: FinansowaniePuli, lat: int, udzial_pum: Decimal
) -> Decimal:
    """Rozsadny zysk (RZ) dla calego okresu — suma rozkladu rocznego."""
    return sum(rozsadny_zysk_lata(w, fin, lat, udzial_pum), ZERO)


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


def _prog_tolerancji(
    w: Wejscie, sciezka: str, edb_grantu: Decimal, edb_kredytu: Decimal
) -> Tuple[Decimal, str, Optional[Decimal]]:
    """Rozstrzyga prog tolerancji. Zwraca (prog, uzasadnienie, prog alternatywny).

    Pakiet naprawczy nr 2, rozdz. 2. Dopoki pula ma jeden instrument, odczyt jest
    jednoznaczny i prog alternatywny nie istnieje. Gdy ma oba — dotacje i kredyt —
    zaden przepis nie mowi, ktory rezim wiaze, wiec rozstrzyga przelacznik,
    a drugi mozliwy odczyt wraca razem z wynikiem, zeby bylo widac, ile zalezy
    od samego zalozenia.
    """
    if edb_grantu <= ZERO or edb_kredytu <= ZERO:
        return prawo.prog_tolerancji_nadwyzki(sciezka), "", None
    regula = w.przelaczniki.prog_tolerancji_przy_dwoch_instrumentach.value
    prog, uzasadnienie = prawo.prog_tolerancji_dwa_instrumenty(
        regula, edb_grantu, edb_kredytu
    )
    mozliwe = {
        prawo.prog_tolerancji_dwa_instrumenty(r, edb_grantu, edb_kredytu)[0]
        for r in prawo.REGULY_PROGU
    }
    inne = sorted(mozliwe - {prog})
    return prog, uzasadnienie, (inne[0] if inne else None)


def _rekompensata_puli(
    w: Wejscie,
    pula: PulaKosztow,
    proj: ProjekcjaPuli,
    fin: FinansowaniePuli,
    h: Optional[Harmonogram],
    edb_kredytu: Decimal,
    wsparcie_dodatkowe: Decimal,
    edb_kredytu_lata: Tuple[Decimal, ...] = (),
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
        # Oplata roczna za grunt (dzierzawa, uzytkowanie wieczyste) siedzi
        # w kosztach operacyjnych projekcji i musi trafic tu razem z reszta —
        # jest kosztem swiadczenia uslugi przez caly okres powierzenia.
        koszty_biezace = rok_proj.koszty_operacyjne
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
    rz_lata = rozsadny_zysk_lata(w, fin, lat, pula.udzial_pum)
    edb_grantu = edb_grant(fin.grant)
    prog, uzasadnienie, prog_alternatywny = _prog_tolerancji(
        w, proj.sciezka, edb_grantu, edb_kredytu
    )

    return RekompensataPuli(
        nazwa=pula.nazwa,
        sciezka=proj.sciezka,
        okres_powierzenia_lat=lat,
        lata=tuple(lata),
        kn=kn,
        rz=sum(rz_lata, ZERO),
        edb_grantu=edb_grantu,
        edb_kredytu=edb_kredytu,
        wsparcie_dodatkowe=wsparcie_dodatkowe,
        prog_tolerancji=prog,
        grunt_ujecie=opis_gruntu,
        edb_kredytu_lata=edb_kredytu_lata,
        rz_lata=rz_lata,
        prog_tolerancji_uzasadnienie=uzasadnienie,
        prog_tolerancji_alternatywny=prog_alternatywny,
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
                    "Do limitu pomocy publicznej wlicza się także wsparcie z Rządowego Funduszu "
                    "i wartość dokumentacji projektowej z zasobu Banku. Nie są darmowe w sensie limitu."
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
            edb_kredytu_lata=(
                edb_dla_harmonogramu_lata(
                    fin.harmonogram_kredytu, w.parametry_zewnetrzne
                )
                if proj.spoleczna.sciezka == "kredyt"
                else ()
            ),
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
        laczna = _scal(w, spoleczna, komunalna)
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
                    "Limit pomocy publicznej liczony jest raz, łącznie dla obu pul. Przy odczycie "
                    "domyślnym były to dwa osobne rachunki o różnych progach."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    for pula in _badane(spoleczna, komunalna, laczna):
        if pula.prog_tolerancji_alternatywny is None:
            continue
        alternatywny = pula.przechodzi_przy_alternatywnym_progu
        zalezy = pula.werdykt_zalezy_od_zalozenia
        rozstrzygniecie = (
            "PRZY DRUGIM ODCZYCIE WYNIK JEST ODWROTNY: "
            + ("test przechodzi" if alternatywny else "test nie przechodzi")
            + ". O werdykcie przesadza samo zalozenie, nie dane."
            if zalezy
            else "Przy drugim odczycie werdykt jest taki sam, wiec zalozenie nie wazy."
        )
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY",
                tresc=(
                    f"Pula {pula.nazwa} laczy dotacje z kredytem, a kazdy z instrumentow ma "
                    f"wlasny prog tolerancji nadwyzki: {prawo.PROG_TOLERANCJI_NADWYZKI_GRANT:.0%} "
                    f"(§ 7 ust. 9 rozp. 1897) i {prawo.PROG_TOLERANCJI_NADWYZKI_KREDYT:.0%} "
                    f"(§ 13 ust. 8 rozp. 766). Zaden przepis nie rozstrzyga zbiegu. Przyjeto "
                    f"{pula.prog_tolerancji:.0%} — {pula.prog_tolerancji_uzasadnienie}. "
                    f"Odczyt alternatywny daje {pula.prog_tolerancji_alternatywny:.0%}. "
                    f"{rozstrzygniecie}"
                ),
                podstawa=(
                    "§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 "
                    "poz. 766 — zbieg nierozstrzygniety, pakiet naprawczy nr 2 rozdz. 2"
                ),
                tresc_potoczna=(
                    f"Ta pula korzysta z dotacji i z kredytu naraz, a przepisy podają dla nich "
                    f"różne limity nadwyżki pomocy: {prawo.PROG_TOLERANCJI_NADWYZKI_GRANT:.0%} "
                    f"i {prawo.PROG_TOLERANCJI_NADWYZKI_KREDYT:.0%}. Przyjęto ostrożniejszy "
                    f"({pula.prog_tolerancji:.0%})."
                    + (
                        " Przy drugim odczycie wynik testu jest odwrotny — to założenie, a nie "
                        "liczby, przesądza o odpowiedzi."
                        if zalezy else ""
                    )
                ),
                waga=Waga.ZMIENIA_WERDYKT if zalezy else Waga.ZMIENIA_KWOTE,
            )
        )

    for pula in _badane(spoleczna, komunalna, laczna):
        if pula.nadwyzka <= ZERO or not pula.profil_zaostrza_werdykt:
            continue
        najgorszy = pula.okres_najgorszy
        ostrzezenia.append(
            Ostrzezenie(
                kod="NADWYZKA_ROZLOZONA_NIEROWNO",
                tresc=(
                    f"Nadwyzka puli {pula.nazwa} nie rozklada sie rowno w okresie powierzenia. "
                    f"Usredniona wynosi {pula.nadwyzka_wzgledna:.1%} rekompensaty, ale w roku "
                    f"{najgorszy.rok} stan rozliczenia narastajaco daje "
                    f"{najgorszy.nadwyzka_wzgledna:.1%}. Werdykt oparty jest na roku najgorszym, "
                    f"bo prog {pula.prog_tolerancji:.0%} obowiazuje w kazdym rozliczeniu, "
                    "a nie tylko na koniec okresu."
                ),
                podstawa="§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766",
                tresc_potoczna=(
                    f"Nadwyżka pomocy nie rozkłada się równo: średnio {pula.nadwyzka_wzgledna:.1%}, "
                    f"ale w roku {najgorszy.rok} narastająco {najgorszy.nadwyzka_wzgledna:.1%}. "
                    "Liczy się rok najgorszy."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    for pula in _badane(spoleczna, komunalna, laczna):
        if pula.nadwyzka <= ZERO:
            continue
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI",
                tresc=(
                    f"Nadwyzka puli {pula.nazwa} ({pula.nadwyzka:.2f} zl) badana jest w ujeciu "
                    f"narastajacym, rok po roku przez caly {pula.okres_powierzenia_lat}-letni "
                    f"okres powierzenia, i porownywana z progiem {pula.prog_tolerancji:.0%} "
                    "rekompensaty otrzymanej do danego roku. Przepis odnosi prog do okresu "
                    "rozliczeniowego, a model nie zna jego dlugosci — profil roczny jest "
                    "najblizszym przyblizeniem, jakie da sie zbudowac bez tej danej."
                ),
                podstawa="§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897; § 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766",
                tresc_potoczna=(
                    "Nadwyżka liczona jest narastająco, rok po roku. Bank rozlicza ją w okresach "
                    "wskazanych w umowie — jeżeli będą inne, wynik może się przesunąć."
                ),
                waga=Waga.ZMIENIA_KWOTE,
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
                    "Według modelu inwestycja zarabia więcej, niż kosztuje utrzymanie usługi. Każda "
                    "złotówka dotacji jest wtedy nadwyżką — sprawdź czynsz i sposób rozliczenia nakładu."
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


def _badane(spoleczna, komunalna, laczna) -> Tuple[RekompensataPuli, ...]:
    """Pule faktycznie badane — przy hybrydzie jako jednym przedsiewzieciu jedna.

    Ostrzezenia musza dotyczyc tego samego rachunku, ktory daje werdykt. Gdyby
    szly po pulach skladowych mimo scalenia, opisywalyby progi i nadwyzki,
    ktorych wynik nie uzywa.
    """
    if laczna is not None:
        return (laczna,)
    return tuple(p for p in (spoleczna, komunalna) if p is not None)


def _scal(w: Wejscie, a: RekompensataPuli, b: RekompensataPuli) -> RekompensataPuli:
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
    edb_grantu = a.edb_grantu + b.edb_grantu
    edb_kredytu = a.edb_kredytu + b.edb_kredytu
    prog, uzasadnienie, prog_alternatywny = _prog_tolerancji(
        w, sciezka, edb_grantu, edb_kredytu
    )
    return RekompensataPuli(
        nazwa="laczna",
        sciezka=sciezka,
        okres_powierzenia_lat=lat,
        lata=tuple(lata),
        kn=a.kn + b.kn,
        rz=a.rz + b.rz,
        edb_grantu=edb_grantu,
        edb_kredytu=edb_kredytu,
        wsparcie_dodatkowe=a.wsparcie_dodatkowe + b.wsparcie_dodatkowe,
        prog_tolerancji=prog,
        grunt_ujecie=f"spoleczna: {a.grunt_ujecie}; komunalna: {b.grunt_ujecie}",
        edb_kredytu_lata=_zsumuj_lata(a.edb_kredytu_lata, b.edb_kredytu_lata, lat),
        rz_lata=_zsumuj_lata(a.rz_lata, b.rz_lata, lat),
        prog_tolerancji_uzasadnienie=uzasadnienie,
        prog_tolerancji_alternatywny=prog_alternatywny,
    )


def _zsumuj_lata(
    a: Tuple[Decimal, ...], b: Tuple[Decimal, ...], lat: int
) -> Tuple[Decimal, ...]:
    """Suma dwoch szeregow rocznych, dopelniona zerami do dlugosci `lat`."""
    return tuple(
        (a[i] if i < len(a) else ZERO) + (b[i] if i < len(b) else ZERO)
        for i in range(lat)
    )
