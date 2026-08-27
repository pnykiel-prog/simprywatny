"""Dataclasses wejscia i wyjscia oraz walidacja danych wejsciowych.

Modul nie zawiera zadnej liczby pochodzacej z ustawy — progi i limity pochodza
wylacznie z `prawo.py`.

Zasada: zadnych milczacych wartosci domyslnych dla parametrow zewnetrznych.
Brak stopy referencyjnej ma zatrzymac obliczenie, nie podstawic ostatnia znana.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import yaml

from . import prawo
from .waluta import ZERO, zl


class BladWalidacji(ValueError):
    """Twardy blad danych wejsciowych. Obliczenie sie nie zaczyna."""


class BladObliczenia(ValueError):
    """Silnik nie moze zwrocic wiarygodnej liczby — przerywa zamiast zgadywac."""


class Waga(int, Enum):
    """Istotnosc ostrzezenia — decyduje, ktore trafia do widoku glownego.

    Najpierw te, ktore zmieniaja werdykt, potem te, ktore przesuwaja kwote,
    na koncu pozostale (rozdz. 5.3 uzupelnienia specyfikacji).
    """

    ZMIENIA_WERDYKT = 3
    ZMIENIA_KWOTE = 2
    POZOSTALE = 1


@dataclass(frozen=True)
class Ostrzezenie:
    """Sygnal, ktory nie zatrzymuje obliczenia, ale musi dotrzec do uzytkownika.

    Niesie dwie redakcje tej samej rzeczy. `tresc` jest techniczna i idzie do
    arkusza — z artykulami, bo arkusz czyta analityk i Bank. `tresc_potoczna`
    idzie na ekran: mowi, co sie stalo i co z tym zrobic, bez numeru przepisu.
    Ekran sluzy rozmowie, arkusz dokumentacji.
    """

    kod: str
    tresc: str
    podstawa: str = ""
    tresc_potoczna: str = ""
    waga: Waga = Waga.POZOSTALE

    @property
    def dla_ekranu(self) -> str:
        return self.tresc_potoczna or self.tresc

    def __str__(self) -> str:
        return f"[{self.kod}] {self.tresc}" + (f" ({self.podstawa})" if self.podstawa else "")


class PochodzenieGruntu(str, Enum):
    """Poziom 1 pytania o grunt — czyja jest dzialka.

    Sam w sobie nie zmienia zadnej liczby; rozstrzyga, ktore formy wniesienia
    sa w ogole dopuszczalne (`prawo.FORMY_WG_POCHODZENIA`).
    """

    INWESTOR = prawo.POCHODZENIE_INWESTOR
    RYNEK_PRYWATNY = prawo.POCHODZENIE_RYNEK_PRYWATNY
    GMINA = prawo.POCHODZENIE_GMINA

    @property
    def etykieta(self) -> str:
        return prawo.ETYKIETY_POCHODZENIA[self.value]

    @property
    def formy(self) -> tuple:
        return tuple(FormaGruntu(f) for f in prawo.formy_dla_pochodzenia(self.value))

    def formy_wartosci(self) -> tuple:
        return prawo.formy_dla_pochodzenia(self.value)


class FormaGruntu(str, Enum):
    """Poziom 2 pytania o grunt — w jakiej formie dzialka trafia do projektu.

    Wszystkie skutki formy siedza w matrycy w `prawo.MATRYCA_GRUNTU`, nie tutaj.
    Enum wystawia je tylko jako wlasciwosci, zeby reszta silnika nie musiala
    znac ani nazw form, ani przepisow.
    """

    APORT_INWESTORA = "aport_inwestora"
    SPOLKA_WLASCICIELEM = "spolka_wlascicielem"
    NABYCIE_PRYWATNE = "nabycie_prywatne"
    NABYCIE_OD_GMINY = "nabycie_od_gminy"
    LOKAL_ZA_GRUNT = "lokal_za_grunt"
    # APORT_GMINY usuniety — pakiet naprawczy nr 2, rozdz. 11. Gmina obejmowala
    # wtedy udzialy, a przy dzialce porownywalnej z wkladem inwestora wychodzila
    # jej wiekszosc. Wraz z nia stawki czynszu ustala zgromadzenie wspolnikow
    # (art. 28 ust. 1 ustawy z 26.10.1995), wiec suwak czynszu przestaje byc
    # dzwignia inwestora, a glowna liczba wyjsciowa — wymagany wklad inwestora —
    # traci sens. To nie prywatny SIM z komplikacja, tylko inny podmiot.
    UZYTKOWANIE_WIECZYSTE = "uzytkowanie_wieczyste"
    DZIERZAWA = "dzierzawa"

    @property
    def skutki(self) -> prawo.SkutkiFormyGruntu:
        """Wiersz matrycy skutkow — rozdz. 3 uzupelnienia nr 2."""
        return prawo.skutki_gruntu(self.value)

    @property
    def pochodzenie(self) -> "PochodzenieGruntu":
        return PochodzenieGruntu(self.skutki.pochodzenie)

    @property
    def wniesiony_aportem(self) -> bool:
        """Wklad niepieniezny — § 12 ust. 6 i 7 rozp. 766."""
        return self.value in prawo.FORMY_APORTOWE

    @property
    def daje_pasmo_45(self) -> bool:
        """Kanal A: czy forma odblokowuje wsparcie ponad prog gruntowy.

        art. 13 ust. 1 pkt 1 ustawy z 8.12.2006 mowi o wartosci prawa wlasnosci
        albo uzytkowania wieczystego. Dzierzawa nie jest zadnym z tych praw.
        """
        return self.value in prawo.FORMY_DAJACE_PASMO_45

    @property
    def wymaga_oplaty_rocznej(self) -> bool:
        return self.value in prawo.FORMY_Z_OPLATA_ROCZNA

    @property
    def etykieta(self) -> str:
        return self.skutki.etykieta

    @property
    def podpis(self) -> str:
        return self.skutki.podpis


class UjecieKosztowInwestycyjnych(str, Enum):
    """Jak koszt przedsiewziecia wchodzi do kosztow UOIG w rachunku kosztow netto.

    Specyfikacja odsyla do katalogu z art. 5 ust. 7-8 ustawy z 8.12.2006, ale go
    nie przytacza. Ujecie nakladu inwestycyjnego zmienia KN o rzad wielkosci,
    wiec jest przelacznikiem z jawnym oznaczeniem zalozenia — patrz LUKI.md.
    """

    AMORTYZACJA = "amortyzacja"              # roczny odpis przez okres amortyzacji budynkow
    # Naklad rozlozony rowno na lata okresu powierzenia — odczyt spojny z sama
    # formula KN, ktora sumuje dokladnie po i = 1..n tego okresu.
    AMORTYZACJA_W_OKRESIE_POWIERZENIA = "amortyzacja_w_okresie_powierzenia"
    NAKLAD_POCZATKOWY = "naklad_poczatkowy"  # caly naklad w roku pierwszym
    POMINIETE = "pominiete"                  # tylko koszty biezace


class TrybKredytu(str, Enum):
    """Skad bierze sie kwota kredytu.

    AUTOMATYCZNY — silnik liczy maksymalny kredyt, ktory uniesie zakladany
    czynsz. Wskaznik pokrycia obslugi dlugu wychodzi wtedy 1,0 z konstrukcji,
    a cale napiecie montazu przenosi sie do wymaganego wkladu wlasnego.

    RECZNY — kwote wyznacza udzial docelowy podany na wejsciu. Wskaznik
    pokrycia wraca do roli miary, ktora moze byc mniejsza albo wieksza od 1,0.
    """

    AUTOMATYCZNY = "automatyczny"
    RECZNY = "reczny"


class MetodaRozsadnegoZysku(str, Enum):
    """Sposob wyliczenia rozsadnego zysku (RZ).

    Specyfikacja podaje zrodlo stopy (IRS 20-letni na bazie WIBOR 3M, z BIP BGK),
    ale nie podaje wzoru. Do czasu potwierdzenia w Banku metoda jest przelacznikiem
    z jawnym oznaczeniem zalozenia — patrz LUKI.md.
    """

    KAPITAL_ZAANGAZOWANY = "kapital_zaangazowany"
    KWOTA_WPROST = "kwota_wprost"


class RegulaProgu(str, Enum):
    """Ktory prog tolerancji wiaze pule laczaca dotacje z kredytem.

    Pakiet naprawczy nr 2, rozdz. 2. Dotacja podlega rozporzadzeniu o wsparciu
    finansowym (prog 10%), kredyt rozporzadzeniu o finansowaniu zwrotnym (20%).
    Pula spoleczna ma oba instrumenty naraz, a zaden przepis nie mowi, ktory
    rezim wtedy wiaze. Wartosc domyslna jest ZALOZENIEM — i to zalozeniem, ktore
    potrafi samo przewrocic werdykt zbiorczy.
    """

    NIZSZY = prawo.REGULA_PROGU_NIZSZY
    WYZSZY = prawo.REGULA_PROGU_WYZSZY
    WEDLUG_INSTRUMENTU_DOMINUJACEGO = prawo.REGULA_PROGU_DOMINUJACY


class ZrodloLokaliDlaGminy(str, Enum):
    """Z ktorej puli pochodza lokale oddawane gminie w trybie "lokal za grunt".

    Ustawa z 16.12.2020 (Dz.U. 2021 poz. 223) mowi o przeniesieniu wlasnosci
    lokali w zamian za grunt, ale nie wskazuje, ktora czesc przedsiewziecia
    ich dostarcza. Wybor nie jest obojetny: pula, ktora je oddaje, traci
    powierzchnie przychodowa, zachowujac pelny koszt.
    """

    PROPORCJONALNIE = prawo.LOKALE_GMINY_PROPORCJONALNIE
    KOMUNALNA = prawo.LOKALE_GMINY_Z_KOMUNALNEJ
    SPOLECZNA = prawo.LOKALE_GMINY_ZE_SPOLECZNEJ


# ---------------------------------------------------------------------------
# Warstwa wspolna
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Projekt:
    nazwa: str
    gmina: str
    wojewodztwo: str


@dataclass(frozen=True)
class Powierzchnie:
    pum_laczne: Decimal
    liczba_lokali: int
    liczba_kondygnacji: int
    udzial_puli_komunalnej: Decimal   # 0.0-1.0 — GLOWNE POKRETLO

    @property
    def pum_komunalne(self) -> Decimal:
        return self.pum_laczne * self.udzial_puli_komunalnej

    @property
    def pum_spoleczne(self) -> Decimal:
        return self.pum_laczne - self.pum_komunalne

    @property
    def srednie_pum_lokalu(self) -> Decimal:
        if self.liczba_lokali == 0:
            return ZERO
        return self.pum_laczne / Decimal(self.liczba_lokali)


@dataclass(frozen=True)
class Koszty:
    koszt_budowy_na_m2: Decimal
    infrastruktura: Decimal
    projekt_i_nadzor: Decimal
    koszty_ogolne: Decimal
    rezerwa: Decimal
    vat_odliczalny: bool           # art. 13 ust. 3 — wplywa na podstawe grantu
    stawka_vat: Decimal            # potrzebna, gdy VAT nie jest odliczalny
    dzwigi: Decimal = ZERO         # osobna pozycja — walidacja standardow technicznych


@dataclass(frozen=True)
class Grunt:
    """Dzialka w dwoch poziomach: skad pochodzi i w jakiej formie wchodzi.

    `wartosc` to zawsze wartosc z operatu. Cena rzeczywiscie zaplacona gminie
    (po bonifikacie) siedzi osobno w `cena_nabycia`, bo art. 13 ust. 1 pkt 1
    mowi o wartosci prawa, a nie o cenie nabycia — patrz kwestia 9.3.
    """

    wartosc: Decimal                              # z operatu
    pochodzenie: PochodzenieGruntu
    forma: FormaGruntu
    obciazony_hipoteka: bool
    # tylko dla dzierzawy i uzytkowania wieczystego — koszt biezacy, nie kapitalowy
    oplata_roczna: Optional[Decimal] = None
    # cena po bonifikacie; wymagana tylko przy odczycie alternatywnym kwestii 9.3
    cena_nabycia: Optional[Decimal] = None
    # tylko dla formy "lokal za grunt" — rozliczenie ceny lokalami
    liczba_lokali_dla_gminy: int = 0
    pum_lokali_dla_gminy: Decimal = ZERO

    @property
    def rozliczany_lokalami(self) -> bool:
        return self.forma is FormaGruntu.LOKAL_ZA_GRUNT

    @property
    def oplata_roczna_lub_zero(self) -> Decimal:
        return self.oplata_roczna if self.oplata_roczna is not None else ZERO

    @property
    def koszt_lokali_dla_gminy_na_m2(self) -> Decimal:
        """Efektywny koszt gruntu na m2 lokali oddawanych gminie — rozdz. 6.

        Do zestawienia z kosztem budowy metra. Jezeli gmina zada lokali wartych
        wiecej niz dzialka, wariant jest niekorzystny i ma to byc widoczne.
        """
        if self.pum_lokali_dla_gminy <= ZERO:
            return ZERO
        return self.wartosc / self.pum_lokali_dla_gminy


# ---------------------------------------------------------------------------
# Pula spoleczna
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Kredyt:
    oprocentowanie: Decimal        # rp
    okres_lat: int                 # N, laczny z karencja
    karencja_lat: int              # T
    udzial_docelowy: Decimal       # 0.0-0.80

    @property
    def aktywny(self) -> bool:
        return self.udzial_docelowy > 0


@dataclass(frozen=True)
class Partycypacja:
    stawka_procent_kosztu_lokalu: Decimal   # 0.0-0.30
    rotacja_roczna: Decimal                 # do rezerwy na zwrot


@dataclass(frozen=True)
class PulaSpoleczna:
    kredyt: Kredyt
    partycypacja: Partycypacja
    czynsz_zakladany_m2_mies: Decimal
    bonus_rewitalizacyjny: bool             # tylko gdy brak kredytu, art. 13 ust. 4


# ---------------------------------------------------------------------------
# Pula komunalna — kredyt i partycypacja niedopuszczalne (art. 5a ust. 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PulaKomunalna:
    czynsz_placony_przez_gmine_m2_mies: Decimal
    bonus_rewitalizacyjny: bool


# ---------------------------------------------------------------------------
# Eksploatacja i parametry zewnetrzne
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Eksploatacja:
    koszt_eksploatacji_m2_rok: Decimal
    odpis_remontowy_m2_rok: Decimal
    ubezpieczenie_rocznie: Decimal
    koszty_stale_zarzadu_rocznie: Decimal
    pustostany_procent: Decimal
    indeksacja_kosztow_rocznie: Decimal
    indeksacja_czynszu_rocznie: Decimal


@dataclass(frozen=True)
class ParametryZewnetrzne:
    wartosc_odtworzeniowa_m2: Decimal        # obwieszczenie wojewody
    stopa_bazowa_ke: Decimal                 # rb — dyskonto w KN
    stopa_referencyjna_ke: Decimal           # r  — w EDB
    stopa_dyskontowa: Decimal                # rd — w EDB
    stopa_irs_bgk: Decimal                   # do rozsadnego zysku, z BIP BGK
    waloryzacja_partycypacji_rocznie: Decimal  # wskaznik ceny 1 m2 GUS, art. 29a ust. 3
    okres_amortyzacji_budynkow_lat: int      # limit okresu powierzenia, § 11 rozp. 766
    data_parametrow: _dt.date
    # Margines przyjmowany przy WYMIAROWANIU kredytu maksymalnego (pakiet nr 2,
    # rozdz. 1). Nie jest odczytem z przepisu ani z informatora BGK — patrz
    # `prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY`. Pole ma wartosc domyslna,
    # bo brak wpisu ma dawac wariant ostrozniejszy, a nie wariant bez bufora;
    # sama wartosc nigdy nie przechodzi po cichu — silnik oznacza ja ostrzezeniem.
    minimalny_wskaznik_pokrycia_obslugi_dlugu: Decimal = (
        prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY
    )
    zrodla: Mapping[str, str] = field(default_factory=dict)

    @property
    def bufor_obslugi_dlugu_podany(self) -> bool:
        """Czy wskaznik pokrycia pochodzi z wejscia, czy z wartosci domyslnej."""
        return "minimalny_wskaznik_pokrycia_obslugi_dlugu" in self.zrodla

    def wiek_miesiecy(self, na_dzien: Optional[_dt.date] = None) -> int:
        na_dzien = na_dzien or _dt.date.today()
        return (na_dzien.year - self.data_parametrow.year) * 12 + (
            na_dzien.month - self.data_parametrow.month
        )


@dataclass(frozen=True)
class Rynek:
    """Obserwacja o rynku najmu — nie jest liczona, tylko podawana.

    Na czynsz w puli spolecznej dzialaja TRZY sufity, nie dwa: dwa limity ustawowe,
    ktore silnik wylicza, i poziom akceptowany przez rynek, ktorego wyliczyc sie
    nie da. Trzeci nie jest mniej realny od dwoch pierwszych — czynsz zgodny
    z ustawa, ale wyzszy od tego, co mozna uzyskac w danej miejscowosci, daje
    pustostany, a nie przychod.

    Pole jest opcjonalne i puste niczego nie blokuje. Gdy jednak wartosc podano,
    zrodlo jest obowiazkowe: liczba bez zrodla wyglada w wyniku identycznie jak
    dana rzeczywista i wchodzi do rozmowy z gmina jako argument.

    W puli komunalnej ten sufit NIE WYSTEPUJE — najemca jest gmina, a oplaty
    podnajemcow sa ustawione na poziomie zasobu komunalnego.
    """

    czynsz_rynkowy_m2_mies: Optional[Decimal] = None
    zrodlo: Optional[str] = None
    data: Optional[_dt.date] = None

    @property
    def podano(self) -> bool:
        return self.czynsz_rynkowy_m2_mies is not None


@dataclass(frozen=True)
class Rekompensata:
    """Skladniki wliczane do rekompensaty poza grantem — § 7 ust. 7 rozp. 1897."""

    wsparcie_rfrm: Decimal                   # Rzadowy Fundusz Rozwoju Mieszkalnictwa
    wartosc_dokumentacji_bgk: Decimal        # nieodplatne prawo do dokumentacji BGK
    rozsadny_zysk_kwota: Optional[Decimal] = None   # tylko dla metody KWOTA_WPROST


@dataclass(frozen=True)
class Inwestor:
    """Zdolnosc kapitalowa inwestora.

    `dostepny_wklad_wlasny` jest OPCJONALNY. Wymagany wklad jest wynikiem
    obliczenia, nie jego warunkiem — deklarowana kwota sluzy wylacznie za punkt
    odniesienia i nigdy nie blokuje przeliczenia.
    """

    dostepny_wklad_wlasny: Optional[Decimal] = None

    @property
    def zadeklarowany(self) -> bool:
        return self.dostepny_wklad_wlasny is not None


@dataclass(frozen=True)
class Przelaczniki:
    """Kwestie otwarte z rozdz. 10 specyfikacji — wartosc domyslna jest ZALOZENIEM."""

    # 10.1. Czy hybryda to jedno przedsiewziecie, czy dwa. Domyslnie dwa odrebne.
    hybryda_jako_jedno_przedsiewziecie: bool = False
    # Kwestia 9.1 uzupelnienia nr 2: czy grunt nabyty w trybie "lokal za grunt"
    # jest przychodem uslugi publicznej. Domyslnie NIE — to nabycie, a nie
    # wniesienie przez jednostke samorzadu terytorialnego. ZALOZENIE.
    lokal_za_grunt_jest_przychodem_uoig: bool = False
    # Kwestia 9.2: czy wartosc prawa uzytkowania wieczystego ustanowionego przez
    # gmine jest przychodem uslugi publicznej. Domyslnie wariant ostrozniejszy:
    # TAK, jest przychodem. ZALOZENIE.
    uzytkowanie_wieczyste_jest_przychodem_uoig: bool = True
    # Kwestia 9.3: czy pasmo dotacji liczy sie od wartosci z operatu, czy od ceny
    # po bonifikacie. Domyslnie od operatu — art. 13 ust. 1 pkt 1 mowi o wartosci
    # prawa, nie o cenie nabycia. ZALOZENIE.
    pasmo_liczone_od_wartosci_z_operatu: bool = True
    # Brak wzoru na rozsadny zysk w specyfikacji — patrz LUKI.md.
    metoda_rozsadnego_zysku: MetodaRozsadnegoZysku = MetodaRozsadnegoZysku.KAPITAL_ZAANGAZOWANY
    # art. 5 ust. 1 pkt 2 u.f.w. — remont i przebudowa zamiast budowy (limit czynszu 5%).
    remont_i_przebudowa: bool = False
    # Skad bierze sie kwota kredytu — patrz TrybKredytu.
    tryb_kredytu: TrybKredytu = TrybKredytu.AUTOMATYCZNY
    # Ujecie nakladu inwestycyjnego w kosztach UOIG — patrz LUKI.md.
    koszty_inwestycyjne_w_kn: UjecieKosztowInwestycyjnych = UjecieKosztowInwestycyjnych.AMORTYZACJA
    # Czy zalozony wskaznik pustostanow obciaza takze pule komunalna. Domyslnie nie:
    # najemca calej puli jest gmina, wiec ryzyko pustostanu zostaje po jej stronie.
    # ZALOZENIE — zmienia wynik testu 2, wiec jest przelacznikiem, nie zaszyta reguła.
    pustostany_takze_w_puli_komunalnej: bool = False
    # Pakiet nr 2, rozdz. 2 — zbieg progow tolerancji w puli laczacej dotacje
    # z kredytem. Domyslnie prog NIZSZY, jako ostrozniejszy. ZALOZENIE.
    prog_tolerancji_przy_dwoch_instrumentach: RegulaProgu = RegulaProgu.NIZSZY
    # Czy bonus rewitalizacyjny +5 pp podnosi takze prog gruntowy, czy tylko
    # limit gorny. Domyslnie TYLKO limit gorny — art. 13 ust. 4 mowi o zwiekszeniu
    # kwoty wsparcia, nie o przesunieciu progu z art. 13 ust. 1 pkt 1. ZALOZENIE.
    bonus_podnosi_prog_gruntowy: bool = False
    # Z ktorej puli pochodza lokale oddawane gminie. Domyslnie proporcjonalnie
    # kluczem PUM — ustawa nie wskazuje puli. ZALOZENIE.
    lokale_dla_gminy_z_puli: ZrodloLokaliDlaGminy = ZrodloLokaliDlaGminy.PROPORCJONALNIE
    # Dlugosc okresu rozliczeniowego nadwyzki rekompensaty w latach. Domyslnie 1 —
    # najgestsza siatka, jaka model potrafi zbudowac, czyli wariant najostrozniejszy.
    # Przepis odnosi prog do "okresu rozliczeniowego", nie podajac jego dlugosci.
    # ZALOZENIE do potwierdzenia w BGK.
    okres_rozliczeniowy_nadwyzki_lat: int = 1


@dataclass(frozen=True)
class Wejscie:
    projekt: Projekt
    powierzchnie: Powierzchnie
    koszty: Koszty
    grunt: Grunt
    pula_spoleczna: PulaSpoleczna
    pula_komunalna: PulaKomunalna
    eksploatacja: Eksploatacja
    parametry_zewnetrzne: ParametryZewnetrzne
    rekompensata: Rekompensata
    inwestor: Inwestor
    rynek: Rynek
    przelaczniki: Przelaczniki
    ostrzezenia: Sequence[Ostrzezenie] = field(default_factory=tuple)

    def z_udzialem_komunalnym(self, udzial: Decimal, na_dzien=None) -> "Wejscie":
        """Kopia wejscia z innym ustawieniem glownego pokretla — do sweepu.

        Walidacja idzie od nowa. Przesuniecie pokretla potrafi uczynic konfiguracje
        bezprawna — na przyklad kredyt SBC przy 100% puli komunalnej (art. 5a ust. 3) —
        a sweep nie moze takiego punktu policzyc po cichu.
        """
        kopia = replace(
            self,
            powierzchnie=replace(self.powierzchnie, udzial_puli_komunalnej=zl(udzial)),
            ostrzezenia=(),
        )
        return replace(kopia, ostrzezenia=tuple(waliduj(kopia, na_dzien=na_dzien)))

    def z_forma_gruntu(self, forma: "FormaGruntu", na_dzien=None) -> "Wejscie":
        """Kopia wejscia z inna forma wniesienia gruntu — do widoku porownawczego.

        Pochodzenie idzie za forma, bo kazda forma nalezy do dokladnie jednego
        pochodzenia. Walidacja od nowa: czesc form wymaga danych, ktorych wejscie
        moze nie miec (oplata roczna, lokale dla gminy), a czesc odpada wprost
        (aport nieruchomosci obciazonej hipoteka). Wariant niepoliczalny ma wrocic
        z powodem, nie z liczba.
        """
        kopia = replace(
            self,
            grunt=replace(self.grunt, forma=forma, pochodzenie=forma.pochodzenie),
            ostrzezenia=(),
        )
        return replace(kopia, ostrzezenia=tuple(waliduj(kopia, na_dzien=na_dzien)))


# ---------------------------------------------------------------------------
# Parser YAML
# ---------------------------------------------------------------------------

def _sekcja(dane: Mapping[str, Any], nazwa: str) -> Mapping[str, Any]:
    if nazwa not in dane or dane[nazwa] is None:
        raise BladValidacjiBrak(nazwa)
    wartosc = dane[nazwa]
    if not isinstance(wartosc, Mapping):
        raise BladWalidacji(f"Sekcja '{nazwa}' musi byc mapowaniem, jest {type(wartosc).__name__}.")
    return wartosc


def BladValidacjiBrak(sciezka: str) -> BladWalidacji:  # noqa: N802 — czytelnosc komunikatu
    return BladWalidacji(
        f"Brak wymaganej sekcji/parametru '{sciezka}' w pliku wejsciowym. "
        "Silnik nie podstawia wartosci domyslnych — uzupelnij dane i powtorz."
    )


def _kwota(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> Decimal:
    if klucz not in sekcja or sekcja[klucz] is None:
        raise BladValidacjiBrak(f"{sciezka}.{klucz}")
    try:
        return zl(sekcja[klucz])
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BladWalidacji(f"'{sciezka}.{klucz}' nie jest liczba: {sekcja[klucz]!r}") from exc


def _data_opcjonalna(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> Optional[_dt.date]:
    if klucz not in sekcja or sekcja[klucz] is None:
        return None
    return _data(sekcja, klucz, sciezka)


def _kwota_opcjonalna(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> Optional[Decimal]:
    """Kwota, ktorej brak jest dopuszczalny i znaczacy — None, nie zero.

    Rozroznienie jest istotne: "nie podano oplaty rocznej" i "oplata roczna
    wynosi zero" to dwie rozne sytuacje, a silnik nie podstawia wartosci
    domyslnych za parametry zewnetrzne.
    """
    if klucz not in sekcja or sekcja[klucz] is None:
        return None
    return _kwota(sekcja, klucz, sciezka)


def _wskaznik_pokrycia(sekcja: Mapping[str, Any]) -> Decimal:
    """Minimalny wskaznik pokrycia obslugi dlugu — pakiet nr 2, rozdz. 1.

    Jedyny parametr zewnetrzny z wartoscia domyslna, i to swiadomie. Reszta
    sekcji to odczyty (obwieszczenie wojewody, stopy, wskaznik GUS), ktorych
    podstawic sie nie da; tutaj chodzi o margines ostroznosci przy wymiarowaniu
    kredytu. Brak wpisu ma dawac wariant ostrozniejszy, a nie wariant bez bufora
    — dlatego zamiast bledu wchodzi 1,20 z jawnym ostrzezeniem.
    """
    klucz = "minimalny_wskaznik_pokrycia_obslugi_dlugu"
    if klucz not in sekcja or sekcja[klucz] is None:
        return prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY
    wartosc = _kwota(sekcja, klucz, "parametry_zewnetrzne")
    if wartosc < prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_MINIMUM:
        raise BladWalidacji(
            f"'parametry_zewnetrzne.{klucz}' wynosi {wartosc}, a nie moze byc "
            f"mniejszy niz {prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_MINIMUM}. "
            "Pokrycie ponizej jednosci oznacza rate, ktorej przychod nie unosi "
            "juz w chwili wyliczenia — to nie jest montaz, tylko niedobor."
        )
    return wartosc


def _calkowita(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> int:
    if klucz not in sekcja or sekcja[klucz] is None:
        raise BladValidacjiBrak(f"{sciezka}.{klucz}")
    wartosc = sekcja[klucz]
    if isinstance(wartosc, bool) or not isinstance(wartosc, int):
        raise BladWalidacji(f"'{sciezka}.{klucz}' musi byc liczba calkowita, jest {wartosc!r}")
    return wartosc


def _flaga(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> bool:
    if klucz not in sekcja or sekcja[klucz] is None:
        raise BladValidacjiBrak(f"{sciezka}.{klucz}")
    wartosc = sekcja[klucz]
    if not isinstance(wartosc, bool):
        raise BladWalidacji(f"'{sciezka}.{klucz}' musi byc true/false, jest {wartosc!r}")
    return wartosc


def _tekst(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> str:
    if not sekcja.get(klucz):
        raise BladValidacjiBrak(f"{sciezka}.{klucz}")
    return str(sekcja[klucz])


def _data(sekcja: Mapping[str, Any], klucz: str, sciezka: str) -> _dt.date:
    if klucz not in sekcja or sekcja[klucz] is None:
        raise BladValidacjiBrak(f"{sciezka}.{klucz}")
    wartosc = sekcja[klucz]
    if isinstance(wartosc, _dt.datetime):
        return wartosc.date()
    if isinstance(wartosc, _dt.date):
        return wartosc
    try:
        return _dt.date.fromisoformat(str(wartosc))
    except ValueError as exc:
        raise BladWalidacji(f"'{sciezka}.{klucz}' nie jest data ISO: {wartosc!r}") from exc


def wczytaj_yaml(sciezka: Path | str) -> Wejscie:
    """Wczytuje plik YAML i zwraca zwalidowane wejscie."""
    sciezka = Path(sciezka)
    if not sciezka.exists():
        raise BladWalidacji(f"Plik wejsciowy nie istnieje: {sciezka}")
    with sciezka.open("r", encoding="utf-8") as plik:
        dane = yaml.safe_load(plik)
    if not isinstance(dane, Mapping):
        raise BladWalidacji(f"Plik {sciezka} nie zawiera mapowania YAML.")
    return zbuduj(dane)


def zbuduj(dane: Mapping[str, Any], na_dzien: Optional[_dt.date] = None) -> Wejscie:
    """Buduje `Wejscie` ze slownika i uruchamia komplet walidacji."""
    surowy_projekt = _sekcja(dane, "projekt")
    projekt = Projekt(
        nazwa=_tekst(surowy_projekt, "nazwa", "projekt"),
        gmina=_tekst(surowy_projekt, "gmina", "projekt"),
        wojewodztwo=_tekst(surowy_projekt, "wojewodztwo", "projekt"),
    )

    sp = _sekcja(dane, "powierzchnie")
    powierzchnie = Powierzchnie(
        pum_laczne=_kwota(sp, "pum_laczne", "powierzchnie"),
        liczba_lokali=_calkowita(sp, "liczba_lokali", "powierzchnie"),
        liczba_kondygnacji=_calkowita(sp, "liczba_kondygnacji", "powierzchnie"),
        udzial_puli_komunalnej=_kwota(sp, "udzial_puli_komunalnej", "powierzchnie"),
    )

    sk = _sekcja(dane, "koszty")
    koszty = Koszty(
        koszt_budowy_na_m2=_kwota(sk, "koszt_budowy_na_m2", "koszty"),
        infrastruktura=_kwota(sk, "infrastruktura", "koszty"),
        projekt_i_nadzor=_kwota(sk, "projekt_i_nadzor", "koszty"),
        koszty_ogolne=_kwota(sk, "koszty_ogolne", "koszty"),
        rezerwa=_kwota(sk, "rezerwa", "koszty"),
        vat_odliczalny=_flaga(sk, "vat_odliczalny", "koszty"),
        stawka_vat=_kwota(sk, "stawka_vat", "koszty"),
        dzwigi=zl(sk.get("dzwigi", 0)),
    )

    sg = _sekcja(dane, "grunt")
    pochodzenie_surowe = _tekst(sg, "pochodzenie", "grunt")
    try:
        pochodzenie = PochodzenieGruntu(pochodzenie_surowe)
    except ValueError as exc:
        dozwolone = ", ".join(p.value for p in PochodzenieGruntu)
        raise BladWalidacji(
            f"'grunt.pochodzenie' ma nieznana wartosc {pochodzenie_surowe!r}. "
            f"Dozwolone: {dozwolone}."
        ) from exc
    forma_surowa = _tekst(sg, "forma", "grunt")
    try:
        forma = FormaGruntu(forma_surowa)
    except ValueError as exc:
        dozwolone = ", ".join(f.value for f in FormaGruntu)
        raise BladWalidacji(
            f"'grunt.forma' ma nieznana wartosc {forma_surowa!r}. Dozwolone: {dozwolone}."
        ) from exc
    grunt = Grunt(
        wartosc=_kwota(sg, "wartosc", "grunt"),
        pochodzenie=pochodzenie,
        forma=forma,
        obciazony_hipoteka=_flaga(sg, "obciazony_hipoteka", "grunt"),
        oplata_roczna=_kwota_opcjonalna(sg, "oplata_roczna", "grunt"),
        cena_nabycia=_kwota_opcjonalna(sg, "cena_nabycia", "grunt"),
        liczba_lokali_dla_gminy=int(sg.get("liczba_lokali_dla_gminy") or 0),
        pum_lokali_dla_gminy=zl(sg.get("pum_lokali_dla_gminy") or 0),
    )

    ss = _sekcja(dane, "pula_spoleczna")
    sk_kredyt = _sekcja(ss, "kredyt")
    kredyt = Kredyt(
        oprocentowanie=_kwota(sk_kredyt, "oprocentowanie", "pula_spoleczna.kredyt"),
        okres_lat=_calkowita(sk_kredyt, "okres_lat", "pula_spoleczna.kredyt"),
        karencja_lat=_calkowita(sk_kredyt, "karencja_lat", "pula_spoleczna.kredyt"),
        udzial_docelowy=_kwota(sk_kredyt, "udzial_docelowy", "pula_spoleczna.kredyt"),
    )
    sp_part = _sekcja(ss, "partycypacja")
    partycypacja = Partycypacja(
        stawka_procent_kosztu_lokalu=_kwota(
            sp_part, "stawka_procent_kosztu_lokalu", "pula_spoleczna.partycypacja"
        ),
        rotacja_roczna=_kwota(sp_part, "rotacja_roczna", "pula_spoleczna.partycypacja"),
    )
    if "czynsz_rynkowy_m2_mies" in ss:
        raise BladWalidacji(
            "'pula_spoleczna.czynsz_rynkowy_m2_mies' zostal przeniesiony do osobnej sekcji "
            "'rynek'. Stawka rynkowa nie jest parametrem puli, tylko obserwacja o rynku "
            "najmu w danej miejscowosci, i wymaga podania zrodla."
        )
    pula_spoleczna = PulaSpoleczna(
        kredyt=kredyt,
        partycypacja=partycypacja,
        czynsz_zakladany_m2_mies=_kwota(ss, "czynsz_zakladany_m2_mies", "pula_spoleczna"),
        bonus_rewitalizacyjny=_flaga(ss, "bonus_rewitalizacyjny", "pula_spoleczna"),
    )

    sko = _sekcja(dane, "pula_komunalna")
    # art. 5a ust. 3 u.f.w. — rozlacznosc konstrukcyjna. Sama obecnosc klucza to blad.
    for zabroniony in ("kredyt", "partycypacja"):
        if zabroniony in sko:
            raise BladWalidacji(
                f"'pula_komunalna.{zabroniony}' jest niedopuszczalna. "
                "Przedsiewziecie z art. 5a ust. 1 ustawy z 8.12.2006 nie moze byc "
                "finansowane kredytem SBC (art. 5a ust. 3), a najemca jest gmina, "
                "wiec partycypacja nie wystepuje. To rozlacznosc konstrukcyjna, nie limit."
            )
    pula_komunalna = PulaKomunalna(
        czynsz_placony_przez_gmine_m2_mies=_kwota(
            sko, "czynsz_placony_przez_gmine_m2_mies", "pula_komunalna"
        ),
        bonus_rewitalizacyjny=_flaga(sko, "bonus_rewitalizacyjny", "pula_komunalna"),
    )

    se = _sekcja(dane, "eksploatacja")
    eksploatacja = Eksploatacja(
        koszt_eksploatacji_m2_rok=_kwota(se, "koszt_eksploatacji_m2_rok", "eksploatacja"),
        odpis_remontowy_m2_rok=_kwota(se, "odpis_remontowy_m2_rok", "eksploatacja"),
        ubezpieczenie_rocznie=_kwota(se, "ubezpieczenie_rocznie", "eksploatacja"),
        koszty_stale_zarzadu_rocznie=_kwota(se, "koszty_stale_zarzadu_rocznie", "eksploatacja"),
        pustostany_procent=_kwota(se, "pustostany_procent", "eksploatacja"),
        indeksacja_kosztow_rocznie=_kwota(se, "indeksacja_kosztow_rocznie", "eksploatacja"),
        indeksacja_czynszu_rocznie=_kwota(se, "indeksacja_czynszu_rocznie", "eksploatacja"),
    )

    sz = _sekcja(dane, "parametry_zewnetrzne")
    parametry = ParametryZewnetrzne(
        wartosc_odtworzeniowa_m2=_kwota(sz, "wartosc_odtworzeniowa_m2", "parametry_zewnetrzne"),
        stopa_bazowa_ke=_kwota(sz, "stopa_bazowa_ke", "parametry_zewnetrzne"),
        stopa_referencyjna_ke=_kwota(sz, "stopa_referencyjna_ke", "parametry_zewnetrzne"),
        stopa_dyskontowa=_kwota(sz, "stopa_dyskontowa", "parametry_zewnetrzne"),
        stopa_irs_bgk=_kwota(sz, "stopa_irs_bgk", "parametry_zewnetrzne"),
        waloryzacja_partycypacji_rocznie=_kwota(
            sz, "waloryzacja_partycypacji_rocznie", "parametry_zewnetrzne"
        ),
        okres_amortyzacji_budynkow_lat=_calkowita(
            sz, "okres_amortyzacji_budynkow_lat", "parametry_zewnetrzne"
        ),
        minimalny_wskaznik_pokrycia_obslugi_dlugu=_wskaznik_pokrycia(sz),
        data_parametrow=_data(sz, "data_parametrow", "parametry_zewnetrzne"),
        zrodla=dict(sz.get("zrodla") or {}),
    )

    # Sekcja opcjonalna w calosci — brak stawki rynkowej niczego nie blokuje.
    sy = dane.get("rynek") or {}
    if not isinstance(sy, Mapping):
        raise BladWalidacji(
            f"Sekcja 'rynek' musi byc mapowaniem, jest {type(sy).__name__}."
        )
    stawka_rynkowa = sy.get("czynsz_rynkowy_m2_mies")
    rynek = Rynek(
        czynsz_rynkowy_m2_mies=zl(stawka_rynkowa) if stawka_rynkowa is not None else None,
        zrodlo=(str(sy["zrodlo"]).strip() or None) if sy.get("zrodlo") else None,
        data=_data_opcjonalna(sy, "data", "rynek"),
    )

    sr = _sekcja(dane, "rekompensata")
    rzk = sr.get("rozsadny_zysk_kwota")
    rekompensata = Rekompensata(
        wsparcie_rfrm=_kwota(sr, "wsparcie_rfrm", "rekompensata"),
        wartosc_dokumentacji_bgk=_kwota(sr, "wartosc_dokumentacji_bgk", "rekompensata"),
        rozsadny_zysk_kwota=zl(rzk) if rzk is not None else None,
    )

    si = dane.get("inwestor") or {}
    surowy_wklad = si.get("dostepny_wklad_wlasny")
    inwestor = Inwestor(
        dostepny_wklad_wlasny=zl(surowy_wklad) if surowy_wklad is not None else None
    )

    spr = dane.get("przelaczniki") or {}
    metoda_surowa = spr.get(
        "metoda_rozsadnego_zysku", MetodaRozsadnegoZysku.KAPITAL_ZAANGAZOWANY.value
    )
    try:
        metoda = MetodaRozsadnegoZysku(metoda_surowa)
    except ValueError as exc:
        dozwolone = ", ".join(m.value for m in MetodaRozsadnegoZysku)
        raise BladWalidacji(
            f"'przelaczniki.metoda_rozsadnego_zysku' ma nieznana wartosc {metoda_surowa!r}. "
            f"Dozwolone: {dozwolone}."
        ) from exc
    tryb_surowy = spr.get("tryb_kredytu", TrybKredytu.AUTOMATYCZNY.value)
    try:
        tryb = TrybKredytu(tryb_surowy)
    except ValueError as exc:
        dozwolone = ", ".join(t.value for t in TrybKredytu)
        raise BladWalidacji(
            f"'przelaczniki.tryb_kredytu' ma nieznana wartosc {tryb_surowy!r}. "
            f"Dozwolone: {dozwolone}."
        ) from exc
    ujecie_surowe = spr.get(
        "koszty_inwestycyjne_w_kn", UjecieKosztowInwestycyjnych.AMORTYZACJA.value
    )
    try:
        ujecie = UjecieKosztowInwestycyjnych(ujecie_surowe)
    except ValueError as exc:
        dozwolone = ", ".join(u.value for u in UjecieKosztowInwestycyjnych)
        raise BladWalidacji(
            f"'przelaczniki.koszty_inwestycyjne_w_kn' ma nieznana wartosc {ujecie_surowe!r}. "
            f"Dozwolone: {dozwolone}."
        ) from exc
    regula_surowa = spr.get(
        "prog_tolerancji_przy_dwoch_instrumentach", RegulaProgu.NIZSZY.value
    )
    try:
        regula_progu = RegulaProgu(regula_surowa)
    except ValueError as exc:
        dozwolone = ", ".join(r.value for r in RegulaProgu)
        raise BladWalidacji(
            f"'przelaczniki.prog_tolerancji_przy_dwoch_instrumentach' ma nieznana wartosc "
            f"{regula_surowa!r}. Dozwolone: {dozwolone}."
        ) from exc
    zrodlo_surowe = spr.get(
        "lokale_dla_gminy_z_puli", ZrodloLokaliDlaGminy.PROPORCJONALNIE.value
    )
    try:
        zrodlo_lokali = ZrodloLokaliDlaGminy(zrodlo_surowe)
    except ValueError as exc:
        dozwolone = ", ".join(z.value for z in ZrodloLokaliDlaGminy)
        raise BladWalidacji(
            f"'przelaczniki.lokale_dla_gminy_z_puli' ma nieznana wartosc "
            f"{zrodlo_surowe!r}. Dozwolone: {dozwolone}."
        ) from exc
    okres_rozliczeniowy = int(spr.get("okres_rozliczeniowy_nadwyzki_lat", 1) or 1)
    if okres_rozliczeniowy < 1:
        raise BladWalidacji(
            "'przelaczniki.okres_rozliczeniowy_nadwyzki_lat' musi byc dodatnia liczba lat, "
            f"jest {okres_rozliczeniowy}."
        )
    przelaczniki = Przelaczniki(
        hybryda_jako_jedno_przedsiewziecie=bool(
            spr.get("hybryda_jako_jedno_przedsiewziecie", False)
        ),
        lokal_za_grunt_jest_przychodem_uoig=bool(
            spr.get("lokal_za_grunt_jest_przychodem_uoig", False)
        ),
        uzytkowanie_wieczyste_jest_przychodem_uoig=bool(
            spr.get("uzytkowanie_wieczyste_jest_przychodem_uoig", True)
        ),
        pasmo_liczone_od_wartosci_z_operatu=bool(
            spr.get("pasmo_liczone_od_wartosci_z_operatu", True)
        ),
        metoda_rozsadnego_zysku=metoda,
        tryb_kredytu=tryb,
        koszty_inwestycyjne_w_kn=ujecie,
        remont_i_przebudowa=bool(spr.get("remont_i_przebudowa", False)),
        pustostany_takze_w_puli_komunalnej=bool(
            spr.get("pustostany_takze_w_puli_komunalnej", False)
        ),
        prog_tolerancji_przy_dwoch_instrumentach=regula_progu,
        bonus_podnosi_prog_gruntowy=bool(spr.get("bonus_podnosi_prog_gruntowy", False)),
        lokale_dla_gminy_z_puli=zrodlo_lokali,
        okres_rozliczeniowy_nadwyzki_lat=okres_rozliczeniowy,
    )

    wejscie = Wejscie(
        projekt=projekt,
        powierzchnie=powierzchnie,
        koszty=koszty,
        grunt=grunt,
        pula_spoleczna=pula_spoleczna,
        pula_komunalna=pula_komunalna,
        eksploatacja=eksploatacja,
        parametry_zewnetrzne=parametry,
        rekompensata=rekompensata,
        inwestor=inwestor,
        rynek=rynek,
        przelaczniki=przelaczniki,
    )
    ostrzezenia = waliduj(wejscie, na_dzien=na_dzien)
    return replace(wejscie, ostrzezenia=tuple(ostrzezenia))


# ---------------------------------------------------------------------------
# Walidacja
# ---------------------------------------------------------------------------

def waliduj(w: Wejscie, na_dzien: Optional[_dt.date] = None) -> List[Ostrzezenie]:
    """Twarde bledy podnosza `BladWalidacji`. Reszta wraca jako lista ostrzezen."""
    ostrzezenia: List[Ostrzezenie] = []

    _waliduj_powierzchnie(w, ostrzezenia)
    _waliduj_kredyt(w)
    _waliduj_bonus(w)
    _waliduj_partycypacje(w, ostrzezenia)
    _waliduj_grunt(w, ostrzezenia)
    _waliduj_rynek(w, ostrzezenia)
    _waliduj_eksploatacje(w)
    _waliduj_parametry(w, ostrzezenia, na_dzien)
    _waliduj_przelaczniki(w, ostrzezenia)

    return ostrzezenia


def _waliduj_powierzchnie(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    p = w.powierzchnie
    if p.pum_laczne <= 0:
        raise BladWalidacji("'powierzchnie.pum_laczne' musi byc dodatnie.")
    if p.liczba_lokali <= 0:
        raise BladWalidacji("'powierzchnie.liczba_lokali' musi byc dodatnia.")
    if p.liczba_kondygnacji <= 0:
        raise BladWalidacji("'powierzchnie.liczba_kondygnacji' musi byc dodatnia.")
    if not (ZERO <= p.udzial_puli_komunalnej <= 1):
        raise BladWalidacji(
            f"'powierzchnie.udzial_puli_komunalnej' musi miescic sie w przedziale 0.0-1.0, "
            f"jest {p.udzial_puli_komunalnej}."
        )

    srednie = p.srednie_pum_lokalu
    if srednie < prawo.PUM_LOKALU_MIN_M2 or srednie > prawo.PUM_LOKALU_MAX_M2:
        ostrzezenia.append(
            Ostrzezenie(
                kod="PUM_POZA_PRZEDZIALEM",
                tresc=(
                    f"Srednie PUM lokalu wynosi {srednie:.1f} m2 i wykracza poza przedzial "
                    f"{prawo.PUM_LOKALU_MIN_M2}-{prawo.PUM_LOKALU_MAX_M2} m2. Powyzej gornej "
                    "granicy lokal dopuszczalny wylacznie dla rodzin wielodzietnych."
                ),
                podstawa="rozp. MIiR z 4.03.2019, Dz.U. 2019 poz. 457",
            
                tresc_potoczna=(
                    f"Średnie mieszkanie wychodzi {srednie:.0f} m². Przy dotacji z Funduszu Dopłat "
                    "mieszkania mogą mieć od 25 do 80 m² — większe tylko dla rodzin wielodzietnych."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )
    if p.liczba_kondygnacji >= prawo.DZWIG_OBOWIAZKOWY_OD_KONDYGNACJI and w.koszty.dzwigi <= 0:
        ostrzezenia.append(
            Ostrzezenie(
                kod="BRAK_POZYCJI_DZWIGI",
                tresc=(
                    f"Budynek ma {p.liczba_kondygnacji} kondygnacji naziemnych, wiec dzwigi "
                    "osobowe sa obowiazkowe, a w kosztach nie ma pozycji 'dzwigi'. "
                    "Prawdopodobne niedoszacowanie kosztow przedsiewziecia."
                ),
                podstawa="rozp. MIiR z 4.03.2019, Dz.U. 2019 poz. 457",
            
                tresc_potoczna=(
                    "Budynek ma tyle kondygnacji, że winda jest obowiązkowa, a w kosztach jej nie ma. "
                    "Koszt inwestycji jest zaniżony — dopisz tę pozycję."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )


def _waliduj_kredyt(w: Wejscie) -> None:
    k = w.pula_spoleczna.kredyt
    # W trybie automatycznym udzial docelowy nie jest uzywany — kwote kredytu
    # wyznacza czynsz, a przy samych mieszkaniach komunalnych wychodzi zero.
    # Zakaz z art. 5a ust. 3 nie ma wtedy czego naruszyc, wiec sterowanie
    # kredytem po prostu znika, zamiast zglaszac blad (rozdz. 5.1 uzupelnienia).
    tryb_reczny = w.przelaczniki.tryb_kredytu is TrybKredytu.RECZNY
    if k.udzial_docelowy < 0:
        raise BladWalidacji("'pula_spoleczna.kredyt.udzial_docelowy' nie moze byc ujemny.")
    if k.udzial_docelowy > prawo.KREDYT_MAKSYMALNY_UDZIAL:
        raise BladWalidacji(
            f"Udzial kredytu {k.udzial_docelowy} przekracza maksimum "
            f"{prawo.KREDYT_MAKSYMALNY_UDZIAL} kosztow przedsiewziecia "
            "(art. 15b ust. 2 ustawy z 26.10.1995)."
        )
    if k.karencja_lat < 0:
        raise BladWalidacji("'pula_spoleczna.kredyt.karencja_lat' nie moze byc ujemna.")
    if k.oprocentowanie < 0:
        raise BladWalidacji("'pula_spoleczna.kredyt.oprocentowanie' nie moze byc ujemne.")
    if tryb_reczny and not k.aktywny:
        return
    if k.okres_lat <= 0:
        raise BladWalidacji("Kredyt aktywny wymaga dodatniego 'okres_lat'.")
    if k.okres_lat > prawo.KREDYT_MAKSYMALNY_OKRES_LAT:
        raise BladWalidacji(
            f"Okres kredytowania {k.okres_lat} lat przekracza maksimum "
            f"{prawo.KREDYT_MAKSYMALNY_OKRES_LAT} lat wliczajac karencje "
            "(art. 15b ust. 3 ustawy z 26.10.1995)."
        )
    if k.karencja_lat >= k.okres_lat:
        raise BladWalidacji(
            f"Karencja ({k.karencja_lat} lat) musi byc krotsza niz okres kredytowania "
            f"({k.okres_lat} lat) — okres liczy sie lacznie z karencja."
        )
    # art. 5a ust. 3 — kredyt istnieje tylko wtedy, gdy istnieje pula spoleczna.
    if tryb_reczny and w.powierzchnie.udzial_puli_komunalnej >= 1:
        raise BladWalidacji(
            "Kredyt SBC ustawiony przy udziale puli komunalnej rownym 100%. "
            "Przedsiewziecie z art. 5a ust. 1 ustawy z 8.12.2006 nie moze byc finansowane "
            "kredytem (art. 5a ust. 3) — wyzeruj 'udzial_docelowy' albo zmniejsz udzial puli."
        )


def _waliduj_bonus(w: Wejscie) -> None:
    # art. 13 ust. 4 — bonus wylaczony wprost przy finansowaniu zwrotnym.
    if w.pula_spoleczna.bonus_rewitalizacyjny and w.pula_spoleczna.kredyt.aktywny:
        raise BladWalidacji(
            "Bonus rewitalizacyjny / 'Za zyciem' (+5 pp) ustawiony w puli spolecznej razem "
            "z aktywnym kredytem SBC. Art. 13 ust. 4 ustawy z 8.12.2006 wylacza bonus przy "
            "finansowaniu zwrotnym — wybierz jedno."
        )


def _waliduj_partycypacje(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    stawka = w.pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu
    rotacja = w.pula_spoleczna.partycypacja.rotacja_roczna
    if stawka < 0:
        raise BladWalidacji("'partycypacja.stawka_procent_kosztu_lokalu' nie moze byc ujemna.")
    if stawka > prawo.PARTYCYPACJA_MAKSIMUM:
        raise BladWalidacji(
            f"Partycypacja {stawka} przekracza maksimum {prawo.PARTYCYPACJA_MAKSIMUM} "
            "kosztu budowy lokalu dla osoby fizycznej przy finansowaniu zwrotnym "
            "(art. 29a ust. 2 ustawy z 26.10.1995)."
        )
    if not (ZERO <= rotacja <= 1):
        raise BladWalidacji("'partycypacja.rotacja_roczna' musi miescic sie w przedziale 0.0-1.0.")
    # Kwestia otwarta 10.2 — zbieg progow. Silnik zwraca ostrzezenie, nie werdykt.
    if prawo.PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA <= stawka < prawo.PARTYCYPACJA_PROG_WYLACZENIA_ART_7B:
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZBIEG_PROGOW_PARTYCYPACJI",
                tresc=(
                    f"Partycypacja {stawka:.1%} miesci sie w przedziale "
                    f"{prawo.PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA:.0%}-"
                    f"{prawo.PARTYCYPACJA_PROG_WYLACZENIA_ART_7B:.0%}. Art. 29a ust. 2b nakazuje "
                    "umowe na czas nieoznaczony albo najem instytucjonalny z dojsciem do wlasnosci, "
                    "a art. 7b ust. 1 wciaz wymaga czasu oznaczonego min. 5 lat. Wnioski sa "
                    "sprzeczne — silnik nie rozstrzyga typu umowy. Kwestia otwarta 10.2."
                ),
                podstawa="art. 29a ust. 2a i 2b, art. 7b ust. 1 ustawy z 26.10.1995",
            
                tresc_potoczna=(
                    "Przy tym poziomie partycypacji przepisy nie są jednoznaczne co do rodzaju umowy "
                    "najmu. Warto to uzgodnić z prawnikiem albo wybrać poziom powyżej 15%."
                ),
                waga=Waga.POZOSTALE,
            )
        )


def _waliduj_grunt(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    """Walidacje twarde z rozdz. 5 uzupelnienia nr 2.

    Wszystkie blokuja obliczenie. Wariant niedopuszczalny nie jest ostrzezeniem —
    policzenie go i opatrzenie uwaga bylo by podaniem uzytkownikowi liczby,
    ktorej nie wolno mu uzyc.
    """
    g = w.grunt

    if g.wartosc < 0:
        raise BladWalidacji("'grunt.wartosc' nie moze byc ujemna.")

    # 1. Forma niezgodna z pochodzeniem.
    dozwolone = prawo.formy_dla_pochodzenia(g.pochodzenie.value)
    if g.forma.value not in dozwolone:
        raise BladWalidacji(
            f"Forma gruntu '{g.forma.value}' jest niedostepna przy pochodzeniu "
            f"'{g.pochodzenie.value}'. Dla tego pochodzenia dopuszczalne sa: "
            f"{', '.join(dozwolone)}."
        )

    # 2. Aport nieruchomosci obciazonej hipoteka — wariant odpada.
    if g.obciazony_hipoteka and g.forma.wniesiony_aportem:
        raise BladWalidacji(
            "Nieruchomosc wnoszona aportem jest obciazona hipoteka — wariant jest "
            "niedopuszczalny, a nie obarczony ryzykiem. Podstawa wprost: § 12 ust. 6 "
            "rozp. t.j. Dz.U. 2021 poz. 766, dotyczacy sciezki finansowania zwrotnego; "
            "kalkulator blokuje ten wariant takze poza ta sciezka, bo hipoteka na gruncie "
            "wniesionym do spolki obciaza majatek SIM niezaleznie od zrodla finansowania. "
            "Zdejmij obciazenie albo wybierz forme nabycia."
        )

    # 3. Brak oplaty rocznej przy dzierzawie i uzytkowaniu wieczystym.
    if g.forma.wymaga_oplaty_rocznej and g.oplata_roczna is None:
        raise BladWalidacji(
            f"Forma gruntu '{g.forma.value}' rozlicza sie oplata roczna, a "
            "'grunt.oplata_roczna' nie zostala podana. Silnik nie podstawia wartosci "
            "domyslnych — bez tej kwoty nie da sie policzyc kosztow biezacych."
        )
    if g.oplata_roczna is not None:
        if g.oplata_roczna < 0:
            raise BladWalidacji("'grunt.oplata_roczna' nie moze byc ujemna.")
        if not g.forma.wymaga_oplaty_rocznej and g.oplata_roczna > ZERO:
            ostrzezenia.append(
                Ostrzezenie(
                    kod="OPLATA_ROCZNA_BEZ_ZASTOSOWANIA",
                    tresc=(
                        f"Podano 'grunt.oplata_roczna' = {g.oplata_roczna:.2f} zl, ale forma "
                        f"'{g.forma.value}' nie wiaze sie z oplata roczna. Kwota jest pomijana."
                    ),
                    podstawa="",
                    tresc_potoczna=(
                        "Wpisana opłata roczna za grunt nie jest uwzględniana — wybrana forma "
                        "nie wiąże się z opłatami rocznymi."
                    ),
                    waga=Waga.POZOSTALE,
                )
            )

    # 4. "Lokal za grunt" — rozliczenie lokalami wymaga podania, iloma.
    if g.rozliczany_lokalami:
        # Pochodzenie inne niz gmina jest juz odciete walidacja 1; komunikat
        # zostaje osobno, bo to najczestsza pomylka konfiguracyjna.
        if g.pochodzenie is not PochodzenieGruntu.GMINA:
            raise BladWalidacji(
                "Forma 'lokal_za_grunt' jest mozliwa wylacznie przy pochodzeniu 'gmina' — "
                "cene rozlicza sie lokalami z gmina, nie z podmiotem prywatnym."
            )
        if g.liczba_lokali_dla_gminy <= 0:
            raise BladWalidacji(
                "Forma 'lokal_za_grunt' wymaga podania 'grunt.liczba_lokali_dla_gminy'. "
                "Liczba i powierzchnia przekazywanych lokali sa przedmiotem uchwaly rady "
                "gminy (ustawa z 16.12.2020, Dz.U. 2021 poz. 223), wiec sa negocjowane, "
                "a nie domyslne."
            )
        if g.pum_lokali_dla_gminy <= ZERO:
            raise BladWalidacji(
                "Forma 'lokal_za_grunt' wymaga podania 'grunt.pum_lokali_dla_gminy' — "
                "powierzchni uzytkowej lokali przekazywanych gminie."
            )
        if g.pum_lokali_dla_gminy >= w.powierzchnie.pum_laczne:
            raise BladWalidacji(
                f"'grunt.pum_lokali_dla_gminy' ({g.pum_lokali_dla_gminy}) nie moze siegac "
                f"calej powierzchni przedsiewziecia ({w.powierzchnie.pum_laczne}). "
                "Po przekazaniu lokali gminie musi zostac powierzchnia na wynajem."
            )
    elif g.liczba_lokali_dla_gminy or g.pum_lokali_dla_gminy > ZERO:
        # Nie blad: liczba i powierzchnia lokali sa przedmiotem negocjacji z gmina,
        # wiec moga byc podane zawczasu i czekac na przelaczenie formy. Widok
        # porownawczy form gruntu bez nich nie policzy wariantu lokalowego.
        ostrzezenia.append(
            Ostrzezenie(
                kod="LOKALE_DLA_GMINY_BEZ_ZASTOSOWANIA",
                tresc=(
                    f"Podano lokale dla gminy ({g.liczba_lokali_dla_gminy} szt., "
                    f"{g.pum_lokali_dla_gminy} m2) przy formie '{g.forma.value}'. "
                    "Rozliczenie ceny lokalami wystepuje tylko w trybie 'lokal_za_grunt', "
                    "wiec te wielkosci sa pomijane w obliczeniu."
                ),
                podstawa="ustawa z 16.12.2020, Dz.U. 2021 poz. 223",
                tresc_potoczna=(
                    "Lokale dla gminy nie są tu uwzględniane — wybrana forma gruntu nie "
                    "rozlicza ceny lokalami. Posłużą do porównania form."
                ),
                waga=Waga.POZOSTALE,
            )
        )
        if g.pum_lokali_dla_gminy >= w.powierzchnie.pum_laczne:
            raise BladWalidacji(
                f"'grunt.pum_lokali_dla_gminy' ({g.pum_lokali_dla_gminy}) siega calej "
                f"powierzchni przedsiewziecia ({w.powierzchnie.pum_laczne}). Po przekazaniu "
                "lokali gminie musi zostac powierzchnia na wynajem."
            )

    # 5. Odczyt alternatywny kwestii 9.3 wymaga ceny po bonifikacie.
    if not w.przelaczniki.pasmo_liczone_od_wartosci_z_operatu:
        if g.forma is not FormaGruntu.NABYCIE_OD_GMINY:
            ostrzezenia.append(
                Ostrzezenie(
                    kod="BONIFIKATA_BEZ_ZASTOSOWANIA",
                    tresc=(
                        "Przelacznik 'pasmo_liczone_od_wartosci_z_operatu' jest wylaczony, ale "
                        f"forma '{g.forma.value}' nie jest sprzedaza przez gmine, wiec bonifikaty "
                        "nie ma. Pasmo liczone od wartosci z operatu."
                    ),
                    podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
                    tresc_potoczna=(
                        "Ustawienie o bonifikacie nie ma tu zastosowania — działka nie jest "
                        "kupowana od gminy."
                    ),
                    waga=Waga.POZOSTALE,
                )
            )
        elif g.cena_nabycia is None:
            raise BladWalidacji(
                "Przelacznik 'pasmo_liczone_od_wartosci_z_operatu' jest wylaczony, wiec pasmo "
                "dotacji ma sie liczyc od ceny po bonifikacie — a 'grunt.cena_nabycia' nie "
                "zostala podana. Silnik nie zgaduje wysokosci bonifikaty: podaj cene albo "
                "wroc do odczytu domyslnego (wartosc z operatu)."
            )
        elif g.cena_nabycia > g.wartosc:
            raise BladWalidacji(
                f"'grunt.cena_nabycia' ({g.cena_nabycia}) przewyzsza wartosc z operatu "
                f"({g.wartosc}). Bonifikata obniza cene, nie podnosi jej."
            )


def _waliduj_rynek(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    """Stawka rynkowa jest opcjonalna, ale nie moze byc anonimowa.

    Errata nr 1, rozdz. 3.1: pole `zrodlo` jest obowiazkowe, gdy podano wartosc.
    Liczba bez zrodla wyglada w wyniku identycznie jak dana rzeczywista i wchodzi
    do rozmowy z gmina jako argument — a nikt jej pozniej nie odtworzy.
    """
    r = w.rynek
    if not r.podano:
        if r.zrodlo or r.data:
            ostrzezenia.append(
                Ostrzezenie(
                    kod="RYNEK_ZRODLO_BEZ_WARTOSCI",
                    tresc=(
                        "W sekcji 'rynek' podano zrodlo albo date, ale nie podano samej "
                        "stawki 'czynsz_rynkowy_m2_mies'. Sufit rynkowy pozostaje nieznany."
                    ),
                    podstawa="",
                    tresc_potoczna=(
                        "Podano opis źródła stawki rynkowej, ale nie samą stawkę — "
                        "narzędzie nadal jej nie zna."
                    ),
                    waga=Waga.POZOSTALE,
                )
            )
        return

    if r.czynsz_rynkowy_m2_mies <= ZERO:
        raise BladWalidacji(
            "'rynek.czynsz_rynkowy_m2_mies' musi byc dodatni. Zeby zostawic stawke "
            "nieznana, usun to pole zamiast wpisywac zero."
        )
    if not r.zrodlo:
        raise BladWalidacji(
            "Podano 'rynek.czynsz_rynkowy_m2_mies', ale nie podano 'rynek.zrodlo'. "
            "Stawka rynkowa jest obserwacja, nie wyliczeniem — bez wskazania, skad "
            "pochodzi, nie da sie jej pozniej zweryfikowac ani odtworzyc wyniku. "
            "Wpisz np. 'mediana z 15 ofert najmu 40-55 m2, otodom, 2026-08'."
        )
    if r.data is None:
        ostrzezenia.append(
            Ostrzezenie(
                kod="RYNEK_BEZ_DATY",
                tresc=(
                    "Stawka rynkowa nie ma podanej daty obserwacji. Rynek najmu zmienia "
                    "sie szybciej niz wskazniki ustawowe — bez daty nie wiadomo, jak stara "
                    "jest ta liczba."
                ),
                podstawa="",
                tresc_potoczna=(
                    "Stawka rynkowa nie ma daty. Warto ją dopisać — rynek najmu zmienia się "
                    "szybko."
                ),
                waga=Waga.POZOSTALE,
            )
        )


def _waliduj_eksploatacje(w: Wejscie) -> None:
    e = w.eksploatacja
    if not (ZERO <= e.pustostany_procent <= 1):
        raise BladWalidacji(
            f"'eksploatacja.pustostany_procent' musi miescic sie w przedziale 0.0-1.0, "
            f"jest {e.pustostany_procent}. Wskaznik podaje sie jako ulamek (0,05 nie 5)."
        )
    for nazwa in (
        "koszt_eksploatacji_m2_rok",
        "odpis_remontowy_m2_rok",
        "ubezpieczenie_rocznie",
        "koszty_stale_zarzadu_rocznie",
    ):
        if getattr(e, nazwa) < 0:
            raise BladWalidacji(f"'eksploatacja.{nazwa}' nie moze byc ujemny.")


def _waliduj_parametry(
    w: Wejscie, ostrzezenia: List[Ostrzezenie], na_dzien: Optional[_dt.date]
) -> None:
    p = w.parametry_zewnetrzne
    if p.wartosc_odtworzeniowa_m2 <= 0:
        raise BladWalidacji(
            "'parametry_zewnetrzne.wartosc_odtworzeniowa_m2' musi byc dodatnia — "
            "wartosc pochodzi z obwieszczenia wojewody."
        )
    if p.okres_amortyzacji_budynkow_lat <= 0:
        raise BladWalidacji(
            "'parametry_zewnetrzne.okres_amortyzacji_budynkow_lat' musi byc dodatni — "
            "limituje okres powierzenia w sciezce kredytowej (§ 11 rozp. t.j. Dz.U. 2021 poz. 766)."
        )
    for nazwa in (
        "stopa_bazowa_ke",
        "stopa_referencyjna_ke",
        "stopa_dyskontowa",
        "stopa_irs_bgk",
    ):
        wartosc = getattr(p, nazwa)
        if wartosc < 0:
            raise BladWalidacji(f"'parametry_zewnetrzne.{nazwa}' nie moze byc ujemna.")
        if wartosc > 1:
            raise BladWalidacji(
                f"'parametry_zewnetrzne.{nazwa}' = {wartosc} wyglada na wartosc procentowa. "
                "Stopy podaje sie jako ulamki dziesietne (0,035 nie 3,5)."
            )

    wiek = p.wiek_miesiecy(na_dzien)
    if wiek > prawo.PARAMETRY_MAKSYMALNY_WIEK_MIESIECY:
        ostrzezenia.append(
            Ostrzezenie(
                kod="PARAMETRY_PRZETERMINOWANE",
                tresc=(
                    f"Parametry zewnetrzne pochodza z {p.data_parametrow.isoformat()}, "
                    f"czyli sprzed {wiek} miesiecy. Prog to "
                    f"{prawo.PARAMETRY_MAKSYMALNY_WIEK_MIESIECY} miesiecy. Stopy KE, IRS BGK "
                    "i wartosc odtworzeniowa zmieniaja sie miedzy edycjami programu — "
                    "przed naborem odswiez wszystkie."
                ),
                podstawa="wymog metodyczny, rozdz. 4.4 specyfikacji",
            
                tresc_potoczna=(
                    "Wskaźniki rynkowe pochodzą sprzed ponad pół roku. Wynik będzie orientacyjny, "
                    "dopóki ich nie odświeżysz."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )
    brakujace_zrodla = [
        nazwa
        for nazwa in (
            "wartosc_odtworzeniowa_m2",
            "stopa_bazowa_ke",
            "stopa_referencyjna_ke",
            "stopa_dyskontowa",
            "stopa_irs_bgk",
            "waloryzacja_partycypacji_rocznie",
            "okres_amortyzacji_budynkow_lat",
        )
        if nazwa not in p.zrodla
    ]
    if brakujace_zrodla:
        ostrzezenia.append(
            Ostrzezenie(
                kod="BRAK_ZRODLA_PARAMETRU",
                tresc=(
                    "Parametry zewnetrzne bez wskazanego zrodla: "
                    + ", ".join(brakujace_zrodla)
                    + ". Kazdy parametr zewnetrzny ma miec w YAML zrodlo i date, inaczej "
                    "wyniku nie da sie odtworzyc."
                ),
                podstawa="wymog metodyczny, rozdz. 4.4 specyfikacji",
            
                tresc_potoczna=(
                    "Część wskaźników rynkowych nie ma podanego źródła. Bez tego nie da się później "
                    "odtworzyć, na czym liczono."
                ),
                waga=Waga.POZOSTALE,
            )
        )

    _waliduj_bufor_obslugi_dlugu(w, ostrzezenia)


def _waliduj_bufor_obslugi_dlugu(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    """Bufor obslugi dlugu jest zalozeniem — i ma byc widoczny jako zalozenie.

    Pakiet naprawczy nr 2, rozdz. 1. Ostrzezenie idzie za kazdym razem, gdy
    sciezka kredytowa jest wlaczona, niezaleznie od tego, czy wartosc wpisano
    recznie, czy weszla domyslna. Nie chodzi o brak wpisu, tylko o to, ze samej
    liczby nie ma z czego odczytac: nie podaje jej ani rozporzadzenie
    o finansowaniu zwrotnym, ani informator BGK.
    """
    if not w.pula_spoleczna.kredyt.aktywny:
        return                              # bez kredytu nie ma czego buforowac
    if w.powierzchnie.udzial_puli_komunalnej >= 1:
        return                              # sama pula komunalna — kredyt tam nie wchodzi
    wskaznik = w.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
    if wskaznik == prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_MINIMUM:
        ostrzezenia.append(
            Ostrzezenie(
                kod="BUFOR_OBSLUGI_DLUGU_ZEROWY",
                tresc=(
                    "Kredyt maksymalny wymierzony przy wskazniku pokrycia obslugi dlugu "
                    "1,00 — cala nadwyzka operacyjna idzie na rate, bez marginesu. "
                    "Pierwsze odchylenie od zalozen (pustostan ponad plan, awaria, wzrost "
                    "kosztow energii) daje niedobor na racie. Zaden bank tak nie kredytuje."
                ),
                podstawa="pakiet naprawczy nr 2, rozdz. 1 — zalozenie modelu",
                tresc_potoczna=(
                    "Kredyt policzony bez marginesu bezpieczeństwa: cała nadwyżka z czynszu "
                    "idzie na ratę. To wynik graniczny, a nie kwota, którą bank przyzna."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )
        return
    ostrzezenia.append(
        Ostrzezenie(
            kod="ZALOZENIE_BUFOR_OBSLUGI_DLUGU",
            tresc=(
                f"Kredyt maksymalny wymierzony przy wskazniku pokrycia obslugi dlugu "
                f"{wskaznik:.2f}. Wartosc jest ZALOZENIEM, nie odczytem: ani rozporzadzenie "
                "o finansowaniu zwrotnym, ani informator BGK nie podaja wymaganego pokrycia. "
                f"{wskaznik:.2f} jest poziomem typowym dla kredytowania nieruchomosci "
                "przychodowych. Do potwierdzenia w BGK przed naborem — inny wskaznik zmienia "
                "kwote kredytu, a przez to wymagany wklad wlasny."
            ),
            podstawa="pakiet naprawczy nr 2, rozdz. 1 — zalozenie do potwierdzenia w BGK",
            tresc_potoczna=(
                f"Przyjęto, że bank wymaga zapasu {wskaznik:.2f}× na obsługę kredytu. "
                "Tej liczby nie ma w żadnym dokumencie programu — trzeba ją potwierdzić w BGK."
            ),
            waga=Waga.ZMIENIA_KWOTE,
        )
    )


def _waliduj_przelaczniki(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> None:
    pz = w.przelaczniki
    hybryda = ZERO < w.powierzchnie.udzial_puli_komunalnej < 1
    if hybryda:
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_HYBRYDA",
                tresc=(
                    "Wariant hybrydowy. Przyjeto, ze hybryda to "
                    + (
                        "JEDNO przedsiewziecie ze wspolnym limitem wsparcia"
                        if pz.hybryda_jako_jedno_przedsiewziecie
                        else "DWA odrebne przedsiewziecia — dwa wnioski, dwa okresy powierzenia, "
                        "dwa testy rekompensaty"
                    )
                    + ". To ZALOZENIE, nie rozstrzygniecie — art. 13 ust. 1a czyta sie dwojako. "
                    "Do potwierdzenia w BGK. Kwestia otwarta 10.1."
                ),
                podstawa="art. 13 ust. 1a w zw. z art. 5a ust. 1 i 3 ustawy z 8.12.2006",
            
                tresc_potoczna=(
                    "Część mieszkań idzie do gminy, część na wynajem społeczny. Przyjęto, że są to dwie "
                    "odrębne inwestycje z osobnymi wnioskami. To założenie — potwierdź je w Banku, "
                    "bo zmienia wysokość dotacji."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )
    if pz.metoda_rozsadnego_zysku is MetodaRozsadnegoZysku.KWOTA_WPROST and (
        w.rekompensata.rozsadny_zysk_kwota is None
    ):
        raise BladWalidacji(
            "Metoda rozsadnego zysku 'kwota_wprost' wymaga podania "
            "'rekompensata.rozsadny_zysk_kwota'. Silnik nie podstawia wartosci domyslnej."
        )
    if w.powierzchnie.udzial_puli_komunalnej > 0 and w.eksploatacja.pustostany_procent > 0:
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_PUSTOSTANY_KOMUNALNE",
                tresc=(
                    "Wskaznik pustostanow "
                    + (
                        "obciaza takze pule komunalna"
                        if pz.pustostany_takze_w_puli_komunalnej
                        else "NIE obciaza puli komunalnej — przyjeto, ze najemca calej puli "
                        "jest gmina i ryzyko pustostanu zostaje po jej stronie"
                    )
                    + ". ZALOZENIE modelowe: przesuwa przychod puli komunalnej, a wiec i wynik "
                    "testu 2. Sprawdz, co mowi projekt umowy z gmina."
                ),
                podstawa="zalozenie modelowe, nie przepis",
            
                tresc_potoczna=(
                    "Przyjęto, że pustostany obciążają tylko mieszkania społeczne, bo najemcą całej "
                    "puli komunalnej jest gmina. Sprawdź, co mówi projekt umowy z gminą."
                ),
                waga=Waga.POZOSTALE,
            )
        )
    ostrzezenia.append(
        Ostrzezenie(
            kod="ZALOZENIE_KOSZTY_INWESTYCYJNE_W_KN",
            tresc=(
                "Naklad inwestycyjny wchodzi do kosztow UOIG w ujeciu "
                f"'{pz.koszty_inwestycyjne_w_kn.value}'. Specyfikacja odsyla do katalogu "
                "z art. 5 ust. 7-8 ustawy z 8.12.2006, ale go nie przytacza, a wybor ujecia "
                "zmienia koszty netto o rzad wielkosci — a wiec i wynik testu 3. "
                "ZALOZENIE do potwierdzenia w BGK. Patrz LUKI.md."
            ),
            podstawa="art. 5 ust. 7-8 ustawy z 8.12.2006 — katalog nieprzytoczony w specyfikacji",
        
                tresc_potoczna=(
                    "Sposób rozliczenia nakładu inwestycyjnego przesądza o tym, ile dotacji wolno "
                    "przyjąć. To założenie do potwierdzenia w Banku — potrafi odwrócić wynik."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
    )
    ostrzezenia.append(
        Ostrzezenie(
            kod="ZALOZENIE_ROZSADNY_ZYSK",
            tresc=(
                "Rozsadny zysk liczony metoda "
                f"'{pz.metoda_rozsadnego_zysku.value}'. Specyfikacja wskazuje zrodlo stopy "
                "(IRS 20-letni na bazie WIBOR 3M z BIP BGK), ale nie podaje wzoru — "
                "przyjeta metoda jest ZALOZENIEM do potwierdzenia w Banku. Patrz LUKI.md."
            ),
            podstawa="§ 6 ust. 5 rozp. Dz.U. 2025 poz. 1897; § 12 ust. 10 rozp. Dz.U. 2021 poz. 766",
        
                tresc_potoczna=(
                    "Godziwy zysk inwestora liczony jest metodą przyjętą założeniowo — przepisy "
                    "wskazują źródło stopy, ale nie podają wzoru. Do potwierdzenia w Banku."
                ),
                waga=Waga.POZOSTALE,
            )
    )
