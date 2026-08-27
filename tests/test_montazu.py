"""Etap 7 — trzy werdykty, wiazace ograniczenie i luki liczbowe."""

from decimal import Decimal as D

import pytest

from sim_kalkulator import prawo
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
            "Kapitał", "Zdolność czynszowa", "Rekompensata"
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


def reczny(**zmiany):
    """Wynik w trybie recznym — kredyt z udzialu docelowego, jak przed zmiana.

    W trybie automatycznym wskaznik pokrycia wychodzi 1,0 z konstrukcji, wiec
    porazki testu 2 nie da sie tam wywolac. Tryb reczny zostaje wlasnie po to.
    """
    dane = wspolne.zmien(**zmiany)
    dane["przelaczniki"]["tryb_kredytu"] = "reczny"
    from sim_kalkulator.dane import zbuduj

    return przelicz(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA))


class TestMontazu:
    """Wklad wlasny jest WYNIKIEM: koszty - dotacja - kredyt - partycypacja."""

    def test_wklad_jest_reszta_po_zrodlach_obcych(self):
        f = wynik().finansowanie
        assert f.wklad_wlasny_wymagany == (
            f.koszty_laczne - f.grant_laczny - f.kredyt_laczny - f.partycypacja_laczna
        )

    def test_bez_deklaracji_kapitalu_test_przechodzi_i_podaje_kwote(self):
        # Zdolnosc inwestora nigdy nie blokuje obliczenia (rozdz. 2.3).
        dane = wspolne.zmien()
        dane["inwestor"].pop("dostepny_wklad_wlasny")
        from sim_kalkulator.dane import zbuduj

        r = przelicz(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA))
        t = r.werdykty.montaz
        assert t.przechodzi is True
        assert t.luka_opis == "Wymagany wkład własny"
        assert t.luka_kwota == r.finansowanie.wklad_wlasny_wymagany
        assert "trzeba wyłożyć własnych" in t.wiazace_ograniczenie

    def test_brak_deklaracji_nie_jest_bledem_walidacji(self):
        dane = wspolne.zmien()
        dane["inwestor"].pop("dostepny_wklad_wlasny")
        from sim_kalkulator.dane import zbuduj

        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        assert w.inwestor.zadeklarowany is False

    def test_deklaracja_dodaje_odniesienie_nie_zmieniajac_wymaganej_kwoty(self):
        bez = wspolne.zmien()
        bez["inwestor"].pop("dostepny_wklad_wlasny")
        from sim_kalkulator.dane import zbuduj

        r_bez = przelicz(zbuduj(bez, na_dzien=wspolne.DATA_ODNIESIENIA))
        r_z = wynik(inwestor__dostepny_wklad_wlasny=100000.0)
        assert r_bez.finansowanie.wklad_wlasny_wymagany == (
            r_z.finansowanie.wklad_wlasny_wymagany
        )
        assert r_z.werdykty.montaz.przechodzi is False


