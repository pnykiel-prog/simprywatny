"""Uwagi z audytu scenariusza odniesienia — punkty 4-7.

Punkty 1-3 maja wlasne testy: spojnosc widokow w `test_spojnosc_widokow.py`,
prog tolerancji w `test_rekompensata.py`, baza dotacji jako ostrzezenie ponizej.
"""

from decimal import Decimal as D

import pytest

from sim_kalkulator import api, prawo, wrazliwosc
from sim_kalkulator.silnik import przelicz

from . import wspolne

# Aport gminy zostal usuniety z zakresu (pakiet nr 2, rozdz. 11). Wklad rzeczowy
# w gruncie bada teraz aport INWESTORA — ta sama gałąź obliczeniowa, ten sam
# rozjazd miedzy wkladem brutto a gotowkowym, bez skutku ustrojowego.
APORT = dict(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")


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


class TestUsunietegoAportuGminy:
    """Pakiet nr 2, rozdz. 11 — wariant usuniety z zakresu, ale nie po cichu."""

    def test_aport_gminy_nie_jest_dopuszczalna_forma(self):
        from sim_kalkulator.dane import BladWalidacji, FormaGruntu

        assert "aport_gminy" not in {f.value for f in FormaGruntu}
        with pytest.raises(BladWalidacji, match="nieznana wartosc"):
            wspolne.wejscie(grunt__pochodzenie="gmina", grunt__forma="aport_gminy")

    def test_zadna_forma_nie_czyni_gminy_wspolnikiem(self):
        assert [w.forma for w in prawo.MATRYCA_GRUNTU if w.gmina_wspolnikiem] == []

    def test_dzialka_gminy_ma_cztery_formy(self):
        assert prawo.formy_dla_pochodzenia("gmina") == (
            "nabycie_od_gminy", "lokal_za_grunt", "uzytkowanie_wieczyste", "dzierzawa"
        )

    def test_interfejs_wyjasnia_brak_zamiast_milczec(self):
        # Gmina zaproponuje aport, bo dla niej to najprostsze — inwestor przy stole
        # ma dostac gotowa odpowiedz wraz z alternatywa, a nie puste miejsce.
        r = przelicz(wspolne.wejscie())
        wylaczone = api._grunt_json(r)["wylaczone"]
        assert len(wylaczone) == 1
        assert "lokal za grunt" in wylaczone[0]
        assert "prywatny SIM" in wylaczone[0]

    def test_przy_gruncie_inwestora_nie_ma_tego_wyjasnienia(self):
        r = przelicz(wspolne.wejscie(**APORT))
        assert api._grunt_json(r)["wylaczone"] == []

    def test_model_nie_liczy_juz_podzialu_udzialow(self):
        from sim_kalkulator import projekcja

        assert not hasattr(projekcja.Finansowanie, "udzial_gminy_w_spolce")
        assert not hasattr(prawo, "WIEKSZOSC_UDZIALOW")

    def test_wklad_rzeczowy_gminy_jest_zawsze_zerem(self):
        # Pole zostaje, bo rozroznienie "czyj wklad" jest potrzebne przy aporcie
        # inwestora, ale zadna dopuszczalna forma go juz nie zasila.
        for pochodzenie, forma, dodatki in (
            ("inwestor", "aport_inwestora", {}),
            ("gmina", "nabycie_od_gminy", {}),
            ("gmina", "uzytkowanie_wieczyste", {}),
            ("gmina", "dzierzawa", {}),
        ):
            r = przelicz(
                wspolne.wejscie(grunt__pochodzenie=pochodzenie, grunt__forma=forma, **dodatki)
            )
            assert r.finansowanie.wklad_rzeczowy_gminy_laczny == D("0"), forma


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

    def test_dzwignia_wskazuje_konkretna_sekcje_interfejsu(self):
        _, s = api.obsluz("sweep", api.wczytaj_parametry(wspolne.WZORCOWY), {})
        assert s["dzwignia_poza_osia"]["cel"] in {"grunt", "dzwignie"}


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


class TestKwotyKredytu:
    """Kredyt liczony automatycznie — co go ogranicza i czy jest obslugiwany."""

    def test_tryb_automatyczny_jest_domyslny(self):
        from sim_kalkulator.dane import Przelaczniki, TrybKredytu

        assert Przelaczniki().tryb_kredytu is TrybKredytu.AUTOMATYCZNY
        assert wspolne.wejscie().przelaczniki.tryb_kredytu is TrybKredytu.AUTOMATYCZNY

    def test_kwota_nie_pochodzi_z_udzialu_docelowego(self):
        # W trybie automatycznym `udzial_docelowy` nie wyznacza kwoty.
        for udzial in (0.10, 0.40, 0.80):
            r = przelicz(
                wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=udzial, **APORT)
            )
            wg_udzialu = r.alokacja.spoleczna.koszty_przedsiewziecia * D(str(udzial))
            assert abs(r.finansowanie.kredyt_laczny - wg_udzialu) > D("1")

    def test_ta_sama_kwota_niezaleznie_od_udzialu_docelowego(self):
        kwoty = {
            przelicz(
                wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=u, **APORT)
            ).finansowanie.kredyt_laczny
            for u in (0.10, 0.25, 0.60)
        }
        assert len(kwoty) == 1

    def test_zerowy_udzial_wylacza_kredyt_zamiast_zostawiac_go_bez_obslugi(self):
        # Regresja: silnik przyjmowal kredyt, a projekcja szla sciezka grantowa —
        # rata nigdy nie byla naliczana, wiec kredyt obnizal wklad za darmo.
        r = przelicz(
            wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=0.0, **APORT)
        )
        assert r.finansowanie.kredyt_laczny == D("0")
        assert r.projekcja.spoleczna.sciezka == "grant"

    def test_kazdy_przyjety_kredyt_jest_obslugiwany_w_projekcji(self):
        for udzial in (0.0, 0.25, 0.80):
            r = przelicz(
                wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=udzial, **APORT)
            )
            ma_kredyt = r.finansowanie.kredyt_laczny > 0
            placi_rate = any(rok.obsluga_dlugu > 0 for rok in r.projekcja.spoleczna.lata)
            assert ma_kredyt == placi_rate, f"udzial {udzial}"

    def test_kwota_ograniczona_potrzeba_a_nie_udzwigiem_czynszu(self):
        # Scenariusz odniesienia: dotacja, partycypacja i aport pokrywaja tyle,
        # ze brakujaca reszta jest mniejsza niz to, co uniosłby czynsz.
        r = przelicz(wspolne.wejscie(**APORT))
        f, a = r.finansowanie, r.alokacja
        potrzebny = (
            a.spoleczna.koszty_przedsiewziecia
            - f.spoleczna.grant
            - f.spoleczna.partycypacja
            - f.spoleczna.wklad_rzeczowy
        )
        assert f.kredyt_laczny == pytest.approx(potrzebny)
        assert f.kredyt_laczny < a.spoleczna.koszty_przedsiewziecia * D("0.80")


