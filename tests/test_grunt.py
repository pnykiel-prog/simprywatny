"""Uzupelnienie nr 2 — rozstrzyganie kanalow gruntowych i wariant lokalowy.

Testy z rozdz. 8 uzupelnienia, ktore nie mieszcza sie w testach grantu ani
rekompensaty: kanal D, wariant "lokal za grunt" i spojnosc matrycy skutkow.
"""

from decimal import Decimal as D

import pytest

from sim_kalkulator import alokacja, grunt, prawo
from sim_kalkulator.dane import FormaGruntu
from sim_kalkulator.silnik import przelicz

from . import wspolne

LOKALOWE = dict(
    grunt__pochodzenie="gmina",
    grunt__forma="lokal_za_grunt",
    grunt__liczba_lokali_dla_gminy=6,
    grunt__pum_lokali_dla_gminy=300.0,
)


def rozstrzygnij(**zmiany):
    return grunt.rozstrzygnij(wspolne.wejscie(**zmiany))


class TestSpojnoscMatrycy:
    def test_matryca_pokrywa_wszystkie_formy_enumu(self):
        assert {w.forma for w in prawo.MATRYCA_GRUNTU} == {f.value for f in FormaGruntu}

    def test_pochodzenia_pokrywaja_matryce_bez_powtorzen(self):
        z_pochodzen = [
            forma
            for pochodzenie in prawo.POCHODZENIA_GRUNTU
            for forma in prawo.formy_dla_pochodzenia(pochodzenie)
        ]
        assert sorted(z_pochodzen) == sorted(w.forma for w in prawo.MATRYCA_GRUNTU)

    def test_przelacznik_przychodu_wskazuje_istniejace_pole(self):
        przelaczniki = wspolne.wejscie().przelaczniki
        for wiersz in prawo.MATRYCA_GRUNTU:
            if wiersz.przelacznik_przychodu:
                assert hasattr(przelaczniki, wiersz.przelacznik_przychodu)

    def test_kazde_zalozenie_z_rozdz_9_ma_przelacznik(self):
        przelaczniki = wspolne.wejscie().przelaczniki
        for _, nazwa, domyslna, _, _ in prawo.ZALOZENIA_GRUNTOWE_DO_POTWIERDZENIA:
            assert getattr(przelaczniki, nazwa) is domyslna

    def test_forma_z_oznaczeniem_pytajnika_wymaga_potwierdzenia(self):
        wymagajace = {w.forma for w in prawo.MATRYCA_GRUNTU if w.wymaga_potwierdzenia}
        assert wymagajace == {"lokal_za_grunt", "uzytkowanie_wieczyste"}


