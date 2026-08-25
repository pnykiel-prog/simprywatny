"""Etap 8 — sweep udzialu pul, punkt graniczny i ranking parametrow."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import wrazliwosc
from sim_kalkulator.dane import wczytaj_yaml

from . import wspolne

DOMYKAJACY = wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"


@pytest.fixture(scope="module")
def sweep_domykajacy():
    return wrazliwosc.sweep_udzialu(wczytaj_yaml(DOMYKAJACY))


@pytest.fixture(scope="module")
def sweep_wzorcowy():
    return wrazliwosc.sweep_udzialu(wczytaj_yaml(wspolne.WZORCOWY))


class TestZakresSweepu:
    def test_krok_005_daje_21_punktow(self, sweep_domykajacy):
        assert len(sweep_domykajacy.punkty) == 21
        assert sweep_domykajacy.punkty[0].udzial == D("0.0")
        assert sweep_domykajacy.punkty[-1].udzial == D("1.00")

    def test_kazdy_punkt_ma_trzy_werdykty(self, sweep_domykajacy):
        for punkt in sweep_domykajacy.punkty:
            assert len(punkt.werdykty) == 3

    def test_kazdy_punkt_ma_wiazace_ograniczenie(self, sweep_domykajacy):
        for punkt in sweep_domykajacy.punkty:
            assert punkt.wiazace_ograniczenie.strip()

    def test_wlasny_krok_zmienia_gestosc(self):
        s = wrazliwosc.sweep_udzialu(wczytaj_yaml(DOMYKAJACY), krok=D("0.25"))
        assert [p.udzial for p in s.punkty] == [D("0.00"), D("0.25"), D("0.50"), D("0.75"), D("1.00")]


class TestPunktGraniczny:
    def test_maksymalny_udzial_i_punkt_graniczny(self, sweep_domykajacy):
        assert sweep_domykajacy.maksymalny_udzial_komunalny == D("0.80")
        assert sweep_domykajacy.punkt_graniczny == D("0.85")

    def test_ponizej_granicy_wszystko_przechodzi(self, sweep_domykajacy):
        for punkt in sweep_domykajacy.punkty:
            if punkt.udzial <= D("0.80"):
                assert punkt.domyka_sie is True, punkt.udzial

    def test_powyzej_granicy_blokuje_test_montazu(self, sweep_domykajacy):
        powyzej = [p for p in sweep_domykajacy.punkty if D("0.85") <= p.udzial <= D("0.95")]
        assert powyzej
        for punkt in powyzej:
            assert punkt.domyka_sie is False
            assert punkt.werdykty[0] is False      # test 1 — kapital
            assert punkt.werdykty[1] is True       # test 2 przechodzi z konstrukcji

    def test_luka_kapitalowa_rosnie_z_udzialem_komunalnym(self, sweep_domykajacy):
        # Kazdy metr przesuniety do puli komunalnej traci dzwignie kredytowa
        # i partycypacje, wiec musi go pokryc grant albo kapital wlasny.
        luki = [
            (p.udzial, p.luki[0][1])
            for p in sweep_domykajacy.punkty
            if p.policzalny and p.luki
        ]
        assert luki
        assert all(b > a for (_, a), (_, b) in zip(luki, luki[1:]))

    def test_luka_zawsze_podana_z_jednostka(self, sweep_domykajacy):
        for punkt in sweep_domykajacy.punkty:
            for opis, kwota, jednostka in punkt.luki:
                assert opis and jednostka
                assert kwota > D("0")


class TestBrakDomkniecia:
    def test_gdy_nic_nie_domyka_wskazywany_jest_test_blokujacy(self, sweep_wzorcowy):
        assert sweep_wzorcowy.maksymalny_udzial_komunalny is None
        assert sweep_wzorcowy.punkt_graniczny is None
        assert sweep_wzorcowy.test_blokujacy == 3

    def test_wzorcowy_blokuje_rekompensate_w_calym_zakresie(self, sweep_wzorcowy):
        policzalne = [p for p in sweep_wzorcowy.punkty if p.policzalny]
        assert all(p.werdykty[2] is False for p in policzalne if p.udzial < D("1.0"))


class TestPunktyNiepoliczalne:
    def test_kredyt_przy_pelnej_puli_komunalnej_jest_niepoliczalny(self, sweep_domykajacy):
        ostatni = sweep_domykajacy.punkty[-1]
        assert ostatni.udzial == D("1.00")
        assert ostatni.policzalny is False
        assert "art. 5a ust. 3" in ostatni.powod_niepoliczalnosci

    def test_niepoliczalny_nie_liczy_sie_jako_domykajacy(self, sweep_domykajacy):
        assert all(p.policzalny for p in sweep_domykajacy.punkty_domykajace)

    def test_bez_kredytu_pelna_pula_komunalna_jest_policzalna(self):
        dane = wspolne.zmien(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        s = wrazliwosc.sweep_udzialu(w, krok=D("0.5"))
        assert s.punkty[-1].policzalny is True


class TestWrazliwoscJednoparametrowa:
    @staticmethod
    @pytest.fixture(scope="class")
    def wyniki():
        return wrazliwosc.wrazliwosc_jednoparametrowa(
            wczytaj_yaml(DOMYKAJACY), krok=D("0.10")
        )

    def test_badane_sa_wszystkie_parametry_z_rozdzialu_7_2(self, wyniki):
        nazwy = {r.nazwa for r in wyniki}
        assert nazwy == {
            "Koszt budowy na m2",
            "Oprocentowanie kredytu",
            "Czynsz w puli spolecznej",
            "Czynsz placony przez gmine",
            "Pustostany",
            "Wartosc gruntu",
            "Stopa referencyjna KE",
        }

    def test_stopa_referencyjna_badana_zawsze(self, wyniki):
        # Rozdz. 7.3 — wynik testu rekompensaty jest na nia bardzo wrazliwy,
        # a horyzont siega 30 lat.
        assert any(r.nazwa == "Stopa referencyjna KE" for r in wyniki)

    def test_zakres_to_plus_minus_20_procent(self, wyniki):
        for r in wyniki:
            assert r.wartosc_dol == r.wartosc_bazowa * D("0.80")
            assert r.wartosc_gora == r.wartosc_bazowa * D("1.20")

    def test_wyzszy_koszt_budowy_zaweza_pole_manewru(self, wyniki):
        koszt = next(r for r in wyniki if r.nazwa == "Koszt budowy na m2")
        assert koszt.maks_udzial_gora is not None
        assert koszt.maks_udzial_gora <= koszt.maks_udzial_bazowo

    def test_ranking_porzadkuje_wg_sily_wplywu(self, wyniki):
        r = wrazliwosc.ranking(wyniki)
        sily = [x.sila_wplywu for x in r]
        assert sily == sorted(sily, reverse=True)
        assert len(r) == len(wyniki)

    def test_sila_wplywu_liczy_obie_strony_zakresu(self, wyniki):
        # Parametr, ktory granice wylacznie obniza, tez ma sile wplywu — inaczej
        # ranking milczalby o ryzyku.
        grunt = next(r for r in wyniki if r.nazwa == "Wartosc gruntu")
        dol, gora = grunt.przesuniecia
        assert grunt.sila_wplywu == max(abs(p) for p in (dol, gora) if p is not None)

    def test_kierunek_korzystny_wskazuje_strone_zakresu(self, wyniki):
        koszt = next(r for r in wyniki if r.nazwa == "Koszt budowy na m2")
        assert koszt.kierunek_korzystny == "-20%"

    def test_sila_wplywu_nigdy_ujemna(self, wyniki):
        for r in wyniki:
            assert r.sila_wplywu >= D("0")


class TestAnalizaZbiorcza:
    def test_podsumowanie_podaje_granice_w_procentach(self):
        a = wrazliwosc.build(wczytaj_yaml(DOMYKAJACY), krok=D("0.05"))
        assert "80%" in a.podsumowanie
        assert "85%" in a.podsumowanie

    def test_podsumowanie_braku_domkniecia_wskazuje_test(self):
        a = wrazliwosc.build(wczytaj_yaml(wspolne.WZORCOWY), krok=D("0.25"))
        assert "nie domyka sie przy zadnym udziale" in a.podsumowanie
        assert "test 3" in a.podsumowanie

    def test_analiza_zawiera_sweep_i_ranking(self):
        a = wrazliwosc.build(wczytaj_yaml(DOMYKAJACY), krok=D("0.25"))
        assert a.sweep.punkty
        assert len(a.ranking) == len(wrazliwosc.PARAMETRY_WRAZLIWOSCI)


class TestPunktPrzelamania:
    """Rozdz. 7.1 — gdy montaz nie domyka sie przy zadnym udziale, narzedzie ma
    wskazac, przy jakiej wartosci parametru zaczalby przechodzic."""

    @staticmethod
    def wariant(koszt_budowy):
        from sim_kalkulator.dane import zbuduj

        dane = wspolne.zmien(koszty__koszt_budowy_na_m2=koszt_budowy)
        dane["przelaczniki"]["koszty_inwestycyjne_w_kn"] = "naklad_poczatkowy"
        dane["pula_spoleczna"]["kredyt"]["udzial_docelowy"] = 0.25
        dane["pula_spoleczna"]["kredyt"]["karencja_lat"] = 0
        dane["inwestor"]["dostepny_wklad_wlasny"] = 4600000.0
        return wrazliwosc.build(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA))

    def test_wariant_ktory_sie_domyka_nie_szuka_przelamania(self):
        a = self.wariant(7500.0)
        assert a.sweep.maksymalny_udzial_komunalny is not None
        for r in a.wrazliwosc:
            assert r.przelamanie_zbadane is False
            assert r.przelamuje is False

    def test_wariant_bez_domkniecia_wskazuje_wartosc_przelamania(self):
        a = self.wariant(12500.0)
        assert a.sweep.maksymalny_udzial_komunalny is None
        koszt = next(r for r in a.wrazliwosc if r.nazwa == "Koszt budowy na m2")
        assert koszt.przelamanie_zbadane is True
        assert koszt.przelamuje is True
        assert koszt.przelamanie_wartosc is not None
        assert koszt.przelamanie_maks_udzial is not None

    def test_wskazana_wartosc_faktycznie_domyka_montaz(self):
        # Kontrola wprost: podstawiamy wskazana wartosc i sprawdzamy, ze sweep
        # rzeczywiscie znajduje punkt domkniecia.
        from sim_kalkulator.dane import zbuduj

        a = self.wariant(12500.0)
        koszt = next(r for r in a.wrazliwosc if r.nazwa == "Koszt budowy na m2")
        dane = wspolne.zmien(koszty__koszt_budowy_na_m2=float(koszt.przelamanie_wartosc))
        dane["przelaczniki"]["koszty_inwestycyjne_w_kn"] = "naklad_poczatkowy"
        dane["pula_spoleczna"]["kredyt"]["udzial_docelowy"] = 0.25
        dane["pula_spoleczna"]["kredyt"]["karencja_lat"] = 0
        dane["inwestor"]["dostepny_wklad_wlasny"] = 4600000.0
        sweep = wrazliwosc.sweep_udzialu(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA))
        assert sweep.maksymalny_udzial_komunalny == koszt.przelamanie_maks_udzial

    def test_szuka_najtanszej_zmiany(self):
        # Mnozniki badane od najblizszego wartosci bazowej, wiec znaleziona
        # zmiana jest najmniejsza z mozliwych w siatce.
        a = self.wariant(12500.0)
        koszt = next(r for r in a.wrazliwosc if r.nazwa == "Koszt budowy na m2")
        assert abs(koszt.przelamanie_zmiana) <= wrazliwosc.PRZELAMANIE_ZASIEG

    def test_ranking_stawia_najtansza_dzwignie_pierwsza(self):
        a = self.wariant(12500.0)
        przelamujace = [r for r in a.ranking if r.przelamuje]
        assert przelamujace, "zaden parametr nie przelamuje — brak czego rankingowac"
        koszty = [r.koszt_przelamania for r in przelamujace]
        assert koszty == sorted(koszty)
        assert a.ranking[0].przelamuje is True

    def test_opis_dzwigni_zawsze_cos_mowi(self):
        # Pusta komorka w rankingu jest bezuzyteczna — kazdy wiersz ma niesc tresc.
        for koszt_budowy in (7500.0, 12500.0):
            for r in self.wariant(koszt_budowy).ranking:
                assert r.opis_dzwigni.strip()
                assert r.opis_dzwigni != "nieokreslony"

    def test_parametr_bez_przelamania_mowi_to_wprost(self):
        from sim_kalkulator.dane import wczytaj_yaml

        a = wrazliwosc.build(wczytaj_yaml(wspolne.WZORCOWY))
        assert a.sweep.maksymalny_udzial_komunalny is None
        for r in a.ranking:
            assert "nie przelamuje" in r.opis_dzwigni
            assert r.koszt_przelamania == D("999")
