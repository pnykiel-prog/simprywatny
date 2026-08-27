"""Stale prawne — jedyne miejsce w projekcie z liczbami pochodzacymi z ustaw.

Jezeli liczba z przepisu pojawia sie w innym module, jest to blad do naprawienia,
nawet gdy wynik jest poprawny.

Teksty jednolite obowiazujace w sierpniu 2026 r.:
  * ustawa z 26.10.1995 o spolecznych formach rozwoju mieszkalnictwa
    — t.j. Dz.U. 2025 poz. 1273, ze zm. Dz.U. 2026 poz. 39 i poz. 986   [dalej: u.s.f.r.m.]
  * ustawa z 8.12.2006 o finansowym wsparciu niektorych przedsiewziec mieszkaniowych
    — t.j. Dz.U. 2026 poz. 511                                          [dalej: u.f.w.]
  * ustawa z 25.07.2025 o zmianie ustawy o spolecznych formach rozwoju mieszkalnictwa
    — Dz.U. 2025 poz. 1077
  * rozp. RM z 20.10.2015 o warunkach finansowania zwrotnego
    — t.j. Dz.U. 2021 poz. 766, ze zm. Dz.U. 2024 poz. 1732             [dalej: rozp. 766]
  * rozp. MFiG z 29.12.2025 o finansowym wsparciu — Dz.U. 2025 poz. 1897 [dalej: rozp. 1897]
  * rozp. RM z 11.08.2004 o obliczaniu wartosci pomocy publicznej
    — t.j. Dz.U. 2018 poz. 461                                          [dalej: rozp. EDB]
  * rozp. MIiR z 4.03.2019 o standardach — Dz.U. 2019 poz. 457          [dalej: rozp. 457]

Konwencja: udzialy i limity procentowe trzymane jako Decimal, bo mnoza kwoty.
Nazwy dziedzinowe po polsku — "rekompensata" to termin ustawowy o precyzyjnym
znaczeniu, ktorego angielskie "compensation" nie oddaje.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

# --------------------------------------------------------------------------
# 3.1. Wysokosc wsparcia
# --------------------------------------------------------------------------

# art. 13 ust. 1 pkt 1 u.f.w. — limit podstawowy wsparcia dla przedsiewziecia
# z art. 5 ust. 1 pkt 1 (pula spoleczna)
GRANT_SPOLECZNY_LIMIT_PODSTAWOWY = Decimal("0.45")

# art. 13 ust. 1 pkt 1 u.f.w. — czesc ponad ten prog pokrywana wylacznie do
# wysokosci wartosci prawa wlasnosci albo uzytkowania wieczystego gruntu
# bedacego we wladaniu inwestora
GRANT_SPOLECZNY_PROG_GRUNTOWY = Decimal("0.35")

# art. 13 ust. 1 pkt 3 lit. c u.f.w. w zw. z art. 5a ust. 1 — pula komunalna
GRANT_KOMUNALNY = Decimal("0.80")

# art. 13 ust. 4 u.f.w. — bonus rewitalizacyjny / "Za zyciem", +5 punktow
# procentowych; przepis wylacza go wprost przy finansowaniu zwrotnym
BONUS_REWITALIZACYJNY_PP = Decimal("0.05")

# art. 13 ust. 1a u.f.w. — gdy przedsiewziecie obejmuje koszty objete roznymi
# limitami, wsparcie nie moze przekroczyc tego udzialu; wyjatek dla art. 5a ust. 1.
# Stosowane tylko przy przelaczniku hybryda_jako_jedno_przedsiewziecie = True
# (kwestia otwarta 10.1 specyfikacji).
GRANT_HYBRYDA_LIMIT_LACZNY = Decimal("0.45")

# --------------------------------------------------------------------------
# 3.2. Finansowanie zwrotne
# --------------------------------------------------------------------------

# art. 15b ust. 2 u.s.f.r.m. — maksymalny udzial kredytu w kosztach przedsiewziecia
KREDYT_MAKSYMALNY_UDZIAL = Decimal("0.80")

# art. 15b ust. 3 u.s.f.r.m. — maksymalny okres kredytowania, wliczajac karencje
KREDYT_MAKSYMALNY_OKRES_LAT = 30

# art. 5a ust. 3 u.f.w. — rozlacznosc konstrukcyjna, nie limit: przedsiewziecie
# z art. 5a ust. 1 nie moze byc finansowane kredytem SBC
KREDYT_W_PULI_KOMUNALNEJ_DOPUSZCZALNY = False

# --------------------------------------------------------------------------
# 3.3. Limity czynszu
# --------------------------------------------------------------------------

# art. 7c u.f.w. — procent wartosci odtworzeniowej lokalu rocznie, zalezny od
# udzialu wsparcia w kosztach przedsiewziecia. Progi czytane jako "co najmniej".
# Tabela od najwyzszego progu, zeby wyszukiwanie bralo pierwszy pasujacy.
LIMIT_CZYNSZU_ART_7C: Tuple[Tuple[Decimal, Decimal], ...] = (
    (Decimal("0.90"), Decimal("0.020")),   # co najmniej 90% wsparcia -> 2,0%
    (Decimal("0.75"), Decimal("0.025")),   # co najmniej 75%          -> 2,5%
    (Decimal("0.60"), Decimal("0.030")),   # co najmniej 60%          -> 3,0%
    (Decimal("0.45"), Decimal("0.035")),   # co najmniej 45%          -> 3,5%
    (Decimal("0.00"), Decimal("0.040")),   # ponizej 45%              -> 4,0%
)

# art. 7c u.f.w. — przedsiewziecie polegajace na remoncie i przebudowie
# (art. 5 ust. 1 pkt 2 u.f.w.)
LIMIT_CZYNSZU_REMONT_I_PRZEBUDOWA = Decimal("0.050")

# art. 28 ust. 2 pkt 2 u.s.f.r.m. — niezalezny limit dla lokali wybudowanych
# przy wykorzystaniu finansowania zwrotnego
LIMIT_CZYNSZU_FINANSOWANIE_ZWROTNE = Decimal("0.050")

# art. 28 ust. 4-5 u.s.f.r.m. — oplaty za OZE, termomodernizacje, dostepnosc
# i rewitalizacje pobierane OBOK czynszu, lacznie do 1% wartosci odtworzeniowej
# rocznie. Osobny strumien, nigdy nie doliczany do czynszu.
LIMIT_OPLAT_POZA_CZYNSZEM = Decimal("0.010")

# --------------------------------------------------------------------------
# 3.4. Partycypacja
# --------------------------------------------------------------------------

# art. 29a ust. 2b u.s.f.r.m. — od tego progu umowa najmu na czas nieoznaczony
# albo najem instytucjonalny z dojsciem do wlasnosci
PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA = Decimal("0.10")

# art. 29a ust. 2a u.s.f.r.m. — od tego progu nie stosuje sie art. 7b ust. 1
# (wymog czasu oznaczonego min. 5 lat)
PARTYCYPACJA_PROG_WYLACZENIA_ART_7B = Decimal("0.15")

# art. 29a ust. 2 u.s.f.r.m. — gorny limit dla osoby fizycznej przy
# finansowaniu zwrotnym
PARTYCYPACJA_MAKSIMUM = Decimal("0.30")

# art. 29a ust. 3 u.s.f.r.m. — zwrot partycypacji wymagalny nie pozniej niz
# 12 miesiecy od oproznienia lokalu, kwota podlega waloryzacji wskaznikiem
# ceny 1 m2 GUS (sam wskaznik jest parametrem zewnetrznym, nie stala)
PARTYCYPACJA_TERMIN_ZWROTU_MIESIECY = 12

# --------------------------------------------------------------------------
# 3.5. Rekompensata
# --------------------------------------------------------------------------

# art. 5 ust. 10 pkt 1 u.f.w. — okres powierzenia w sciezce grantowej
OKRES_POWIERZENIA_GRANT_LAT = 25

# § 7 ust. 9 rozp. 1897 — prog tolerancji nadwyzki rekompensaty, sciezka grantowa
PROG_TOLERANCJI_NADWYZKI_GRANT = Decimal("0.10")

# § 13 ust. 8 rozp. 766 — prog tolerancji nadwyzki, sciezka kredytowa
PROG_TOLERANCJI_NADWYZKI_KREDYT = Decimal("0.20")

# § 12 ust. 7 rozp. 766 — grunt wniesiony aportem w sciezce kredytowej jest
# kosztem, ale tylko do tego udzialu calkowitych kosztow przedsiewziecia
GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT = Decimal("0.20")

# --------------------------------------------------------------------------
# 3.6. Grunt — matryca skutkow (uzupelnienie nr 2 do specyfikacji, rozdz. 3)
# --------------------------------------------------------------------------
#
# Grunt dziala na wynik czterema niezaleznymi kanalami, ktore nie sumuja sie
# w jeden parametr:
#   A — pasmo dotacji: czy wsparcie moze przekroczyc prog gruntowy i siegnac
#       limitu podstawowego              (art. 13 ust. 1 pkt 1 u.f.w.),
#   B — koszt przedsiewziecia: czy i w jakiej wysokosci wartosc gruntu wchodzi
#       do podstawy                      (art. 5 ust. 7 pkt 7 i ust. 8 u.f.w.;
#                                         § 12 ust. 7 rozp. 766),
#   C — przychod uslugi publicznej: czy grunt obniza koszty netto, a przez to
#       dopuszczalna rekompensate        (art. 5 ust. 9 pkt 4 u.f.w.),
#   D — zapotrzebowanie na gotowke: czy wklad inwestora jest pieniezny,
#       czy rzeczowy                     (poza przepisem — klasyfikacja modelu).
#
# ZAWEZENIE ZAKRESU (pakiet naprawczy nr 2, rozdz. 11): aport dzialki przez gmine
# zostal usuniety z listy form. Gmina obejmuje wtedy udzialy — przy dzialce
# porownywalnej z wkladem inwestora wychodzi jej wiekszosc — a wraz z nia stawki
# czynszu ustala zgromadzenie wspolnikow (art. 28 ust. 1 ustawy z 26.10.1995).
# Suwak czynszu przestaje byc dzwignia inwestora, glowna liczba wyjsciowa traci
# sens, a wykres negocjacyjny nie ma z kim negocjowac. To nie jest wariant
# prywatnego SIM z komplikacja, tylko inny podmiot — narzedzie odpowiadaloby
# poprawnie na pytanie, ktorego nikt nie zadal.
#
# Kolumna E ("gmina wspolnikiem") zostaje w matrycy pusta we wszystkich wierszach.
# Nie usuwam jej: aport inwestora nadal istnieje, wiec logika aportu zyje, a gdyby
# zakres kiedys wrocil, wiersz da sie dopisac bez przebudowy struktury.

# Oznaczenia pewnosci wg rozdz. 3 uzupelnienia nr 2.
PEWNOSC_ZRODLO = "Z"             # odczytane wprost w przepisie
PEWNOSC_WNIOSEK = "W"            # wniosek z odczytanych przepisow
PEWNOSC_DO_POTWIERDZENIA = "?"   # wymaga potwierdzenia w BGK

# Pochodzenie dzialki — poziom 1 pytania do uzytkownika (rozdz. 2).
POCHODZENIE_INWESTOR = "inwestor"
POCHODZENIE_RYNEK_PRYWATNY = "rynek_prywatny"
POCHODZENIE_GMINA = "gmina"

# Rodzaj wydatku na grunt (kanal D). Nie jest to kategoria ustawowa, tylko
# klasyfikacja na potrzeby montazu — decyduje o tym, ile gotowki trzeba wylozyc.
WYDATEK_PELNY = "pelny"                            # cena placona w pieniadzu
WYDATEK_BRAK = "brak"                              # wklad rzeczowy, bez gotowki
WYDATEK_PONIESIONY_WCZESNIEJ = "poniesiony_wczesniej"
WYDATEK_OPLATY_ROCZNE = "oplaty_roczne"            # dzierzawa, uzytkowanie wieczyste
WYDATEK_LOKALE = "lokale"                          # rozliczenie lokalami


@dataclass(frozen=True)
class SkutkiFormyGruntu:
    """Jeden wiersz matrycy skutkow z rozdz. 3 uzupelnienia nr 2.

    Pola z sufiksem `_pewnosc` niosa oznaczenie zrodla (Z / W / ?), zeby arkusz
    i interfejs mogly pokazac, ktory skutek jest odczytany w przepisie, a ktory
    jest wnioskiem albo zalozeniem. `przelacznik_przychodu` wskazuje przelacznik
    rozstrzygajacy kanal C tam, gdzie odczyt nie jest przesadzony (kwestie 9.1 i 9.2).
    """

    forma: str
    pochodzenie: str
    # kanal A
    pasmo_45: bool
    pasmo_45_pewnosc: str
    # kanal B
    wartosc_w_kosztach: bool
    limit_aportowy: bool          # § 12 ust. 7 rozp. 766 — tylko sciezka kredytowa
    wartosc_w_kosztach_pewnosc: str
    # kanal C
    przychod_uoig: bool           # wartosc domyslna; przelacznik moze ja odwrocic
    przychod_uoig_pewnosc: str
    przelacznik_przychodu: str
    # kanal D
    wydatek: str
    # kanal E
    gmina_wspolnikiem: bool
    # warstwa interakcji — rozdz. 7.2
    etykieta: str
    podpis: str
    podstawa: str

    @property
    def wnoszony_aportem(self) -> bool:
        """Aport jest wkladem niepienieznym — § 12 ust. 6 i 7 rozp. 766."""
        return self.limit_aportowy

    @property
    def z_oplata_roczna(self) -> bool:
        return self.wydatek == WYDATEK_OPLATY_ROCZNE

    @property
    def wymaga_potwierdzenia(self) -> bool:
        return PEWNOSC_DO_POTWIERDZENIA in (
            self.pasmo_45_pewnosc,
            self.wartosc_w_kosztach_pewnosc,
            self.przychod_uoig_pewnosc,
        )


# Kolejnosc wierszy odpowiada matrycy z rozdz. 3 i jest kolejnoscia prezentacji
# w interfejsie oraz w widoku porownawczym form gruntu.
MATRYCA_GRUNTU: Tuple[SkutkiFormyGruntu, ...] = (
    SkutkiFormyGruntu(
        forma="aport_inwestora",
        pochodzenie=POCHODZENIE_INWESTOR,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=True, limit_aportowy=True,
        wartosc_w_kosztach_pewnosc=PEWNOSC_ZRODLO,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_WNIOSEK,
        przelacznik_przychodu="",
        wydatek=WYDATEK_BRAK,
        gmina_wspolnikiem=False,
        etykieta="Wnoszę działkę aportem",
        podpis=(
            "Nie wydajesz gotówki na grunt, ale w ścieżce kredytowej do kosztów "
            "wejdzie tylko 20% wartości działki."
        ),
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006; § 12 ust. 7 rozp. t.j. Dz.U. 2021 poz. 766",
    ),
    SkutkiFormyGruntu(
        forma="spolka_wlascicielem",
        pochodzenie=POCHODZENIE_INWESTOR,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=True, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_WNIOSEK,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_WNIOSEK,
        przelacznik_przychodu="",
        wydatek=WYDATEK_PONIESIONY_WCZESNIEJ,
        gmina_wspolnikiem=False,
        etykieta="Spółka już jest właścicielem",
        podpis=(
            "Działka jest w spółce, wydatek został poniesiony wcześniej. "
            "Pełna wartość wchodzi do kosztów i podnosi dotację."
        ),
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006; art. 5 ust. 7 pkt 7 i ust. 8",
    ),
    SkutkiFormyGruntu(
        forma="nabycie_prywatne",
        pochodzenie=POCHODZENIE_RYNEK_PRYWATNY,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=True, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_WNIOSEK,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_WNIOSEK,
        przelacznik_przychodu="",
        wydatek=WYDATEK_PELNY,
        gmina_wspolnikiem=False,
        etykieta="Kupuję od podmiotu prywatnego",
        podpis=(
            "Zwykłe nabycie za gotówkę. Pełna wartość wchodzi do kosztów, "
            "bez skutków ubocznych."
        ),
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006; art. 5 ust. 7 pkt 7 i ust. 8",
    ),
    SkutkiFormyGruntu(
        forma="nabycie_od_gminy",
        pochodzenie=POCHODZENIE_GMINA,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=True, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_WNIOSEK,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_WNIOSEK,
        przelacznik_przychodu="",
        wydatek=WYDATEK_PELNY,
        gmina_wspolnikiem=False,
        etykieta="Gmina sprzedaje działkę",
        podpis=(
            "Zwykłe nabycie. Podnosi zapotrzebowanie na gotówkę, "
            "ale nie ma skutków ubocznych."
        ),
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006; art. 5 ust. 7 pkt 7 i ust. 8",
    ),
    SkutkiFormyGruntu(
        forma="lokal_za_grunt",
        pochodzenie=POCHODZENIE_GMINA,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_WNIOSEK,
        wartosc_w_kosztach=True, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_WNIOSEK,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_DO_POTWIERDZENIA,
        przelacznik_przychodu="lokal_za_grunt_jest_przychodem_uoig",
        wydatek=WYDATEK_LOKALE,
        gmina_wspolnikiem=False,
        etykieta="Lokal za grunt",
        podpis=(
            "Płacisz gminie lokalami zamiast pieniędzmi. Nie wydajesz gotówki, "
            "ale część mieszkań nie będzie Twoja."
        ),
        podstawa=(
            "ustawa z 16.12.2020, Dz.U. 2021 poz. 223; art. 13 ust. 1 pkt 1 ustawy z 8.12.2006"
        ),
    ),
    SkutkiFormyGruntu(
        forma="uzytkowanie_wieczyste",
        pochodzenie=POCHODZENIE_GMINA,
        pasmo_45=True, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=True, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_DO_POTWIERDZENIA,
        przychod_uoig=True, przychod_uoig_pewnosc=PEWNOSC_DO_POTWIERDZENIA,
        przelacznik_przychodu="uzytkowanie_wieczyste_jest_przychodem_uoig",
        wydatek=WYDATEK_OPLATY_ROCZNE,
        gmina_wspolnikiem=False,
        etykieta="Użytkowanie wieczyste",
        podpis="Płacisz opłaty roczne zamiast ceny. Zachowujesz pełną dotację.",
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006; art. 5 ust. 9 pkt 4",
    ),
    SkutkiFormyGruntu(
        forma="dzierzawa",
        pochodzenie=POCHODZENIE_GMINA,
        pasmo_45=False, pasmo_45_pewnosc=PEWNOSC_ZRODLO,
        wartosc_w_kosztach=False, limit_aportowy=False,
        wartosc_w_kosztach_pewnosc=PEWNOSC_WNIOSEK,
        przychod_uoig=False, przychod_uoig_pewnosc=PEWNOSC_WNIOSEK,
        przelacznik_przychodu="",
        wydatek=WYDATEK_OPLATY_ROCZNE,
        gmina_wspolnikiem=False,
        etykieta="Dzierżawa",
        podpis="Najtańsze wejście, ale dotacja spada z 45% do 35%. Sprawdź, czy się opłaca.",
        podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
    ),
)

SKUTKI_GRUNTU = {wiersz.forma: wiersz for wiersz in MATRYCA_GRUNTU}

# art. 13 ust. 1 pkt 1 u.f.w. mowi o wartosci prawa WLASNOSCI albo UZYTKOWANIA
# WIECZYSTEGO nieruchomosci gruntowej bedacej we wladaniu inwestora. Dzierzawa
# i uzyczenie nie sa zadnym z tych praw, wiec nie odblokowuja pasma ponad prog
# gruntowy — dotacja zatrzymuje sie na GRANT_SPOLECZNY_PROG_GRUNTOWY.
FORMY_DAJACE_PASMO_45 = frozenset(w.forma for w in MATRYCA_GRUNTU if w.pasmo_45)

# § 12 ust. 6 i 7 rozp. 766 — formy bedace wkladem niepienieznym.
FORMY_APORTOWE = frozenset(w.forma for w in MATRYCA_GRUNTU if w.limit_aportowy)

# Formy, przy ktorych rozliczenie z gmina ma postac oplaty rocznej, a nie ceny.
FORMY_Z_OPLATA_ROCZNA = frozenset(w.forma for w in MATRYCA_GRUNTU if w.z_oplata_roczna)

# Poziom 2 pytania do uzytkownika — zestaw form dopuszczalnych dla pochodzenia.
POCHODZENIA_GRUNTU: Tuple[str, ...] = (
    POCHODZENIE_INWESTOR,
    POCHODZENIE_RYNEK_PRYWATNY,
    POCHODZENIE_GMINA,
)

FORMY_WG_POCHODZENIA = {
    pochodzenie: tuple(w.forma for w in MATRYCA_GRUNTU if w.pochodzenie == pochodzenie)
    for pochodzenie in POCHODZENIA_GRUNTU
}

ETYKIETY_POCHODZENIA = {
    POCHODZENIE_INWESTOR: "Inwestor już ma działkę",
    POCHODZENIE_RYNEK_PRYWATNY: "Działkę trzeba kupić od podmiotu prywatnego",
    POCHODZENIE_GMINA: "Działka należy do gminy",
}


def skutki_gruntu(forma: str) -> SkutkiFormyGruntu:
    """Wiersz matrycy skutkow dla danej formy wniesienia gruntu."""
    try:
        return SKUTKI_GRUNTU[str(forma)]
    except KeyError as exc:
        dozwolone = ", ".join(SKUTKI_GRUNTU)
        raise ValueError(
            "Nieznana forma gruntu: %r (dopuszczalne: %s)" % (forma, dozwolone)
        ) from exc


def formy_dla_pochodzenia(pochodzenie: str) -> Tuple[str, ...]:
    """Formy wniesienia dopuszczalne przy danym pochodzeniu dzialki."""
    try:
        return FORMY_WG_POCHODZENIA[str(pochodzenie)]
    except KeyError as exc:
        dozwolone = ", ".join(POCHODZENIA_GRUNTU)
        raise ValueError(
            "Nieznane pochodzenie gruntu: %r (dopuszczalne: %s)" % (pochodzenie, dozwolone)
        ) from exc


# Zalozenia z rozdz. 9 uzupelnienia nr 2 — pozycje oznaczone [?] w matrycy.
# Kazde siedzi na przelaczniku w `dane.Przelaczniki`; wartosc domyslna jest
# ZALOZENIEM, nie odczytem przepisu, i musi byc widoczna w arkuszu.
ZALOZENIA_GRUNTOWE_DO_POTWIERDZENIA = (
    (
        "9.1",
        "lokal_za_grunt_jest_przychodem_uoig",
        False,
        "Czy wartosc gruntu nabytego w trybie 'lokal za grunt' jest przychodem uslugi "
        "publicznej. Przyjeto, ze NIE jest — transakcja jest nabyciem, a nie wniesieniem "
        "przez jednostke samorzadu terytorialnego.",
        "art. 5 ust. 9 pkt 4 ustawy z 8.12.2006",
    ),
    (
        "9.2",
        "uzytkowanie_wieczyste_jest_przychodem_uoig",
        True,
        "Czy wartosc prawa uzytkowania wieczystego ustanowionego przez gmine jest "
        "przychodem uslugi publicznej. Przyjeto wariant ostrozniejszy: JEST przychodem.",
        "art. 5 ust. 9 pkt 4 ustawy z 8.12.2006",
    ),
    (
        "9.3",
        "pasmo_liczone_od_wartosci_z_operatu",
        True,
        "Czy bonifikata przy sprzedazy gruntu przez gmine obniza wartosc przyjmowana do "
        "pasma dotacji. Przyjeto, ze NIE — art. 13 ust. 1 pkt 1 mowi o wartosci prawa, "
        "nie o cenie nabycia, wiec pasmo liczy sie od wartosci z operatu.",
        "art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
    ),
)

# --------------------------------------------------------------------------
# 3.7. Standardy techniczne — rozp. 457
# --------------------------------------------------------------------------

PUM_LOKALU_MIN_M2 = Decimal("25")          # § standardow, rozp. 457
PUM_LOKALU_MAX_M2 = Decimal("80")          # powyzej wylacznie dla rodzin wielodzietnych
DZWIG_OBOWIAZKOWY_OD_KONDYGNACJI = 3       # kondygnacje naziemne
DROGA_PUBLICZNA_MIN_SZEROKOSC_M = Decimal("6")

# --------------------------------------------------------------------------
# Higiena danych wejsciowych (nie jest to stala ustawowa — patrz rozdz. 4 spec.)
# --------------------------------------------------------------------------

# Specyfikacja, rozdz. 4.4: silnik ostrzega, gdy data_parametrow jest starsza
# niz 6 miesiecy. To wymog metodyczny projektu, nie przepis.
PARAMETRY_MAKSYMALNY_WIEK_MIESIECY = 6

# Pakiet naprawczy nr 2, rozdz. 1 — minimalny wskaznik pokrycia obslugi dlugu
# przyjmowany przy WYMIAROWANIU kredytu maksymalnego.
#
# NIE JEST TO STALA USTAWOWA ANI ODCZYT Z DOKUMENTU PROGRAMU. Ani rozporzadzenie
# o finansowaniu zwrotnym, ani informator BGK nie podaja wymaganego pokrycia.
# 1,20 jest wartoscia typowa dla kredytowania nieruchomosci przychodowych
# i wchodzi tu jako ostrozne zalozenie do potwierdzenia w BGK — silnik oznacza
# je ostrzezeniem przy kazdym przeliczeniu ze sciezka kredytowa.
#
# Rozroznienie, ktore latwo zgubic: 1,0 pozostaje progiem TESTU 2 (montaz sie
# spina albo nie), a ponizsza wartosc jest marginesem przyjmowanym przy
# wyznaczaniu kwoty kredytu. Kredyt wymiarowany z buforem daje w projekcji
# pokrycie okolo 1,2 i test przechodzi z zapasem — to sa dwie rozne liczby
# o dwoch roznych rolach, nie jedna liczba w dwoch miejscach.
WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY = Decimal("1.20")

# Ponizej tej wartosci wymiarowanie kredytu nie ma sensu — pokrycie mniejsze
# niz jednosc oznacza rate, ktorej przychod nie unosi juz w chwili wyliczenia.
WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_MINIMUM = Decimal("1.00")


# --------------------------------------------------------------------------
# Odczyt tabel
# --------------------------------------------------------------------------

def limit_czynszu_art_7c(udzial_wsparcia: Decimal, remont_i_przebudowa: bool = False) -> Decimal:
    """Roczny limit czynszu jako udzial wartosci odtworzeniowej lokalu — art. 7c u.f.w.

    `udzial_wsparcia` to udzial wsparcia w kosztach przedsiewziecia (0.0-1.0+).
    Progi czytane jako "co najmniej": 0.449 -> 4,0%, 0.45 -> 3,5%, 0.75 -> 2,5%.
    """
    if remont_i_przebudowa:
        return LIMIT_CZYNSZU_REMONT_I_PRZEBUDOWA
    if udzial_wsparcia < 0:
        raise ValueError("Udzial wsparcia nie moze byc ujemny.")
    for prog, limit in LIMIT_CZYNSZU_ART_7C:
        if udzial_wsparcia >= prog:
            return limit
    raise AssertionError("Tabela art. 7c nie pokrywa wartosci %s" % udzial_wsparcia)


def grunt_aport_maksymalny_w_kosztach(koszty_bez_gruntu: Decimal) -> Decimal:
    """Maksymalna wartosc gruntu z aportu zaliczalna do kosztow przedsiewziecia.

    § 12 ust. 7 rozp. 766: wartosc gruntu wniesionego jako wklad niepienienzy
    zalicza sie do kosztow przedsiewziecia do wysokosci GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT
    calkowitych kosztow przedsiewziecia. Warunek jest samozwrotny, bo wartosc gruntu
    jest skladnikiem tych kosztow. Model rozwiazuje go tak, zeby udzial gruntu
    w KONCOWEJ podstawie wyszedl dokladnie na limicie:

        u = limit * (K_bez_gruntu + u)   =>   u = K_bez_gruntu * limit / (1 - limit)

    Odczyt alternatywny — limit liczony od kosztow z pelna, nieobcieta wartoscia
    gruntu — daje kwote wyzsza i udzial ponizej limitu w podstawie faktycznie
    przyjetej. Patrz LUKI.md.
    """
    if koszty_bez_gruntu <= 0:
        return Decimal(0)
    limit = GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT
    return koszty_bez_gruntu * limit / (Decimal(1) - limit)


def prog_tolerancji_nadwyzki(sciezka: str) -> Decimal:
    """Prog tolerancji nadwyzki rekompensaty wg sciezki wsparcia."""
    if sciezka == "grant":
        return PROG_TOLERANCJI_NADWYZKI_GRANT
    if sciezka == "kredyt":
        return PROG_TOLERANCJI_NADWYZKI_KREDYT
    raise ValueError("Nieznana sciezka wsparcia: %r (dopuszczalne: grant, kredyt)" % sciezka)


# Wykaz do zakladki `Podstawy_prawne` w arkuszu — pary (opis, wartosc, podstawa).
WYKAZ_PODSTAW = (
    ("Grant spoleczny — limit podstawowy", GRANT_SPOLECZNY_LIMIT_PODSTAWOWY,
     "art. 13 ust. 1 pkt 1 ustawy z 8.12.2006"),
    ("Grant spoleczny — prog gruntowy", GRANT_SPOLECZNY_PROG_GRUNTOWY,
     "art. 13 ust. 1 pkt 1 ustawy z 8.12.2006"),
    ("Grant komunalny", GRANT_KOMUNALNY,
     "art. 13 ust. 1 pkt 3 lit. c w zw. z art. 5a ust. 1 ustawy z 8.12.2006"),
    ("Bonus rewitalizacyjny / Za zyciem (pp)", BONUS_REWITALIZACYJNY_PP,
     "art. 13 ust. 4 ustawy z 8.12.2006 — wylaczony przy finansowaniu zwrotnym"),
    ("Limit laczny wsparcia przy hybrydzie jako jednym przedsiewzieciu",
     GRANT_HYBRYDA_LIMIT_LACZNY, "art. 13 ust. 1a ustawy z 8.12.2006"),
    ("Maksymalny udzial kredytu", KREDYT_MAKSYMALNY_UDZIAL,
     "art. 15b ust. 2 ustawy z 26.10.1995"),
    ("Maksymalny okres kredytowania (lata, z karencja)", Decimal(KREDYT_MAKSYMALNY_OKRES_LAT),
     "art. 15b ust. 3 ustawy z 26.10.1995"),
    ("Kredyt w puli komunalnej", Decimal(0),
     "art. 5a ust. 3 ustawy z 8.12.2006 — wykluczony konstrukcyjnie"),
    ("Limit czynszu — wsparcie ponizej 45%", Decimal("0.040"), "art. 7c ustawy z 8.12.2006"),
    ("Limit czynszu — wsparcie co najmniej 45%", Decimal("0.035"), "art. 7c ustawy z 8.12.2006"),
    ("Limit czynszu — wsparcie co najmniej 60%", Decimal("0.030"), "art. 7c ustawy z 8.12.2006"),
    ("Limit czynszu — wsparcie co najmniej 75%", Decimal("0.025"), "art. 7c ustawy z 8.12.2006"),
    ("Limit czynszu — wsparcie co najmniej 90%", Decimal("0.020"), "art. 7c ustawy z 8.12.2006"),
    ("Limit czynszu — remont i przebudowa", LIMIT_CZYNSZU_REMONT_I_PRZEBUDOWA,
     "art. 7c ustawy z 8.12.2006 w zw. z art. 5 ust. 1 pkt 2"),
    ("Limit czynszu — finansowanie zwrotne", LIMIT_CZYNSZU_FINANSOWANIE_ZWROTNE,
     "art. 28 ust. 2 pkt 2 ustawy z 26.10.1995"),
    ("Limit oplat poza czynszem", LIMIT_OPLAT_POZA_CZYNSZEM,
     "art. 28 ust. 4-5 ustawy z 26.10.1995"),
    ("Partycypacja — prog umowy bezterminowej", PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA,
     "art. 29a ust. 2b ustawy z 26.10.1995"),
    ("Partycypacja — prog wylaczenia art. 7b ust. 1", PARTYCYPACJA_PROG_WYLACZENIA_ART_7B,
     "art. 29a ust. 2a ustawy z 26.10.1995"),
    ("Partycypacja — maksimum", PARTYCYPACJA_MAKSIMUM,
     "art. 29a ust. 2 ustawy z 26.10.1995"),
    ("Okres powierzenia — grant (lata)", Decimal(OKRES_POWIERZENIA_GRANT_LAT),
     "art. 5 ust. 10 pkt 1 ustawy z 8.12.2006"),
    ("Prog tolerancji nadwyzki — grant", PROG_TOLERANCJI_NADWYZKI_GRANT,
     "§ 7 ust. 9 rozp. Dz.U. 2025 poz. 1897"),
    ("Prog tolerancji nadwyzki — kredyt", PROG_TOLERANCJI_NADWYZKI_KREDYT,
     "§ 13 ust. 8 rozp. t.j. Dz.U. 2021 poz. 766"),
    ("Grunt z aportu w kosztach — sciezka kredytowa, limit", GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT,
     "§ 12 ust. 7 rozp. t.j. Dz.U. 2021 poz. 766"),
    ("PUM lokalu — minimum (m2)", PUM_LOKALU_MIN_M2, "rozp. MIiR z 4.03.2019, Dz.U. 2019 poz. 457"),
    ("PUM lokalu — maksimum (m2)", PUM_LOKALU_MAX_M2,
     "rozp. MIiR z 4.03.2019 — powyzej wylacznie dla rodzin wielodzietnych"),
    ("Dzwigi osobowe — od kondygnacji", Decimal(DZWIG_OBOWIAZKOWY_OD_KONDYGNACJI),
     "rozp. MIiR z 4.03.2019, Dz.U. 2019 poz. 457"),
    ("Minimalna szerokosc drogi publicznej (m)", DROGA_PUBLICZNA_MIN_SZEROKOSC_M,
     "rozp. MIiR z 4.03.2019, Dz.U. 2019 poz. 457"),
)
