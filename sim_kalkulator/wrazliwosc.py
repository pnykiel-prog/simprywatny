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
    # Wymagany wklad GOTOWKOWY w tym punkcie — os pionowa wykresu negocjacyjnego.
    # Ta sama wielkosc, ktora pokazuje kaskada i test kapitalowy: pieniadze, ktore
    # inwestor musi wylozyc. Grunt wniesiony rzeczowo domyka koszty, nie wymagajac
    # zlotowki, wiec do tej liczby nie wchodzi.
    wklad_wymagany: Optional[Decimal] = None
    # Czynsz spoleczny domykajacy montaz bez wkladu wlasnego przy tym udziale.
    # Errata nr 1, rozdz. 5.2: wzrost udzialu puli komunalnej wypycha go w gore,
    # bo pula komunalna wnosi mniej — nizszy limit czynszu, brak kredytu, brak
    # partycypacji — a ciezar przenosi sie na kurczaca sie pule spoleczna.
    czynsz_domykajacy: Optional[Decimal] = None
    # Czy przy tym udziale wymagany czynsz spoleczny miesci sie pod stawka rynkowa.
    # None, gdy stawki rynkowej nie podano — wtedy tego sufitu po prostu nie ma.
    miesci_sie_w_rynku: Optional[bool] = None
    # Czesc wymaganego wkladu, ktorej zaden czynsz nie domknie — pula komunalna
    # nie ma kredytu (art. 5a ust. 3), a tylko kredyt zamienia przyszly czynsz
    # na kapital poczatkowy. Pakiet nr 2, rozdz. 5: to jest most miedzy wykresem
    # czynszowym a negocjacyjnym, bo wielkosc plateau rosnie z udzialem gminy.
    wklad_poza_zasiegiem_czynszu: Optional[Decimal] = None
    powod_niepoliczalnosci: str = ""

    @property
    def wklad_do_domkniecia_czynszem(self) -> Optional[Decimal]:
        """Czesc wkladu, ktora da sie zdjac podnoszac czynsz. Reszta zostaje."""
        if self.wklad_wymagany is None or self.wklad_poza_zasiegiem_czynszu is None:
            return None
        return max(ZERO, self.wklad_wymagany - self.wklad_poza_zasiegiem_czynszu)

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
    def punkt_graniczny_rynkowy(self) -> Optional[Decimal]:
        """Pierwszy udzial, przy ktorym wymagany czynsz spoleczny przebija rynek.

        Errata nr 1, rozdz. 5.2. Bywa wczesniejszy niz punkt kapitalowy i jest
        calkowicie niewidoczny, jesli sledzi sie wylacznie limity ustawowe.
        None, gdy stawki rynkowej nie podano albo gdy rynek udzwiga caly zakres —
        drugiego punktu wtedy po prostu nie ma.
        """
        przebijajace = [
            p.udzial
            for p in self.punkty
            if p.policzalny and p.miesci_sie_w_rynku is False
        ]
        return min(przebijajace) if przebijajace else None

    @property
    def punkt_graniczny_wiazacy(self) -> Optional[Decimal]:
        """Wczesniejszy z dwoch punktow granicznych — ten, ktory faktycznie wiaze."""
        punkty = [p for p in (self.punkt_graniczny, self.punkt_graniczny_rynkowy) if p is not None]
        return min(punkty) if punkty else None

    @property
    def rodzaj_punktu_wiazacego(self) -> str:
        """'rynkowy', 'kapitalowy' albo '' — czym konczy sie zakres."""
        wiazacy = self.punkt_graniczny_wiazacy
        if wiazacy is None:
            return ""
        if self.punkt_graniczny_rynkowy is not None and wiazacy == self.punkt_graniczny_rynkowy:
            return "rynkowy"
        return "kapitalowy"

    @property
    def blokada_niezalezna_od_osi(self) -> Optional[int]:
        """Numer testu, ktory nie przechodzi w ZADNYM punkcie sweepu.

        Gdy montaz nie domyka sie na calej osi, samo tlo wykresu niczego nie
        wyjasnia — a przyczyna moze lezec zupelnie gdzie indziej niz proporcja
        mieszkan. Test oblany niezaleznie od udzialu pul znaczy, ze przesuwanie
        tego pokretla nic nie da i trzeba szukac dzwigni poza osia.
        """
        policzalne = [p for p in self.punkty if p.policzalny]
        if not policzalne or self.punkty_domykajace:
            return None
        for numer in (1, 2, 3):
            if all(not p.werdykty[numer - 1] for p in policzalne):
                return numer
        return None

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
    # Test rynkowy — sufit faktyczny. Gdy stawki nie podano, punktu granicznego
    # rynkowego po prostu nie ma; narzedzie go nie wymysla.
    domykajacy = wynik.czynsz_domykajacy_m2_mies
    rynkowy = w.rynek.czynsz_rynkowy_m2_mies
    if rynkowy is None or domykajacy is None:
        # Brak stawki rynkowej — sufitu nie ma, wiec nie ma czego testowac.
        # Brak stawki domykajacej — montazu nie domyka ZADNA stawka, bo kredyt
        # przebija ustawowy pulap. To ograniczenie kapitalowe, nie rynkowe;
        # przypisanie go rynkowi falszowaloby odpowiedz na pytanie, ktory sufit
        # wiaze, a od tego zalezy, czy da sie cokolwiek z tym zrobic.
        miesci = None
    else:
        miesci = domykajacy <= rynkowy
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
        wklad_wymagany=max(ZERO, wynik.finansowanie.wklad_gotowkowy_wymagany),
        czynsz_domykajacy=domykajacy,
        miesci_sie_w_rynku=miesci,
        wklad_poza_zasiegiem_czynszu=min(
            max(ZERO, wynik.finansowanie.wklad_gotowkowy_wymagany),
            wynik.luka_poza_zasiegiem_czynszu,
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

# Zakres poszukiwania punktu przelamania — wartosci parametru, przy ktorej
# montaz w ogole zaczyna sie domykac. Mnozniki badane od najblizszego wartosci
# bazowej, zeby pierwszy trafiony byl zarazem najtanszy.
PRZELAMANIE_ZASIEG = Decimal("0.60")
PRZELAMANIE_KROK = Decimal("0.10")


def _mnozniki_przelamania(zasieg: Decimal, krok: Decimal) -> List[Decimal]:
    """Mnozniki od 1-zasieg do 1+zasieg, uporzadkowane wg odleglosci od 1."""
    kandydaci: List[Decimal] = []
    odchylenie = krok
    while odchylenie <= zasieg + Decimal("1e-9"):
        kandydaci.append(Decimal(1) - odchylenie)
        kandydaci.append(Decimal(1) + odchylenie)
        odchylenie += krok
    return [m for m in kandydaci if m > 0]


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
    # Punkt przelamania — wypelniany tylko wtedy, gdy wariant bazowy nie domyka
    # sie przy zadnym udziale pul. Odpowiada na wymog rozdz. 7.1 specyfikacji:
    # przy jakiej wartosci parametru montaz zaczalby przechodzic.
    przelamanie_wartosc: Optional[Decimal] = None
    przelamanie_zmiana: Optional[Decimal] = None      # wzglednie, np. -0.30
    przelamanie_maks_udzial: Optional[Decimal] = None
    przelamanie_zbadane: bool = False

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
    def przelamuje(self) -> bool:
        """Czy parametr potrafi ruszyc montaz z martwego punktu."""
        return self.przelamanie_wartosc is not None

    @property
    def opis_dzwigni(self) -> str:
        """Jednozdaniowa odpowiedz: co ten parametr daje.

        Rozroznia dwie sytuacje. Gdy wariant bazowy sie domyka — o ile parametr
        przesuwa granice. Gdy nie domyka sie wcale — przy jakiej wartosci
        zaczalby (rozdz. 7.1 specyfikacji).
        """
        if self.maks_udzial_bazowo is not None:
            return self.kierunek_korzystny
        if not self.przelamanie_zbadane:
            return "nie badano"
        if self.przelamanie_wartosc is None:
            return (
                f"nie przelamuje w zakresie +/-{PRZELAMANIE_ZASIEG:.0%} wartosci bazowej"
            )
        return (
            f"montaz zaczyna sie domykac przy {self.przelamanie_zmiana:+.0%} "
            f"(wartosc {self.przelamanie_wartosc:,.4f}".replace(",", " ")
            + f"), do {self.przelamanie_maks_udzial:.0%} udzialu komunalnego"
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
        # Brak punktu bazowego: miara staje sie "ile pola parametr w ogole otwiera".
        kandydaci = [u for u in (self.maks_udzial_dol, self.maks_udzial_gora) if u is not None]
        if kandydaci:
            return max(kandydaci)
        return self.przelamanie_maks_udzial or ZERO

    @property
    def koszt_przelamania(self) -> Decimal:
        """Jak duzej zmiany parametru trzeba, zeby montaz ruszyl. Mniej znaczy taniej."""
        if self.przelamanie_zmiana is None:
            return Decimal("999")
        return abs(self.przelamanie_zmiana)


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

        # Rozdz. 7.1: gdy montaz nie domyka sie przy zadnym udziale, sam ranking
        # przesuniec nie niesie informacji — trzeba wskazac, przy jakiej wartosci
        # parametru zaczalby przechodzic.
        przelamanie = (None, None, None)
        if bazowy_maks is None:
            przelamanie = _szukaj_przelamania(w, podmien, bazowa, krok)

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
                przelamanie_wartosc=przelamanie[0],
                przelamanie_zmiana=przelamanie[1],
                przelamanie_maks_udzial=przelamanie[2],
                przelamanie_zbadane=bazowy_maks is None,
            )
        )
    return tuple(wyniki)