class TestWplywuCzynszuNaWklad:
    """Punkt 5 audytu — zaleznosc jest NIEROSNACA, nie scisle malejaca.

    Podniesienie czynszu obniza wymagany wklad tylko dopoki wiaze udzwig
    czynszowy. Gdy zwiazuje potrzeba — nikt nie zaciaga kredytu wiekszego niz
    brakujaca reszta — dalsze podnoszenie stawki nic nie daje i wklad stoi.
    """

    STAWKI = [D(str(x)) for x in (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32)]

    def wklady(self, **zmiany):
        wynikowe = []
        for stawka in self.STAWKI:
            r = przelicz(
                wspolne.wejscie(
                    pula_spoleczna__czynsz_zakladany_m2_mies=float(stawka), **zmiany
                )
            )
            wynikowe.append((stawka, r.finansowanie.wklad_gotowkowy_wymagany))
        return wynikowe

    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_wyzszy_czynsz_nigdy_nie_podnosi_wymaganego_wkladu(self, zmiany):
        pary = self.wklady(**zmiany)
        for (poprzednia, wcz), (biezaca, teraz) in zip(pary, pary[1:]):
            assert teraz <= wcz + D("0.01"), (
                f"wklad wzrosl z {wcz} do {teraz} przy podniesieniu czynszu "
                f"z {poprzednia} do {biezaca}"
            )

    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_w_zakresie_gdzie_wiaze_czynsz_wklad_scisle_maleje(self, zmiany):
        pary = self.wklady(**zmiany)
        malejace = [
            (a, b) for (_, a), (_, b) in zip(pary, pary[1:]) if b < a
        ]
        assert len(malejace) >= 4, "czynsz nie jest dzwignia w zadnym zakresie"

    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_plateau_rowna_sie_luce_poza_zasiegiem_czynszu(self, zmiany):
        # Gdy czynsz przestaje dzialac, zostaje dokladnie ta czesc luki, ktorej
        # nie da sie zamienic na kredyt — pula komunalna go nie ma.
        pary = self.wklady(**zmiany)
        najnizszy = min(w for _, w in pary)
        r = przelicz(
            wspolne.wejscie(
                pula_spoleczna__czynsz_zakladany_m2_mies=float(self.STAWKI[-1]), **zmiany
            )
        )
        assert najnizszy == pytest.approx(r.luka_poza_zasiegiem_czynszu)

    def test_czynsz_domykajacy_faktycznie_sprowadza_wklad_do_reszty(self):
        r = przelicz(wspolne.wejscie(**APORT))
        domykajacy = r.czynsz_domykajacy_m2_mies
        assert domykajacy is not None
        po = przelicz(
            wspolne.wejscie(
                pula_spoleczna__czynsz_zakladany_m2_mies=float(round(domykajacy, 2)),
                **APORT,
            )
        )
        assert po.finansowanie.wklad_gotowkowy_wymagany == pytest.approx(
            r.luka_poza_zasiegiem_czynszu
        )

    def test_w_trybie_recznym_stawka_domykajaca_jest_oznaczona_jako_hipotetyczna(self):
        r = przelicz(
            wspolne.wejscie(przelaczniki__tryb_kredytu="reczny", **APORT)
        )
        assert r.czynsz_domykajacy_jest_hipotetyczny is True
        c = api._czynsz_poziomy(r)
        assert "ustawiasz samodzielnie" in c["zastrzezenie_do_wymaganego"]

    def test_w_trybie_recznym_czynsz_nie_zmienia_kredytu(self):
        kwoty = {
            przelicz(
                wspolne.wejscie(
                    przelaczniki__tryb_kredytu="reczny",
                    pula_spoleczna__czynsz_zakladany_m2_mies=c,
                    **APORT,
                )
            ).finansowanie.kredyt_laczny
            for c in (12.0, 22.0, 30.0)
        }
        assert len(kwoty) == 1


