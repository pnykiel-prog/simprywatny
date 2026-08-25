"""Etap 10 — API serwera. UI wola API, API wola silnik; przegladarka nie liczy."""

import json
import threading
import urllib.error
import urllib.request
from decimal import Decimal as D
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import serwer
from sim_kalkulator.dane import BladWalidacji

from . import wspolne

DOMYKAJACY = wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"


@pytest.fixture(scope="module")
def adres():
    serwer.Uchwyt.stan = serwer.Stan(DOMYKAJACY)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), serwer.Uchwyt)
    watek = threading.Thread(target=srv.serve_forever, daemon=True)
    watek.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def wolaj(adres, sciezka, cialo=None):
    dane = json.dumps(cialo).encode() if cialo is not None else None
    zadanie = urllib.request.Request(
        adres + sciezka, data=dane,
        headers={"Content-Type": "application/json"} if dane else {},
    )
    try:
        with urllib.request.urlopen(zadanie, timeout=180) as odp:
            return odp.status, json.loads(odp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


class TestStronaGlowna:
    def test_serwuje_jednoplikowy_html(self, adres):
        with urllib.request.urlopen(adres + "/", timeout=30) as odp:
            tresc = odp.read().decode()
        assert odp.status == 200
        assert "<title>Kalkulator montażu" in tresc

    def test_ui_nie_ma_zaleznosci_zewnetrznych_z_sieci(self, adres):
        import re

        tresc = (Path(serwer.WEB) / "index.html").read_text(encoding="utf-8")
        # Przed sprawdzeniem wycinamy dwie rzeczy, ktore wygladaja jak adres,
        # a niczego nie pobieraja: data-URI oraz identyfikator przestrzeni nazw
        # SVG, ktory jest wymagany przez createElementNS.
        oczyszczone = re.sub(r'href="data:[^"]*"', 'href="data:"', tresc)
        oczyszczone = oczyszczone.replace("http://www.w3.org/2000/svg", "<svg-ns>")
        for wzorzec in ("http://", "https://", "cdn.", "<script src", '<link rel="stylesheet"'):
            assert wzorzec not in oczyszczone, f"UI siega po zasob zewnetrzny: {wzorzec}"

    def test_ui_nie_pobiera_niczego_z_obcego_zrodla(self, adres):
        import re

        tresc = (Path(serwer.WEB) / "index.html").read_text(encoding="utf-8")
        zrodla = re.findall(r'(?:src|href)="([^"]+)"', tresc)
        for zrodlo in zrodla:
            assert zrodlo.startswith("data:") or zrodlo.startswith("/") or zrodlo.startswith("#"), (
                f"UI odwoluje sie do zasobu spoza wlasnego pochodzenia: {zrodlo}"
            )

    def test_ui_nie_liczy_niczego_poza_formatowaniem(self, adres):
        # Jeden silnik. W JavaScripcie nie ma prawa byc zadnej stalej z ustawy.
        tresc = (Path(serwer.WEB) / "index.html").read_text(encoding="utf-8")
        skrypt = tresc.split("<script>")[1]
        for stala in ("0.45", "0.35", "0.80", "0.025", "0.035", "OKRES_POWIERZENIA"):
            assert stala not in skrypt, f"Stala '{stala}' zaszyta w UI"

    def test_ui_niesie_zastrzezenia_z_rozdzialu_13(self, adres):
        tresc = (Path(serwer.WEB) / "index.html").read_text(encoding="utf-8")
        assert "Nie zastępuje wyliczenia Banku" in tresc
        assert "niepotwierdzona" in tresc
        assert "Wiążące jest wyliczenie Banku" in tresc


class TestPrzelicz:
    def test_zwraca_trzy_werdykty(self, adres):
        kod, dane = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        assert kod == 200 and dane["ok"] is True
        assert [t["numer"] for t in dane["werdykty"]] == [1, 2, 3]

    def test_kazdy_werdykt_ma_liczbe_i_wiazace_ograniczenie(self, adres):
        _, dane = wolaj(adres, "/api/przelicz",
                        {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.75}})
        for t in dane["werdykty"]:
            assert t["wiazace_ograniczenie"]
            if not t["przechodzi"]:
                assert t["luka_kwota"] is not None and t["luka_kwota"] > 0
                assert t["luka_jednostka"]

    def test_wskazniki_licza_sie_na_m2_pum(self, adres):
        _, dane = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        assert set(dane["na_m2"]) == {
            "koszt", "grant", "kredyt", "partycypacja", "wklad_wlasny", "luka_kapitalowa"
        }

    def test_suwak_zmienia_wynik(self, adres):
        _, malo = wolaj(adres, "/api/przelicz",
                        {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.1}})
        _, duzo = wolaj(adres, "/api/przelicz",
                        {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.95}})
        assert duzo["wklad_wymagany"] > malo["wklad_wymagany"]
        assert malo["domyka_sie"] and not duzo["domyka_sie"]

    def test_api_zgadza_sie_z_silnikiem(self, adres):
        from sim_kalkulator.dane import wczytaj_yaml
        from sim_kalkulator.silnik import przelicz

        _, dane = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        r = przelicz(wczytaj_yaml(DOMYKAJACY))
        assert dane["domyka_sie"] == r.domyka_sie
        assert dane["wklad_wymagany"] == pytest.approx(
            float(r.finansowanie.wklad_wlasny_wymagany)
        )
        assert dane["edb_kredytu"] == pytest.approx(float(r.edb_kredytu))

    def test_ostrzezenia_wracaja_do_ui(self, adres):
        _, dane = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        kody = {o["kod"] for o in dane["ostrzezenia"]}
        assert "ZALOZENIE_ROZSADNY_ZYSK" in kody
        assert all(o["tresc"] for o in dane["ostrzezenia"])

    def test_rekompensata_niesie_ujecie_gruntu(self, adres):
        _, dane = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        assert dane["rekompensata"]
        assert all(p["grunt_ujecie"] for p in dane["rekompensata"])

    def test_daty_z_yaml_serializuja_sie(self, adres):
        kod, dane = wolaj(adres, "/api/parametry")
        assert kod == 200
        assert isinstance(dane["parametry"]["parametry_zewnetrzne"]["data_parametrow"], str)


