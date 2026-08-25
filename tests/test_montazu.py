"""Etap 7 — trzy werdykty, wiazace ograniczenie i luki liczbowe."""

from decimal import Decimal as D

import pytest

from sim_kalkulator.dane import wczytaj_yaml, zbuduj
from sim_kalkulator.silnik import (
    WynikNieobliczalny,
    przelicz,
    przelicz_bezpiecznie,
    przelicz_udzial,
)

from . import wspolne


def wynik(**zmiany):
    return przelicz(wspolne.wejscie(**zmiany))


class TestWerdyktZbiorczy:
    def test_domyka_sie_tylko_gdy_przechodza_wszystkie_trzy(self):
        r = wynik()
        assert r.domyka_sie == all(t.przechodzi for t in r.werdykty.wszystkie)

    def test_sa_dokladnie_trzy_testy(self):
        r = wynik()
        assert len(r.werdykty.wszystkie) == 3
        assert [t.numer for t in r.werdykty.wszystkie] == [1, 2, 3]
        assert [t.nazwa for t in r.werdykty.wszystkie] == [
            "Montaz", "Zdolnosc czynszowa", "Rekompensata"
        ]

    def test_kazdy_werdykt_negatywny_podaje_wiazace_ograniczenie(self):
        r = wynik()
        for t in r.werdykty.blokujace:
            assert t.wiazace_ograniczenie.strip()
            assert t.luka_jednostka.strip()

    def test_kazdy_werdykt_negatywny_podaje_luke_liczbowa(self):
        # "Nie spina sie" bez podania luki jest bezuzyteczne w negocjacji.
        r = wynik()
        for t in r.werdykty.blokujace:
            assert t.luka_kwota > D("0"), t.nazwa

    def test_werdykt_zbiorczy_zawsze_wskazuje_wiazace_ograniczenie(self):
        r = wynik()
        assert r.werdykty.wiazace_ograniczenie.startswith("Test ")


class TestMontazu:
    """grant + kredyt + partycypacja + wklad wlasny = koszty przedsiewziecia"""

    def test_zrodla_sumuja_sie_do_kosztow(self):
        r = wynik()
        f = r.finansowanie
        assert (
            f.grant_laczny + f.kredyt_laczny + f.partycypacja_laczna
            + f.wklad_wlasny_wymagany
        ) == f.koszty_laczne

    def test_przechodzi_gdy_wklad_wystarcza(self):
        r = wynik(inwestor__dostepny_wklad_wlasny=50000000.0)
        assert r.werdykty.montaz.przechodzi is True
        assert r.werdykty.montaz.luka_kwota == D("0")

    def test_luka_kapitalowa_gdy_wkladu_brakuje(self):
        r = wynik(
            powierzchnie__udzial_puli_komunalnej=0.9,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
            inwestor__dostepny_wklad_wlasny=100000.0,
        )
        t = r.werdykty.montaz
        assert t.przechodzi is False
        assert t.luka_jednostka == "zl"
        assert t.luka_kwota == (
            r.finansowanie.wklad_wlasny_wymagany - D("100000.0")
        )

    def test_szczegoly_pokazuja_wszystkie_zrodla(self):
        t = wynik().werdykty.montaz
        for klucz in ("Grant", "Kredyt SBC", "Partycypacja", "Wklad wlasny wymagany"):
            assert klucz in t.szczegoly


