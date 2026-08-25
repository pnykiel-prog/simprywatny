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


def konfiguracja():
    return json.loads((KORZEN / "vercel.json").read_text(encoding="utf-8"))


# Katalogi spoza `api/`, ktorych funkcje potrzebuja w czasie dzialania:
# pakiet silnika, plik interfejsu i parametry bazowe. Jezeli ktorykolwiek nie
# trafi do paczki funkcji, wdrozenie wywala sie w czasie dzialania, nie przy
# budowaniu — dlatego istnieje endpoint /api/diag.
KATALOGI_CZASU_DZIALANIA = ("sim_kalkulator", "przyklady", "web")


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
        assert isinstance(konfiguracja(), dict)

    def test_korzen_prowadzi_do_strony(self):
        zrodla = {r["source"]: r["destination"] for r in konfiguracja()["rewrites"]}
        assert zrodla.get("/") == "/api/index"

    def test_konfiguracja_nie_przestawia_katalogu_wyjsciowego(self):
        # `outputDirectory` przesuwa katalog, w ktorym platforma szuka funkcji,
        # przez co `api/` w korzeniu przestaje byc widoczne i build konczy sie
        # bledem "pattern doesn't match any Serverless Functions".
        assert "outputDirectory" not in konfiguracja()

    def test_include_files_pokrywa_katalogi_czasu_dzialania(self):
        # Blok `functions` sluzy wylacznie temu, zeby pliki spoza api/ trafily
        # do paczki funkcji. Sam w sobie buildu nie psuje — psulo go
        # outputDirectory, ktore przestawialo katalog poszukiwan.
        wzorzec = konfiguracja()["functions"]["api/*.py"]["includeFiles"]
        objete = {w.strip().split("/")[0] for w in wzorzec.strip("{}").split(",")}
        assert objete >= set(KATALOGI_CZASU_DZIALANIA)

    def test_wzorzec_funkcji_pasuje_do_istniejacych_plikow(self):
        # Wzorzec, ktory nic nie lapie, przerywa build komunikatem
        # "doesn't match any Serverless Functions inside the api directory".
        wzorzec = next(iter(konfiguracja()["functions"]))
        assert wzorzec == "api/*.py"
        assert list(API.glob("*.py")), "wzorzec api/*.py nie lapie zadnego pliku"

    def test_vercelignore_nie_wyklucza_niczego_potrzebnego(self):
        wykluczone = {
            w.strip().rstrip("/")
            for w in (KORZEN / ".vercelignore").read_text(encoding="utf-8").splitlines()
            if w.strip() and not w.startswith("#")
        }
        assert wykluczone.isdisjoint(set(KATALOGI_CZASU_DZIALANIA))

    def test_requirements_pokrywa_zaleznosci_spoza_biblioteki_standardowej(self):
        tresc = (KORZEN / "requirements.txt").read_text(encoding="utf-8").lower()
        for pakiet in ("openpyxl", "pyyaml"):
            assert pakiet in tresc, f"brak {pakiet} w requirements.txt"

    def test_requirements_nie_zawiera_pytest(self):
        # Zaleznosci testowe nie maja po co jechac na wdrozenie.
        tresc = (KORZEN / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "pytest" not in tresc


class TestPaczkaFunkcji:
    """Symulacja paczki funkcji: katalog api/ plus katalogi czasu dzialania.

    Sprawdza, ze funkcja startuje, gdy te pliki sa na miejscu — i ze bez nich
    konczy sie czytelnym bledem, a nie cicha awaria."""

    @staticmethod
    @pytest.fixture(scope="class")
    def paczka(tmp_path_factory):
        import shutil

        cel = tmp_path_factory.mktemp("paczka")
        shutil.copytree(KORZEN / "api", cel / "api")
        for katalog in KATALOGI_CZASU_DZIALANIA:
            zrodlo = KORZEN / katalog
            if zrodlo.is_dir():
                shutil.copytree(
                    zrodlo, cel / katalog, ignore=shutil.ignore_patterns("__pycache__")
                )
        return cel

    def test_funkcja_startuje_w_paczce(self, paczka):
        import subprocess
        import sys as _sys

        skrypt = (
            "import importlib.util,sys;from pathlib import Path;"
            "spec=importlib.util.spec_from_file_location('fn',"
            "Path(sys.argv[1])/'api'/'przelicz.py');"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "print('handler' if hasattr(m,'handler') else 'brak')"
        )
        r = subprocess.run(
            [_sys.executable, "-c", skrypt, str(paczka)],
            cwd=paczka, capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0, r.stderr[-800:]
        assert r.stdout.strip() == "handler"

    def test_paczka_bez_pakietu_silnika_odpowiada_diagnoza_nie_pustym_500(self, tmp_path):
        # Import silnika dzieje sie przy ladowaniu modulu, czyli zanim
        # jakikolwiek kod obslugi bledow zdazy zadzialac. Straznik startu
        # zamienia nieczytelne 500 platformy na odpowiedz mowiaca, czego brakuje.
        import shutil
        import subprocess
        import sys as _sys

        shutil.copytree(KORZEN / "api", tmp_path / "api")
        skrypt = (
            "import importlib.util,sys,threading,urllib.request,urllib.error;"
            "from http.server import ThreadingHTTPServer;from pathlib import Path;"
            "K=Path(sys.argv[1]);"
            "spec=importlib.util.spec_from_file_location('fn',K/'api'/'diag.py');"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "srv=ThreadingHTTPServer(('127.0.0.1',0),m.handler);"
            "threading.Thread(target=srv.serve_forever,daemon=True).start();"
            "url='http://127.0.0.1:%d/'%srv.server_address[1];"
            "\ntry:\n    urllib.request.urlopen(url,timeout=30)"
            "\nexcept urllib.error.HTTPError as e:\n    print(e.code);print(e.read().decode())"
        )
        r = subprocess.run(
            [_sys.executable, "-c", skrypt, str(tmp_path)],
            cwd=tmp_path, capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0, r.stderr[-800:]
        kod, _, cialo = r.stdout.partition("\n")
        assert kod.strip() == "500"
        raport = json.loads(cialo)
        assert raport["ok"] is False
        assert raport["typ"] == "start"
        assert "No module named 'sim_kalkulator'" in raport["powod"]
        assert raport["pakiet_silnika_obecny"] is False
        assert "includeFiles" in raport["podpowiedz"]

    def test_straznik_startu_jest_w_kazdej_funkcji(self):
        for plik in API.glob("*.py"):
            tresc = plik.read_text(encoding="utf-8")
            assert "typ\": \"start" in tresc or '"typ": "start"' in tresc, plik.name

    def test_wszystkie_pliki_czasu_dzialania_sa_w_paczce(self, paczka):
        assert (paczka / "sim_kalkulator" / "silnik.py").exists()
        assert (paczka / "web" / "index.html").exists()
        assert (paczka / "przyklady" / "domykajacy_sie.yaml").exists()


class TestDiagnostyka:
    def test_diag_potwierdza_kompletnosc_paczki(self):
        srv, adres = uruchom(zaladuj("diag").handler)
        try:
            kod, tresc = wolaj(adres)
        finally:
            srv.shutdown()
            srv.server_close()
        dane = json.loads(tresc)
        assert kod == 200 and dane["ok"] is True
        assert dane["pakiet_silnika"]["istnieje"]
        assert dane["interfejs"]["istnieje"]
        assert dane["parametry"]["istnieje"]
        assert dane["silnik"]["przeliczenie"] == "ok"

    def test_diag_nie_ujawnia_zmiennych_srodowiskowych(self):
        srv, adres = uruchom(zaladuj("diag").handler)
        try:
            _, tresc = wolaj(adres)
        finally:
            srv.shutdown()
            srv.server_close()
        assert "environ" not in tresc and "SECRET" not in tresc.upper()


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
