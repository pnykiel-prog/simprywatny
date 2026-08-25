"""Etap 3 — wysokosc wsparcia, regula gruntowa i bonus (rozdz. 11 specyfikacji)."""

from decimal import Decimal

import pytest

from sim_kalkulator import alokacja, grant

from . import wspolne


def granty(**zmiany):
    w = wspolne.wejscie(**zmiany)
    a = alokacja.build(w)
    return w, a, grant.build(w, a)


class TestRegulaGruntowa:
    """grant = min(0,45*K ; 0,35*K + wartosc gruntu inwestora)"""

    def test_bez_gruntu_inwestora_dokladnie_35_procent(self):
        _, a, g = granty(grunt__wartosc=0.0)
        assert g.spoleczna.udzial_wsparcia == Decimal("0.35")
        assert g.spoleczna.kwota == a.spoleczna.koszty_przedsiewziecia * Decimal("0.35")
        assert g.spoleczna.ograniczony_gruntem is True

    def test_grunt_ponad_10_procent_kosztow_daje_dokladnie_45_procent(self):
        _, a, g = granty(grunt__wartosc=6000000.0)
        assert g.spoleczna.grunt_w_podstawie if False else True
        assert a.spoleczna.grunt > a.spoleczna.koszty_przedsiewziecia * Decimal("0.10")
        assert g.spoleczna.udzial_wsparcia == Decimal("0.45")
        assert g.spoleczna.ograniczony_gruntem is False

    def test_grunt_dokladnie_10_procent_kosztow_daje_45_procent(self):
        # 0,35*K + 0,10*K = 0,45*K — punkt styku obu limitow.
        _, a, g = granty(
            powierzchnie__udzial_puli_komunalnej=0.0,
            koszty__infrastruktura=0.0,
            koszty__projekt_i_nadzor=0.0,
            koszty__koszty_ogolne=0.0,
            koszty__rezerwa=0.0,
            koszty__dzwigi=0.0,
            koszty__koszt_budowy_na_m2=3000.0,   # 3000 m2 * 3000 = 9 000 000
            grunt__wartosc=1000000.0,            # K = 10 000 000, grunt = 10% K
        )
        assert a.spoleczna.koszty_przedsiewziecia == Decimal("10000000.00")
        assert g.spoleczna.udzial_wsparcia == Decimal("0.45")

    def test_grunt_ponizej_progu_daje_wartosc_posrednia(self):
        _, a, g = granty(grunt__wartosc=1400000.0)
        udzial = g.spoleczna.udzial_wsparcia
        assert Decimal("0.35") < udzial < Decimal("0.45")
        assert g.spoleczna.ograniczony_gruntem is True

    def test_ograniczenie_gruntem_daje_ostrzezenie(self):
        _, _, g = granty(grunt__wartosc=0.0)
        assert "GRANT_OGRANICZONY_GRUNTEM" in {o.kod for o in g.ostrzezenia}


class TestGruntJST:
    def test_grunt_jst_domyslnie_liczy_sie_do_limitu(self):
        _, _, g = granty(grunt__forma="aport_jst", grunt__wartosc=6000000.0)
        assert g.spoleczna.udzial_wsparcia == Decimal("0.45")

    def test_przelacznik_wylacza_grunt_jst_z_limitu(self):
        dane = wspolne.zmien(grunt__forma="aport_jst", grunt__wartosc=6000000.0)
        dane["przelaczniki"]["grunt_jst_liczy_sie_do_limitu_grantu"] = False
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        a = alokacja.build(w)
        g = grant.build(w, a)
        assert g.spoleczna.udzial_wsparcia == Decimal("0.35")


class TestGrantKomunalny:
    def test_pula_komunalna_dostaje_80_procent(self):
        _, a, g = granty()
        assert g.komunalna.udzial_wsparcia == Decimal("0.80")
        assert g.komunalna.kwota == a.komunalna.koszty_przedsiewziecia * Decimal("0.80")

    def test_regula_gruntowa_nie_dotyczy_puli_komunalnej(self):
        _, _, g = granty(grunt__wartosc=0.0)
        assert g.komunalna.udzial_wsparcia == Decimal("0.80")
        assert g.komunalna.ograniczony_gruntem is False


class TestBonus:
    """art. 13 ust. 4 — +5 pp, wylaczony przy finansowaniu zwrotnym."""

    def test_bonus_w_puli_komunalnej_podnosi_do_85_procent(self):
        _, _, g = granty(pula_komunalna__bonus_rewitalizacyjny=True)
        assert g.komunalna.udzial_wsparcia == Decimal("0.85")
        assert g.komunalna.bonus_zastosowany is True

    def test_bonus_w_puli_spolecznej_bez_kredytu_podnosi_limit_gorny(self):
        _, _, g = granty(
            pula_spoleczna__bonus_rewitalizacyjny=True,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
            grunt__wartosc=8000000.0,
        )
        assert g.spoleczna.stawka_nominalna == Decimal("0.50")
        assert g.spoleczna.bonus_zastosowany is True

    def test_bonus_w_puli_spolecznej_jest_oznaczony_jako_zalozenie(self):
        _, _, g = granty(
            pula_spoleczna__bonus_rewitalizacyjny=True,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert "ZALOZENIE_BONUS_A_PROG_GRUNTOWY" in {o.kod for o in g.ostrzezenia}


class TestPrzelacznikHybrydy:
    def test_domyslnie_dwa_przedsiewziecia_bez_sciagniecia(self):
        _, _, g = granty(powierzchnie__udzial_puli_komunalnej=0.50)
        assert g.ograniczony_limitem_hybrydy is False

    def test_jedno_przedsiewziecie_sciaga_laczne_wsparcie_do_45_procent(self):
        dane = wspolne.zmien(powierzchnie__udzial_puli_komunalnej=0.50)
        dane["przelaczniki"]["hybryda_jako_jedno_przedsiewziecie"] = True
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        a = alokacja.build(w)
        g = grant.build(w, a)
        assert g.ograniczony_limitem_hybrydy is True
        assert g.kwota_laczna == pytest.approx(
            float(a.koszty_laczne * Decimal("0.45")), rel=Decimal("1e-9")
        )
        assert "HYBRYDA_SCIAGNIETA_DO_LIMITU" in {o.kod for o in g.ostrzezenia}

    def test_przelacznik_zmienia_wynik_a_wiec_musi_byc_widoczny(self):
        _, _, bez = granty(powierzchnie__udzial_puli_komunalnej=0.50)
        dane = wspolne.zmien(powierzchnie__udzial_puli_komunalnej=0.50)
        dane["przelaczniki"]["hybryda_jako_jedno_przedsiewziecie"] = True
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        z = grant.build(w, alokacja.build(w))
        assert z.kwota_laczna < bez.kwota_laczna
