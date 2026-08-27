"""Uwagi z audytu scenariusza odniesienia — punkty 4-7.

Punkty 1-3 maja wlasne testy: spojnosc widokow w `test_spojnosc_widokow.py`,
prog tolerancji w `test_rekompensata.py`, baza dotacji jako ostrzezenie ponizej.
"""

from decimal import Decimal as D

import pytest

from sim_kalkulator import api, prawo, wrazliwosc
from sim_kalkulator.silnik import przelicz

from . import wspolne

APORT_GMINY = dict(grunt__pochodzenie="gmina", grunt__forma="aport_gminy")


def kody(r):
    return {o.kod for o in r.ostrzezenia}


class TestBazaDotacjiJakoZalozenie:
    """Punkt 2 — implementacja bez zmian, ale wynik ma byc oznaczony."""

    def test_grunt_wchodzi_do_bazy_naliczania(self):
        r = przelicz(wspolne.wejscie())
        a = r.alokacja.spoleczna
        assert r.granty.spoleczna.podstawa_kosztowa == a.koszty_przedsiewziecia
        assert a.grunt_w_podstawie > 0

    def test_wynik_niesie_ostrzezenie_o_zalozeniu(self):
        assert "ZALOZENIE_GRUNT_W_BAZIE_DOTACJI" in kody(przelicz(wspolne.wejscie()))

    def test_ostrzezenie_podaje_skale_odczytu_alternatywnego(self):
        r = przelicz(wspolne.wejscie())
        o = next(o for o in r.ostrzezenia if o.kod == "ZALOZENIE_GRUNT_W_BAZIE_DOTACJI")
        assert "niższa" in o.dla_ekranu
        assert "zł" in o.dla_ekranu

    def test_bez_gruntu_nie_ma_tego_ostrzezenia(self):
        assert "ZALOZENIE_GRUNT_W_BAZIE_DOTACJI" not in kody(
            przelicz(wspolne.wejscie(grunt__wartosc=0.0))
        )


class TestPodzialuUdzialow:
    """Punkt 4 — aport gminy wyrazony w procentach kapitalu spolki."""

    def test_aport_gminy_daje_wyliczony_udzial(self):
        r = przelicz(wspolne.wejscie(**APORT_GMINY))
        udzial = r.finansowanie.udzial_gminy_w_spolce
        assert udzial is not None
        assert D("0") < udzial < D("1")

    def test_udzial_to_aport_do_calego_kapitalu(self):
        r = przelicz(wspolne.wejscie(**APORT_GMINY))
        f = r.finansowanie
        assert f.udzial_gminy_w_spolce == pytest.approx(
            f.kapital_gminy / (f.kapital_gminy + f.kapital_inwestora_w_spolce)
        )

    def test_bez_aportu_gminy_nie_ma_podzialu(self):
        r = przelicz(wspolne.wejscie())
        assert r.finansowanie.udzial_gminy_w_spolce is None
        assert "UDZIAL_GMINY_W_SPOLCE" not in kody(r)

    def test_wiekszosc_gminy_jest_ostrzezeniem_zmieniajacym_werdykt(self):
        from sim_kalkulator.dane import Waga

        r = przelicz(wspolne.wejscie(**APORT_GMINY))
        assert r.finansowanie.udzial_gminy_w_spolce > prawo.WIEKSZOSC_UDZIALOW
        o = next(o for o in r.ostrzezenia if o.kod == "UDZIAL_GMINY_W_SPOLCE")
        assert o.waga is Waga.ZMIENIA_WERDYKT
        assert "prywatny SIM" in o.dla_ekranu

    def test_tanszy_grunt_zostawia_kontrole_inwestorowi(self):
        r = przelicz(wspolne.wejscie(grunt__wartosc=400000.0, **APORT_GMINY))
        udzial = r.finansowanie.udzial_gminy_w_spolce
        assert udzial < prawo.WIEKSZOSC_UDZIALOW
        o = next(o for o in r.ostrzezenia if o.kod == "UDZIAL_GMINY_W_SPOLCE")
        assert "Zachowujesz kontrolę" in o.dla_ekranu

    def test_udzial_jedzie_do_interfejsu(self):
        r = przelicz(wspolne.wejscie(**APORT_GMINY))
        b = api._grunt_json(r)["biezace"]
        assert b["gmina_ma_wiekszosc"] is True
        assert any("udziałów" in x for x in b["opisy"])


