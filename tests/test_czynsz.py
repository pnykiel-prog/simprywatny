"""Etap 3 — limity czynszu, podstawa naliczenia i limit wiazacy."""

from decimal import Decimal

import pytest

from sim_kalkulator import alokacja, czynsz, grant
from sim_kalkulator.dane import BladWalidacji

from . import wspolne


def limity(pula="spoleczna", **zmiany):
    w = wspolne.wejscie(**zmiany)
    a = alokacja.build(w)
    g = grant.build(w, a)
    if pula == "spoleczna":
        return w, czynsz.build(
            w, a.spoleczna, g.spoleczna,
            w.pula_spoleczna.czynsz_zakladany_m2_mies,
            finansowanie_zwrotne=w.pula_spoleczna.kredyt.aktywny,
        )
    return w, czynsz.build(
        w, a.komunalna, g.komunalna,
        w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies,
        finansowanie_zwrotne=False,
    )


class TestPodstawaNaliczenia:
    """art. 28 ust. 2b — podstawa wyzsza z dwoch."""

    def test_drogi_grunt_przesuwa_podstawe_na_koszt_budowy(self):
        w, l = limity()
        assert l.podstawa_koszt_budowy_m2 > l.podstawa_wartosc_odtworzeniowa_m2
        assert l.podstawa_wiazaca_m2 == l.podstawa_koszt_budowy_m2
        assert "art. 28 ust. 2b" in l.podstawa_wiazaca_zrodlo

    def test_wysoka_wartosc_odtworzeniowa_wraca_do_wskaznika_wojewody(self):
        w, l = limity(parametry_zewnetrzne__wartosc_odtworzeniowa_m2=15000.0)
        assert l.podstawa_wiazaca_m2 == Decimal("15000.0")
        assert "obwieszczenie wojewody" in l.podstawa_wiazaca_zrodlo


class TestLimitWiazacy:
    def test_pula_komunalna_z_grantem_80_procent_wiaze_2_5_procent(self):
        _, l = limity("komunalna")
        assert l.udzial_wsparcia == Decimal("0.80")
        assert l.stawka_art_7c == Decimal("0.025")
        assert l.limit_wiazacy_zrodlo == "art. 7c ustawy z 8.12.2006"

    def test_pula_spoleczna_z_grantem_45_procent_wiaze_3_5_procent(self):
        _, l = limity(grunt__wartosc=6000000.0)
        assert l.udzial_wsparcia == Decimal("0.45")
        assert l.stawka_art_7c == Decimal("0.035")

    def test_silnik_wylicza_stawke_zamiast_ja_zakladac(self):
        # Grant ograniczony gruntem schodzi ponizej 45%, wiec wiaze 4,0%, nie 3,5%.
        _, l = limity(grunt__wartosc=2800000.0)
        assert l.udzial_wsparcia < Decimal("0.45")
        assert l.stawka_art_7c == Decimal("0.040")

    def test_limit_finansowania_zwrotnego_liczony_tylko_przy_kredycie(self):
        _, z_kredytem = limity()
        assert z_kredytem.stawka_art_28 == Decimal("0.050")
        _, bez_kredytu = limity(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        assert bez_kredytu.stawka_art_28 is None

    def test_wiaze_nizszy_z_dwoch_limitow(self):
        _, l = limity()
        assert l.limit_wiazacy_m2_mies == min(
            l.limit_art_7c_m2_mies, l.limit_art_28_m2_mies
        )

    def test_limit_28_wiaze_gdy_jest_nizszy(self):
        # Wsparcie ponizej 45% daje 4,0% z art. 7c przy remoncie 5,0% — sprawdzamy
        # przypadek, w ktorym 5% z art. 28 schodzi ponizej stawki z art. 7c.
        dane = wspolne.zmien(pula_spoleczna__czynsz_zakladany_m2_mies=1.0)
        dane["przelaczniki"]["remont_i_przebudowa"] = True
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        a = alokacja.build(w)
        g = grant.build(w, a)
        l = czynsz.build(w, a.spoleczna, g.spoleczna, Decimal("1.0"), finansowanie_zwrotne=True)
        assert l.stawka_art_7c == Decimal("0.050")
        assert l.limit_wiazacy_m2_mies == l.limit_art_28_m2_mies


class TestCzynszPonadLimit:
    """Przekroczenie limitu to twardy blad walidacji, nie porazka testu 2."""

    def test_czynsz_ponad_limit_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="przekracza limit wiazacy"):
            limity(pula_spoleczna__czynsz_zakladany_m2_mies=99.0)

    def test_czynsz_gminy_ponad_limit_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="przekracza limit wiazacy"):
            limity("komunalna", pula_komunalna__czynsz_placony_przez_gmine_m2_mies=99.0)

    def test_czynsz_dokladnie_na_limicie_przechodzi(self):
        # Czynsz podawany wprost jako Decimal, zeby nie zgubic cyfr na konwersji
        # przez float — granica limitu jest tu badana co do grosza.
        w = wspolne.wejscie()
        a = alokacja.build(w)
        g = grant.build(w, a)
        odniesienie = czynsz.build(
            w, a.spoleczna, g.spoleczna, Decimal("0"), finansowanie_zwrotne=True
        )
        na_limicie = odniesienie.limit_wiazacy_m2_mies
        l = czynsz.build(w, a.spoleczna, g.spoleczna, na_limicie, finansowanie_zwrotne=True)
        assert l.zapas_do_limitu_m2_mies == Decimal("0")

    def test_grosz_ponad_limit_juz_zatrzymuje_obliczenie(self):
        w = wspolne.wejscie()
        a = alokacja.build(w)
        g = grant.build(w, a)
        odniesienie = czynsz.build(
            w, a.spoleczna, g.spoleczna, Decimal("0"), finansowanie_zwrotne=True
        )
        ponad = odniesienie.limit_wiazacy_m2_mies + Decimal("0.01")
        with pytest.raises(BladWalidacji, match="przekracza limit wiazacy"):
            czynsz.build(w, a.spoleczna, g.spoleczna, ponad, finansowanie_zwrotne=True)


class TestOplatyPozaCzynszem:
    """art. 28 ust. 4-5 — osobny strumien, nigdy doliczany do czynszu."""

    def test_limit_oplat_to_1_procent_wartosci_odtworzeniowej_rocznie(self):
        w, l = limity()
        oczekiwany = Decimal("6500.0") * Decimal("0.010") / Decimal(12)
        assert l.limit_oplat_poza_czynszem_m2_mies == oczekiwany

    def test_oplaty_liczone_od_wartosci_odtworzeniowej_nie_od_kosztu_budowy(self):
        # Podstawa czynszu moze byc kosztem budowy (art. 28 ust. 2b), ale oplaty
        # z art. 28 ust. 4 maja wlasna podstawe — wartosc odtworzeniowa.
        w, l = limity()
        assert l.podstawa_wiazaca_m2 != l.podstawa_wartosc_odtworzeniowa_m2
        assert l.limit_oplat_poza_czynszem_m2_mies == (
            l.podstawa_wartosc_odtworzeniowa_m2 * Decimal("0.010") / Decimal(12)
        )

    def test_limit_oplat_nie_wchodzi_do_limitu_czynszu(self):
        _, l = limity()
        assert l.limit_wiazacy_m2_mies == min(l.limit_art_7c_m2_mies, l.limit_art_28_m2_mies)
