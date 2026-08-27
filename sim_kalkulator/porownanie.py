"""Porownanie form wniesienia gruntu i wnioski, ktore narzedzie ma wyciagnac samo.

Rozdz. 4 uzupelnienia nr 2. Roznice miedzy formami sa duze i nieoczywiste —
dzierzawa wyglada na najtansze wejscie, a jest najdrozszym; aport gminy wyglada
na prezent, a kosztuje dwa razy. Zeby to pokazac, nie wystarczy opis: trzeba
przeliczyc caly model dla kazdej dopuszczalnej formy przy niezmienionych
pozostalych parametrach i zestawic wyniki.

Kwoty w komunikatach sa liczone rzeczywiscie, nie ilustracyjnie. Wariant, ktorego
nie da sie policzyc — bo brakuje danych albo odpada z mocy przepisu — wraca
z powodem, nigdy z podstawiona liczba.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from . import prawo
from .dane import BladWalidacji, FormaGruntu, Wejscie
from .waluta import ZERO


@dataclass(frozen=True)
class WariantGruntu:
    """Jedna forma wniesienia, przeliczona w calosci albo odrzucona z powodem."""

    forma: str
    etykieta: str
    podpis: str
    wybrany: bool
    policzalny: bool
    powod: str = ""
    wklad_gotowkowy: Decimal = ZERO
    grant_laczny: Decimal = ZERO
    grant_utracony: Decimal = ZERO
    dopuszczalna_pomoc: Decimal = ZERO
    pum_przychodowe: Decimal = ZERO
    oplata_roczna: Decimal = ZERO
    domyka_sie: bool = False
    gmina_wspolnikiem: bool = False
    udzial_gminy_w_spolce: Optional[Decimal] = None
    pasmo_45: bool = True


@dataclass(frozen=True)
class Wniosek:
    """Zdanie, ktore narzedzie formuluje samo, z kwotami z rzeczywistego przeliczenia."""

    kod: str
    tresc: str
    forma_polecana: str = ""
    kwota: Decimal = ZERO


@dataclass(frozen=True)
class PorownanieForm:
    warianty: Tuple[WariantGruntu, ...]
    wnioski: Tuple[Wniosek, ...]

    @property
    def policzalne(self) -> Tuple[WariantGruntu, ...]:
        return tuple(w for w in self.warianty if w.policzalny)

    @property
    def wybrany(self) -> Optional[WariantGruntu]:
        for w in self.warianty:
            if w.wybrany:
                return w
        return None

    def wedlug_wkladu(self) -> Tuple[WariantGruntu, ...]:
        """Warianty policzalne od najtanszego kapitalowo — kolejnosc slupkow."""
        return tuple(sorted(self.policzalne, key=lambda w: w.wklad_gotowkowy))

    def wariant(self, forma: str) -> Optional[WariantGruntu]:
        for w in self.warianty:
            if w.forma == forma:
                return w
        return None


def _zl(kwota: Decimal) -> str:
    """Kwota po polsku, zaokraglona do pelnych zlotych, ze spacja nierozdzielajaca."""
    return f"{kwota:,.0f} zł".replace(",", " ")


def _mln(kwota: Decimal) -> str:
    """Kwota w milionach, gdy jest duza — tak, jak brzmi w rozmowie."""
    if abs(kwota) >= 1_000_000:
        return f"{kwota / Decimal(1_000_000):.1f} mln zł".replace(".", ",")
    return _zl(kwota)


def _przelicz(w: Wejscie, forma: FormaGruntu):
    """Przeliczenie wariantu. Zwraca (wynik, powod) — dokladnie jedno jest puste."""
    from .silnik import przelicz

    try:
        wariant = w.z_forma_gruntu(forma)
    except BladWalidacji as blad:
        return None, str(blad)
    try:
        return przelicz(wariant), ""
    except BladWalidacji as blad:
        return None, str(blad)


def buduj(w: Wejscie) -> PorownanieForm:
    """Przelicza wszystkie formy dopuszczalne dla pochodzenia dzialki.

    Zestaw form bierze sie z pochodzenia, bo tylko one sa realna alternatywa:
    dzialki gminnej nie da sie wniesc aportem inwestora, a wlasnej — kupic od gminy.
    """
    warianty: List[WariantGruntu] = []
    wyniki: Dict[str, object] = {}

    for nazwa in prawo.formy_dla_pochodzenia(w.grunt.pochodzenie.value):
        forma = FormaGruntu(nazwa)
        skutki = forma.skutki
        wybrany = forma is w.grunt.forma
        wynik, powod = _przelicz(w, forma)
        if wynik is None:
            warianty.append(
                WariantGruntu(
                    forma=nazwa,
                    etykieta=skutki.etykieta,
                    podpis=skutki.podpis,
                    wybrany=wybrany,
                    policzalny=False,
                    powod=powod,
                    gmina_wspolnikiem=skutki.gmina_wspolnikiem,
                    pasmo_45=skutki.pasmo_45,
                )
            )
            continue

        wyniki[nazwa] = wynik
        warianty.append(
            WariantGruntu(
                forma=nazwa,
                etykieta=skutki.etykieta,
                podpis=skutki.podpis,
                wybrany=wybrany,
                policzalny=True,
                wklad_gotowkowy=wynik.finansowanie.wklad_gotowkowy_wymagany,
                grant_laczny=wynik.finansowanie.grant_laczny,
                grant_utracony=wynik.granty.spoleczna.grant_utracony,
                dopuszczalna_pomoc=_dopuszczalna(wynik),
                pum_przychodowe=wynik.alokacja.pum_przychodowe_laczne,
                oplata_roczna=wynik.grunt.oplata_roczna,
                domyka_sie=wynik.domyka_sie,
                gmina_wspolnikiem=wynik.grunt.gmina_wspolnikiem,
                udzial_gminy_w_spolce=wynik.finansowanie.udzial_gminy_w_spolce,
                pasmo_45=wynik.granty.spoleczna.pasmo_45,
            )
        )

    return PorownanieForm(
        warianty=tuple(warianty),
        wnioski=tuple(_wnioski(w, warianty, wyniki)),
    )


def _dopuszczalna(wynik) -> Decimal:
    """Laczna dopuszczalna rekompensata obu badanych pul — KN + RZ."""
    return sum((p.dopuszczalna for p in wynik.rekompensata.badane), ZERO)


# ---------------------------------------------------------------------------
# Wnioski, ktore narzedzie formuluje samo
# ---------------------------------------------------------------------------

def _wnioski(w: Wejscie, warianty: List[WariantGruntu], wyniki: Dict[str, object]) -> List[Wniosek]:
    lista: List[Wniosek] = []
    wybrana = w.grunt.forma.value
    indeks = {wariant.forma: wariant for wariant in warianty}

    lista.extend(_wniosek_dzierzawa(wybrana, indeks))
    lista.extend(_wniosek_aport_gminy(wybrana, indeks, wyniki))
    lista.extend(_wniosek_najtanszy(wybrana, indeks))
    return lista


def _wniosek_dzierzawa(wybrana: str, indeks: Dict[str, WariantGruntu]) -> List[Wniosek]:
    """Rozdz. 4.1 — dzierzawa jest pulapka kosztowa.

    Wyglada na najtansze wejscie, bo nie ma wydatku kapitalowego. W rzeczywistosci
    scina dotacje z limitu podstawowego do progu gruntowego, a roznica jest wieksza
    niz oszczednosc na cenie dzialki przy kazdym rozsadnym czynszu dzierzawnym.
    """
    dzierzawa = indeks.get("dzierzawa")
    nabycie = indeks.get("nabycie_od_gminy")
    if dzierzawa is None or not dzierzawa.wybrany or not dzierzawa.policzalny:
        return []
    if nabycie is None or not nabycie.policzalny:
        return []

    roznica_dotacji = nabycie.grant_laczny - dzierzawa.grant_laczny
    if roznica_dotacji <= ZERO:
        return []

    limit = prawo.GRANT_SPOLECZNY_LIMIT_PODSTAWOWY
    prog = prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY
    tresc = (
        f"Przy dzierżawie dotacja wynosi {prog:.0%} zamiast {limit:.0%}. "
        f"Na tej inwestycji to {_mln(roznica_dotacji)} mniej."
    )

    # Wniosek najmocniejszy: dzierzawa wyglada na wejscie bez wydatku kapitalowego,
    # a potrafi wymagac WIEKSZEGO wkladu niz nabycie — bo utracona dotacja i czynsz
    # dzierzawny obciazajacy przeplyw przebijaja oszczednosc na cenie dzialki.
    oszczednosc = nabycie.wklad_gotowkowy - dzierzawa.wklad_gotowkowy
    if oszczednosc > ZERO:
        netto = roznica_dotacji - oszczednosc
        if netto > ZERO:
            tresc += (
                f" Oszczędzasz {_mln(oszczednosc)} na wkładzie własnym, więc dzierżawa "
                f"kosztuje netto {_mln(netto)} — nie licząc czynszu dzierżawnego "
                f"({_zl(dzierzawa.oplata_roczna)} rocznie) przez cały okres."
            )
        else:
            tresc += (
                f" Oszczędzasz przy tym {_mln(oszczednosc)} na wkładzie własnym, więc mimo "
                f"niższej dotacji wariant wychodzi na plus — ale sprawdź, czy czynsz "
                f"dzierżawny {_zl(dzierzawa.oplata_roczna)} rocznie tego nie zjada."
            )
    else:
        tresc += (
            f" Mimo braku wydatku na działkę dzierżawa wymaga o {_mln(-oszczednosc)} "
            f"WIĘKSZEGO wkładu własnego niż nabycie: utracona dotacja i czynsz dzierżawny "
            f"({_zl(dzierzawa.oplata_roczna)} rocznie) przebijają oszczędność na cenie gruntu."
        )
    tresc += " Sprawdź wariant z nabyciem."
    return [
        Wniosek(
            kod="DZIERZAWA_PULAPKA_KOSZTOWA",
            tresc=tresc,
            forma_polecana="nabycie_od_gminy",
            kwota=roznica_dotacji,
        )
    ]


def _wniosek_aport_gminy(
    wybrana: str, indeks: Dict[str, WariantGruntu], wyniki: Dict[str, object]
) -> List[Wniosek]:
    """Rozdz. 4.2 — aport gminy kosztuje dwa razy.

    Obniza dopuszczalna pomoc kanalem C i wprowadza gmine do spolki. Wariant
    "lokal za grunt" daje ta sama dzialke bez zadnego z tych skutkow, bo jest
    nabyciem, a nie wniesieniem przez jednostke samorzadu.
    """
    aport = indeks.get("aport_gminy")
    if aport is None or not aport.wybrany or not aport.policzalny:
        return []

    # Miara skutku kanalu C: o ile spada dopuszczalna pomoc wzgledem tej samej
    # dzialki nabytej od gminy. Nabycie nie wymaga zadnych dodatkowych danych,
    # wiec jest zawsze policzalnym punktem odniesienia.
    nabycie = indeks.get("nabycie_od_gminy")
    if nabycie is None or not nabycie.policzalny:
        return []
    spadek = nabycie.dopuszczalna_pomoc - aport.dopuszczalna_pomoc
    if spadek <= ZERO:
        return []

    lokal = indeks.get("lokal_za_grunt")
    tresc = (
        f"Grunt wniesiony przez gminę zmniejsza dopuszczalną pomoc publiczną "
        f"o {_mln(spadek)}, a gmina staje się wspólnikiem spółki."
    )
    if lokal is not None and lokal.policzalny:
        tresc += (
            " Rozliczenie w trybie „lokal za grunt” daje tę samą działkę bez obu "
            "tych skutków — sprawdź to porównanie."
        )
        polecana = "lokal_za_grunt"
    else:
        tresc += (
            " Rozliczenie w trybie „lokal za grunt” daje tę samą działkę bez obu tych "
            "skutków; żeby je przeliczyć, podaj liczbę i powierzchnię lokali dla gminy."
        )
        polecana = ""
    return [
        Wniosek(
            kod="APORT_GMINY_KOSZTUJE_DWA_RAZY",
            tresc=tresc,
            forma_polecana=polecana,
            kwota=spadek,
        )
    ]


def _wniosek_najtanszy(wybrana: str, indeks: Dict[str, WariantGruntu]) -> List[Wniosek]:
    """Gdy inna dopuszczalna forma wymaga istotnie mniej kapitalu niz wybrana."""
    wybrany = indeks.get(wybrana)
    if wybrany is None or not wybrany.policzalny:
        return []
    kandydaci = [
        w
        for w in indeks.values()
        if w.policzalny and not w.wybrany and w.wklad_gotowkowy < wybrany.wklad_gotowkowy
    ]
    if not kandydaci:
        return []
    najtanszy = min(kandydaci, key=lambda w: w.wklad_gotowkowy)
    roznica = wybrany.wklad_gotowkowy - najtanszy.wklad_gotowkowy
    if roznica <= ZERO:
        return []
    tresc = (
        f"„{najtanszy.etykieta}” wymaga o {_mln(roznica)} mniej kapitału niż "
        f"„{wybrany.etykieta}”."
    )
    if not najtanszy.pasmo_45:
        tresc += " Ale ścina dotację — sprawdź, czy bilans wychodzi na plus."
    elif najtanszy.gmina_wspolnikiem:
        tresc += (
            f" Ale gmina obejmuje wtedy {najtanszy.udzial_gminy_w_spolce:.0%} udziałów w spółce."
            if najtanszy.udzial_gminy_w_spolce is not None
            else " Ale gmina obejmuje wtedy udziały w spółce."
        )
    elif najtanszy.oplata_roczna > ZERO:
        tresc += (
            f" Kosztem jest opłata roczna {_zl(najtanszy.oplata_roczna)} przez cały okres."
        )
    return [
        Wniosek(
            kod="TANSZA_FORMA_GRUNTU",
            tresc=tresc,
            forma_polecana=najtanszy.forma,
            kwota=roznica,
        )
    ]
