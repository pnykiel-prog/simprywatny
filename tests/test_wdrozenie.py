"""Wdrozenie na Vercela — funkcje serverless i konfiguracja.

Ta sciezka wczesniej nie istniala i dlatego wdrozenie sie wywracalo. Testy
pilnuja trzech rzeczy: ze funkcje sa poprawnie zbudowane, ze wolaja ten sam
silnik co serwer lokalny, i ze konfiguracja pokrywa wszystkie trasy uzywane
przez interfejs.
"""

import importlib.util
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from sim_kalkulator import api as _api

KORZEN = Path(__file__).resolve().parent.parent
API = KORZEN / "api"
AKCJE = ("przelicz", "sweep", "parametry", "arkusz")


def zaladuj(nazwa):
    sciezka = API / f"{nazwa}.py"
    spec = importlib.util.spec_from_file_location(f"api_{nazwa}", sciezka)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def uruchom(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def wolaj(adres, cialo=None):
    dane = json.dumps(cialo).encode() if cialo is not None else None
    zadanie = urllib.request.Request(
        adres + "/", data=dane,
        headers={"Content-Type": "application/json"} if dane else {},
    )
    try:
        with urllib.request.urlopen(zadanie, timeout=120) as odp:
            return odp.status, odp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


class TestStrukturaKatalogu:
    def test_kazdy_plik_w_api_jest_funkcja_z_handlerem(self):
        # Vercel buduje kazdy plik .py w api/ jako funkcje. Plik pomocniczy
        # bez obiektu `handler` wywrocilby build calego wdrozenia.
        pliki = sorted(p.stem for p in API.glob("*.py"))
        assert pliki, "katalog api/ jest pusty"
        for nazwa in pliki:
            assert hasattr(zaladuj(nazwa), "handler"), f"api/{nazwa}.py bez `handler`"

    def test_katalog_api_nie_ma_plikow_pomocniczych(self):
        pomocnicze = [p.name for p in API.glob("*.py") if p.stem.startswith("_")]
        assert pomocnicze == [], f"pliki pomocnicze w api/: {pomocnicze}"

    def test_sa_funkcje_dla_wszystkich_tras_uzywanych_przez_ui(self):
        html = (KORZEN / "web" / "index.html").read_text(encoding="utf-8")
        wolane = set(re.findall(r'api\("/api/(\w+)"', html))
        assert wolane, "UI nie wola zadnego endpointu"
        dostepne = {p.stem for p in API.glob("*.py")}
        assert wolane <= dostepne, f"UI wola trasy bez funkcji: {wolane - dostepne}"

    def test_jest_funkcja_serwujaca_strone(self):
        assert (API / "index.py").exists()


class TestKonfiguracja:
    def test_vercel_json_jest_poprawnym_jsonem(self):
        dane = json.loads((KORZEN / "vercel.json").read_text(encoding="utf-8"))
        assert "rewrites" in dane

    def test_korzen_prowadzi_do_strony(self):
        dane = json.loads((KORZEN / "vercel.json").read_text(encoding="utf-8"))
        zrodla = {r["source"]: r["destination"] for r in dane["rewrites"]}
        assert zrodla.get("/") == "/api/index"

    def test_requirements_pokrywa_zaleznosci_spoza_biblioteki_standardowej(self):
        tresc = (KORZEN / "requirements.txt").read_text(encoding="utf-8").lower()
        for pakiet in ("openpyxl", "pyyaml"):
            assert pakiet in tresc, f"brak {pakiet} w requirements.txt"

    def test_requirements_nie_zawiera_pytest(self):
        # Zaleznosci testowe nie maja po co jechac na wdrozenie.
        tresc = (KORZEN / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "pytest" not in tresc


class TestFunkcjeOdpowiadaja:
    @pytest.mark.parametrize("akcja", AKCJE)
    def test_get_zwraca_poprawny_json(self, akcja):
        srv, adres = uruchom(zaladuj(akcja).handler)
        try:
            kod, tresc = wolaj(adres)
        finally:
            srv.shutdown()
            srv.server_close()
        assert kod == 200
        assert json.loads(tresc)["ok"] is True

    @pytest.mark.parametrize("akcja", AKCJE)
    def test_post_ze_zmianami_dziala(self, akcja):
        srv, adres = uruchom(zaladuj(akcja).handler)
        try:
            kod, tresc = wolaj(
                adres, {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.45}}
            )
        finally:
            srv.shutdown()
            srv.server_close()
        assert kod == 200 and json.loads(tresc)["ok"] is True

    def test_strona_glowna_serwuje_interfejs(self):
        srv, adres = uruchom(zaladuj("index").handler)
        try:
            with urllib.request.urlopen(adres + "/", timeout=30) as odp:
                tresc = odp.read().decode()
                typ = odp.headers.get("Content-Type")
        finally:
            srv.shutdown()
            srv.server_close()
        assert "<title>Kalkulator montażu" in tresc
        assert "text/html" in typ

    def test_blad_walidacji_wraca_z_powodem_a_nie_wywala_funkcji(self):
        srv, adres = uruchom(zaladuj("przelicz").handler)
        try:
            kod, tresc = wolaj(
                adres, {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 1.0}}
            )
        finally:
            srv.shutdown()
            srv.server_close()
        dane = json.loads(tresc)
        assert kod == 400 and dane["ok"] is False
        assert "art. 5a ust. 3" in dane["powod"]

    def test_niepoprawne_cialo_zadania_nie_wywala_funkcji(self):
        srv, adres = uruchom(zaladuj("przelicz").handler)
        try:
            zadanie = urllib.request.Request(
                adres + "/", data=b"{to nie jest json",
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(zadanie, timeout=30) as odp:
                    kod, tresc = odp.status, odp.read().decode()
            except urllib.error.HTTPError as exc:
                kod, tresc = exc.code, exc.read().decode()
        finally:
            srv.shutdown()
            srv.server_close()
        assert kod == 400 and json.loads(tresc)["ok"] is False


class TestJedenSilnik:
    """Wdrozenie i serwer lokalny musza liczyc dokladnie to samo."""

    def test_funkcja_daje_ten_sam_wynik_co_warstwa_wspolna(self):
        srv, adres = uruchom(zaladuj("przelicz").handler)
        try:
            _, tresc = wolaj(adres, {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.4}})
        finally:
            srv.shutdown()
            srv.server_close()
        z_funkcji = json.loads(tresc)

        from sim_kalkulator.serverless import parametry_bazowe

        _, z_warstwy = _api.obsluz(
            "przelicz", parametry_bazowe(), {"powierzchnie.udzial_puli_komunalnej": 0.4}
        )
        assert z_funkcji["domyka_sie"] == z_warstwy["domyka_sie"]
        assert z_funkcji["wklad_wymagany"] == z_warstwy["wklad_wymagany"]
        assert z_funkcji["edb_kredytu"] == z_warstwy["edb_kredytu"]

    def test_serwer_lokalny_i_funkcja_uzywaja_tej_samej_warstwy(self):
        import serwer
        from sim_kalkulator import serverless

        assert serwer._api is _api
        assert serverless._api is _api


