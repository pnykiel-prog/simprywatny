"""Etap 2 — walidacja danych wejsciowych."""

import datetime as _dt
from decimal import Decimal

import pytest

from sim_kalkulator.dane import (
    BladWalidacji,
    FormaGruntu,
    MetodaRozsadnegoZysku,
    PochodzenieGruntu,
    zbuduj,
)

from . import wspolne


def kody(w) -> set:
    return {o.kod for o in w.ostrzezenia}


class TestWczytanieWzorcowego:
    def test_wzorcowy_przechodzi_walidacje(self):
        w = wspolne.wejscie()
        assert w.powierzchnie.pum_laczne == Decimal("3000.0")
        assert w.grunt.forma is FormaGruntu.NABYCIE_OD_GMINY
        assert w.grunt.pochodzenie is PochodzenieGruntu.GMINA
        assert w.przelaczniki.hybryda_jako_jedno_przedsiewziecie is False

    def test_podzial_pum_wg_glownego_pokretla(self):
        w = wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=0.25)
        assert w.powierzchnie.pum_komunalne == Decimal("750.00")
        assert w.powierzchnie.pum_spoleczne == Decimal("2250.00")

    def test_wzorcowy_nie_ma_ostrzezen_technicznych(self):
        w = wspolne.wejscie()
        assert "PUM_POZA_PRZEDZIALEM" not in kody(w)
        assert "BRAK_POZYCJI_DZWIGI" not in kody(w)
        assert "PARAMETRY_PRZETERMINOWANE" not in kody(w)


class TestKredytWPuliKomunalnej:
    """art. 5a ust. 3 — rozlacznosc konstrukcyjna, nie limit. Blad, nie ostrzezenie."""

    def test_klucz_kredyt_w_puli_komunalnej_to_wyjatek(self):
        dane = wspolne.zmien()
        dane["pula_komunalna"]["kredyt"] = {"udzial_docelowy": 0.5}
        with pytest.raises(BladWalidacji, match="art. 5a ust. 3"):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)

    def test_klucz_partycypacja_w_puli_komunalnej_to_wyjatek(self):
        dane = wspolne.zmien()
        dane["pula_komunalna"]["partycypacja"] = {"stawka_procent_kosztu_lokalu": 0.1}
        with pytest.raises(BladWalidacji, match="niedopuszczalna"):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)

    def test_kredyt_reczny_przy_stu_procentach_puli_komunalnej_to_wyjatek(self):
        # W trybie recznym kwota kredytu pochodzi z udzialu docelowego, wiec
        # przy samych mieszkaniach komunalnych naprawde bylby to kredyt w puli,
        # ktorej przepisy go zabraniaja.
        dane = wspolne.zmien(powierzchnie__udzial_puli_komunalnej=1.0)
        dane["przelaczniki"]["tryb_kredytu"] = "reczny"
        with pytest.raises(BladWalidacji, match="art. 5a ust. 3"):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)

    def test_tryb_automatyczny_przy_stu_procentach_po_prostu_nie_ma_kredytu(self):
        # Sterowanie kredytem znika, zamiast zglaszac blad — kwote wyznacza
        # czynsz, a bez mieszkan spolecznych wychodzi zero.
        w = wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=1.0)
        assert w.powierzchnie.udzial_puli_komunalnej == Decimal("1.0")

    def test_pula_calkowicie_komunalna_bez_kredytu_jest_poprawna(self):
        w = wspolne.wejscie(
            powierzchnie__udzial_puli_komunalnej=1.0,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert w.pula_spoleczna.kredyt.aktywny is False


class TestBonusPrzyKredycie:
    """art. 13 ust. 4 — bonus wylaczony wprost przy finansowaniu zwrotnym."""

    def test_bonus_z_aktywnym_kredytem_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="[Aa]rt. 13 ust. 4"):
            wspolne.wejscie(pula_spoleczna__bonus_rewitalizacyjny=True)

    def test_bonus_bez_kredytu_jest_dopuszczalny(self):
        w = wspolne.wejscie(
            pula_spoleczna__bonus_rewitalizacyjny=True,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert w.pula_spoleczna.bonus_rewitalizacyjny is True

    def test_bonus_w_puli_komunalnej_jest_dopuszczalny(self):
        # W puli komunalnej kredytu nie ma z definicji, wiec bonus jest dostepny.
        w = wspolne.wejscie(pula_komunalna__bonus_rewitalizacyjny=True)
        assert w.pula_komunalna.bonus_rewitalizacyjny is True


class TestLimityKredytu:
    def test_udzial_ponad_80_procent_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="art. 15b ust. 2"):
            wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=0.81)

    def test_udzial_dokladnie_80_procent_przechodzi(self):
        w = wspolne.wejscie(pula_spoleczna__kredyt__udzial_docelowy=0.80)
        assert w.pula_spoleczna.kredyt.udzial_docelowy == Decimal("0.80")

    def test_okres_ponad_30_lat_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="art. 15b ust. 3"):
            wspolne.wejscie(pula_spoleczna__kredyt__okres_lat=31)

    def test_karencja_nie_krotsza_niz_okres_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="Karencja"):
            wspolne.wejscie(
                pula_spoleczna__kredyt__okres_lat=10,
                pula_spoleczna__kredyt__karencja_lat=10,
            )


