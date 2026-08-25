"""Etap 3 — alokacja kosztow wspolnych kluczem PUM."""

from decimal import Decimal

import pytest

from sim_kalkulator import alokacja

from . import wspolne


def zbuduj(**zmiany):
    w = wspolne.wejscie(**zmiany)
    return w, alokacja.build(w)


class TestKluczPUM:
    def test_koszty_wspolne_dziela_sie_proporcjonalnie_do_pum(self):
        w, a = zbuduj(powierzchnie__udzial_puli_komunalnej=0.25)
        assert a.spoleczna.udzial_pum == Decimal("0.75")
        assert a.komunalna.udzial_pum == Decimal("0.25")
        assert a.komunalna.infrastruktura == Decimal("1200000.0") * Decimal("0.25")

    def test_grunt_nie_jest_liczony_dwa_razy(self):
        # "Nie licz wartosci gruntu dwa razy — raz w kazdej puli."
        w, a = zbuduj(powierzchnie__udzial_puli_komunalnej=0.40)
        assert a.grunt_laczny == w.grunt.wartosc
        assert a.spoleczna.grunt + a.komunalna.grunt == Decimal("2800000.0")

    def test_koszt_budowy_idzie_wprost_wg_wlasnego_pum(self):
        w, a = zbuduj(powierzchnie__udzial_puli_komunalnej=0.30)
        assert a.spoleczna.koszt_budowy == Decimal("7500.0") * Decimal("2100.00")
        assert a.komunalna.koszt_budowy == Decimal("7500.0") * Decimal("900.00")

    @pytest.mark.parametrize("udzial", [0.0, 0.05, 0.5, 0.95, 1.0])
    def test_suma_kosztow_nie_zalezy_od_podzialu_pul(self, udzial):
        zmiany = {"powierzchnie__udzial_puli_komunalnej": udzial}
        if udzial >= 1.0:
            zmiany["pula_spoleczna__kredyt__udzial_docelowy"] = 0.0
        _, a = zbuduj(**zmiany)
        assert a.koszty_laczne == Decimal("29050000.00")

    def test_pula_o_zerowym_pum_jest_nieaktywna(self):
        _, a = zbuduj(powierzchnie__udzial_puli_komunalnej=0.0)
        assert a.komunalna.aktywna is False
        assert a.komunalna.koszty_przedsiewziecia == Decimal("0")


class TestVAT:
    """art. 13 ust. 3 — VAT w podstawie tylko przy braku prawa do odliczenia."""

    def test_vat_odliczalny_zostawia_koszty_netto(self):
        _, a = zbuduj(koszty__vat_odliczalny=True)
        assert a.spoleczna.koszty_przedsiewziecia == a.spoleczna.koszty_przedsiewziecia_netto

    def test_vat_nieodliczalny_podnosi_podstawe(self):
        _, a = zbuduj(koszty__vat_odliczalny=False, koszty__stawka_vat=0.08)
        oczekiwane = a.spoleczna.koszty_przedsiewziecia_netto * Decimal("1.08")
        assert a.spoleczna.koszty_przedsiewziecia == oczekiwane

    def test_vat_nieodliczalny_podnosi_takze_grunt_w_podstawie(self):
        _, a = zbuduj(koszty__vat_odliczalny=False, koszty__stawka_vat=0.08)
        assert a.spoleczna.grunt_w_podstawie == a.spoleczna.grunt * Decimal("1.08")


class TestPodstawaNaM2:
    def test_koszt_na_m2_jest_taki_sam_w_obu_pulach_przy_kluczu_pum(self):
        _, a = zbuduj(powierzchnie__udzial_puli_komunalnej=0.30)
        assert a.spoleczna.koszt_budowy_lokalu_na_m2 == a.komunalna.koszt_budowy_lokalu_na_m2