class TestBledy:
    def test_kredyt_reczny_przy_pelnej_puli_komunalnej_to_blad_walidacji(self, adres):
        kod, dane = wolaj(adres, "/api/przelicz", {"zmiany": {
            "przelaczniki.tryb_kredytu": "reczny",
            "powierzchnie.udzial_puli_komunalnej": 1.0,
        }})
        assert kod == 400 and dane["ok"] is False
        assert dane["typ"] == "walidacja"
        assert "art. 5a ust. 3" in dane["powod"]

    def test_czynsz_ponad_limit_jest_sciagany_a_nie_zglaszany_jako_blad(self, adres):
        # Ograniczenie ustawowe jest wbudowane w sterowanie: stawka ponad limit
        # zostaje sciagnieta i zakomunikowana, zamiast wracac jako blad.
        kod, dane = wolaj(adres, "/api/przelicz",
                          {"zmiany": {"pula_spoleczna.czynsz_zakladany_m2_mies": 99.0}})
        assert kod == 200 and dane["ok"] is True
        assert dane["sciagniete"], "sciagniecie stawki nie zostalo zakomunikowane"
        assert "obniżony" in dane["sciagniete"][0]
        pula = next(p for p in dane["pule"] if p["nazwa"] == "spoleczna")
        assert pula["czynsz"] <= pula["limit_czynszu"]

    def test_silnik_nadal_odmawia_liczenia_stawki_ponad_limit(self):
        # Sciaganie dzieje sie w warstwie API. Sam silnik ma pozostac twardy —
        # nie liczy scenariusza bezprawnego, kto by go nie podal.
        from sim_kalkulator import alokacja, czynsz, grant
        from sim_kalkulator.dane import BladWalidacji as BW, wczytaj_yaml

        w = wczytaj_yaml(DOMYKAJACY)
        a = alokacja.build(w)
        g = grant.build(w, a)
        with pytest.raises(BW, match="przekracza limit wiazacy"):
            czynsz.build(w, a.spoleczna, g.spoleczna, D("99"), True)

    def test_nieznany_parametr_jest_odrzucany(self, adres):
        kod, dane = wolaj(adres, "/api/przelicz", {"zmiany": {"koszty.wymyslony": 1}})
        assert kod == 400 and "Nieznany parametr" in dane["powod"]

    def test_sciezka_z_dziwnymi_znakami_jest_odrzucana(self, adres):
        kod, dane = wolaj(adres, "/api/przelicz", {"zmiany": {"../../etc/passwd": 1}})
        assert kod == 400 and "Niepoprawna sciezka" in dane["powod"]

    def test_brak_parametru_zewnetrznego_zatrzymuje_obliczenie(self, adres):
        kod, dane = wolaj(adres, "/api/przelicz",
                          {"zmiany": {"parametry_zewnetrzne.stopa_referencyjna_ke": None}})
        assert kod == 400
        assert "stopa_referencyjna_ke" in dane["powod"]

    def test_diag_dostepny_takze_lokalnie(self, adres):
        # Endpoint diagnostyczny ma dzialac w obu srodowiskach, inaczej nie da
        # sie porownac dzialajacego lokalnie z niedzialajacym wdrozeniem.
        kod, dane = wolaj(adres, "/api/diag")
        assert kod == 200
        assert dane["ok"] is True
        assert dane["silnik"]["przeliczenie"] == "ok"

    def test_nieznany_zasob_daje_404(self, adres):
        kod, dane = wolaj(adres, "/api/nie-ma")
        assert kod == 404 and dane["ok"] is False