class TestArkuszBezSystemuPlikow:
    """Na Vercelu system plikow jest tylko do odczytu — arkusz wraca strumieniem."""

    def test_arkusz_wraca_w_base64_a_nie_sciezka(self):
        srv, adres = uruchom(zaladuj("arkusz").handler)
        try:
            _, tresc = wolaj(adres, {"zmiany": {}})
        finally:
            srv.shutdown()
            srv.server_close()
        dane = json.loads(tresc)
        assert "arkusz_base64" in dane and "parametry_yaml" in dane
        assert dane["nazwa"]

    def test_zwrocone_bajty_to_prawdziwy_skoroszyt(self, tmp_path):
        import base64

        import openpyxl

        srv, adres = uruchom(zaladuj("arkusz").handler)
        try:
            _, tresc = wolaj(adres, {"zmiany": {}})
        finally:
            srv.shutdown()
            srv.server_close()
        dane = json.loads(tresc)
        plik = tmp_path / "z_funkcji.xlsx"
        plik.write_bytes(base64.b64decode(dane["arkusz_base64"]))
        wb = openpyxl.load_workbook(plik)
        assert wb.sheetnames == [
            "Zalozenia", "Alokacja", "Pula_spoleczna", "Pula_komunalna",
            "Rekompensata", "Werdykty", "Wrazliwosc", "Podstawy_prawne",
        ]

    def test_zwrocony_yaml_odtwarza_ten_sam_wariant(self, tmp_path):
        from sim_kalkulator.dane import wczytaj_yaml
        from sim_kalkulator.silnik import przelicz

        srv, adres = uruchom(zaladuj("arkusz").handler)
        try:
            _, tresc = wolaj(adres, {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.5}})
        finally:
            srv.shutdown()
            srv.server_close()
        plik = tmp_path / "parametry.yaml"
        plik.write_text(json.loads(tresc)["parametry_yaml"], encoding="utf-8")
        r = przelicz(wczytaj_yaml(plik))
        assert float(r.wejscie.powierzchnie.udzial_puli_komunalnej) == 0.5


class TestBezstanowosc:
    """Funkcja serverless nie pamieta niczego miedzy wywolaniami."""

    def test_zmiany_nie_wyciekaja_do_kolejnego_zadania(self):
        srv, adres = uruchom(zaladuj("przelicz").handler)
        try:
            _, ze_zmiana = wolaj(
                adres, {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.9}}
            )
            _, bez_zmiany = wolaj(adres, {"zmiany": {}})
        finally:
            srv.shutdown()
            srv.server_close()
        assert json.loads(ze_zmiana)["udzial_komunalny"] == 0.9
        assert json.loads(bez_zmiany)["udzial_komunalny"] == 0.3

    def test_zastosuj_zmiany_nie_rusza_oryginalu(self):
        bazowe = _api.wczytaj_parametry(KORZEN / "przyklady" / "domykajacy_sie.yaml")
        _api.zastosuj_zmiany(bazowe, {"koszty.rezerwa": 1})
        assert bazowe["koszty"]["rezerwa"] != 1