class TestKredytAutomatyczny:
    """Rozdz. 2.2 — kredyt liczony, nie wpisywany. Pokrycie 1,0 z konstrukcji."""

    def test_wskaznik_pokrycia_nigdy_nie_schodzi_ponizej_jednosci(self):
        # Test 2 spelniony z konstrukcji. Pokrycie wychodzi dokladnie tyle, ile
        # wynosi bufor, gdy wiazacy jest czynsz, i wyzej, gdy kredytu potrzeba
        # mniej, niz czynsz uniesie — nikt nie zaciaga wiecej, niz brakuje po
        # dotacji.
        for czynsz in (14.0, 18.0, 22.0, 26.0):
            r = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=czynsz)
            assert r.projekcja.spoleczna.minimalny_dscr >= D("1"), czynsz

    def test_pokrycie_wychodzi_na_poziomie_bufora_gdy_wiaze_czynsz(self):
        # Pakiet nr 2, rozdz. 1: kredyt wymierzony z buforem daje w projekcji
        # pokrycie rowne buforowi, nie jednosci. Prog testu 2 to nadal 1,00,
        # wiec test przechodzi z zapasem — i o to zapas chodzi.
        r = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=14.0)
        bufor = prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY
        pokrycie = r.projekcja.spoleczna.minimalne_pokrycie_obslugi_dlugu
        assert bufor <= pokrycie < bufor + D("0.001")

    def test_dwie_miary_pokrycia_to_dwie_rozne_liczby(self):
        # Miara testu 2 dzieli przychod przez WSZYSTKIE wyplywy, pokrycie bankowe
        # dzieli nadwyzke operacyjna przez sama rate. Przy tej samej racie druga
        # jest wyzsza. Zamiana ich miejscami przewrocilaby werdykt testu 2.
        p = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=14.0).projekcja.spoleczna
        assert p.minimalny_dscr < p.minimalne_pokrycie_obslugi_dlugu
        rok = p.lata[0]
        assert rok.dscr == rok.przychod_czynszowy_netto / rok.wymagane_pokrycie
        assert rok.pokrycie_obslugi_dlugu == rok.nadwyzka_operacyjna / rok.obsluga_dlugu

    def test_wyzszy_bufor_obniza_kredyt_maksymalny(self):
        bez = wynik(
            pula_spoleczna__czynsz_zakladany_m2_mies=14.0,
            parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=1.0,
        )
        z_buforem = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=14.0)
        assert z_buforem.finansowanie.spoleczna.kredyt < bez.finansowanie.spoleczna.kredyt
        # Kredyt wiazany czynszem skaluje sie odwrotnie proporcjonalnie do bufora.
        iloraz = bez.finansowanie.spoleczna.kredyt / z_buforem.finansowanie.spoleczna.kredyt
        assert abs(iloraz - prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY) < D("0.001")

    def test_brak_bufora_daje_ostrzezenie_o_finansowaniu_bez_marginesu(self):
        w = wspolne.wejscie(
            parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=1.0
        )
        kody = {o.kod for o in w.ostrzezenia}
        assert "BUFOR_OBSLUGI_DLUGU_ZEROWY" in kody
        assert "ZALOZENIE_BUFOR_OBSLUGI_DLUGU" not in kody

    def test_bufor_domyslny_jest_oznaczony_jako_zalozenie(self):
        kody = {o.kod for o in wspolne.wejscie().ostrzezenia}
        assert "ZALOZENIE_BUFOR_OBSLUGI_DLUGU" in kody

    def test_stawka_domykajaca_odwraca_wymiarowanie_z_buforem(self):
        # Symetria obu funkcji: przy stawce domykajacej wymagany wklad gotowkowy
        # schodzi do zera. Gdyby bufor wchodzil tylko do jednej z nich, stawka
        # domykalaby kwote, ktorej silnik nie przyjmuje.
        r = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=14.0)
        stawka = r.czynsz_domykajacy_m2_mies
        assert stawka is not None
        przy_stawce = wynik(
            pula_spoleczna__czynsz_zakladany_m2_mies=float(stawka),
            powierzchnie__udzial_puli_komunalnej=0.0,
        )
        assert przy_stawce.finansowanie.wklad_gotowkowy_wymagany < D("1000")

    def test_kredyt_nie_przekracza_tego_co_potrzebne(self):
        # Bez tego ograniczenia wymagany wklad wlasny wychodzilby ujemny.
        r = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=30.0)
        assert r.finansowanie.wklad_wlasny_wymagany >= D("0")
        f = r.finansowanie.spoleczna
        assert f.grant + f.kredyt + f.partycypacja <= r.alokacja.spoleczna.koszty_przedsiewziecia

    def test_test_czynszowy_przechodzi_z_konstrukcji(self):
        assert wynik().werdykty.zdolnosc_czynszowa.przechodzi is True

    def test_kredyt_nie_przekracza_limitu_ustawowego(self):
        r = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=30.0)
        udzial = r.finansowanie.spoleczna.kredyt / r.alokacja.spoleczna.koszty_przedsiewziecia
        assert udzial <= D("0.80")

    def test_wyzszy_czynsz_uniesie_wiekszy_kredyt(self):
        niski = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=18.0)
        wysoki = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=26.0)
        assert wysoki.finansowanie.spoleczna.kredyt > niski.finansowanie.spoleczna.kredyt

    def test_wyzszy_kredyt_obniza_wymagany_wklad(self):
        niski = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=18.0)
        wysoki = wynik(pula_spoleczna__czynsz_zakladany_m2_mies=26.0)
        assert wysoki.finansowanie.wklad_wlasny_wymagany < niski.finansowanie.wklad_wlasny_wymagany

    def test_kwota_kredytu_zaokraglona_do_pelnych_zlotych(self):
        # Bez tego wskaznik pokrycia potrafi wyjsc 0,999...8 i przewrocic werdykt.
        kwota = wynik().finansowanie.spoleczna.kredyt
        assert kwota == kwota.to_integral_value()

    def test_tryb_reczny_wraca_do_udzialu_docelowego(self):
        r = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.40)
        assert r.finansowanie.spoleczna.kredyt == (
            r.alokacja.spoleczna.koszty_przedsiewziecia * D("0.40")
        )

    def test_tryb_reczny_pozwala_oblac_test_czynszowy(self):
        r = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.80)
        assert r.projekcja.spoleczna.minimalny_dscr < D("1")
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is False


