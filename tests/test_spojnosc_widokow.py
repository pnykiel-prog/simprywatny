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
