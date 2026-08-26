"""Errata nr 1 — czynsz rynkowy jako sufit faktyczny, nigdy jako liczba wymyslona.

Rozdz. 7 erraty. Trzeci sufit dziala tylko w puli spolecznej, jest opcjonalny,
a gdy go podano — musi miec zrodlo. Brak danej daje pytanie, nie oszacowanie.
"""

import re
from decimal import Decimal as D
from pathlib import Path

import pytest

from sim_kalkulator import api, wrazliwosc
from sim_kalkulator.dane import BladWalidacji
from sim_kalkulator.silnik import przelicz

from . import wspolne

KORZEN = Path(__file__).resolve().parent.parent
DOMYKAJACY = wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"
RYNEK = dict(
    rynek__czynsz_rynkowy_m2_mies=28.0,
    rynek__zrodlo="mediana z 15 ofert 40-55 m2, portal ogloszeniowy",
    rynek__data="2026-08-10",
)


def domykajacy(**rynek):
    """Wariant domykajacy sie — potrzebny tam, gdzie badamy punkt graniczny.

    Wariant wzorcowy nie domyka sie przy zadnym udziale, wiec nie ma w nim
    punktu kapitalowego, z ktorym mozna by porownac punkt rynkowy.
    """
    import copy

    import yaml

    from sim_kalkulator.dane import zbuduj

    dane = yaml.safe_load(DOMYKAJACY.read_text(encoding="utf-8"))
    if rynek:
        dane["rynek"] = copy.deepcopy(rynek)
    return zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)


def poziomy(**zmiany):
    return api._czynsz_poziomy(przelicz(wspolne.wejscie(**zmiany)))


def wiersz(dane, pula):
    return next(w for w in dane["wiersze"] if w["pula"] == pula)


class TestBrakDanej:
    """Puste pole nie moze zostac zastapione zadna liczba."""

    def test_przyklady_nie_niosa_stawki_rynkowej(self):
        # Errata rozdz. 1: wartosc przykladowa wygladala w wyniku jak dana.
        w = wspolne.wejscie()
        assert w.rynek.podano is False
        assert w.rynek.czynsz_rynkowy_m2_mies is None

    def test_brak_stawki_nie_blokuje_obliczenia(self):
        r = przelicz(wspolne.wejscie())
        assert r.werdykty is not None

    def test_brak_stawki_daje_pytanie_zamiast_liczby(self):
        dane = poziomy()
        assert dane["rynek_podano"] is False
        assert wiersz(dane, "spoleczna")["rynkowy"] is None
        assert dane["pytanie"]
        assert "?" in dane["pytanie"]

    def test_pytanie_niesie_stawke_domykajaca_a_nie_rynkowa(self):
        r = przelicz(wspolne.wejscie())
        dane = api._czynsz_poziomy(r)
        assert f"{r.czynsz_domykajacy_m2_mies:.2f}".replace(".", ",") in dane["pytanie"]

    def test_bez_stawki_nie_ma_oceny_rynkowej(self):
        assert poziomy()["ocena_rynkowa"] == ""

    def test_sufitem_jest_wtedy_limit_prawny(self):
        assert wiersz(poziomy(), "spoleczna")["sufit_rodzaj"] == "prawny"


