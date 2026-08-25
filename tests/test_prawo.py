"""Etap 1 — testy stalych prawnych i progow (rozdz. 11 specyfikacji)."""

from decimal import Decimal

import pytest

from sim_kalkulator import prawo


class TestProgiCzynszuArt7c:
    """udzial wsparcia 44,9% -> 4,0%; 45,0% -> 3,5%; 75,0% -> 2,5%"""

    def test_ponizej_45_procent_daje_4_procent(self):
        assert prawo.limit_czynszu_art_7c(Decimal("0.449")) == Decimal("0.040")

    def test_dokladnie_45_procent_daje_3_5_procent(self):
        assert prawo.limit_czynszu_art_7c(Decimal("0.450")) == Decimal("0.035")

    def test_dokladnie_75_procent_daje_2_5_procent(self):
        assert prawo.limit_czynszu_art_7c(Decimal("0.750")) == Decimal("0.025")

    @pytest.mark.parametrize(
        "udzial, oczekiwany",
        [
            ("0.000", "0.040"),
            ("0.4499999", "0.040"),
            ("0.45", "0.035"),
            ("0.599999", "0.035"),
            ("0.60", "0.030"),
            ("0.749999", "0.030"),
            ("0.75", "0.025"),
            ("0.899999", "0.025"),
            ("0.90", "0.020"),
            ("1.00", "0.020"),
        ],
    )
    def test_pelna_tabela_progow(self, udzial, oczekiwany):
        assert prawo.limit_czynszu_art_7c(Decimal(udzial)) == Decimal(oczekiwany)

    def test_remont_i_przebudowa_omija_tabele(self):
        assert prawo.limit_czynszu_art_7c(Decimal("0.90"), remont_i_przebudowa=True) == Decimal("0.050")

    def test_ujemny_udzial_wsparcia_to_blad(self):
        with pytest.raises(ValueError):
            prawo.limit_czynszu_art_7c(Decimal("-0.01"))


class TestStaleWsparcia:
    def test_wartosci_z_rozdzialu_3_1(self):
        assert prawo.GRANT_SPOLECZNY_LIMIT_PODSTAWOWY == Decimal("0.45")
        assert prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY == Decimal("0.35")
        assert prawo.GRANT_KOMUNALNY == Decimal("0.80")
        assert prawo.BONUS_REWITALIZACYJNY_PP == Decimal("0.05")

    def test_wartosci_z_rozdzialu_3_2(self):
        assert prawo.KREDYT_MAKSYMALNY_UDZIAL == Decimal("0.80")
        assert prawo.KREDYT_MAKSYMALNY_OKRES_LAT == 30
        assert prawo.KREDYT_W_PULI_KOMUNALNEJ_DOPUSZCZALNY is False

    def test_wartosci_z_rozdzialu_3_4(self):
        assert prawo.PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA == Decimal("0.10")
        assert prawo.PARTYCYPACJA_PROG_WYLACZENIA_ART_7B == Decimal("0.15")
        assert prawo.PARTYCYPACJA_MAKSIMUM == Decimal("0.30")

    def test_wartosci_z_rozdzialu_3_5(self):
        assert prawo.OKRES_POWIERZENIA_GRANT_LAT == 25
        assert prawo.PROG_TOLERANCJI_NADWYZKI_GRANT == Decimal("0.10")
        assert prawo.PROG_TOLERANCJI_NADWYZKI_KREDYT == Decimal("0.20")
        assert prawo.GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT == Decimal("0.20")

    def test_wartosci_z_rozdzialu_3_7(self):
        assert prawo.PUM_LOKALU_MIN_M2 == Decimal("25")
        assert prawo.PUM_LOKALU_MAX_M2 == Decimal("80")
        assert prawo.DZWIG_OBOWIAZKOWY_OD_KONDYGNACJI == 3


class TestProgTolerancji:
    def test_grant_i_kredyt(self):
        assert prawo.prog_tolerancji_nadwyzki("grant") == Decimal("0.10")
        assert prawo.prog_tolerancji_nadwyzki("kredyt") == Decimal("0.20")

    def test_nieznana_sciezka_to_blad(self):
        with pytest.raises(ValueError):
            prawo.prog_tolerancji_nadwyzki("hybryda")


class TestHigienaModulu:
    def test_kazda_stala_ma_podstawe_w_wykazie(self):
        # Wykaz zasila zakladke Podstawy_prawne — czytajacy ma moc zweryfikowac liczby.
        for opis, wartosc, podstawa in prawo.WYKAZ_PODSTAW:
            assert opis and podstawa, opis
            assert isinstance(wartosc, Decimal), opis

    def test_stale_kwotowe_sa_decimalami_nie_floatami(self):
        # Model operuje na pieniadzach przez 30 lat — float w stalej to blad.
        for nazwa in dir(prawo):
            if nazwa.isupper():
                wartosc = getattr(prawo, nazwa)
                assert not isinstance(wartosc, float), nazwa