class TestBlokadyNiezaleznejOdOsi:
    """Punkt 5 — test oblany w calym zakresie nie jest kwestia proporcji mieszkan."""

    def test_wykrywa_test_oblany_w_calym_zakresie(self):
        s = wrazliwosc.sweep_udzialu(
            wspolne.wejscie(), krok=D("0.1")
        )
        assert s.blokada_niezalezna_od_osi == 3

    def test_wariant_domykajacy_nie_zglasza_blokady(self):
        from sim_kalkulator.dane import wczytaj_yaml

        s = wrazliwosc.sweep_udzialu(
            wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"), krok=D("0.1")
        )
        assert s.blokada_niezalezna_od_osi is None

    def test_podsumowanie_mowi_ze_os_nie_jest_dzwignia(self):
        a = wrazliwosc.build(wspolne.wejscie(), krok=D("0.2"))
        assert "nie jest tu dzwignia" in a.podsumowanie

    def test_sweep_wskazuje_dzialajaca_dzwignie(self):
        _, s = api.obsluz("sweep", api.wczytaj_parametry(wspolne.WZORCOWY), {})
        assert s["blokada_niezalezna_od_osi"] == 3
        dz = s["dzwignia_poza_osia"]
        assert dz["opis"] and dz["dzialanie"] and dz["cel"] in {"grunt", "dzwignie"}

    def test_przy_aporcie_gminy_dzwignia_wskazuje_forme_dzialki(self):
        _, s = api.obsluz(
            "sweep", api.wczytaj_parametry(wspolne.WZORCOWY),
            {"grunt.pochodzenie": "gmina", "grunt.forma": "aport_gminy"},
        )
        if s["blokada_niezalezna_od_osi"]:
            assert s["dzwignia_poza_osia"]["cel"] == "grunt"


class TestEtykietyRekompensaty:
    """Punkt 6 — „114% dopuszczalnej pomocy” czytalo sie jak wskaznik pokrycia."""

    def test_przekroczenie_podane_wprost(self):
        r = przelicz(wspolne.wejscie())
        g = api._zapas_rekompensaty(r)
        assert g["przechodzi"] is False
        assert g["przekroczenie"] > 0
        assert g["zapas"] == 0
        assert g["etykieta"].startswith("Przekroczenie limitu o")

    def test_liczba_glowna_to_przekroczenie_a_nie_wykorzystanie(self):
        g = api._zapas_rekompensaty(przelicz(wspolne.wejscie()))
        # Przekroczenie moze byc dowolnie duze — chodzi o to, ze pokazujemy
        # NADWYZKE ponad limit, a nie stosunek do limitu.
        assert g["liczba_glowna"] == pytest.approx(g["wykorzystanie"] - 1)
        assert g["liczba_glowna"] < g["wykorzystanie"]

    def test_gdy_miesci_sie_podawany_jest_zapas(self):
        from sim_kalkulator.dane import wczytaj_yaml

        r = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        g = api._zapas_rekompensaty(r)
        if g["przechodzi"]:
            assert g["etykieta"].startswith("Zapas do limitu")
            assert g["liczba_glowna"] == pytest.approx(1 - g["wykorzystanie"])


class TestProguArt7c:
    """Punkt 7 — prog czytany jako „co najmniej”, a skok limitu ma byc widoczny."""

    @pytest.mark.parametrize(
        "udzial,oczekiwany",
        [("0.4499", "0.040"), ("0.45", "0.035"), ("0.4501", "0.035"),
         ("0.7499", "0.030"), ("0.75", "0.025")],
    )
    def test_prog_czytany_jako_co_najmniej(self, udzial, oczekiwany):
        assert prawo.limit_czynszu_art_7c(D(udzial)) == D(oczekiwany)

    def test_udzial_tuz_pod_progiem_pokazuje_skok_limitu(self):
        r = przelicz(wspolne.wejscie())
        spol = next(
            w for w in api._czynsz_poziomy(r)["wiersze"] if w["pula"] == "spoleczna"
        )
        assert D("0.44") < D(str(r.granty.spoleczna.udzial_wsparcia)) < D("0.45")
        prog = spol["prog_sasiedni"]
        assert prog is not None
        assert prog["udzial_progu"] == 0.45
        assert prog["limit_po_progu"] < spol["limit"]
        assert "spada z" in prog["opis"]

    def test_daleko_od_progu_nie_ma_znacznika(self):
        # Grunt zerowy scina dotacje do progu gruntowego — 35%, czyli 10 pp od 45%.
        r = przelicz(wspolne.wejscie(grunt__wartosc=0.0))
        spol = next(
            w for w in api._czynsz_poziomy(r)["wiersze"] if w["pula"] == "spoleczna"
        )
        assert spol["prog_sasiedni"] is None

    def test_znacznik_nigdy_nie_pokazuje_limitu_wyzszego(self):
        for udzial in (0.0, 0.2, 0.4, 0.6):
            r = przelicz(wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=udzial))
            for w in api._czynsz_poziomy(r)["wiersze"]:
                if w["prog_sasiedni"]:
                    assert w["prog_sasiedni"]["limit_po_progu"] < w["limit"]