class TestZrodloObowiazkowe:
    def test_stawka_bez_zrodla_to_blad_walidacji(self):
        with pytest.raises(BladWalidacji, match="rynek.zrodlo"):
            wspolne.wejscie(rynek__czynsz_rynkowy_m2_mies=28.0)

    def test_stawka_ze_zrodlem_przechodzi(self):
        w = wspolne.wejscie(**RYNEK)
        assert w.rynek.podano is True
        assert w.rynek.zrodlo

    def test_zrodlo_wchodzi_do_szczegolow_werdyktu(self):
        r = przelicz(wspolne.wejscie(**RYNEK))
        opis = r.werdykty.zdolnosc_czynszowa.szczegoly["Czynsz rynkowy — pula spoleczna"]
        assert "portal" in opis

    def test_brak_stawki_jest_nazwany_wprost_w_szczegolach(self):
        r = przelicz(wspolne.wejscie())
        opis = r.werdykty.zdolnosc_czynszowa.szczegoly["Czynsz rynkowy — pula spoleczna"]
        assert "nie podano" in opis

    def test_zero_nie_jest_sposobem_na_brak_danej(self):
        with pytest.raises(BladWalidacji, match="musi byc dodatni"):
            wspolne.wejscie(
                rynek__czynsz_rynkowy_m2_mies=0.0, rynek__zrodlo="cokolwiek"
            )

    def test_stawka_bez_daty_daje_ostrzezenie(self):
        w = wspolne.wejscie(
            rynek__czynsz_rynkowy_m2_mies=28.0, rynek__zrodlo="oferty najmu"
        )
        assert "RYNEK_BEZ_DATY" in {o.kod for o in w.ostrzezenia}

    def test_stare_pole_w_puli_spolecznej_jest_odrzucane(self):
        with pytest.raises(BladWalidacji, match="przeniesiony do osobnej sekcji"):
            wspolne.wejscie(pula_spoleczna__czynsz_rynkowy_m2_mies=34.0)


class TestPulaKomunalna:
    """Rozdz. 2 — w puli komunalnej sufit rynkowy nie wystepuje."""

    def test_wiersz_komunalny_nigdy_nie_ma_linii_rynkowej(self):
        for zmiany in ({}, RYNEK):
            dane = poziomy(**zmiany)
            assert wiersz(dane, "komunalna")["rynkowy"] is None

    def test_sufitem_komunalnym_jest_zawsze_limit_prawny(self):
        assert wiersz(poziomy(**RYNEK), "komunalna")["sufit_rodzaj"] == "prawny"

    def test_wiersz_spoleczny_linie_rynkowa_ma(self):
        assert wiersz(poziomy(**RYNEK), "spoleczna")["rynkowy"] == 28.0

    def test_przy_czystej_puli_komunalnej_jest_jeden_wiersz(self):
        dane = poziomy(powierzchnie__udzial_puli_komunalnej=1.0, **RYNEK)
        assert [w["pula"] for w in dane["wiersze"]] == ["komunalna"]


class TestHybrydy:
    """Rozdz. 5 — czynsz komunalny zadany, spoleczny residualny."""

    def test_wymagany_czynsz_spoleczny_rosnie_z_udzialem_komunalnym(self):
        poprzedni = None
        for udzial in ("0", "0.1", "0.2", "0.3", "0.4", "0.5"):
            r = przelicz(
                wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=float(udzial))
            )
            biezacy = r.czynsz_domykajacy_m2_mies
            assert biezacy is not None
            if poprzedni is not None:
                assert biezacy > poprzedni, f"spadek przy udziale {udzial}"
            poprzedni = biezacy

    def test_czynsz_komunalny_jest_dana_a_nie_wynikiem(self):
        # Stawka komunalna wchodzi do modelu wprost — jest tym, co uzgodniono
        # z gmina. Silnik rozwiazuje rownanie wzgledem stawki SPOLECZNEJ, wiec
        # to ona jest wielkoscia residualna, a nie odwrotnie.
        w = wspolne.wejscie(pula_komunalna__czynsz_placony_przez_gmine_m2_mies=12.5)
        dane = api._czynsz_poziomy(przelicz(w))
        assert wiersz(dane, "komunalna")["przyjety"] == 12.5
        spol = wiersz(dane, "spoleczna")
        assert spol["wymagany"] != spol["przyjety"]

    def test_stawka_komunalna_nie_przenosi_sie_na_wymagany_czynsz_spoleczny(self):
        # Czynsz komunalny nie zamienia sie na kapital poczatkowy — pula komunalna
        # nie ma kredytu — wiec luka kapitalowa od niego nie zalezy. To jest
        # dokladnie sens rozstrzygniecia "komunalny zadany, spoleczny domyka".
        niski = przelicz(
            wspolne.wejscie(pula_komunalna__czynsz_placony_przez_gmine_m2_mies=10.0)
        ).czynsz_domykajacy_m2_mies
        wysoki = przelicz(
            wspolne.wejscie(pula_komunalna__czynsz_placony_przez_gmine_m2_mies=18.0)
        ).czynsz_domykajacy_m2_mies
        assert niski == wysoki

    def test_brak_usredniania_stawek_miedzy_pulami(self):
        dane = poziomy(**RYNEK)
        spol = wiersz(dane, "spoleczna")
        kom = wiersz(dane, "komunalna")
        assert spol["limit"] != kom["limit"]
        assert spol["wymagany"] != kom["wymagany"]
        # Zadna z wielkosci nie jest srednia wazona dwoch pozostalych.
        assert "srednia" not in dane["zdanie"].lower()

    def test_przy_czystej_puli_komunalnej_nie_ma_stawki_spolecznej(self):
        r = przelicz(wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=1.0))
        assert r.czynsz_domykajacy_m2_mies is None


