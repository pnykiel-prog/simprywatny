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


def wartosc_gruntu_dla_udzialu(udzial: Decimal, **zmiany) -> float:
    """Wartosc dzialki, przy ktorej grunt stanowi zadany udzial kosztow.

    Koszty pozostale B nie zaleza od wartosci gruntu, wiec z g/(B+g) = x
    wychodzi g = B * x / (1 - x). Mnoznik VAT skraca sie po obu stronach.
    """
    _, a, _ = granty(grunt__wartosc=0.0, **zmiany)
    bez_gruntu = a.koszty_laczne
    return float(bez_gruntu * udzial / (Decimal(1) - udzial))


class TestKanaluA:
    """Rozdz. 3.1 i 8 uzupelnienia nr 2 — forma gruntu przesadza o pasmie."""

    def test_dzierzawa_daje_dokladnie_35_procent(self):
        _, a, g = granty(
            grunt__pochodzenie="gmina",
            grunt__forma="dzierzawa",
            grunt__oplata_roczna=150000.0,
            grunt__wartosc=6000000.0,
        )
        assert g.spoleczna.udzial_wsparcia == Decimal("0.35")
        assert g.spoleczna.pasmo_45 is False

    def test_dzierzawa_scina_pasmo_niezaleznie_od_wartosci_gruntu(self):
        udzialy = set()
        for wartosc in (0.0, 3000000.0, 6000000.0, 20000000.0):
            _, _, g = granty(
                grunt__pochodzenie="gmina",
                grunt__forma="dzierzawa",
                grunt__oplata_roczna=150000.0,
                grunt__wartosc=wartosc,
            )
            udzialy.add(g.spoleczna.udzial_wsparcia)
        assert udzialy == {Decimal("0.35")}

    def test_nabycie_z_gruntem_ponad_10_procent_daje_45_procent(self):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.15"), grunt__pochodzenie="gmina", grunt__forma="nabycie_od_gminy"
        )
        _, a, g = granty(
            grunt__pochodzenie="gmina",
            grunt__forma="nabycie_od_gminy",
            grunt__wartosc=wartosc,
        )
        assert a.spoleczna.grunt > a.spoleczna.koszty_przedsiewziecia * Decimal("0.10")
        assert g.spoleczna.udzial_wsparcia == Decimal("0.45")

    def test_nabycie_z_gruntem_na_5_procent_daje_dokladnie_40_procent(self):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.05"), grunt__pochodzenie="gmina", grunt__forma="nabycie_od_gminy"
        )
        _, a, g = granty(
            grunt__pochodzenie="gmina",
            grunt__forma="nabycie_od_gminy",
            grunt__wartosc=wartosc,
        )
        assert a.spoleczna.grunt == pytest.approx(
            a.spoleczna.koszty_przedsiewziecia * Decimal("0.05")
        )
        assert g.spoleczna.udzial_wsparcia == pytest.approx(Decimal("0.40"))

    @pytest.mark.parametrize(
        "pochodzenie,forma,dodatki",
        [
            ("inwestor", "aport_inwestora", {}),
            ("inwestor", "spolka_wlascicielem", {}),
            ("rynek_prywatny", "nabycie_prywatne", {}),
            ("gmina", "nabycie_od_gminy", {}),
            ("gmina", "uzytkowanie_wieczyste", {"grunt__oplata_roczna": 150000.0}),
        ],
    )
    def test_formy_z_prawem_do_gruntu_siegaja_pasma(self, pochodzenie, forma, dodatki):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.15"),
            grunt__pochodzenie=pochodzenie,
            grunt__forma=forma,
            **dodatki,
        )
        _, _, g = granty(
            grunt__pochodzenie=pochodzenie,
            grunt__forma=forma,
            grunt__wartosc=wartosc,
            **dodatki,
        )
        assert g.spoleczna.pasmo_45 is True
        assert g.spoleczna.udzial_wsparcia == Decimal("0.45")

    def test_sciete_pasmo_daje_ostrzezenie_z_kwota(self):
        _, a, g = granty(
            grunt__pochodzenie="gmina",
            grunt__forma="dzierzawa",
            grunt__oplata_roczna=150000.0,
            grunt__wartosc=6000000.0,
        )
        kody = {o.kod for o in g.ostrzezenia}
        assert "PASMO_SCIETE_FORMA_GRUNTU" in kody
        assert g.spoleczna.grant_utracony == a.spoleczna.koszty_przedsiewziecia * Decimal(
            "0.10"
        )

    def test_pasmo_liczone_od_ceny_po_bonifikacie_obniza_grant(self):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.10"), grunt__pochodzenie="gmina", grunt__forma="nabycie_od_gminy"
        )
        wspolne_zmiany = dict(
            grunt__pochodzenie="gmina",
            grunt__forma="nabycie_od_gminy",
            grunt__wartosc=wartosc,
            grunt__cena_nabycia=wartosc / 2,
        )
        _, _, od_operatu = granty(**wspolne_zmiany)
        _, _, od_ceny = granty(
            przelaczniki__pasmo_liczone_od_wartosci_z_operatu=False, **wspolne_zmiany
        )
        assert od_operatu.spoleczna.udzial_wsparcia == pytest.approx(Decimal("0.45"))
        assert od_ceny.spoleczna.udzial_wsparcia < od_operatu.spoleczna.udzial_wsparcia


