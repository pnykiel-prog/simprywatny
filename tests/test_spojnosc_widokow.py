"""Kaskada, sweep i test kapitalowy muszą mówić to samo.

Silnik jest jeden — `silnik.przelicz` — i sweep nie ma własnej implementacji
montażu. Rozjazd bierze się nie z duplikacji logiki, tylko z tego, że dwa widoki
serializują RÓŻNE właściwości tego samego wyniku. Te testy wiążą je ze sobą,
żeby taka rozbieżność nie przeszła cicho.
"""

from decimal import Decimal as D

import pytest

from sim_kalkulator import api, wrazliwosc
from sim_kalkulator.silnik import przelicz

from . import wspolne

# Aport gminy zostal usuniety z zakresu (pakiet nr 2, rozdz. 11). Wklad rzeczowy
# w gruncie bada teraz aport INWESTORA — ta sama gałąź obliczeniowa, ten sam
# rozjazd miedzy wkladem brutto a gotowkowym, bez skutku ustrojowego.
APORT = dict(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")


def wynik(udzial, **zmiany):
    return przelicz(
        wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=udzial, **zmiany)
    )


class TestJednaSciezkaObliczeniowa:
    def test_sweep_nie_ma_wlasnej_implementacji_montazu(self):
        # Punkt sweepu to pelne przeliczenie tym samym silnikiem — nie skrot.
        import inspect

        zrodlo = inspect.getsource(wrazliwosc._punkt)
        assert "przelicz_udzial" in zrodlo
        for skrot in ("koszty_przedsiewziecia -", "grant_laczny -", "* Decimal"):
            assert skrot not in zrodlo, f"sweep liczy montaz po swojemu: {skrot}"

    @pytest.mark.parametrize("udzial", [0.0, 0.3, 0.5, 0.75])
    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_sweep_i_kaskada_podaja_ten_sam_wklad(self, udzial, zmiany):
        r = wynik(udzial, **zmiany)
        punkt = wrazliwosc._punkt(wspolne.wejscie(**zmiany), D(str(udzial)))
        kaskada = api._kaskada(r)
        assert punkt.wklad_wymagany == pytest.approx(D(str(kaskada["wymagany"])))

    @pytest.mark.parametrize(
        "scenariusz",
        [
            {},
            APORT,
            # Duze przedsiewziecie — koszt ponad 100 mln. Rzedy wielkosci maja
            # znaczenie: przy takich kwotach zaokraglenia i pulapy kredytu
            # zachowuja sie inaczej niz w przykladzie wzorcowym.
            dict(powierzchnie__pum_laczne=13000.0, powierzchnie__liczba_lokali=240,
                 inwestor__dostepny_wklad_wlasny=4600000.0),
            # Wysoki czynsz — kredyt wiazany udzwigiem, nie potrzeba.
            dict(parametry_zewnetrzne__wartosc_odtworzeniowa_m2=20000.0,
                 pula_spoleczna__czynsz_zakladany_m2_mies=30.0,
                 pula_spoleczna__partycypacja__stawka_procent_kosztu_lokalu=0.05),
        ],
        ids=["wzorcowy", "aport_inwestora", "duze_przedsiewziecie", "wiaze_udzwig"],
    )
    def test_caly_sweep_zgadza_sie_z_kaskada_punkt_po_punkcie(self, scenariusz):
        """Kazdy punkt siatki, nie tylko biezacy i nie tylko srodek zakresu.

        Rozjazd widoczny przy udziale 0% przeszedl wczesniej niezauwazony, bo
        testy porownywaly wybrane punkty. Tutaj porownywana jest CALA siatka
        i to na poziomie ODPOWIEDZI API, a nie funkcji wewnetrznych — bo to
        odpowiedzi widzi przegladarka, a droga do nich (sciaganie czynszu,
        walidacja przy zmianie udzialu) bywa inna dla kazdego z dwoch wywolan.
        """
        bazowe = wspolne.zmien(**scenariusz)
        kod, sweep = api.obsluz("sweep", bazowe, {})
        assert kod == 200, sweep
        policzalne = [p for p in sweep["punkty"] if p["policzalny"]]
        assert len(policzalne) >= 15, "za malo punktow, zeby test cokolwiek znaczyl"

        for punkt in policzalne:
            kod, wynik = api.obsluz(
                "przelicz", bazowe,
                {"powierzchnie.udzial_puli_komunalnej": punkt["udzial"]},
            )
            assert kod == 200, wynik
            kaskada = wynik["wykresy"]["kaskada"]["wymagany"]
            assert punkt["wklad_wymagany"] == pytest.approx(kaskada, abs=0.01), (
                f"udzial {punkt['udzial']:.2f}: sweep {punkt['wklad_wymagany']:,.2f} "
                f"!= kaskada {kaskada:,.2f}"
            )

    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_kaskada_i_test_kapitalowy_podaja_ten_sam_wklad(self, zmiany):
        r = wynik(0.3, **zmiany)
        kaskada = api._kaskada(r)
        szczegoly = r.werdykty.montaz.szczegoly["Wymagany wklad wlasny"]
        # Werdykt formatuje kwote po polsku — porownujemy przez wartosc liczbowa.
        assert szczegoly.replace(" ", "").replace(" ", "").replace("zł", "") == (
            f"{kaskada['wymagany']:,.0f}".replace(",", "")
        )

    @pytest.mark.parametrize("zmiany", [{}, APORT], ids=["nabycie", "aport_inwestora"])
    def test_aport_obniza_wklad_w_obu_widokach_tak_samo(self, zmiany):
        # Grunt wniesiony rzeczowo domyka koszty, nie wymagajac gotowki. Widok,
        # ktory tego nie uwzglednia, zawyza zapotrzebowanie o wartosc dzialki.
        r = wynik(0.3, **zmiany)
        punkt = wrazliwosc._punkt(wspolne.wejscie(**zmiany), D("0.3"))
        rzeczowy = r.finansowanie.wklad_rzeczowy_laczny
        assert punkt.wklad_wymagany == pytest.approx(
            max(D(0), r.finansowanie.wklad_wlasny_wymagany - rzeczowy)
        )

    def test_wklad_w_sweepie_nigdy_nie_jest_ujemny(self):
        # Dotacja 80% w puli komunalnej plus drogi aport potrafia przewyzszyc
        # zapotrzebowanie; ujemna kwota nic nie znaczy dla inwestora.
        s = wrazliwosc.sweep_udzialu(
            wspolne.wejscie(grunt__wartosc=12000000.0, **APORT), krok=D("0.25")
        )
        for punkt in s.punkty:
            if punkt.wklad_wymagany is not None:
                assert punkt.wklad_wymagany >= 0