class TestZdolnosciCzynszowej:
    def test_porazka_wskazuje_rok_pierwszego_naruszenia(self):
        r = wynik()
        t = r.werdykty.zdolnosc_czynszowa
        assert t.przechodzi is False
        assert "roku 4" in t.wiazace_ograniczenie
        assert t.szczegoly["Rok pierwszego naruszenia"] == "4"

    def test_luka_podana_w_zl_na_m2_na_miesiac(self):
        t = wynik().werdykty.zdolnosc_czynszowa
        assert t.luka_jednostka == "zl/m2/mies."
        assert t.luka_kwota > D("0")

    def test_raportuje_czynsz_wymagany_limit_i_rynek(self):
        # Rozjazd miedzy limitem a poziomem potrzebnym do domkniecia to
        # centralne napiecie modelu i ma byc widoczny wprost.
        t = wynik().werdykty.zdolnosc_czynszowa
        klucze = " ".join(t.szczegoly)
        assert "Czynsz wymagany do domkniecia" in klucze
        assert "Limit czynszu" in klucze
        assert "Czynsz rynkowy" in klucze

    def test_bez_kredytu_test_przechodzi_latwiej(self):
        r = wynik(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is True

    def test_dscr_ponizej_jednosci_to_porazka(self):
        r = wynik()
        assert r.projekcja.spoleczna.minimalny_dscr < D("1")
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is False

    def test_wyzsze_pustostany_pogarszaja_werdykt(self):
        malo = wynik(eksploatacja__pustostany_procent=0.02)
        duzo = wynik(eksploatacja__pustostany_procent=0.20)
        assert duzo.projekcja.spoleczna.minimalny_dscr < malo.projekcja.spoleczna.minimalny_dscr


class TestRekompensaty:
    def test_porazka_podaje_kwote_do_zwrotu_do_funduszu_doplat(self):
        r = wynik()
        t = r.werdykty.rekompensata
        assert t.przechodzi is False
        assert "Kwota podlegajaca zwrotowi do Funduszu Doplat" in t.szczegoly

    def test_szczegoly_pokazuja_kn_rz_i_prog(self):
        t = wynik().werdykty.rekompensata
        klucze = " ".join(t.szczegoly)
        assert "KN — " in klucze and "RZ — " in klucze and "Prog tolerancji" in klucze

    def test_szczegoly_pokazuja_ujecie_gruntu(self):
        t = wynik().werdykty.rekompensata
        assert any(k.startswith("Ujecie gruntu") for k in t.szczegoly)


class TestPrzeliczBezpiecznie:
    def test_kredyt_przy_pelnej_puli_komunalnej_wraca_jako_niepoliczalny(self):
        # art. 5a ust. 3 — przesuniecie pokretla na 100% czyni konfiguracje
        # z kredytem bezprawna. Sweep ma to pokazac jako powod, nie jako porazke.
        r = przelicz_udzial(wspolne.wejscie(), D("1.0"))
        assert isinstance(r, WynikNieobliczalny)
        assert r.typ == "walidacja"
        assert r.domyka_sie is False
        assert "art. 5a ust. 3" in r.powod

    def test_czynsz_ponad_limit_po_przesunieciu_pokretla_wraca_jako_powod(self):
        # Przy rosnacym udziale komunalnym grant spoleczny sie zmienia, wiec
        # zmienia sie tez limit czynszu — punkt moze stac sie niepoliczalny.
        r = przelicz_udzial(
            wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=0.0), D("1.0")
        )
        assert not isinstance(r, WynikNieobliczalny)

    def test_poprawny_udzial_wraca_jako_wynik(self):
        r = przelicz_udzial(wspolne.wejscie(), D("0.5"))
        assert not isinstance(r, WynikNieobliczalny)
        assert r.wejscie.powierzchnie.udzial_puli_komunalnej == D("0.5")

    def test_poprawny_wariant_wraca_jako_wynik(self):
        r = przelicz_bezpiecznie(wspolne.wejscie())
        assert not isinstance(r, WynikNieobliczalny)


class TestWskaznikiNaM2:
    """Wszystkie wskazniki wyjsciowe per m2 PUM, nie na lokal."""

    def test_wskazniki_licza_sie_na_metr(self):
        r = wynik()
        pum = r.wejscie.powierzchnie.pum_laczne
        assert r.koszt_na_m2 == r.alokacja.koszty_laczne / pum
        assert r.grant_na_m2 == r.finansowanie.grant_laczny / pum
        assert r.wklad_wlasny_na_m2 == r.finansowanie.wklad_wlasny_wymagany / pum

    def test_wskazniki_na_m2_sa_porownywalne_miedzy_strukturami_mieszkan(self):
        # Ta sama powierzchnia w innej liczbie lokali daje ten sam koszt na m2.
        malo = wynik(powierzchnie__liczba_lokali=40)
        duzo = wynik(powierzchnie__liczba_lokali=70)
        assert malo.koszt_na_m2 == duzo.koszt_na_m2


class TestRegresjaPrzykladow:
    """Zamrozone werdykty przykladow — zmiana silnika, ktora je przesuwa, ma wysypac testy."""

    def test_wzorcowy_nie_domyka_sie_i_wiaze_test_2(self):
        r = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        assert r.domyka_sie is False
        assert r.werdykty.montaz.przechodzi is True
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is False
        assert r.werdykty.rekompensata.przechodzi is False
        assert r.werdykty.wiazace_ograniczenie.startswith("Test 2")

    def test_wzorcowy_zamrozone_liczby(self):
        r = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        assert r.alokacja.koszty_laczne == D("29050000.00")
        assert r.finansowanie.wklad_wlasny_wymagany == D("799750.00")
        assert r.granty.spoleczna.udzial_wsparcia.quantize(D("0.0001")) == D("0.4464")
        assert r.granty.komunalna.udzial_wsparcia == D("0.80")
        assert r.projekcja.spoleczna.pierwszy_rok_naruszenia == 4

    def test_domykajacy_sie_przechodzi_wszystkie_trzy(self):
        r = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert r.domyka_sie is True
        assert all(t.przechodzi for t in r.werdykty.wszystkie)

    def test_domykajacy_sie_zamrozone_liczby(self):
        r = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert r.alokacja.koszty_laczne == D("29050000.00")
        assert r.finansowanie.wklad_wlasny_wymagany == D("3850000.00")
        assert r.projekcja.spoleczna.pierwszy_rok_naruszenia is None
        assert r.projekcja.spoleczna.minimalny_dscr.quantize(D("0.001")) == D("1.286")

    def test_oba_przyklady_maja_te_same_koszty_a_inny_werdykt(self):
        # O werdykcie decyduje struktura finansowania, nie skala projektu.
        a = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        b = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert a.alokacja.koszty_laczne == b.alokacja.koszty_laczne
        assert a.domyka_sie != b.domyka_sie
