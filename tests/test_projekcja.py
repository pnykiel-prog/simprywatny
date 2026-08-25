"""Etap 5 — struktura finansowania i przeplywy rok po rok."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import alokacja, czynsz, grant, projekcja

from . import wspolne


def zestaw(**zmiany):
    w = wspolne.wejscie(**zmiany)
    a = alokacja.build(w)
    g = grant.build(w, a)
    ls = czynsz.build(
        w, a.spoleczna, g.spoleczna,
        w.pula_spoleczna.czynsz_zakladany_m2_mies,
        w.pula_spoleczna.kredyt.aktywny,
    )
    lk = czynsz.build(
        w, a.komunalna, g.komunalna,
        w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies, False,
    )
    f = projekcja.zbuduj_finansowanie(w, a, g)
    return w, a, g, f, projekcja.build(w, a, f, ls, lk)


class TestFinansowanie:
    def test_zrodla_domykaja_koszty_kazdej_puli(self):
        _, _, _, f, _ = zestaw()
        for pula in (f.spoleczna, f.komunalna):
            assert pula.zrodla_obce + pula.wklad_wlasny == pula.koszty_przedsiewziecia

    def test_pula_komunalna_nie_ma_kredytu_ani_partycypacji(self):
        _, _, _, f, _ = zestaw()
        assert f.komunalna.kredyt == D("0")
        assert f.komunalna.partycypacja == D("0")

    def test_wklad_wlasny_to_jeden_bilans_inwestora(self):
        _, _, _, f, _ = zestaw()
        assert f.wklad_wlasny_wymagany == f.spoleczna.wklad_wlasny + f.komunalna.wklad_wlasny

    def test_wiekszy_udzial_komunalny_podnosi_zapotrzebowanie_na_wklad(self):
        # Pula komunalna nie ma dzwigni kredytowej ani partycypacji, wiec kazdy
        # przesuniety metr trzeba pokryc grantem albo wlasnym kapitalem.
        _, _, _, malo, _ = zestaw(powierzchnie__udzial_puli_komunalnej=0.10)
        _, _, _, duzo, _ = zestaw(powierzchnie__udzial_puli_komunalnej=0.60)
        assert duzo.wklad_wlasny_wymagany > malo.wklad_wlasny_wymagany

    def test_kwota_kredytu_wynika_z_udzialu_docelowego(self):
        _, a, _, f, _ = zestaw(pula_spoleczna__kredyt__udzial_docelowy=0.35)
        assert f.spoleczna.kredyt == a.spoleczna.koszty_przedsiewziecia * D("0.35")


class TestOkresPowierzenia:
    def test_sciezka_grantowa_to_25_lat(self):
        w = wspolne.wejscie()
        assert projekcja.okres_powierzenia(w, sciezka_kredytowa=False) == 25

    def test_sciezka_kredytowa_rowna_okresowi_finansowania(self):
        w = wspolne.wejscie(pula_spoleczna__kredyt__okres_lat=28)
        assert projekcja.okres_powierzenia(w, sciezka_kredytowa=True) == 28

    def test_okres_amortyzacji_scina_okres_powierzenia(self):
        w = wspolne.wejscie(
            pula_spoleczna__kredyt__okres_lat=30,
            parametry_zewnetrzne__okres_amortyzacji_budynkow_lat=22,
        )
        assert projekcja.okres_powierzenia(w, sciezka_kredytowa=True) == 22

    def test_pula_komunalna_zawsze_na_sciezce_grantowej(self):
        _, _, _, _, pr = zestaw()
        assert pr.komunalna.sciezka == "grant"
        assert pr.komunalna.okres_powierzenia_lat == 25

    def test_pula_spoleczna_bez_kredytu_wraca_na_sciezke_grantowa(self):
        _, _, _, _, pr = zestaw(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        assert pr.spoleczna.sciezka == "grant"
        assert pr.spoleczna.okres_powierzenia_lat == 25


class TestIndeksacja:
    def test_czynsz_rosnie_wskaznikiem_indeksacji(self):
        w, _, _, _, pr = zestaw()
        rok1, rok2 = pr.spoleczna.lata[0], pr.spoleczna.lata[1]
        assert rok2.czynsz_m2_mies == rok1.czynsz_m2_mies * D("1.030")

    def test_koszty_rosna_wlasnym_wskaznikiem(self):
        _, _, _, _, pr = zestaw()
        rok1, rok2 = pr.spoleczna.lata[0], pr.spoleczna.lata[1]
        assert rok2.koszt_eksploatacji == rok1.koszt_eksploatacji * D("1.035")

    def test_szybsza_indeksacja_kosztow_obniza_dscr_ceteris_paribus(self):
        wolno = zestaw(eksploatacja__indeksacja_kosztow_rocznie=0.020)[4]
        szybko = zestaw(eksploatacja__indeksacja_kosztow_rocznie=0.060)[4]
        assert szybko.spoleczna.lata[-1].dscr < wolno.spoleczna.lata[-1].dscr

    def test_szybsza_indeksacja_czynszu_podnosi_dscr_ceteris_paribus(self):
        wolno = zestaw(eksploatacja__indeksacja_czynszu_rocznie=0.010)[4]
        szybko = zestaw(eksploatacja__indeksacja_czynszu_rocznie=0.045)[4]
        assert szybko.spoleczna.lata[-1].dscr > wolno.spoleczna.lata[-1].dscr

    def test_stala_rata_nominalna_poprawia_dscr_z_biegiem_lat(self):
        # Rata annuitetowa jest nominalnie stala, a czynsz indeksowany — dlatego
        # waskim gardlem testu 2 jest pierwszy rok po karencji, nie ostatni.
        _, _, _, _, pr = zestaw()
        po_karencji = pr.spoleczna.lata[3]
        ostatni = pr.spoleczna.lata[-1]
        assert ostatni.dscr > po_karencji.dscr
        assert pr.spoleczna.pierwszy_rok_naruszenia == po_karencji.rok

    def test_pierwszy_rok_bez_indeksacji(self):
        w, _, _, _, pr = zestaw()
        rok1 = pr.spoleczna.lata[0]
        assert rok1.czynsz_m2_mies == w.pula_spoleczna.czynsz_zakladany_m2_mies


class TestPustostany:
    def test_pustostany_obnizaja_przychod_puli_spolecznej(self):
        _, _, _, _, pr = zestaw()
        rok = pr.spoleczna.lata[0]
        assert rok.strata_na_pustostanach == rok.przychod_czynszowy_potencjalny * D("0.05")
        assert rok.przychod_czynszowy_netto < rok.przychod_czynszowy_potencjalny

    def test_domyslnie_pula_komunalna_bez_pustostanow(self):
        _, _, _, _, pr = zestaw()
        assert pr.komunalna.lata[0].strata_na_pustostanach == D("0")

    def test_przelacznik_wlacza_pustostany_w_puli_komunalnej(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["pustostany_takze_w_puli_komunalnej"] = True
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        a = alokacja.build(w)
        g = grant.build(w, a)
        ls = czynsz.build(w, a.spoleczna, g.spoleczna, w.pula_spoleczna.czynsz_zakladany_m2_mies, True)
        lk = czynsz.build(w, a.komunalna, g.komunalna,
                          w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies, False)
        pr = projekcja.build(w, a, projekcja.zbuduj_finansowanie(w, a, g), ls, lk)
        assert pr.komunalna.lata[0].strata_na_pustostanach > D("0")


class TestRezerwaNaZwrotPartycypacji:
    """art. 29a ust. 3 — zobowiazanie rosnace, niezalezne od ponownego zasiedlenia."""

    def test_rezerwa_rosnie_waloryzacja(self):
        _, _, _, _, pr = zestaw()
        rok1, rok2 = pr.spoleczna.lata[0], pr.spoleczna.lata[1]
        assert rok2.rezerwa_zwrot_partycypacji == rok1.rezerwa_zwrot_partycypacji * D("1.040")

    def test_rezerwa_proporcjonalna_do_rotacji(self):
        _, _, _, f, pr = zestaw()
        oczekiwana = f.spoleczna.partycypacja * D("0.07") * D("1.040")
        assert pr.spoleczna.lata[0].rezerwa_zwrot_partycypacji == oczekiwana

    def test_brak_rotacji_zeruje_rezerwe(self):
        _, _, _, _, pr = zestaw(pula_spoleczna__partycypacja__rotacja_roczna=0.0)
        assert pr.spoleczna.lata[0].rezerwa_zwrot_partycypacji == D("0")

    def test_pula_komunalna_nie_ma_rezerwy_bo_nie_ma_partycypacji(self):
        _, _, _, _, pr = zestaw()
        assert all(r.rezerwa_zwrot_partycypacji == D("0") for r in pr.komunalna.lata)

    def test_rezerwa_obniza_saldo_ale_nie_dscr(self):
        bez = zestaw(pula_spoleczna__partycypacja__rotacja_roczna=0.0)[4].spoleczna.lata[5]
        z = zestaw()[4].spoleczna.lata[5]
        assert z.saldo < bez.saldo
        assert z.dscr == bez.dscr


class TestObslugaDlugu:
    def test_w_karencji_placone_sa_same_odsetki(self):
        _, _, _, f, pr = zestaw()
        rata_karencji = pr.spoleczna.lata[0].obsluga_dlugu
        assert rata_karencji == f.spoleczna.kredyt * D("0.025")

    def test_po_karencji_rata_skacze(self):
        _, _, _, _, pr = zestaw()
        assert pr.spoleczna.lata[3].obsluga_dlugu > pr.spoleczna.lata[2].obsluga_dlugu

    def test_pula_komunalna_nie_ma_obslugi_dlugu(self):
        _, _, _, _, pr = zestaw()
        assert all(r.obsluga_dlugu == D("0") for r in pr.komunalna.lata)

    def test_dscr_liczony_wzorem_z_testu_2(self):
        _, _, _, _, pr = zestaw()
        rok = pr.spoleczna.lata[5]
        assert rok.dscr == rok.przychod_czynszowy_netto / (
            rok.koszt_eksploatacji + rok.odpis_remontowy + rok.ubezpieczenie
            + rok.koszty_zarzadu + rok.obsluga_dlugu
        )

    def test_pierwszy_rok_naruszenia_wskazywany_wprost(self):
        _, _, _, _, pr = zestaw()
        rok = pr.spoleczna.pierwszy_rok_naruszenia
        assert rok is not None
        assert pr.spoleczna.lata[rok - 1].dscr < D("1")
        assert all(r.dscr >= D("1") for r in pr.spoleczna.lata[: rok - 1])


class TestOplatyPozaCzynszem:
    def test_pulap_oplat_jest_osobna_pozycja(self):
        _, _, _, _, pr = zestaw()
        rok = pr.spoleczna.lata[0]
        assert rok.pulap_oplat_poza_czynszem > D("0")
        # Nie wchodzi ani do przychodu czynszowego, ani do mianownika testu 2.
        assert rok.pulap_oplat_poza_czynszem not in (
            rok.przychod_czynszowy_netto, rok.wymagane_pokrycie
        )
        assert rok.dscr == rok.przychod_czynszowy_netto / rok.wymagane_pokrycie


class TestHoryzont:
    def test_horyzont_to_dluzszy_z_okresow_powierzenia(self):
        _, _, _, _, pr = zestaw()
        assert pr.horyzont_lat == 30
        assert len(pr.spoleczna.lata) == 30
        assert len(pr.komunalna.lata) == 25

    def test_pula_o_zerowym_pum_nie_wchodzi_do_projekcji(self):
        _, _, _, _, pr = zestaw(powierzchnie__udzial_puli_komunalnej=0.0)
        assert pr.komunalna.aktywna is False
        assert len(pr.pule) == 1