class TestPunktuGranicznego:
    """Rozdz. 5.2 — dwa punkty graniczne na osi udzialu pul."""

    def test_bez_stawki_rynkowej_nie_ma_punktu_rynkowego(self):
        s = wrazliwosc.sweep_udzialu(domykajacy(), krok=D("0.1"))
        assert s.punkt_graniczny_rynkowy is None
        assert all(p.miesci_sie_w_rynku is None for p in s.punkty if p.policzalny)

    def test_niska_stawka_rynkowa_daje_wczesniejszy_punkt_wiazacy(self):
        s = wrazliwosc.sweep_udzialu(
            domykajacy(
                czynsz_rynkowy_m2_mies=28.0,
                zrodlo="mediana z 15 ofert 40-55 m2, portal ogloszeniowy",
                data="2026-08-10",
            ),
            krok=D("0.1"),
        )
        assert s.punkt_graniczny_rynkowy is not None
        assert s.punkt_graniczny is not None
        assert s.punkt_graniczny_rynkowy < s.punkt_graniczny
        assert s.punkt_graniczny_wiazacy == s.punkt_graniczny_rynkowy
        assert s.rodzaj_punktu_wiazacego == "rynkowy"

    def test_wysoka_stawka_rynkowa_nie_wiaze(self):
        s = wrazliwosc.sweep_udzialu(
            domykajacy(czynsz_rynkowy_m2_mies=90.0, zrodlo="oferty najmu"),
            krok=D("0.1"),
        )
        assert s.rodzaj_punktu_wiazacego == "kapitalowy"

    def test_czynsz_domykajacy_znika_dopiero_gdy_kredyt_przebija_pulap(self):
        # Wariant moze sie domykac (przechodzi trzy testy przy realnym kapitale),
        # a mimo to nie miec stawki, ktora domknelaby go BEZ wkladu wlasnego.
        # To dwie rozne rzeczy i nie wolno ich mylic.
        s = wrazliwosc.sweep_udzialu(domykajacy(), krok=D("0.1"))
        wartosci = [p.czynsz_domykajacy for p in s.punkty if p.policzalny]
        assert wartosci[0] is not None
        # Raz utracona, stawka domykajaca juz nie wraca — udzial komunalny
        # wypycha ja w gore monotonicznie, az przebije pulap kredytu.
        pierwszy_brak = next(
            (i for i, v in enumerate(wartosci) if v is None), len(wartosci)
        )
        assert all(v is None for v in wartosci[pierwszy_brak:])

    def test_brak_stawki_domykajacej_nie_jest_przypisywany_rynkowi(self):
        # Gdy kredyt przebija ustawowy pulap, montazu nie domyka zadna stawka.
        # To ograniczenie kapitalowe — nie wolno go raportowac jako rynkowe,
        # bo od tego zalezy, czy da sie z tym cokolwiek zrobic.
        s = wrazliwosc.sweep_udzialu(
            domykajacy(czynsz_rynkowy_m2_mies=90.0, zrodlo="oferty najmu"),
            krok=D("0.1"),
        )
        bez_stawki = [p for p in s.punkty if p.policzalny and p.czynsz_domykajacy is None]
        assert bez_stawki
        assert all(p.miesci_sie_w_rynku is None for p in bez_stawki)