class TestPUM:
    """rozp. MIiR z 4.03.2019 — walidacja wejscia, nie element obliczen."""

    def test_srednie_pum_ponizej_25_daje_ostrzezenie(self):
        w = wspolne.wejscie(powierzchnie__liczba_lokali=150)  # 20 m2 srednio
        assert "PUM_POZA_PRZEDZIALEM" in kody(w)

    def test_srednie_pum_powyzej_80_daje_ostrzezenie(self):
        w = wspolne.wejscie(powierzchnie__liczba_lokali=30)   # 100 m2 srednio
        assert "PUM_POZA_PRZEDZIALEM" in kody(w)

    def test_pum_w_przedziale_nie_daje_ostrzezenia(self):
        w = wspolne.wejscie(powierzchnie__liczba_lokali=60)   # 50 m2 srednio
        assert "PUM_POZA_PRZEDZIALEM" not in kody(w)

    def test_trzy_kondygnacje_bez_dzwigow_daja_ostrzezenie(self):
        w = wspolne.wejscie(koszty__dzwigi=0.0)
        assert "BRAK_POZYCJI_DZWIGI" in kody(w)

    def test_dwie_kondygnacje_bez_dzwigow_nie_daja_ostrzezenia(self):
        w = wspolne.wejscie(powierzchnie__liczba_kondygnacji=2, koszty__dzwigi=0.0)
        assert "BRAK_POZYCJI_DZWIGI" not in kody(w)


class TestWiekParametrow:
    def test_parametry_starsze_niz_6_miesiecy_daja_ostrzezenie(self):
        w = wspolne.wejscie(na_dzien=_dt.date(2027, 6, 1))
        assert "PARAMETRY_PRZETERMINOWANE" in kody(w)

    def test_parametry_dokladnie_6_miesiecy_jeszcze_przechodza(self):
        w = wspolne.wejscie(na_dzien=_dt.date(2027, 2, 1))
        assert "PARAMETRY_PRZETERMINOWANE" not in kody(w)

    def test_brak_zrodla_parametru_daje_ostrzezenie(self):
        dane = wspolne.zmien()
        dane["parametry_zewnetrzne"]["zrodla"].pop("stopa_referencyjna_ke")
        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        assert "BRAK_ZRODLA_PARAMETRU" in kody(w)


class TestBrakParametrowZewnetrznych:
    """Zadnych milczacych wartosci domyslnych — brak stopy zatrzymuje obliczenie."""

    @pytest.mark.parametrize(
        "parametr",
        [
            "stopa_referencyjna_ke",
            "stopa_bazowa_ke",
            "stopa_dyskontowa",
            "stopa_irs_bgk",
            "wartosc_odtworzeniowa_m2",
            "waloryzacja_partycypacji_rocznie",
            "okres_amortyzacji_budynkow_lat",
            "data_parametrow",
        ],
    )
    def test_brak_parametru_zatrzymuje_obliczenie(self, parametr):
        dane = wspolne.zmien()
        dane["parametry_zewnetrzne"].pop(parametr)
        with pytest.raises(BladWalidacji, match=parametr):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)

    def test_stopa_podana_procentowo_zamiast_ulamkiem_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="ulamki dziesietne"):
            wspolne.wejscie(parametry_zewnetrzne__stopa_referencyjna_ke=5.42)


class TestPartycypacja:
    def test_ponad_30_procent_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="art. 29a ust. 2"):
            wspolne.wejscie(pula_spoleczna__partycypacja__stawka_procent_kosztu_lokalu=0.31)

    @pytest.mark.parametrize("stawka", [0.10, 0.12, 0.1499])
    def test_przedzial_10_15_daje_ostrzezenie_nie_werdykt(self, stawka):
        w = wspolne.wejscie(pula_spoleczna__partycypacja__stawka_procent_kosztu_lokalu=stawka)
        assert "ZBIEG_PROGOW_PARTYCYPACJI" in kody(w)

    @pytest.mark.parametrize("stawka", [0.05, 0.15, 0.20])
    def test_poza_przedzialem_bez_ostrzezenia(self, stawka):
        w = wspolne.wejscie(pula_spoleczna__partycypacja__stawka_procent_kosztu_lokalu=stawka)
        assert "ZBIEG_PROGOW_PARTYCYPACJI" not in kody(w)


