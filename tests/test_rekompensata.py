"""Etap 6 — koszty netto, rozsadny zysk, asymetria gruntu i test nadwyzki."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import alokacja, czynsz, grant, kredyt, projekcja, rekompensata
from sim_kalkulator.dane import zbuduj

from . import wspolne


def policz(dane=None, **zmiany):
    dane = dane if dane is not None else wspolne.zmien(**zmiany)
    w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
    a = alokacja.build(w)
    g = grant.build(w, a)
    ls = czynsz.build(
        w, a.spoleczna, g.spoleczna,
        w.pula_spoleczna.czynsz_zakladany_m2_mies, w.pula_spoleczna.kredyt.aktywny,
    )
    lk = czynsz.build(
        w, a.komunalna, g.komunalna,
        w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies, False,
    )
    f = projekcja.zbuduj_finansowanie(w, a, g)
    pr = projekcja.build(w, a, f, ls, lk)
    edb_k = kredyt.edb_dla_harmonogramu(f.harmonogram_kredytu, w.parametry_zewnetrzne)
    return w, rekompensata.build(w, a, f, pr, edb_k)


def puli(wynik, nazwa):
    return getattr(wynik, nazwa)


class TestAsymetriaGruntu:
    """Grunt inwestora podnosi podstawe, grunt gminy ja obniza."""

    def test_grunt_jst_jako_przychod_obniza_kn(self):
        # Dwa identyczne warianty roznia sie WYLACZNIE forma wniesienia gruntu.
        # Sciezka grantowa w obu pulach — kredyt wylaczony, zeby izolowac efekt.
        wspolne_zmiany = dict(
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
            przelaczniki_grunt=None,
        )
        _, inwestora = policz(
            grunt__forma="wlasnosc_inwestora",
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        _, jst = policz(
            grunt__forma="aport_jst",
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert jst.spoleczna.kn < inwestora.spoleczna.kn
        assert jst.komunalna.kn < inwestora.komunalna.kn

    def test_grunt_inwestora_wchodzi_jako_koszt(self):
        _, wynik = policz(
            grunt__forma="wlasnosc_inwestora",
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        rok1 = wynik.spoleczna.lata[0]
        assert rok1.grunt_jako_koszt > D("0")
        assert rok1.grunt_jako_przychod == D("0")
        assert "art. 5 ust. 7 pkt 7" in wynik.spoleczna.grunt_ujecie

    def test_grunt_jst_wchodzi_jako_przychod(self):
        _, wynik = policz(
            grunt__forma="aport_jst",
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        rok1 = wynik.spoleczna.lata[0]
        assert rok1.grunt_jako_przychod > D("0")
        assert rok1.grunt_jako_koszt == D("0")
        assert "art. 5 ust. 9 pkt 4" in wynik.spoleczna.grunt_ujecie

    def test_roznica_kn_rowna_podwojonej_wartosci_gruntu_puli(self):
        # Grunt przesuwa sie ze strony kosztowej na przychodowa, wiec KN spada
        # o dwukrotnosc jego wartosci (dyskonto roku 1 = 1).
        _, inwestora = policz(
            grunt__forma="wlasnosc_inwestora", pula_spoleczna__kredyt__udzial_docelowy=0.0
        )
        _, jst = policz(grunt__forma="aport_jst", pula_spoleczna__kredyt__udzial_docelowy=0.0)
        grunt_puli = inwestora.spoleczna.lata[0].grunt_jako_koszt
        roznica = inwestora.spoleczna.kn - jst.spoleczna.kn
        assert abs(roznica - grunt_puli * 2) < D("0.01")

    def test_lokal_za_grunt_traktowany_jak_grunt_jst(self):
        _, wynik = policz(
            grunt__forma="lokal_za_grunt", pula_spoleczna__kredyt__udzial_docelowy=0.0
        )
        assert wynik.spoleczna.lata[0].grunt_jako_przychod > D("0")


class TestGruntWSciezceKredytowej:
    """§ 12 ust. 7 rozp. 766 — aport jako koszt, ale tylko do 20% kosztow."""

    def test_aport_ograniczony_do_20_procent_kosztow(self):
        _, wynik = policz(grunt__forma="aport_inwestora", grunt__wartosc=12000000.0)
        rok1 = wynik.spoleczna.lata[0]
        pulap = wynik.spoleczna.lata[0].grunt_jako_koszt
        assert "§ 12 ust. 7" in wynik.spoleczna.grunt_ujecie
        assert "obcieto" in wynik.spoleczna.grunt_ujecie
        # Uznany koszt nie przekracza 20% kosztow przedsiewziecia puli.
        w, _ = policz(grunt__forma="aport_inwestora", grunt__wartosc=12000000.0)
        a = alokacja.build(w)
        assert pulap == a.spoleczna.koszty_przedsiewziecia * D("0.20")

    def test_maly_aport_miesci_sie_w_limicie(self):
        _, wynik = policz(grunt__forma="aport_inwestora", grunt__wartosc=1000000.0)
        assert "obcieto" not in wynik.spoleczna.grunt_ujecie

    def test_grunt_jst_w_sciezce_kredytowej_jest_kosztem_nie_przychodem(self):
        # W sciezce kredytowej regula z art. 5 ust. 9 pkt 4 nie ma zastosowania —
        # § 12 ust. 7 traktuje kazdy aport jako koszt limitowany.
        _, wynik = policz(grunt__forma="aport_jst", grunt__wartosc=1000000.0)
        assert wynik.spoleczna.lata[0].grunt_jako_koszt > D("0")
        assert wynik.spoleczna.lata[0].grunt_jako_przychod == D("0")


class TestKosztyNetto:
    def test_kn_jest_suma_zdyskontowanych_roznic(self):
        _, wynik = policz()
        recznie = sum((r.netto_zdyskontowane for r in wynik.komunalna.lata), D("0"))
        assert wynik.komunalna.kn == recznie

    def test_pierwszy_rok_nie_jest_dyskontowany(self):
        _, wynik = policz()
        assert wynik.komunalna.lata[0].czynnik_dyskonta == D("1")

    def test_dyskonto_rosnie_stopa_bazowa_ke(self):
        w, wynik = policz()
        rb = w.parametry_zewnetrzne.stopa_bazowa_ke
        assert wynik.komunalna.lata[1].czynnik_dyskonta == (D("1") + rb) ** 1
        assert wynik.komunalna.lata[4].czynnik_dyskonta == (D("1") + rb) ** 4

    def test_stopa_bazowa_istotnie_przesuwa_kn(self):
        # KN nie jest monotoniczne wzgledem rb: koszt gruntu siedzi w roku 1
        # (dyskonto = 1), a nadwyzki przychodowe w latach pozniejszych. Wyzsza
        # stopa oslabia ogon, wiec suma moze isc w obie strony. Dlatego rozdz. 7.3
        # specyfikacji kaze liczyc wrazliwosc na stope zawsze, niezaleznie od
        # konfiguracji — nie da sie jej przewidziec znakiem.
        _, niska = policz(parametry_zewnetrzne__stopa_bazowa_ke=0.01)
        _, wysoka = policz(parametry_zewnetrzne__stopa_bazowa_ke=0.09)
        assert niska.komunalna.kn != wysoka.komunalna.kn

    def test_wyzsza_stopa_bazowa_oslabia_wage_lat_pozniejszych(self):
        _, niska = policz(parametry_zewnetrzne__stopa_bazowa_ke=0.01)
        _, wysoka = policz(parametry_zewnetrzne__stopa_bazowa_ke=0.09)
        ostatni_n = niska.komunalna.lata[-1]
        ostatni_w = wysoka.komunalna.lata[-1]
        assert abs(ostatni_w.netto_zdyskontowane) < abs(ostatni_n.netto_zdyskontowane)

    def test_odsetki_wchodza_do_kosztow_tylko_w_sciezce_kredytowej(self):
        _, wynik = policz()
        assert wynik.spoleczna.lata[0].odsetki > D("0")
        assert all(r.odsetki == D("0") for r in wynik.komunalna.lata)


class TestUjecieKosztowInwestycyjnych:
    def test_grunt_nie_wchodzi_do_nakladu_inwestycyjnego(self):
        # Grunt ma wlasna regule asymetryczna, wiec ujety takze w nakladzie
        # trafialby do KN dwa razy.
        w, wynik = policz()
        a = alokacja.build(w)
        rok1 = wynik.komunalna.lata[0]
        podstawa = a.komunalna.koszty_przedsiewziecia_bez_gruntu
        assert podstawa == a.komunalna.koszty_przedsiewziecia - a.komunalna.grunt
        assert rok1.koszty_inwestycyjne * D("100") == podstawa
        assert rok1.grunt_jako_koszt == a.komunalna.grunt

    def test_amortyzacja_rozklada_naklad_rowno(self):
        w, wynik = policz()
        a = alokacja.build(w)
        oczekiwany = a.komunalna.koszty_przedsiewziecia_bez_gruntu / D("100")
        assert all(r.koszty_inwestycyjne == oczekiwany for r in wynik.komunalna.lata)

    def test_naklad_poczatkowy_ladu_je_w_roku_pierwszym(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["koszty_inwestycyjne_w_kn"] = "naklad_poczatkowy"
        w, wynik = policz(dane)
        a = alokacja.build(w)
        assert (
            wynik.komunalna.lata[0].koszty_inwestycyjne
            == a.komunalna.koszty_przedsiewziecia_bez_gruntu
        )
        assert wynik.komunalna.lata[1].koszty_inwestycyjne == D("0")

    def test_pominiecie_zeruje_pozycje(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["koszty_inwestycyjne_w_kn"] = "pominiete"
        _, wynik = policz(dane)
        assert all(r.koszty_inwestycyjne == D("0") for r in wynik.komunalna.lata)

    def test_ujecie_zmienia_kn_istotnie_wiec_musi_byc_widoczne(self):
        _, amort = policz()
        dane = wspolne.zmien()
        dane["przelaczniki"]["koszty_inwestycyjne_w_kn"] = "naklad_poczatkowy"
        _, naklad = policz(dane)
        assert naklad.komunalna.kn > amort.komunalna.kn
        w, _ = policz()
        assert "ZALOZENIE_KOSZTY_INWESTYCYJNE_W_KN" in {o.kod for o in w.ostrzezenia}


class TestProgNadwyzki:
    """Prog tolerancji: 10% sredniej rocznej rekompensaty w grancie, 20% w kredycie."""

    def zbuduj_pule(self, sciezka, nadwyzka_wzgledna):
        from sim_kalkulator import prawo
        from sim_kalkulator.rekompensata import RekompensataPuli

        lat = 25
        ruoig = D("2500000")
        srednia = ruoig / D(lat)
        nadwyzka = srednia * D(str(nadwyzka_wzgledna))
        return RekompensataPuli(
            nazwa="test",
            sciezka=sciezka,
            okres_powierzenia_lat=lat,
            lata=(),
            kn=ruoig - nadwyzka,
            rz=D("0"),
            edb_grantu=ruoig,
            edb_kredytu=D("0"),
            wsparcie_dodatkowe=D("0"),
            prog_tolerancji=prawo.prog_tolerancji_nadwyzki(sciezka),
            grunt_ujecie="",
        )

    def test_nadwyzka_9_9_procent_w_grancie_przechodzi(self):
        pula = self.zbuduj_pule("grant", "0.099")
        assert pula.przechodzi is True
        assert pula.kwota_do_zwrotu == D("0")

    def test_nadwyzka_10_1_procent_w_grancie_uruchamia_zwrot(self):
        pula = self.zbuduj_pule("grant", "0.101")
        assert pula.przechodzi is False
        assert pula.kwota_do_zwrotu == pula.nadwyzka
        assert pula.kwota_do_zwrotu > D("0")

    def test_nadwyzka_dokladnie_10_procent_w_grancie_przechodzi(self):
        pula = self.zbuduj_pule("grant", "0.10")
        assert pula.przechodzi is True

    def test_prog_kredytowy_jest_dwa_razy_luzniejszy(self):
        assert self.zbuduj_pule("kredyt", "0.199").przechodzi is True
        assert self.zbuduj_pule("kredyt", "0.201").przechodzi is False

    def test_ta_sama_nadwyzka_przechodzi_w_kredycie_a_nie_w_grancie(self):
        assert self.zbuduj_pule("kredyt", "0.15").przechodzi is True
        assert self.zbuduj_pule("grant", "0.15").przechodzi is False


class TestRozsadnyZysk:
    def test_metoda_kwota_wprost_dzieli_kwote_kluczem_pum(self):
        dane = wspolne.zmien(powierzchnie__udzial_puli_komunalnej=0.25)
        dane["przelaczniki"]["metoda_rozsadnego_zysku"] = "kwota_wprost"
        dane["rekompensata"]["rozsadny_zysk_kwota"] = 1000000.0
        _, wynik = policz(dane)
        assert wynik.spoleczna.rz == D("750000.00")
        assert wynik.komunalna.rz == D("250000.00")

    def test_rz_rosnie_ze_stopa_irs(self):
        _, niska = policz(parametry_zewnetrzne__stopa_irs_bgk=0.02)
        _, wysoka = policz(parametry_zewnetrzne__stopa_irs_bgk=0.07)
        assert wysoka.komunalna.rz > niska.komunalna.rz

    def test_rz_zero_gdy_nie_ma_kapitalu_wlasnego(self):
        # Pula finansowana w calosci ze zrodel obcych nie angazuje kapitalu wlasnego.
        _, wynik = policz(pula_komunalna__bonus_rewitalizacyjny=True,
                          powierzchnie__udzial_puli_komunalnej=0.3)
        assert wynik.komunalna.rz >= D("0")

    def test_rz_zawsze_oznaczony_jako_zalozenie(self):
        w, _ = policz()
        assert "ZALOZENIE_ROZSADNY_ZYSK" in {o.kod for o in w.ostrzezenia}


class TestWarunekGraniczny:
    def test_ruoig_to_suma_edb_i_wsparcia_dodatkowego(self):
        _, wynik = policz(rekompensata__wsparcie_rfrm=500000.0)
        p = wynik.komunalna
        assert p.ruoig == p.edb_grantu + p.edb_kredytu + p.wsparcie_dodatkowe

    def test_wsparcie_dodatkowe_dzieli_sie_kluczem_pum(self):
        _, wynik = policz(
            rekompensata__wsparcie_rfrm=1000000.0,
            powierzchnie__udzial_puli_komunalnej=0.40,
        )
        assert wynik.komunalna.wsparcie_dodatkowe == D("400000.000")
        assert wynik.spoleczna.wsparcie_dodatkowe == D("600000.000")
        assert "WSPARCIE_DODATKOWE_W_REKOMPENSACIE" in {o.kod for o in wynik.ostrzezenia}

    def test_edb_grantu_rowna_sie_kwocie_grantu(self):
        w, wynik = policz()
        a = alokacja.build(w)
        g = grant.build(w, a)
        assert wynik.komunalna.edb_grantu == g.komunalna.kwota

    def test_dopuszczalna_rekompensata_to_kn_plus_rz(self):
        _, wynik = policz()
        p = wynik.komunalna
        assert p.dopuszczalna == p.kn + p.rz


class TestDwaTestyCzyJeden:
    def test_domyslnie_dwa_osobne_testy_rekompensaty(self):
        _, wynik = policz()
        assert wynik.laczna is None
        assert len(wynik.badane) == 2
        assert {p.sciezka for p in wynik.badane} == {"grant", "kredyt"}

    def test_progi_tolerancji_roznia_sie_miedzy_pulami(self):
        _, wynik = policz()
        assert wynik.spoleczna.prog_tolerancji == D("0.20")   # sciezka kredytowa
        assert wynik.komunalna.prog_tolerancji == D("0.10")   # sciezka grantowa

    def test_przelacznik_scala_w_jeden_test(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["hybryda_jako_jedno_przedsiewziecie"] = True
        _, wynik = policz(dane)
        assert wynik.laczna is not None
        assert len(wynik.badane) == 1
        assert wynik.laczna.kn == wynik.spoleczna.kn + wynik.komunalna.kn
        assert "REKOMPENSATA_JEDEN_TEST" in {o.kod for o in wynik.ostrzezenia}

    def test_scalona_pula_bierze_luzniejszy_prog_kredytowy(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["hybryda_jako_jedno_przedsiewziecie"] = True
        _, wynik = policz(dane)
        assert wynik.laczna.sciezka == "kredyt"
        assert wynik.laczna.prog_tolerancji == D("0.20")

    def test_ujemne_kn_daje_ostrzezenie(self):
        _, wynik = policz()
        if any(p.kn < D("0") for p in wynik.badane):
            assert "KOSZTY_NETTO_UJEMNE" in {o.kod for o in wynik.ostrzezenia}