def _szukaj_przelamania(
    w: Wejscie,
    podmien: Callable[[Wejscie, Decimal], Wejscie],
    bazowa: Decimal,
    krok: Decimal,
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """Najblizsza wartosc parametru, przy ktorej montaz zaczyna sie domykac.

    Zwraca (wartosc bezwzgledna, zmiana wzgledna, osiagalny udzial komunalny).
    Mnozniki badane od najblizszego wartosci bazowej, wiec pierwszy trafiony
    jest zarazem najtanszy. Wartosci odrzucone przez walidacje sa pomijane —
    nie sa alternatywa, tylko konfiguracja bezprawna.
    """
    if bazowa == ZERO:
        return (None, None, None)

    for mnoznik in _mnozniki_przelamania(PRZELAMANIE_ZASIEG, PRZELAMANIE_KROK):
        wartosc = bazowa * mnoznik
        try:
            sweep = sweep_udzialu(podmien(w, wartosc), krok)
        except Exception:  # noqa: BLE001 — wartosc niedopuszczalna, probujemy dalej
            continue
        osiagalny = sweep.maksymalny_udzial_komunalny
        if osiagalny is not None:
            return (wartosc, mnoznik - Decimal(1), osiagalny)
    return (None, None, None)


def ranking(wyniki: Sequence[WynikWrazliwosci]) -> Tuple[WynikWrazliwosci, ...]:
    """Parametry uporzadkowane wg sily wplywu — ktory najtaniej rusza montaz.

    Porzadek zalezy od sytuacji. Gdy wariant bazowy sie domyka, liczy sie to,
    o ile parametr przesuwa punkt graniczny. Gdy nie domyka sie wcale, liczy sie
    to, jak malej zmiany trzeba, zeby w ogole ruszyl — wtedy mniejszy koszt
    przelamania jest lepszy.
    """
    if not wyniki:
        return ()
    bazowy_domyka = any(r.maks_udzial_bazowo is not None for r in wyniki)
    if bazowy_domyka:
        return tuple(
            sorted(wyniki, key=lambda r: (r.sila_wplywu, r.zmienia_werdykt), reverse=True)
        )
    return tuple(
        sorted(wyniki, key=lambda r: (r.koszt_przelamania, -r.sila_wplywu))
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
        niezalezny = self.sweep.blokada_niezalezna_od_osi
        if niezalezny is not None:
            return (
                f"Montaz nie domyka sie przy zadnym udziale puli komunalnej, bo test "
                f"{niezalezny} nie przechodzi w calym zakresie. Proporcja mieszkan nie "
                "jest tu dzwignia — przyczyna lezy poza ta osia."
            )
        return (
            f"Montaz nie domyka sie przy zadnym udziale puli komunalnej. "
            f"Blokuje test {blokujacy}."
        )


def build(w: Wejscie, krok: Decimal = KROK_SWEEPU) -> Analiza:
    return Analiza(
        sweep=sweep_udzialu(w, krok),
        wrazliwosc=wrazliwosc_jednoparametrowa(w, krok=krok),
    )
