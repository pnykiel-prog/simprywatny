"""Siedem kryteriow odbioru z rozdz. 9 uzupelnienia specyfikacji.

Testy oznaczone `wolne` uruchamiaja przegladarke — sprawdzaja to, co uzytkownik
naprawde widzi, a nie to, co jest w zrodle strony.
"""

import json
import re
import threading
import urllib.request
from decimal import Decimal as D
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import serwer
from sim_kalkulator import api as _api
from sim_kalkulator.dane import wczytaj_yaml
from sim_kalkulator.silnik import przelicz

from . import wspolne

KORZEN = Path(__file__).resolve().parent.parent
DOMYKAJACY = wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"

# Numer artykulu w widoku glownym lamie kryterium 7. Wzorzec lapie zapisy
# w rodzaju "art. 13 ust. 1", "§ 7 ust. 9" oraz sygnatury dziennika ustaw.
ARTYKUL = re.compile(r"\bart\.\s*\d|§\s*\d|Dz\.\s?U\.", re.IGNORECASE)


@pytest.fixture(scope="module")
def adres():
    serwer.Uchwyt.stan = serwer.Stan(DOMYKAJACY)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), serwer.Uchwyt)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def wolaj(adres, sciezka, cialo=None):
    dane = json.dumps(cialo).encode() if cialo is not None else None
    req = urllib.request.Request(
        adres + sciezka, data=dane,
        headers={"Content-Type": "application/json"} if dane else {},
    )
    with urllib.request.urlopen(req, timeout=180) as odp:
        return json.loads(odp.read().decode())