class TestKanaluD:
    """Wklad rzeczowy kontra pieniezny — klasyfikacja modelu, nie przepisu."""

    def test_nabycie_wymaga_gotowki(self):
        u = rozstrzygnij()
        assert u.wydatek_gotowkowy == u.wartosc_operatu
        assert u.wklad_rzeczowy_laczny == D("0")

    def test_aport_inwestora_nie_wymaga_gotowki(self):
        u = rozstrzygnij(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        assert u.wydatek_gotowkowy == D("0")
        assert u.wklad_rzeczowy_inwestora > D("0")
        assert u.wklad_rzeczowy_gminy == D("0")

    def test_aport_gminy_to_wklad_gminy_nie_inwestora(self):
        u = rozstrzygnij(grunt__forma="aport_gminy")
        assert u.wklad_rzeczowy_inwestora == D("0")
        assert u.wklad_rzeczowy_gminy > D("0")
        assert u.gmina_wspolnikiem is True

    def test_bonifikata_obniza_wydatek_niezaleznie_od_pasma(self):
        # Cena rzeczywiscie placona zmienia zapotrzebowanie na gotowke takze wtedy,
        # gdy pasmo dotacji liczy sie od wartosci z operatu (odczyt domyslny 9.3).
        u = rozstrzygnij(grunt__cena_nabycia=1400000.0)
        assert u.wydatek_gotowkowy == D("1400000.00")
        assert u.wartosc_do_pasma == u.wartosc_operatu

    def test_aport_gminy_nie_nalicza_inwestorowi_rozsadnego_zysku(self):
        wlasny = przelicz(
            wspolne.wejscie(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        )
        gminny = przelicz(wspolne.wejscie(grunt__forma="aport_gminy"))
        assert (
            gminny.finansowanie.spoleczna.kapital_inwestora
            < wlasny.finansowanie.spoleczna.kapital_inwestora
        )

    def test_kredyt_nie_doplaca_do_wkladu_rzeczowego_puli(self):
        # Bez odjecia wkladu rzeczowego od zapotrzebowania puli kredyt
        # finansowalby aport, ktory juz pokryl czesc kosztow.
        r = przelicz(
            wspolne.wejscie(grunt__pochodzenie="inwestor", grunt__forma="aport_inwestora")
        )
        f = r.finansowanie.spoleczna
        assert f.wklad_gotowkowy >= D("0")

    def test_wklad_rzeczowy_ponad_potrzebe_daje_zapas_zamiast_ujemnej_kwoty(self):
        # Dotacja 80% w puli komunalnej plus drogi grunt domykaja ja z zapasem.
        # Ujemna "wymagana gotowka" nic nie znaczy — test ma podac zero i zapas.
        r = przelicz(
            wspolne.wejscie(
                grunt__pochodzenie="inwestor",
                grunt__forma="aport_inwestora",
                grunt__wartosc=12000000.0,
            )
        )
        assert r.finansowanie.nadwyzka_wkladu_rzeczowego > D("0")
        werdykt = r.werdykty.montaz
        assert werdykt.przechodzi is True
        assert werdykt.luka_kwota == D("0")
        assert "Nie musisz dokładać gotówki" in werdykt.wiazace_ograniczenie


class TestLokalZaGrunt:
    """Rozdz. 6 i 8 — placi sie lokalami, wiec maleje przychod, a nie koszt."""

    def test_pum_przychodowe_pomniejszone_o_lokale_gminy(self):
        w = wspolne.wejscie(**LOKALOWE)
        a = alokacja.build(w)
        assert a.pum_przychodowe_laczne == w.powierzchnie.pum_laczne - D("300.0")
        assert a.pum_oddane_gminie == D("300.0")

    def test_koszt_przedsiewziecia_niepomniejszony(self):
        # Lokale przekazywane gminie trzeba wybudowac — koszt zostaje pelny.
        bez = alokacja.build(wspolne.wejscie())
        z_lokalami = alokacja.build(wspolne.wejscie(**LOKALOWE))
        assert z_lokalami.koszty_laczne == bez.koszty_laczne
        assert z_lokalami.pum_laczne == bez.pum_laczne

    def test_lokale_gminy_nie_generuja_czynszu(self):
        bez = przelicz(wspolne.wejscie())
        z_lokalami = przelicz(wspolne.wejscie(**LOKALOWE))
        udzial = D("2700.0") / D("3000.0")
        assert z_lokalami.projekcja.spoleczna.lata[0].przychod_czynszowy_netto == (
            bez.projekcja.spoleczna.lata[0].przychod_czynszowy_netto * udzial
        )

    def test_brak_wydatku_gotowkowego_na_grunt(self):
        # Za dzialke placi sie lokalami, wiec nie ma za nia wydatku pienieznego,
        # a montaz domyka sie mniejszym dlugiem. Wymagana gotowka nigdy nie
        # wychodzi wyzsza niz przy nabyciu tej samej dzialki.
        z_lokalami = przelicz(wspolne.wejscie(**LOKALOWE))
        nabycie = przelicz(wspolne.wejscie())
        assert z_lokalami.grunt.wydatek_gotowkowy == D("0")
        assert z_lokalami.finansowanie.wklad_rzeczowy_inwestora_laczny > D("0")
        assert (
            z_lokalami.finansowanie.wklad_gotowkowy_wymagany
            <= nabycie.finansowanie.wklad_gotowkowy_wymagany
        )
        assert z_lokalami.finansowanie.kredyt_laczny < nabycie.finansowanie.kredyt_laczny

    def test_efektywny_koszt_metra_oddanych_lokali(self):
        w = wspolne.wejscie(**LOKALOWE)
        assert w.grunt.koszt_lokali_dla_gminy_na_m2 == w.grunt.wartosc / D("300.0")

    def test_zadanie_lokali_wartych_wiecej_niz_dzialka_daje_ostrzezenie(self):
        # Efektywny koszt metra ponizej kosztu budowy oznacza, ze gmina bierze
        # wiecej wartosci, niz oddaje.
        r = przelicz(
            wspolne.wejscie(
                **{**LOKALOWE, "grunt__pum_lokali_dla_gminy": 900.0,
                   "grunt__liczba_lokali_dla_gminy": 18}
            )
        )
        kody = {o.kod for o in r.ostrzezenia}
        assert "LOKAL_ZA_GRUNT_NIEKORZYSTNY" in kody

    def test_korzystny_uklad_nie_daje_tego_ostrzezenia(self):
        r = przelicz(wspolne.wejscie(**LOKALOWE))
        kody = {o.kod for o in r.ostrzezenia}
        assert "LOKAL_ZA_GRUNT_NIEKORZYSTNY" not in kody
        assert "ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM" in kody


class TestOplatyRocznej:
    def test_oplata_obciaza_kazdy_rok_projekcji(self):
        r = przelicz(
            wspolne.wejscie(grunt__forma="dzierzawa", grunt__oplata_roczna=150000.0)
        )
        for rok in r.projekcja.spoleczna.lata:
            assert rok.oplata_za_grunt > D("0")

    def test_oplata_jest_indeksowana_jak_pozostale_koszty(self):
        r = przelicz(
            wspolne.wejscie(grunt__forma="dzierzawa", grunt__oplata_roczna=150000.0)
        )
        lata = r.projekcja.spoleczna.lata
        indeks = wspolne.wejscie().eksploatacja.indeksacja_kosztow_rocznie
        assert lata[4].oplata_za_grunt == pytest.approx(
            lata[0].oplata_za_grunt * (D(1) + indeks) ** 4
        )

    def test_oplata_wchodzi_do_wymaganego_pokrycia(self):
        bez = przelicz(
            wspolne.wejscie(grunt__forma="dzierzawa", grunt__oplata_roczna=0.0)
        )
        z_oplata = przelicz(
            wspolne.wejscie(grunt__forma="dzierzawa", grunt__oplata_roczna=150000.0)
        )
        assert (
            z_oplata.projekcja.spoleczna.lata[0].wymagane_pokrycie
            > bez.projekcja.spoleczna.lata[0].wymagane_pokrycie
        )

    def test_forma_bez_oplaty_nie_obciaza_projekcji(self):
        # Kwota odlozona w wejsciu nie moze przeciekac do formy, ktora jej nie dotyczy.
        r = przelicz(wspolne.wejscie(grunt__oplata_roczna=150000.0))
        assert r.projekcja.spoleczna.lata[0].oplata_za_grunt == D("0")
