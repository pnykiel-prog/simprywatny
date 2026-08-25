"""Etap 2 — walidacja danych wejsciowych."""

import datetime as _dt
from decimal import Decimal

import pytest

from sim_kalkulator.dane import (
    BladWalidacji,
    FormaGruntu,
    MetodaRozsadnegoZysku,
    zbuduj,
)

from . import wspolne


def kody(w) -> set:
    return {o.kod for o in w.ostrzezenia}


class TestWczytanieWzorcowego:
    def test_wzorcowy_przechodzi_walidacje(self):
        w = wspolne.wejscie()
        assert w.powierzchnie.pum_laczne == Decimal("3000.0")
        assert w.grunt.forma is FormaGruntu.WLASNOSC_INWESTORA
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

    def test_kredyt_przy_stu_procentach_puli_komunalnej_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="art. 5a ust. 3"):
            wspolne.wejscie(powierzchnie__udzial_puli_komunalnej=1.0)

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
    def test_aport_z_hipoteka_przy_kredycie_dyskwalifikuje(self):
        with pytest.raises(BladWalidacji, match="hipoteka"):
            wspolne.wejscie(grunt__forma="aport_jst", grunt__obciazony_hipoteka=True)

    def test_aport_z_hipoteka_bez_kredytu_przechodzi(self):
        w = wspolne.wejscie(
            grunt__forma="aport_jst",
            grunt__obciazony_hipoteka=True,
            pula_spoleczna__kredyt__udzial_docelowy=0.0,
        )
        assert w.grunt.obciazony_hipoteka is True

    def test_nieznana_forma_gruntu_to_wyjatek(self):
        with pytest.raises(BladWalidacji, match="nieznana wartosc"):
            wspolne.wejscie(grunt__forma="dzierzawa")

    def test_grunt_jst_daje_ostrzezenie_o_zalozeniu(self):
        w = wspolne.wejscie(grunt__forma="aport_jst")
        assert "ZALOZENIE_GRUNT_JST" in kody(w)


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