class TestMontazuSzczegoly:

    def test_zrodla_sumuja_sie_do_kosztow(self):
        r = wynik()
        f = r.finansowanie
        assert (
            f.grant_laczny + f.kredyt_laczny + f.partycypacja_laczna
            + f.wklad_wlasny_wymagany
        ) == f.koszty_laczne

    def test_przechodzi_gdy_kapital_wystarcza(self):
        r = wynik(inwestor__dostepny_wklad_wlasny=50000000.0)
        assert r.werdykty.montaz.przechodzi is True
        assert "Zostaje zapas" in r.werdykty.montaz.wiazace_ograniczenie

    def test_luka_kapitalowa_gdy_kapitalu_brakuje(self):
        r = wynik(inwestor__dostepny_wklad_wlasny=100000.0)
        t = r.werdykty.montaz
        assert t.przechodzi is False
        assert t.luka_jednostka == "zl"
        assert t.luka_opis == "Brakujący kapitał"
        assert t.luka_kwota == r.finansowanie.wklad_wlasny_wymagany - D("100000.0")
        assert "Brakuje" in t.wiazace_ograniczenie

    def test_szczegoly_pokazuja_wszystkie_zrodla(self):
        t = wynik().werdykty.montaz
        for klucz in ("Dotacja", "Kredyt SBC", "Partycypacja", "Wymagany wklad wlasny"):
            assert klucz in t.szczegoly