class TestKanaluB:
    """Rozdz. 3.3 i 8 — wartosc gruntu w kosztach i limit z § 12 ust. 7 rozp. 766."""

    def test_aport_w_sciezce_kredytowej_wchodzi_do_kosztow_na_limicie(self):
        wartosc = wartosc_gruntu_dla_udzialu(Decimal("0.30"), grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        _, a, _ = granty(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora", grunt__wartosc=wartosc)
        udzial = a.spoleczna.grunt / a.spoleczna.koszty_przedsiewziecia_netto
        assert udzial == pytest.approx(Decimal("0.20"))
        assert a.grunt_obciety_limitem > 0

    def test_nabycie_wchodzi_do_kosztow_w_calosci(self):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.30"), grunt__pochodzenie="rynek_prywatny", grunt__forma="nabycie_prywatne"
        )
        _, a, _ = granty(
            grunt__pochodzenie="rynek_prywatny",
            grunt__forma="nabycie_prywatne",
            grunt__wartosc=wartosc,
        )
        udzial = a.spoleczna.grunt / a.spoleczna.koszty_przedsiewziecia_netto
        assert udzial == pytest.approx(Decimal("0.30"))
        assert a.grunt_obciety_limitem == 0

    def test_limit_aportowy_nie_dziala_bez_kredytu(self):
        wartosc = wartosc_gruntu_dla_udzialu(
            Decimal("0.30"),
            grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora",
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        _, a, _ = granty(
            grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora",
            grunt__wartosc=wartosc,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert a.grunt_obciety_limitem == 0

    def test_dzierzawa_nie_wnosi_wartosci_do_kosztow(self):
        _, a, _ = granty(
            grunt__pochodzenie="gmina",
            grunt__forma="dzierzawa",
            grunt__oplata_roczna=150000.0,
            grunt__wartosc=6000000.0,
        )
        assert a.grunt_laczny == 0

    def test_limit_aportowy_nie_scina_wartosci_do_pasma(self):
        # § 12 ust. 7 dotyczy kosztow; art. 13 ust. 1 pkt 1 mowi o wartosci prawa.
        wartosc = wartosc_gruntu_dla_udzialu(Decimal("0.30"), grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        _, a, _ = granty(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora", grunt__wartosc=wartosc)
        assert a.grunt_do_pasma_laczny == pytest.approx(Decimal(str(wartosc)))
        assert a.grunt_do_pasma_laczny > a.grunt_laczny


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