class TestBuforaObslugiDlugu:
    """Pakiet naprawczy nr 2, rozdz. 1 — kredyt wymierzany z marginesem."""

    def test_wartosc_domyslna_wynosi_1_20(self):
        w = wspolne.wejscie()
        assert (
            w.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
            == D("1.20")
        )

    def test_brak_wpisu_daje_wariant_ostrozniejszy_a_nie_brak_bufora(self):
        # Reguly projektu zabraniaja podstawiania parametrow zewnetrznych. Tutaj
        # wyjatek jest swiadomy i idzie w strone ostrozniejsza: brak wpisu daje
        # bufor, a nie jego brak — i zawsze z ostrzezeniem.
        w = wspolne.wejscie(
            parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=wspolne.USUN
        )
        assert (
            w.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
            == prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY
        )
        assert "ZALOZENIE_BUFOR_OBSLUGI_DLUGU" in {o.kod for o in w.ostrzezenia}

    def test_ponizej_jednosci_jest_bledem_walidacji(self):
        from sim_kalkulator.dane import BladWalidacji

        with pytest.raises(BladWalidacji):
            wspolne.wejscie(
                parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=0.9
            )

    def test_bez_kredytu_nie_ma_ostrzezenia_o_buforze(self):
        # Pula wylacznie komunalna — kredyt niedopuszczalny (art. 5a ust. 3),
        # wiec bufor nie ma czego dotyczyc i nie zaSmieca listy ostrzezen.
        w = wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=1.0)
        kody_o = {o.kod for o in w.ostrzezenia}
        assert "ZALOZENIE_BUFOR_OBSLUGI_DLUGU" not in kody_o
        assert "BUFOR_OBSLUGI_DLUGU_ZEROWY" not in kody_o

    def test_bufor_obniza_kredyt_i_podnosi_wymagany_wklad(self):
        bez = przelicz(
            wspolne.wejscie(
                parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=1.0
            )
        )
        z_buforem = przelicz(wspolne.wejscie())
        assert z_buforem.finansowanie.spoleczna.kredyt < bez.finansowanie.spoleczna.kredyt
        assert (
            z_buforem.finansowanie.wklad_wlasny_wymagany
            > bez.finansowanie.wklad_wlasny_wymagany
        )

    def test_projekcja_potwierdza_zadany_bufor(self):
        r = przelicz(wspolne.wejscie())
        osiagniete = r.projekcja.spoleczna.minimalne_pokrycie_obslugi_dlugu
        zadany = r.wejscie.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
        assert osiagniete >= zadany

    def test_api_podaje_bufor_i_osiagniete_pokrycie(self):
        z = api.wynik_json(przelicz(wspolne.wejscie()))
        spoleczna = next(p for p in z["pule"] if p["nazwa"] == "spoleczna")
        assert spoleczna["bufor_obslugi_dlugu"] == pytest.approx(1.20)
        assert spoleczna["min_pokrycie_obslugi_dlugu"] >= 1.20

    def test_panel_parametrow_oznacza_bufor_jako_zalozenie(self):
        z = api.zakresy_json(przelicz(wspolne.wejscie()))
        pozycja = next(
            p for p in z["parametry_rynkowe"]["pozycje"]
            if p["klucz"].endswith("minimalny_wskaznik_pokrycia_obslugi_dlugu")
        )
        assert pozycja["zalozenie"] is True
        assert "BGK" in pozycja["podpis"]

    def test_najgorszy_rok_wiaze_a_nie_pierwszy(self):
        # Odpowiedz na pytanie towarzyszace z rozdz. 1: udzwig liczony jest
        # na roku najgorszym. Przy indeksacji kosztow szybszej od czynszu
        # waskie gardlo wypada na koncu okresu, nie w roku pierwszym.
        r = przelicz(
            wspolne.wejscie(
                eksploatacja__indeksacja_kosztow_rocznie=0.045,
                eksploatacja__indeksacja_czynszu_rocznie=0.020,
            )
        )
        pokrycia = [
            rok.pokrycie_obslugi_dlugu
            for rok in r.projekcja.spoleczna.lata
            if rok.pokrycie_obslugi_dlugu is not None
        ]
        assert pokrycia[0] > pokrycia[-1]
        assert r.projekcja.spoleczna.minimalne_pokrycie_obslugi_dlugu == pokrycia[-1]
        # Wiazacy jest ostatni rok KREDYTU, a nie ostatni rok sciezki grantowej.
        # Projekcja bez kredytu konczy sie na 25 latach; gdyby udzwig liczono na
        # niej, lata 26-30 nie bylyby zbadane i kredyt wyszedlby za duzy.
        assert len(pokrycia) == r.wejscie.pula_spoleczna.kredyt.okres_lat
        assert pokrycia[-1] >= D("1.20")