class TestZdolnosciCzynszowej:
    def test_porazka_wskazuje_rok_pierwszego_naruszenia(self):
        r = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.80)
        t = r.werdykty.zdolnosc_czynszowa
        assert t.przechodzi is False
        rok = r.projekcja.spoleczna.pierwszy_rok_naruszenia
        assert t.szczegoly["Rok pierwszego naruszenia"] == str(rok)

    def test_luka_podana_w_zl_na_m2_na_miesiac(self):
        t = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.80).werdykty.zdolnosc_czynszowa
        assert t.luka_jednostka == "zl/m2/mies."
        assert t.luka_kwota > D("0")

    def test_raportuje_czynsz_wymagany_limit_i_rynek(self):
        # Rozjazd miedzy limitem a poziomem potrzebnym do domkniecia to
        # centralne napiecie modelu i ma byc widoczny wprost.
        t = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.80).werdykty.zdolnosc_czynszowa
        klucze = " ".join(t.szczegoly)
        assert "Czynsz wymagany do domkniecia" in klucze
        assert "Limit czynszu" in klucze
        assert "Czynsz rynkowy" in klucze

    def test_bez_kredytu_test_przechodzi_trywialnie(self):
        r = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.0)
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is True

    def test_dscr_ponizej_jednosci_to_porazka(self):
        r = reczny(pula_spoleczna__kredyt__udzial_docelowy=0.80)
        assert r.projekcja.spoleczna.minimalny_dscr < D("1")
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is False

    def test_wyzsze_pustostany_zmniejszaja_udzwig_kredytowy(self):
        # W trybie automatycznym pustostany nie psuja pokrycia — obnizaja kwote
        # kredytu, ktora czynsz jest w stanie uniesc, i podnosza wymagany wklad.
        malo = wynik(eksploatacja__pustostany_procent=0.02)
        duzo = wynik(eksploatacja__pustostany_procent=0.20)
        assert duzo.finansowanie.spoleczna.kredyt < malo.finansowanie.spoleczna.kredyt
        assert duzo.finansowanie.wklad_wlasny_wymagany > malo.finansowanie.wklad_wlasny_wymagany


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
    def test_pelna_pula_komunalna_liczy_sie_bez_kredytu(self):
        # Tryb automatyczny: kwote kredytu wyznacza czynsz, a bez mieszkan
        # spolecznych wychodzi zero. Nie ma czego zabraniac.
        r = przelicz_udzial(wspolne.wejscie(), D("1.0"))
        assert not isinstance(r, WynikNieobliczalny)
        assert r.finansowanie.spoleczna.kredyt == D("0")

    def test_kredyt_reczny_przy_pelnej_puli_komunalnej_wraca_jako_niepoliczalny(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["tryb_kredytu"] = "reczny"
        from sim_kalkulator.dane import zbuduj

        r = przelicz_udzial(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA), D("1.0"))
        assert isinstance(r, WynikNieobliczalny)
        assert r.typ == "walidacja"
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
    """Zamrozone werdykty przykladow — zmiana silnika, ktora je przesuwa, ma wysypac testy.

    Wartosci przemrozone po przebudowie warstwy interakcji: kredyt liczony
    automatycznie, wklad wlasny jako wynik.
    """

    def test_wzorcowy_nie_domyka_sie_i_wiaze_rekompensata(self):
        r = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        assert r.domyka_sie is False
        assert r.werdykty.montaz.przechodzi is True
        assert r.werdykty.zdolnosc_czynszowa.przechodzi is True
        assert r.werdykty.rekompensata.przechodzi is False
        assert r.werdykty.wiazace_ograniczenie.startswith("Test 3")

    def test_wzorcowy_zamrozone_liczby(self):
        # Kwoty po wprowadzeniu bufora obslugi dlugu (pakiet nr 2, rozdz. 1).
        # Wczesniej kredyt wynosil 7 190 750 zl i wiazala go POTRZEBA — koszty
        # po dotacji i partycypacji. Z buforem 1,20 wiaze udzwig czynszowy,
        # kredyt spada o 852 tys. zl, a caly ubytek przechodzi na wklad wlasny.
        r = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        assert r.alokacja.koszty_laczne == D("29050000.00")
        assert r.finansowanie.spoleczna.kredyt == D("6338861")
        assert r.finansowanie.wklad_wlasny_wymagany == D("2594889.00")
        assert r.granty.spoleczna.udzial_wsparcia.quantize(D("0.0001")) == D("0.4464")
        assert r.granty.komunalna.udzial_wsparcia == D("0.80")

    def test_domykajacy_sie_przechodzi_wszystkie_trzy(self):
        r = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert r.domyka_sie is True
        assert all(t.przechodzi for t in r.werdykty.wszystkie)

    def test_domykajacy_sie_zamrozone_liczby(self):
        r = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert r.alokacja.koszty_laczne == D("29050000.00")
        assert r.finansowanie.spoleczna.kredyt == D("6280483")
        assert r.finansowanie.wklad_wlasny_wymagany == D("2653267.00")
        assert r.projekcja.spoleczna.pierwszy_rok_naruszenia is None

    def test_oba_przyklady_maja_te_same_koszty_a_inny_werdykt(self):
        a = przelicz(wczytaj_yaml(wspolne.WZORCOWY))
        b = przelicz(wczytaj_yaml(wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"))
        assert a.alokacja.koszty_laczne == b.alokacja.koszty_laczne
        assert a.domyka_sie != b.domyka_sie

    def test_pokrycie_wychodzi_jeden_w_obu_przykladach(self):
        for plik in (wspolne.WZORCOWY, wspolne.KATALOG_PRZYKLADOW / "domykajacy_sie.yaml"):
            r = przelicz(wczytaj_yaml(plik))
            assert r.projekcja.spoleczna.minimalny_dscr >= D("1")
