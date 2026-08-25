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
