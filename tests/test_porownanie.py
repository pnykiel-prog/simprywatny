"""Rozdz. 4 uzupelnienia nr 2 — porownanie form gruntu i wnioski samoczynne."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import porownanie
from sim_kalkulator.dane import FormaGruntu

from . import wspolne


def porownaj(**zmiany):
    return porownanie.buduj(wspolne.wejscie(**zmiany))


def kody(p):
    return {w.kod for w in p.wnioski}


class TestZakresPorownania:
    def test_porownuje_wszystkie_formy_dla_pochodzenia(self):
        p = porownaj()
        formy = {w.forma for w in p.warianty}
        assert formy == {
            "nabycie_od_gminy",
            "lokal_za_grunt",
            "aport_gminy",
            "uzytkowanie_wieczyste",
            "dzierzawa",
        }

    def test_nie_wychodzi_poza_pochodzenie(self):
        # Dzialki gminnej nie da sie wniesc aportem inwestora — i odwrotnie.
        p = porownaj(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        formy = {w.forma for w in p.warianty}
        assert formy == {"aport_inwestora", "spolka_wlascicielem"}

    def test_wybrana_forma_jest_oznaczona_dokladnie_raz(self):
        p = porownaj()
        assert sum(1 for w in p.warianty if w.wybrany) == 1
        assert p.wybrany.forma == "nabycie_od_gminy"

    def test_wariant_bez_danych_wraca_z_powodem_nie_z_liczba(self):
        p = porownaj(grunt__oplata_roczna=wspolne.USUN)
        dzierzawa = p.wariant("dzierzawa")
        assert dzierzawa.policzalny is False
        assert "oplata_roczna" in dzierzawa.powod
        assert dzierzawa.wklad_gotowkowy == D("0")

    def test_hipoteka_wyklucza_warianty_aportowe(self):
        p = porownaj(grunt__obciazony_hipoteka=True)
        aport = p.wariant("aport_gminy")
        assert aport.policzalny is False
        assert "hipoteka" in aport.powod
        assert p.wariant("nabycie_od_gminy").policzalny is True


class TestRoznicMiedzyFormami:
    """Rozdz. 8 — regresja: uporzadkowanie wkladow jest stabilne."""

    def test_kazda_forma_daje_inny_wynik(self):
        p = porownaj()
        wklady = [w.wklad_gotowkowy for w in p.policzalne]
        assert len(wklady) == 5
        # Nie wszystkie sa rowne — grunt zmienia montaz, a nie tylko opis.
        assert len(set(wklady)) > 1

    def test_dzierzawa_ma_najnizsza_dotacje(self):
        p = porownaj()
        dzierzawa = p.wariant("dzierzawa")
        assert dzierzawa.pasmo_45 is False
        for inny in p.policzalne:
            if inny.forma != "dzierzawa":
                assert dzierzawa.grant_laczny < inny.grant_laczny

    def test_aport_gminy_ma_najnizsza_dopuszczalna_pomoc(self):
        p = porownaj()
        aport = p.wariant("aport_gminy")
        for inny in p.policzalne:
            if inny.forma != "aport_gminy":
                assert aport.dopuszczalna_pomoc < inny.dopuszczalna_pomoc

    def test_tylko_lokal_za_grunt_pomniejsza_powierzchnie_przychodowa(self):
        p = porownaj()
        pelne = wspolne.wejscie().powierzchnie.pum_laczne
        for wariant in p.policzalne:
            if wariant.forma == "lokal_za_grunt":
                assert wariant.pum_przychodowe < pelne
            else:
                assert wariant.pum_przychodowe == pelne

    def test_uporzadkowanie_wkladow_jest_stabilne(self):
        # Regresja z rozdz. 8: ten sam projekt we wszystkich formach daje rozne
        # wklady, a ich kolejnosc nie moze sie zmieniac miedzy wersjami silnika.
        p = porownaj()
        kolejnosc = [w.forma for w in p.wedlug_wkladu()]
        assert kolejnosc == [
            "lokal_za_grunt",
            "aport_gminy",
            "uzytkowanie_wieczyste",
            "nabycie_od_gminy",
            "dzierzawa",
        ]


class TestWnioskuDzierzawa:
    """Rozdz. 4.1 — dzierzawa jest pulapka kosztowa, z kwota liczona rzeczywiscie."""

    def test_wybor_dzierzawy_daje_wniosek_z_kwota(self):
        p = porownaj(grunt__forma="dzierzawa")
        assert "DZIERZAWA_PULAPKA_KOSZTOWA" in kody(p)
        wniosek = next(w for w in p.wnioski if w.kod == "DZIERZAWA_PULAPKA_KOSZTOWA")
        assert wniosek.kwota > D("0")
        assert "35%" in wniosek.tresc and "45%" in wniosek.tresc
        assert wniosek.forma_polecana == "nabycie_od_gminy"

    def test_kwota_wniosku_to_rzeczywista_roznica_dotacji(self):
        p = porownaj(grunt__forma="dzierzawa")
        wniosek = next(w for w in p.wnioski if w.kod == "DZIERZAWA_PULAPKA_KOSZTOWA")
        roznica = p.wariant("nabycie_od_gminy").grant_laczny - p.wariant("dzierzawa").grant_laczny
        assert wniosek.kwota == roznica

    def test_bez_dzierzawy_nie_ma_tego_wniosku(self):
        assert "DZIERZAWA_PULAPKA_KOSZTOWA" not in kody(porownaj())


class TestWnioskuAportGminy:
    """Rozdz. 4.2 — aport gminy kosztuje dwa razy."""

    def test_wybor_aportu_gminy_daje_wniosek_z_kwota(self):
        p = porownaj(grunt__forma="aport_gminy")
        assert "APORT_GMINY_KOSZTUJE_DWA_RAZY" in kody(p)
        wniosek = next(w for w in p.wnioski if w.kod == "APORT_GMINY_KOSZTUJE_DWA_RAZY")
        assert wniosek.kwota > D("0")
        assert "wspólnikiem" in wniosek.tresc
        assert wniosek.forma_polecana == "lokal_za_grunt"

    def test_kwota_to_rzeczywisty_spadek_dopuszczalnej_pomocy(self):
        p = porownaj(grunt__forma="aport_gminy")
        wniosek = next(w for w in p.wnioski if w.kod == "APORT_GMINY_KOSZTUJE_DWA_RAZY")
        spadek = (
            p.wariant("nabycie_od_gminy").dopuszczalna_pomoc
            - p.wariant("aport_gminy").dopuszczalna_pomoc
        )
        assert wniosek.kwota == spadek

    def test_bez_danych_o_lokalach_wniosek_prosi_o_nie_zamiast_polecac(self):
        p = porownaj(
            grunt__forma="aport_gminy",
            grunt__liczba_lokali_dla_gminy=wspolne.USUN,
            grunt__pum_lokali_dla_gminy=wspolne.USUN,
        )
        wniosek = next(w for w in p.wnioski if w.kod == "APORT_GMINY_KOSZTUJE_DWA_RAZY")
        assert wniosek.forma_polecana == ""
        assert "podaj liczbę i powierzchnię" in wniosek.tresc


class TestWnioskuTanszaForma:
    def test_wskazuje_forme_o_nizszym_wkladzie_z_zastrzezeniem(self):
        p = porownaj(grunt__forma="dzierzawa")
        wniosek = next(w for w in p.wnioski if w.kod == "TANSZA_FORMA_GRUNTU")
        assert wniosek.kwota > D("0")
        assert wniosek.forma_polecana in {w.forma for w in p.policzalne}

    def test_przy_najtanszej_formie_nie_ma_tego_wniosku(self):
        p = porownaj(grunt__forma="lokal_za_grunt")
        assert "TANSZA_FORMA_GRUNTU" not in kody(p)
