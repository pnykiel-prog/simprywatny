"""Etap 4 — harmonogram splat i ekwiwalent dotacji brutto (rozdz. 11 specyfikacji)."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import kredyt
from sim_kalkulator.dane import BladObliczenia, Kredyt

from . import wspolne

S = D("1000000")


def k(oprocentowanie="0.025", okres=30, karencja=3, udzial="0.4") -> Kredyt:
    return Kredyt(
        oprocentowanie=D(oprocentowanie),
        okres_lat=okres,
        karencja_lat=karencja,
        udzial_docelowy=D(udzial),
    )


class TestHarmonogram:
    def test_karencja_placi_same_odsetki(self):
        h = kredyt.harmonogram(k(karencja=3), S)
        for rata in h.raty[:3]:
            assert rata.karencja is True
            assert rata.kapital == D("0")
            assert rata.odsetki == S * D("0.025")

    def test_saldo_domyka_sie_do_zera(self):
        h = kredyt.harmonogram(k(), S)
        assert abs(h.raty[-1].saldo_koncowe) < D("0.01")

    def test_liczba_rat_rowna_okresowi(self):
        h = kredyt.harmonogram(k(okres=25, karencja=2), S)
        assert len(h.raty) == 25
        assert sum(1 for r in h.raty if r.karencja) == 2

    def test_suma_kapitalu_rowna_kwocie_kredytu(self):
        h = kredyt.harmonogram(k(), S)
        assert abs(sum((r.kapital for r in h.raty), D("0")) - S) < D("0.01")

    def test_rata_po_karencji_jest_stala(self):
        h = kredyt.harmonogram(k(okres=20, karencja=2), S)
        raty_splaty = [r.rata for r in h.raty if not r.karencja]
        # Ostatnia rata domyka saldo, wiec porownujemy raty od drugiej do przedostatniej.
        assert all(abs(r - raty_splaty[0]) < D("0.01") for r in raty_splaty[:-1])

    def test_zerowe_oprocentowanie_dziala(self):
        h = kredyt.harmonogram(k(oprocentowanie="0.0", okres=10, karencja=0), S)
        assert h.suma_odsetek == D("0")
        assert abs(h.raty[-1].saldo_koncowe) < D("0.01")

    def test_brak_kredytu_daje_pusty_harmonogram(self):
        h = kredyt.harmonogram(k(udzial="0.0"), D("0"))
        assert h.aktywny is False
        assert h.raty == ()
        assert h.obsluga_dlugu(1) == D("0")

    def test_obsluga_dlugu_poza_okresem_to_zero(self):
        h = kredyt.harmonogram(k(okres=20, karencja=1), S)
        assert h.obsluga_dlugu(20) > D("0")
        assert h.obsluga_dlugu(21) == D("0")


class TestEDBGrant:
    """§ 4 pkt 1 — dla dotacji EDB jest rowny kwocie dotacji."""

    def test_edb_dotacji_rowna_sie_kwocie(self):
        assert kredyt.edb_grant(D("9077250.00")) == D("9077250.00")

    def test_bez_dyskontowania_i_bez_parametrow(self):
        assert kredyt.edb_grant(D("1")) == D("1")
        assert kredyt.edb_grant(D("0")) == D("0")


class TestEDBKredyt:
    """§ 4 pkt 5 lit. e — kredyt w systemie rownej raty z karencja."""

    def test_rp_rowne_r_daje_dokladnie_zero(self):
        # Najwazniejszy test etapu: jezeli nie wychodzi DOKLADNIE zero,
        # wzor jest zle przepisany.
        wynik = kredyt.edb_kredyt(S, D("0.05"), 30, 3, D("0.05"), D("0.05"))
        assert wynik == D("0")

    @pytest.mark.parametrize("stopa", ["0.01", "0.0442", "0.0542", "0.08"])
    @pytest.mark.parametrize("karencja", [0, 1, 5])
    def test_rp_rowne_r_daje_zero_dla_kazdej_konfiguracji(self, stopa, karencja):
        wynik = kredyt.edb_kredyt(S, D(stopa), 30, karencja, D(stopa), D("0.0542"))
        assert wynik == D("0")

    def test_rp_wieksze_od_r_to_wyjatek(self):
        with pytest.raises(BladObliczenia, match="ujemne"):
            kredyt.edb_kredyt(S, D("0.08"), 30, 3, D("0.0542"), D("0.0542"))

    def test_edb_miesci_sie_miedzy_zerem_a_kwota_kredytu(self):
        edb = kredyt.edb_kredyt(S, D("0.025"), 30, 3, D("0.0542"), D("0.0542"))
        assert D("0") < edb < S

    def test_karencja_zero_redukuje_wzor_do_drugiego_czlonu(self):
        # Przy T = 0 pierwsza suma jest pusta, wiec EDB to sam czlon splaty.
        N, rp, r, rd = 20, D("0.02"), D("0.05"), D("0.045")
        edb = kredyt.edb_kredyt(S, rp, N, 0, r, rd)

        jeden = D(1)
        def annuita(stopa):
            czynnik = (jeden + stopa) ** N
            return S * stopa * czynnik / (czynnik - jeden)

        recznie = sum(
            ((annuita(r) - annuita(rp)) / (jeden + rd) ** i for i in range(1, N + 1)),
            D("0"),
        )
        assert edb == recznie

    def test_dluzsza_karencja_zwieksza_edb(self):
        krotka = kredyt.edb_kredyt(S, D("0.025"), 30, 1, D("0.0542"), D("0.0542"))
        dluga = kredyt.edb_kredyt(S, D("0.025"), 30, 10, D("0.0542"), D("0.0542"))
        assert dluga > krotka

    def test_wieksza_roznica_stop_zwieksza_edb(self):
        maly = kredyt.edb_kredyt(S, D("0.05"), 30, 3, D("0.0542"), D("0.0542"))
        duzy = kredyt.edb_kredyt(S, D("0.01"), 30, 3, D("0.0542"), D("0.0542"))
        assert duzy > maly

    def test_edb_jest_proporcjonalne_do_kwoty_kredytu(self):
        maly = kredyt.edb_kredyt(D("1000000"), D("0.025"), 30, 3, D("0.0542"), D("0.0542"))
        duzy = kredyt.edb_kredyt(D("3000000"), D("0.025"), 30, 3, D("0.0542"), D("0.0542"))
        assert abs(duzy - maly * 3) < D("0.01")

    def test_zerowa_kwota_daje_zero(self):
        assert kredyt.edb_kredyt(D("0"), D("0.025"), 30, 3, D("0.0542"), D("0.0542")) == D("0")

    def test_karencja_nie_krotsza_niz_okres_to_wyjatek(self):
        with pytest.raises(BladObliczenia, match="karencji"):
            kredyt.edb_kredyt(S, D("0.025"), 10, 10, D("0.0542"), D("0.0542"))


class TestEDBNaWejsciuWzorcowym:
    def test_edb_liczone_z_parametrow_wejscia(self):
        w = wspolne.wejscie()
        h = kredyt.harmonogram(w.pula_spoleczna.kredyt, D("8000000"))
        edb = kredyt.edb_dla_harmonogramu(h, w.parametry_zewnetrzne)
        assert D("0") < edb < h.kwota

    def test_brak_kredytu_daje_zerowe_edb(self):
        w = wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        h = kredyt.harmonogram(w.pula_spoleczna.kredyt, D("0"))
        assert kredyt.edb_dla_harmonogramu(h, w.parametry_zewnetrzne) == D("0")