class TestGrunt:
    """Walidacje twarde z rozdz. 5 uzupelnienia nr 2 — wszystkie blokuja obliczenie."""

    def test_forma_niezgodna_z_pochodzeniem_to_blad(self):
        with pytest.raises(BladWalidacji, match="niedostepna przy pochodzeniu"):
            wspolne.wejscie(grunt__pochodzenie="inwestor", grunt__forma="dzierzawa")

    def test_lokal_za_grunt_wymaga_pochodzenia_od_gminy(self):
        with pytest.raises(BladWalidacji, match="niedostepna przy pochodzeniu"):
            wspolne.wejscie(
                grunt__pochodzenie="rynek_prywatny", grunt__forma="lokal_za_grunt"
            )

    def test_aport_z_hipoteka_dyskwalifikuje_wariant(self):
        # § 12 ust. 6 rozp. 766 — warunek zerojedynkowy, nie ostrzezenie.
        with pytest.raises(BladWalidacji, match="hipoteka"):
            wspolne.wejscie(
                grunt__pochodzenie="inwestor",
                grunt__forma="aport_inwestora",
                grunt__obciazony_hipoteka=True,
            )

    def test_aport_z_hipoteka_odpada_takze_bez_kredytu(self):
        with pytest.raises(BladWalidacji, match="hipoteka"):
            wspolne.wejscie(
                grunt__pochodzenie="inwestor",
                grunt__forma="aport_inwestora",
                grunt__obciazony_hipoteka=True,
                pula_spoleczna__kredyt__udzial_docelowy=0.0,
            )

    def test_nabycie_z_hipoteka_przechodzi(self):
        # Zakaz dotyczy wkladu niepienieznego, nie nabycia za gotowke.
        w = wspolne.wejscie(
            grunt__pochodzenie="rynek_prywatny",
            grunt__forma="nabycie_prywatne",
            grunt__obciazony_hipoteka=True,
        )
        assert w.grunt.obciazony_hipoteka is True

    def test_nieznana_forma_gruntu_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="nieznana wartosc"):
            wspolne.wejscie(grunt__forma="uzyczenie")

    def test_nieznane_pochodzenie_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="nieznana wartosc"):
            wspolne.wejscie(grunt__pochodzenie="skarb_panstwa")

    def test_dzierzawa_bez_oplaty_rocznej_to_brak_danych(self):
        with pytest.raises(BladWalidacji, match="oplata_roczna"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="dzierzawa",
                grunt__oplata_roczna=wspolne.USUN,
            )

    def test_uzytkowanie_wieczyste_bez_oplaty_rocznej_to_brak_danych(self):
        with pytest.raises(BladWalidacji, match="oplata_roczna"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="uzytkowanie_wieczyste",
                grunt__oplata_roczna=wspolne.USUN,
            )

    def test_dzierzawa_z_oplata_przechodzi(self):
        w = wspolne.wejscie(
            grunt__pochodzenie="gmina",
            grunt__forma="dzierzawa",
            grunt__oplata_roczna=120000.0,
        )
        assert w.grunt.oplata_roczna == Decimal("120000.00")
        assert w.grunt.forma.wymaga_oplaty_rocznej is True

    def test_lokal_za_grunt_bez_liczby_lokali_to_brak_danych(self):
        with pytest.raises(BladWalidacji, match="liczba_lokali_dla_gminy"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="lokal_za_grunt",
                grunt__liczba_lokali_dla_gminy=wspolne.USUN,
            )

    def test_lokal_za_grunt_bez_pum_to_brak_danych(self):
        with pytest.raises(BladWalidacji, match="pum_lokali_dla_gminy"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="lokal_za_grunt",
                grunt__liczba_lokali_dla_gminy=6,
                grunt__pum_lokali_dla_gminy=wspolne.USUN,
            )

    def test_lokal_za_grunt_nie_moze_zjesc_calego_pum(self):
        with pytest.raises(BladWalidacji, match="calej powierzchni"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="lokal_za_grunt",
                grunt__liczba_lokali_dla_gminy=60,
                grunt__pum_lokali_dla_gminy=3000.0,
            )

    def test_lokale_dla_gminy_poza_trybem_lokalowym_sa_odlozone(self):
        # Liczba i metraz sa przedmiotem uchwaly rady gminy, wiec moga czekac
        # w wejsciu na przelaczenie formy — widok porownawczy ich potrzebuje.
        w = wspolne.wejscie(
            grunt__liczba_lokali_dla_gminy=4, grunt__pum_lokali_dla_gminy=200.0
        )
        assert "LOKALE_DLA_GMINY_BEZ_ZASTOSOWANIA" in kody(w)

    def test_odlozone_lokale_nie_pomniejszaja_powierzchni_przychodowej(self):
        from sim_kalkulator import alokacja

        w = wspolne.wejscie(
            grunt__liczba_lokali_dla_gminy=4, grunt__pum_lokali_dla_gminy=200.0
        )
        a = alokacja.build(w)
        assert a.pum_przychodowe_laczne == w.powierzchnie.pum_laczne

    def test_odczyt_alternatywny_93_bez_ceny_to_brak_danych(self):
        with pytest.raises(BladWalidacji, match="cena_nabycia"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="nabycie_od_gminy",
                przelaczniki__pasmo_liczone_od_wartosci_z_operatu=False,
            )

    def test_cena_wyzsza_niz_operat_to_blad(self):
        with pytest.raises(BladWalidacji, match="Bonifikata obniza cene"):
            wspolne.wejscie(
                grunt__pochodzenie="gmina",
                grunt__forma="nabycie_od_gminy",
                grunt__cena_nabycia=9000000.0,
                przelaczniki__pasmo_liczone_od_wartosci_z_operatu=False,
            )

    def test_oplata_roczna_bez_zastosowania_daje_ostrzezenie(self):
        w = wspolne.wejscie(grunt__oplata_roczna=50000.0)
        assert "OPLATA_ROCZNA_BEZ_ZASTOSOWANIA" in kody(w)