class TestSweep:
    def test_sweep_zwraca_21_punktow_i_punkt_graniczny(self, adres):
        kod, dane = wolaj(adres, "/api/sweep", {"zmiany": {}})
        assert kod == 200
        assert len(dane["punkty"]) == 21
        assert dane["maksymalny_udzial"] == pytest.approx(0.75)
        assert dane["punkt_graniczny"] == pytest.approx(0.80)

    def test_punkty_niepoliczalne_niosa_powod(self, adres):
        # W trybie automatycznym caly zakres jest policzalny; niepoliczalne
        # punkty pojawiaja sie dopiero, gdy kredyt ustawia sie recznie.
        _, dane = wolaj(adres, "/api/sweep",
                        {"zmiany": {"przelaczniki.tryb_kredytu": "reczny"}})
        niepoliczalne = [p for p in dane["punkty"] if not p["policzalny"]]
        assert niepoliczalne
        assert all(p["powod"] for p in niepoliczalne)

    def test_tryb_automatyczny_liczy_caly_zakres(self, adres):
        _, dane = wolaj(adres, "/api/sweep", {"zmiany": {}})
        assert all(p["policzalny"] for p in dane["punkty"])

    def test_ranking_obejmuje_stope_referencyjna(self, adres):
        _, dane = wolaj(adres, "/api/sweep", {"zmiany": {}})
        assert any(r["nazwa"] == "Stopa referencyjna KE" for r in dane["ranking"])


class TestArkusz:
    def test_generuje_arkusz_i_zapisuje_parametry(self, adres, monkeypatch, tmp_path):
        monkeypatch.setattr(serwer, "WYNIKI", tmp_path)
        kod, dane = wolaj(adres, "/api/arkusz",
                          {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.35}})
        assert kod == 200 and dane["ok"] is True
        xlsx, yml = Path(dane["arkusz"]), Path(dane["parametry"])
        assert xlsx.exists() and yml.exists()
        assert "recalc.py" in dane["komunikat"]

    def test_zapisany_yaml_odtwarza_ten_sam_wynik(self, adres, monkeypatch, tmp_path):
        from sim_kalkulator.dane import wczytaj_yaml
        from sim_kalkulator.silnik import przelicz

        monkeypatch.setattr(serwer, "WYNIKI", tmp_path)
        _, dane = wolaj(adres, "/api/arkusz",
                        {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.35}})
        r = przelicz(wczytaj_yaml(Path(dane["parametry"])))
        assert r.wejscie.powierzchnie.udzial_puli_komunalnej == D("0.35")
        _, z_api = wolaj(adres, "/api/przelicz",
                         {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.35}})
        assert z_api["domyka_sie"] == r.domyka_sie


class TestStan:
    def test_podmiana_nie_rusza_oryginalu(self):
        stan = serwer.Stan(DOMYKAJACY)
        stan.podmien({"koszty.rezerwa": 1})
        assert stan.kopia()["koszty"]["rezerwa"] != 1

    def test_nieznana_sekcja_to_blad(self):
        stan = serwer.Stan(DOMYKAJACY)
        with pytest.raises(BladWalidacji, match="Nieznana sekcja"):
            stan.podmien({"wymyslona.sekcja": 1})