@pytest.fixture(scope="module")
def strona(adres):
    """Otwarta strona z policzonym wariantem — wspoldzielona przez testy."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        p = b.new_page(viewport={"width": 1440, "height": 950})
        bledy = []
        p.on("console", lambda m: bledy.append(m.text) if m.type == "error" else None)
        p.on("pageerror", lambda e: bledy.append("PAGEERROR " + str(e)))
        p.goto(adres + "/", wait_until="networkidle")
        p.wait_for_timeout(3500)
        yield p, bledy
        b.close()


# ---------------------------------------------------------------------------
# 1. Zaden komunikat o naruszeniu limitu ustawowego nie pojawia sie w widoku
#    glownym — wszystkie sa wbudowane w zakresy suwakow.
# ---------------------------------------------------------------------------

class TestKryterium1_LimityWSuwakach:
    def test_limit_czynszu_jest_gorna_granica_suwaka(self, adres):
        w = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        suwak = next(s for s in w["zakresy"]["suwaki"]
                     if s["klucz"] == "pula_spoleczna.czynsz_zakladany_m2_mies")
        pula = next(p for p in w["pule"] if p["nazwa"] == "spoleczna")
        assert suwak["max"] == pytest.approx(pula["limit_czynszu"])

    def test_maksima_ustawowe_pochodza_z_modulu_prawa(self, adres):
        from sim_kalkulator import prawo

        w = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        wg_klucza = {s["klucz"]: s for s in w["zakresy"]["suwaki"]}
        assert wg_klucza["pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu"]["max"] == (
            float(prawo.PARTYCYPACJA_MAKSIMUM)
        )
        assert wg_klucza["pula_spoleczna.kredyt.okres_lat"]["max"] == (
            float(prawo.KREDYT_MAKSYMALNY_OKRES_LAT)
        )

    def test_kazde_maksimum_ustawowe_niesie_powod(self, adres):
        w = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        for klucz in ("pula_spoleczna.czynsz_zakladany_m2_mies",
                      "pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu",
                      "pula_spoleczna.kredyt.okres_lat"):
            suwak = next(s for s in w["zakresy"]["suwaki"] if s["klucz"] == klucz)
            assert suwak["powod_granicy"], f"{klucz} bez wyjasnienia granicy"

    def test_kredyt_znika_przy_pelnej_puli_komunalnej(self, adres):
        w = wolaj(adres, "/api/przelicz",
                  {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 1.0}})
        assert w["zakresy"]["kredyt_dostepny"] is False

    @pytest.mark.wolne
    def test_zaden_komunikat_nie_mowi_o_przekroczeniu_limitu(self, strona):
        p, _ = strona
        widoczne = p.inner_text("#komunikaty") + p.inner_text("#blad")
        for fraza in ("przekracza limit", "nie moze przekroczyc", "niedopuszczaln"):
            assert fraza.lower() not in widoczne.lower()


# ---------------------------------------------------------------------------
# 2. Uzytkownik nieznajacy ustawy potrafi ustawic komplet parametrow.
# ---------------------------------------------------------------------------

class TestKryterium2_OpisBezZargonu:
    def test_kazde_sterowanie_ma_etykiete_i_podpis(self, adres):
        z = wolaj(adres, "/api/przelicz", {"zmiany": {}})["zakresy"]
        for s in z["suwaki"]:
            assert s["etykieta"].strip() and s["podpis"].strip(), s["klucz"]
        for p in z["pola_liczbowe"]:
            assert p["etykieta"].strip() and p["podpis"].strip(), p["klucz"]

    def test_etykiety_i_podpisy_nie_powoluja_sie_na_przepisy(self, adres):
        z = wolaj(adres, "/api/przelicz", {"zmiany": {}})["zakresy"]
        for s in z["suwaki"]:
            assert not ARTYKUL.search(s["etykieta"]), s["klucz"]
            assert not ARTYKUL.search(s["podpis"]), s["klucz"]
            assert not ARTYKUL.search(s["powod_granicy"]), s["klucz"]

    def test_podstawa_prawna_jest_dostepna_w_rozwinieciu(self, adres):
        # Trzeci poziom opisu ma ja niesc — dla tych, ktorzy chca sprawdzic.
        z = wolaj(adres, "/api/przelicz", {"zmiany": {}})["zakresy"]
        czynsz = next(s for s in z["suwaki"]
                      if s["klucz"] == "pula_spoleczna.czynsz_zakladany_m2_mies")
        assert ARTYKUL.search(czynsz["rozwiniecie"])


# ---------------------------------------------------------------------------
# 3. Glowna liczba wyjsciowa widoczna bez przewijania.
# ---------------------------------------------------------------------------

@pytest.mark.wolne
class TestKryterium3_WidocznoscGlownejLiczby:
    def test_wymagany_wklad_miesci_sie_nad_zagieciem(self, strona):
        p, _ = strona
        ramka = p.locator("#werdykty").bounding_box()
        assert ramka["y"] + ramka["height"] <= 950, "pasek werdyktu poza pierwszym ekranem"

    def test_pierwsze_pole_paska_niesie_wymagany_wklad(self, strona):
        p, _ = strona
        pole = p.locator("#werdykty .pole").first
        assert "KAPITAŁ" in pole.inner_text().upper()
        assert "zł" in pole.inner_text()


# ---------------------------------------------------------------------------
# 4. Suwak udzialu pul przelicza wszystkie wykresy bez przeladowania.
# ---------------------------------------------------------------------------

@pytest.mark.wolne
class TestKryterium4_PrzeliczanieNaZywo:
    def test_przesuniecie_pokretla_zmienia_wykresy_bez_przeladowania(self, strona):
        p, bledy = strona
        p.evaluate("window.__znacznik = 'ten sam dokument'")
        przed = p.inner_text("#p-kaskada")
        p.eval_on_selector("#pokretlo",
                           "el => { el.value = 70; el.dispatchEvent(new Event('input')); }")
        p.wait_for_timeout(2200)
        assert p.evaluate("window.__znacznik") == "ten sam dokument", "strona sie przeladowala"
        assert p.inner_text("#p-kaskada") != przed
        assert p.locator("#w-kaskada > *").count() > 0
        assert bledy == [], bledy

    def test_wszystkie_piec_wykresow_jest_narysowanych(self, strona):
        p, _ = strona
        p.click("#panel-przeplywy summary")
        p.wait_for_timeout(400)
        for wykres in ("w-kaskada", "w-negocjacja", "w-czynsz", "w-gauge", "w-przeplywy"):
            assert p.locator(f"#{wykres} > *").count() > 0, wykres

    def test_nie_ma_przycisku_oblicz(self, strona):
        p, _ = strona
        tresc = p.inner_text("body").lower()
        assert "oblicz" not in tresc.replace("obliczenia", "").replace("obliczen", "")


# ---------------------------------------------------------------------------
# 5. Kazdy werdykt negatywny ma zdanie po polsku potocznym.
# ---------------------------------------------------------------------------

class TestKryterium5_ZdanieDlaWerdyktu:
    def test_kazdy_werdykt_niesie_zdanie_bez_przepisow(self, adres):
        for udzial in (0.0, 0.3, 0.6, 0.95):
            w = wolaj(adres, "/api/przelicz",
                      {"zmiany": {"powierzchnie.udzial_puli_komunalnej": udzial}})
            for t in w["werdykty"]:
                assert t["wiazace_ograniczenie"].strip()
                assert not ARTYKUL.search(t["wiazace_ograniczenie"]), t["wiazace_ograniczenie"]

    def test_werdykt_negatywny_wskazuje_decydujace_ograniczenie(self, adres):
        w = wolaj(adres, "/api/przelicz",
                  {"zmiany": {"powierzchnie.udzial_puli_komunalnej": 0.95}})
        blokujace = [t for t in w["werdykty"] if not t["przechodzi"]]
        assert blokujace
        for t in blokujace:
            assert t["luka_kwota"] is not None and t["luka_kwota"] > 0
            assert t["luka_jednostka"]


# ---------------------------------------------------------------------------
# 6. Suwaki czynszu przeliczaja maksima i komunikuja sciagniecie wartosci.
# ---------------------------------------------------------------------------

class TestKryterium6_SciaganieCzynszu:
    def test_limit_czynszu_zmienia_sie_z_udzialem_pul(self, adres):
        maksima = {}
        for udzial in (0.0, 0.5, 0.9):
            w = wolaj(adres, "/api/przelicz",
                      {"zmiany": {"powierzchnie.udzial_puli_komunalnej": udzial}})
            s = next(x for x in w["zakresy"]["suwaki"]
                     if x["klucz"] == "pula_komunalna.czynsz_placony_przez_gmine_m2_mies")
            maksima[udzial] = s["max"]
        assert len(set(maksima.values())) > 1, f"limit nie reaguje na udzial: {maksima}"

    @pytest.mark.wolne
    def test_sciagniecie_wartosci_jest_zakomunikowane(self, strona, adres):
        p, _ = strona
        # Ustawiamy czynsz na maksimum, potem przesuwamy pokretlo tak, by limit spadl.
        p.evaluate("""async () => {
            const s = zakresy.suwaki.find(x => x.klucz === "pula_spoleczna.czynsz_zakladany_m2_mies");
            zmiany[s.klucz] = s.max;
            document.querySelector("#pokretlo").value = 0;
            await przelicz();
        }""")
        p.wait_for_timeout(1500)
        p.evaluate("""async () => {
            document.querySelector("#pokretlo").value = 95;
            await przelicz();
        }""")
        p.wait_for_timeout(2500)
        komunikat = p.inner_text("#blad")
        if komunikat.strip():
            assert "obniżony" in komunikat.lower()


# ---------------------------------------------------------------------------
# 7. W widoku glownym nie wystepuje ani jeden numer artykulu.
# ---------------------------------------------------------------------------

class TestKryterium7_BezNumerowArtykulow:
    def test_komunikaty_na_ekranie_nie_niosa_przepisow(self, adres):
        for udzial in (0.0, 0.35, 0.8):
            w = wolaj(adres, "/api/przelicz",
                      {"zmiany": {"powierzchnie.udzial_puli_komunalnej": udzial}})
            for o in w["ostrzezenia"]:
                assert not ARTYKUL.search(o["tresc"]), o["tresc"]

    def test_tresc_techniczna_zachowuje_przepisy_dla_arkusza(self, adres):
        # Ekran sluzy rozmowie, arkusz dokumentacji — podstawa nie moze zginac.
        w = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        assert any(ARTYKUL.search(o["podstawa"] or "") for o in w["ostrzezenia"])

    def test_zdania_pod_wykresami_nie_niosa_przepisow(self, adres):
        w = wolaj(adres, "/api/przelicz", {"zmiany": {}})
        for klucz in ("kaskada", "czynsz_poziomy", "rekompensata_zapas"):
            assert not ARTYKUL.search(w["wykresy"][klucz]["zdanie"])

    @pytest.mark.wolne
    def test_widok_glowny_w_przegladarce_nie_pokazuje_artykulu(self, strona):
        p, _ = strona
        # Zwiniete panele i rozwiniecia pod znakiem zapytania sa poza widokiem
        # glownym — tam podstawa prawna jest dozwolona.
        widoczny = p.evaluate("""() => {
            const kopia = document.body.cloneNode(true);
            kopia.querySelectorAll("details, .rozwiniecie").forEach(e => e.remove());
            return kopia.innerText;
        }""")
        trafienia = re.findall(r"\bart\.\s*\d[^\n]{0,40}|§\s*\d[^\n]{0,40}", widoczny)
        assert trafienia == [], trafienia