class TestMatrycaGruntu:
    """Kazda forma musi miec komplet skutkow i nalezec do swojego pochodzenia."""

    @pytest.mark.parametrize("forma", list(FormaGruntu))
    def test_kazda_forma_ma_wiersz_matrycy(self, forma):
        skutki = forma.skutki
        assert skutki.forma == forma.value
        assert skutki.etykieta and skutki.podpis and skutki.podstawa

    @pytest.mark.parametrize("forma", list(FormaGruntu))
    def test_forma_nalezy_do_swojego_pochodzenia(self, forma):
        assert forma.value in forma.pochodzenie.formy_wartosci()

    def test_tylko_dzierzawa_nie_daje_pasma(self):
        bez_pasma = {f.value for f in FormaGruntu if not f.daje_pasmo_45}
        assert bez_pasma == {"dzierzawa"}

    def test_aport_inwestora_jest_jedyna_forma_aportowa(self):
        # Aport gminy usuniety z zakresu — pakiet nr 2, rozdz. 11. Logika aportu
        # zostaje, bo aport inwestora nadal istnieje.
        aportowe = {f.value for f in FormaGruntu if f.wniesiony_aportem}
        assert aportowe == {"aport_inwestora"}


class TestPrzelaczniki:
    def test_hybryda_daje_ostrzezenie_o_zalozeniu(self):
        w = wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=0.4)
        assert "ZALOZENIE_HYBRYDA" in kody(w)

    def test_wariant_czysty_nie_daje_ostrzezenia_o_hybrydzie(self):
        w = wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=0.0)
        assert "ZALOZENIE_HYBRYDA" not in kody(w)

    def test_rozsadny_zysk_zawsze_oznaczony_jako_zalozenie(self):
        assert "ZALOZENIE_ROZSADNY_ZYSK" in kody(wspolne.wejscie())

    def test_metoda_kwota_wprost_bez_kwoty_to_wyjatek(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["metoda_rozsadnego_zysku"] = "kwota_wprost"
        with pytest.raises(BladWalidacji, match="rozsadny_zysk_kwota"):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)

    def test_metoda_kwota_wprost_z_kwota_przechodzi(self):
        dane = wspolne.zmien()
        dane["przelaczniki"]["metoda_rozsadnego_zysku"] = "kwota_wprost"
        dane["rekompensata"]["rozsadny_zysk_kwota"] = 250000.0
        w = zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
        assert w.przelaczniki.metoda_rozsadnego_zysku is MetodaRozsadnegoZysku.KWOTA_WPROST


class TestPozostaleWalidacje:
    def test_udzial_puli_poza_zakresem_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="0.0-1.0"):
            wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=1.2)

    def test_pustostany_podane_procentowo_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="ulamek"):
            wspolne.wejscie(eksploatacja__pustostany_procent=5.0)

    def test_brak_calej_sekcji_to_wyjatek(self):
        dane = wspolne.zmien()
        dane.pop("eksploatacja")
        with pytest.raises(BladWalidacji, match="eksploatacja"):
            zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA)