class TestZdaniaWiazacego:
    """Rozdz. 6.3 — rozroznienie, ktory sufit wiaze, jest kluczowe dla decyzji."""

    def test_gdy_wszystko_sie_miesci_zdanie_wymienia_oba_sufity(self):
        dane = poziomy(**RYNEK)
        assert "mieści się" in dane["zdanie"]
        assert "rynkow" in dane["zdanie"]

    def test_gdy_wiaze_rynek_zdanie_to_nazywa(self):
        # Stawka rynkowa ponizej czynszu potrzebnego do domkniecia.
        dane = poziomy(
            powierzchnie__udzial_puli_komunalnej=0.5,
            rynek__czynsz_rynkowy_m2_mies=20.0,
            rynek__zrodlo="oferty najmu",
        )
        assert "na tym rynku" in dane["zdanie"].lower()

    def test_gdy_wiaze_limit_zdanie_wskazuje_przepisy(self):
        dane = poziomy(powierzchnie__udzial_puli_komunalnej=0.6)
        assert "przepisy pozwalają najwyżej" in dane["zdanie"]

    def test_ocena_rynkowa_wskazuje_dzwignie_gdy_rynek_nie_udzwiga(self):
        dane = poziomy(
            powierzchnie__udzial_puli_komunalnej=0.5,
            rynek__czynsz_rynkowy_m2_mies=20.0,
            rynek__zrodlo="oferty najmu",
        )
        ocena = dane["ocena_rynkowa"]
        assert "kapitału" in ocena and "partycypacji" in ocena


class TestBrakZaszytejStalej:
    """Rozdz. 7, ostatnia pozycja — ochrona przed powrotem wartosci zaszytej.

    Test wyglada nietypowo, ale ma sens: przy kolejnej iteracji latwo jest
    "tymczasowo" wpisac stawke rynkowa na sztywno, a taka liczba wyglada
    w wyniku identycznie jak dana rzeczywista.
    """

    ZRODLA = ("sim_kalkulator", "api", "web", "scripts", "serwer.py")

    def _pliki(self):
        for nazwa in self.ZRODLA:
            sciezka = KORZEN / nazwa
            if sciezka.is_file():
                yield sciezka
            elif sciezka.is_dir():
                for plik in sciezka.rglob("*"):
                    if plik.suffix in (".py", ".html") and "__pycache__" not in str(plik):
                        yield plik

    def test_zadne_zrodlo_nie_przypisuje_stawki_rynkowej(self):
        # Przypisanie liczby do czegokolwiek, co nazywa sie "rynkowy".
        # Cyfra musi isc zaraz po znaku przypisania. Bez tego wzorzec lapie
        # specyfikacje formatu w f-stringu ("{czynsz_rynkowy:.2f}").
        wzorzec = re.compile(r"rynkow\w*\s*[:=]\s*\d", re.IGNORECASE)
        trafienia = []
        for plik in self._pliki():
            for numer, linia in enumerate(
                plik.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if wzorzec.search(linia):
                    trafienia.append(f"{plik.relative_to(KORZEN)}:{numer}: {linia.strip()}")
        assert trafienia == [], trafienia

    def test_przyklady_nie_niosa_wartosci_stawki(self):
        for plik in (KORZEN / "przyklady").glob("*.yaml"):
            tresc = plik.read_text(encoding="utf-8")
            for numer, linia in enumerate(tresc.splitlines(), start=1):
                if linia.strip().startswith("#"):
                    continue
                if "czynsz_rynkowy_m2_mies" in linia:
                    _, _, wartosc = linia.partition(":")
                    assert wartosc.split("#")[0].strip() == "", (
                        f"{plik.name}:{numer} niesie wartosc stawki rynkowej"
                    )

    def test_silnik_nie_ma_funkcji_szacujacej_rynek(self):
        podejrzane = ("szacuj_rynek", "przyblizony_czynsz", "domyslny_czynsz_rynkowy")
        for plik in self._pliki():
            tresc = plik.read_text(encoding="utf-8")
            for nazwa in podejrzane:
                assert nazwa not in tresc, f"{plik.name}: {nazwa}"
