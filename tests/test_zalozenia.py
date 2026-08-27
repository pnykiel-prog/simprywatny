"""Scenariusze rozstrzygajace dla kazdego zalozenia — pakiet nr 2, rozdz. 7.

Problem, ktory ten modul zamyka: przy okazji bazy dotacji wyszlo, ze testy
odbiorcze korzystaly ze scenariusza, w ktorym obie konkurencyjne interpretacje
daja identyczny wynik. Test przechodzil niezaleznie od tego, ktora przyjeto,
wiec nie chronil przed niczym.

Kazdy wpis ponizej podaje scenariusz, w ktorym oba odczyty daja MIERZALNIE
ROZNY wynik, i zapisuje obie wartosci. Dzieki temu zmiana rozstrzygniecia po
odpowiedzi Banku sprowadza sie do podmiany wartosci domyslnej i liczby w tabeli,
a nie do szukania, gdzie w kodzie siedzi zalozenie.

Test kompletnosci `test_kazdy_kod_ma_wpis_i_scenariusz` pilnuje, zeby nowe
zalozenie nie weszlo do kodu bez wpisu w katalogu i bez scenariusza. To jest
wlasciwa ochrona — reszta to tylko jej wypelnienie.
"""

from decimal import Decimal as D

import pytest

from sim_kalkulator import api, zalozenia
from sim_kalkulator.dane import zbuduj
from sim_kalkulator.silnik import przelicz

from . import wspolne


def wynik(scenariusz=None, **zmiany):
    dane = wspolne.zmien(**{**(scenariusz or {}), **zmiany})
    return przelicz(zbuduj(dane, na_dzien=wspolne.DATA_ODNIESIENIA))


def kody(r):
    return {o.kod for o in r.ostrzezenia}


# ---------------------------------------------------------------------------
# Scenariusze. Kazdy dobrany tak, zeby BADANE zalozenie faktycznie wiazalo.
# ---------------------------------------------------------------------------

# Nadwyzka rekompensaty miedzy progiem 10% a 20% — tylko tam widac, ze o wyniku
# decyduje regula, a nie liczby.
MIEDZY_PROGAMI = dict(
    parametry_zewnetrzne__wartosc_odtworzeniowa_m2=20000.0,
    pula_spoleczna__czynsz_zakladany_m2_mies=30.0,
    przelaczniki__koszty_inwestycyjne_w_kn="naklad_poczatkowy",
)

# Uzytkowanie wieczyste: kanal C w ogole sie uruchamia tylko przy tej formie.
UZYTKOWANIE_WIECZYSTE = dict(
    grunt__pochodzenie="gmina", grunt__forma="uzytkowanie_wieczyste",
)

# Lokal za grunt: bez oddanych lokali kwestia 9.1 i podzial PUM nie maja przedmiotu.
LOKAL_ZA_GRUNT = dict(grunt__pochodzenie="gmina", grunt__forma="lokal_za_grunt")

# Bonus rewitalizacyjny wymaga sciezki BEZKREDYTOWEJ (art. 13 ust. 4), a zeby
# wiazal prog gruntowy, a nie limit gorny, dzialka musi byc skromna.
BONUS_BEZ_KREDYTU = dict(
    pula_spoleczna__kredyt__udzial_docelowy=0.0,
    pula_spoleczna__bonus_rewitalizacyjny=True,
    grunt__pochodzenie="inwestor",
    grunt__forma="aport_inwestora",
    grunt__wartosc=400000.0,
)

# Nabycie z bonifikata — kwestia 9.3 dziala wylacznie, gdy cena odbiega od operatu.
BONIFIKATA = dict(
    grunt__pochodzenie="gmina", grunt__forma="nabycie_od_gminy",
    grunt__cena_nabycia=700000.0,
)


def _grant_spoleczny(r):
    return r.granty.spoleczna.kwota


def _kwota_kredytu(r):
    return r.finansowanie.spoleczna.kredyt


def _dopuszczalna_spoleczna(r):
    return r.rekompensata.spoleczna.dopuszczalna


def _nadwyzka_najgorsza(r):
    """Nadwyzka w najgorszym punkcie kontrolnym — pula komunalna.

    Mierzona na komunalnej z rozmyslem. W spolecznej najgorszy rok wypada
    ostatni, a ostatni jest punktem kontrolnym przy KAZDEJ dlugosci okresu, wiec
    ta pula nie odroznilaby odczytow — dokladnie pulapka, o ktorej mowi rozdz. 7.
    """
    pula = r.rekompensata.komunalna or r.rekompensata.badane[0]
    return pula.nadwyzka_wzgledna_najgorsza


def _prog_tolerancji(r):
    return r.rekompensata.spoleczna.prog_tolerancji


def _pum_przychodowe_spolecznej(r):
    return r.alokacja.spoleczna.pum_przychodowe


def _przychod_komunalnej(r):
    return r.projekcja.komunalna.lata[0].przychod_czynszowy_netto


def _liczba_testow_rekompensaty(r):
    return D(len(r.rekompensata.badane))


def _rz_spoleczna(r):
    return r.rekompensata.spoleczna.rz


def _dopuszczalna_komunalna(r):
    return r.rekompensata.komunalna.dopuszczalna


# (kod, scenariusz, sciezka przelacznika, wartosc alternatywna, miara)
ROZSTRZYGAJACE = (
    (
        "ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY", MIEDZY_PROGAMI,
        "przelaczniki__prog_tolerancji_przy_dwoch_instrumentach", "wyzszy",
        _prog_tolerancji,
    ),
    (
        "ZALOZENIE_BUFOR_OBSLUGI_DLUGU", {},
        "parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu", 1.0,
        _kwota_kredytu,
    ),
    (
        "ZALOZENIE_GRUNT_9_2", UZYTKOWANIE_WIECZYSTE,
        "przelaczniki__uzytkowanie_wieczyste_jest_przychodem_uoig", False,
        _dopuszczalna_spoleczna,
    ),
    (
        "ZALOZENIE_OKRES_ROZLICZENIOWY_NADWYZKI", {},
        "przelaczniki__okres_rozliczeniowy_nadwyzki_lat", 10,
        _nadwyzka_najgorsza,
    ),
    (
        "ZALOZENIE_HYBRYDA", {},
        "przelaczniki__hybryda_jako_jedno_przedsiewziecie", True,
        _liczba_testow_rekompensaty,
    ),
    (
        "ZALOZENIE_GRUNT_9_1", LOKAL_ZA_GRUNT,
        "przelaczniki__lokal_za_grunt_jest_przychodem_uoig", True,
        _dopuszczalna_spoleczna,
    ),
    (
        "ZALOZENIE_GRUNT_9_3", BONIFIKATA,
        "przelaczniki__pasmo_liczone_od_wartosci_z_operatu", False,
        _grant_spoleczny,
    ),
    (
        "ZALOZENIE_PASMO_OD_CENY",
        {**BONIFIKATA, "przelaczniki__pasmo_liczone_od_wartosci_z_operatu": False},
        "przelaczniki__pasmo_liczone_od_wartosci_z_operatu", True,
        _grant_spoleczny,
    ),
    (
        "ZALOZENIE_BONUS_A_PROG_GRUNTOWY", BONUS_BEZ_KREDYTU,
        "przelaczniki__bonus_podnosi_prog_gruntowy", True,
        _grant_spoleczny,
    ),
    (
        "ZALOZENIE_KOSZTY_INWESTYCYJNE_W_KN", {},
        "przelaczniki__koszty_inwestycyjne_w_kn", "naklad_poczatkowy",
        _dopuszczalna_spoleczna,
    ),
    (
        "ZALOZENIE_ROZSADNY_ZYSK",
        dict(rekompensata__rozsadny_zysk_kwota=1000000.0),
        "przelaczniki__metoda_rozsadnego_zysku", "kwota_wprost",
        _rz_spoleczna,
    ),
    (
        "ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM", LOKAL_ZA_GRUNT,
        "przelaczniki__lokale_dla_gminy_z_puli", "komunalna",
        _pum_przychodowe_spolecznej,
    ),
    (
        "ZALOZENIE_PUSTOSTANY_KOMUNALNE", {},
        "przelaczniki__pustostany_takze_w_puli_komunalnej", True,
        _przychod_komunalnej,
    ),
)

WEDLUG_KODU = {wpis[0]: wpis for wpis in ROZSTRZYGAJACE}


class TestKompletnosciKatalogu:
    """Ochrona wlasciwa: zalozenie bez wpisu i bez scenariusza nie przechodzi."""

    def test_kazdy_kod_ma_wpis_i_scenariusz(self):
        # Kody emitowane przez silnik czytane wprost ze zrodel — nie z listy
        # przepisanej recznie, bo taka lista starzeje sie cicho.
        import re
        from pathlib import Path

        korzen = Path(__file__).resolve().parent.parent / "sim_kalkulator"
        emitowane = set()
        for plik in korzen.glob("*.py"):
            tekst = plik.read_text(encoding="utf-8")
            emitowane |= set(re.findall(r'kod="(ZALOZENIE_[A-Z_0-9]+)"', tekst))
        # `grunt.py` sklada kod z numeru kwestii — dopisujemy je z katalogu prawa.
        from sim_kalkulator import prawo

        emitowane.discard("ZALOZENIE_GRUNT_")
        emitowane |= {
            "ZALOZENIE_GRUNT_" + numer.replace(".", "_")
            for numer, *_ in prawo.ZALOZENIA_GRUNTOWE_DO_POTWIERDZENIA
        }

        bez_wpisu = emitowane - set(zalozenia.WEDLUG_KODU)
        assert not bez_wpisu, f"Zalozenia bez wpisu w katalogu: {sorted(bez_wpisu)}"
        # Zalozenie bez przelacznika nie da sie rozstrzygnac przez podmiane flagi,
        # wiec ma wlasny test imienny zamiast wpisu w tabeli scenariuszy. Wyjatek
        # jest waski z rozmyslem: obejmuje wylacznie mechanizm OBLICZANY_OBOK.
        bez_flagi = {
            kod for kod, z in zalozenia.WEDLUG_KODU.items()
            if z.mechanizm == zalozenia.OBLICZANY_OBOK
        }
        bez_scenariusza = emitowane - set(WEDLUG_KODU) - bez_flagi
        assert not bez_scenariusza, (
            f"Zalozenia bez scenariusza rozstrzygajacego: {sorted(bez_scenariusza)}"
        )

    def test_katalog_nie_opisuje_zalozen_ktorych_nie_ma(self):
        # Odwrotna strona tej samej zasady — wpis po usunietym zalozeniu myli
        # tak samo jak zalozenie bez wpisu.
        bez_flagi = {
            kod for kod, z in zalozenia.WEDLUG_KODU.items()
            if z.mechanizm == zalozenia.OBLICZANY_OBOK
        }
        assert set(zalozenia.WEDLUG_KODU) - bez_flagi == set(WEDLUG_KODU)

    def test_kazdy_wpis_ma_pytanie_i_podstawe(self):
        for z in zalozenia.KATALOG:
            assert "?" in z.pytanie_do_bgk, z.kod
            assert z.podstawa.strip()
            assert z.domyslnie.strip() and z.alternatywa.strip()

    def test_wpis_bez_przelacznika_ma_to_odnotowane(self):
        for z in zalozenia.KATALOG:
            assert (z.sciezka is None) == (not z.ma_przelacznik), z.kod


@pytest.mark.parametrize("kod", [w[0] for w in ROZSTRZYGAJACE])
class TestScenariuszyRozstrzygajacych:
    def test_oba_odczyty_daja_mierzalnie_rozny_wynik(self, kod):
        _, scenariusz, sciezka, alternatywa, miara = WEDLUG_KODU[kod]
        domyslny = miara(wynik(scenariusz))
        przeciwny = miara(wynik(scenariusz, **{sciezka: alternatywa}))
        assert domyslny != przeciwny, (
            f"{kod}: oba odczyty daja {domyslny} — scenariusz nie rozstrzyga niczego"
        )

    def test_scenariusz_faktycznie_uruchamia_to_zalozenie(self, kod):
        # Bez tego mozna by zbudowac scenariusz, w ktorym liczby sie roznia
        # z zupelnie innego powodu, a badane zalozenie w ogole nie dziala.
        _, scenariusz, _, _, _ = WEDLUG_KODU[kod]
        assert kod in kody(wynik(scenariusz)), (
            f"{kod}: scenariusz nie wywoluje tego ostrzezenia"
        )


class TestZapisanychWartosci:
    """Obie wartosci zapisane, nie tylko fakt, ze sie roznia.

    Rozdz. 7 wymaga zapisu obu liczb. Kwoty ponizej zamrozono na scenariuszach
    wzorcowych — po odpowiedzi Banku podmienia sie wartosc domyslna przelacznika
    i te liczbe, i tyle.
    """

    def test_prog_tolerancji_10_albo_20_procent(self):
        assert _prog_tolerancji(wynik(MIEDZY_PROGAMI)) == D("0.10")
        assert _prog_tolerancji(
            wynik(MIEDZY_PROGAMI,
                  przelaczniki__prog_tolerancji_przy_dwoch_instrumentach="wyzszy")
        ) == D("0.20")

    def test_bufor_obslugi_dlugu_1_20_albo_1_00(self):
        assert _kwota_kredytu(wynik()) == D("6338861")
        assert _kwota_kredytu(
            wynik(parametry_zewnetrzne__minimalny_wskaznik_pokrycia_obslugi_dlugu=1.0)
        ) == D("7190750")

    def test_uzytkowanie_wieczyste_jako_przychod_albo_nie(self):
        jest = _dopuszczalna_spoleczna(wynik(UZYTKOWANIE_WIECZYSTE))
        nie_jest = _dopuszczalna_spoleczna(
            wynik(UZYTKOWANIE_WIECZYSTE,
                  przelaczniki__uzytkowanie_wieczyste_jest_przychodem_uoig=False)
        )
        # Grunt jako przychod uslugi OBNIZA koszty netto, a z nimi dopuszczalna
        # rekompensate. To jest cala asymetria z art. 5 ust. 9 pkt 4.
        assert jest < nie_jest
        # Roznica to wartosc dzialki wchodzaca do przychodow uslugi, przypadajaca
        # na pule spoleczna (70% PUM), zdyskontowana czynnikiem roku pierwszego.
        assert (nie_jest - jest).quantize(D("1")) == D("3920000")

    def test_okres_rozliczeniowy_roczny_albo_dziesiecioletni(self):
        roczny = _nadwyzka_najgorsza(wynik())
        dziesiecioletni = _nadwyzka_najgorsza(
            wynik(przelaczniki__okres_rozliczeniowy_nadwyzki_lat=10)
        )
        # Rzadsza siatka kontrolna nie moze dac wyniku ostrzejszego — punkty
        # kontrolne sa podzbiorem rocznych.
        assert dziesiecioletni <= roczny
        assert roczny - dziesiecioletni > D("0.001")

    def test_hybryda_jeden_test_albo_dwa(self):
        assert _liczba_testow_rekompensaty(wynik()) == D(2)
        assert _liczba_testow_rekompensaty(
            wynik(przelaczniki__hybryda_jako_jedno_przedsiewziecie=True)
        ) == D(1)

    def test_bonus_a_prog_gruntowy_dwie_kwoty_dotacji(self):
        nizszy = _grant_spoleczny(wynik(BONUS_BEZ_KREDYTU))
        wyzszy = _grant_spoleczny(
            wynik(BONUS_BEZ_KREDYTU, przelaczniki__bonus_podnosi_prog_gruntowy=True)
        )
        # Odczyt podnoszacy oba progi daje dotacje wyzsza — o 5 pp podstawy
        # kosztowej puli spolecznej, chyba ze wczesniej zwiaze limit gorny.
        assert wyzszy > nizszy

    def test_lokale_dla_gminy_z_ktorej_puli(self):
        proporcjonalnie = _pum_przychodowe_spolecznej(wynik(LOKAL_ZA_GRUNT))
        z_komunalnej = _pum_przychodowe_spolecznej(
            wynik(LOKAL_ZA_GRUNT, przelaczniki__lokale_dla_gminy_z_puli="komunalna")
        )
        ze_spolecznej = _pum_przychodowe_spolecznej(
            wynik(LOKAL_ZA_GRUNT, przelaczniki__lokale_dla_gminy_z_puli="spoleczna")
        )
        assert ze_spolecznej < proporcjonalnie < z_komunalnej
        # Suma powierzchni przychodowej jest ta sama we wszystkich trzech
        # odczytach — przesuwa sie wylacznie to, ktora pula traci.
        for odczyt in ("proporcjonalnie", "komunalna", "spoleczna"):
            r = wynik(LOKAL_ZA_GRUNT, przelaczniki__lokale_dla_gminy_z_puli=odczyt)
            assert r.alokacja.pum_przychodowe_laczne == D("2700.00")

    def test_baza_dotacji_bez_przelacznika_ale_z_obiema_liczbami(self):
        # Jedyne zalozenie bez przelacznika. Silnik podaje roznice obu odczytow
        # wprost w tresci ostrzezenia — dzieki temu scenariusz rozstrzyga,
        # mimo ze flagi do przelaczenia nie ma.
        r = wynik()
        o = next(x for x in r.ostrzezenia if x.kod == "ZALOZENIE_GRUNT_W_BAZIE_DOTACJI")
        assert "nizsza o" in o.tresc
        wpis = zalozenia.zalozenie("ZALOZENIE_GRUNT_W_BAZIE_DOTACJI")
        assert wpis.mechanizm == zalozenia.OBLICZANY_OBOK
        assert wpis.sciezka is None


class TestPismaDoBanku:
    """Rozdz. 9 — lista pytan generowana z katalogu, wiec nie rozjezdza sie z kodem."""

    def test_dokument_istnieje_i_wymienia_kazde_pytanie(self):
        from pathlib import Path

        pismo = (Path(__file__).resolve().parent.parent / "PYTANIA_DO_BGK.md").read_text(
            encoding="utf-8"
        )
        for z in zalozenia.do_pisma():
            assert z.kod in pismo, f"Brak {z.kod} w piśmie do Banku"

    def test_pismo_jest_aktualne_wobec_katalogu(self):
        # Dokument jest generowany, wiec rozjazd znaczy, ze ktos zmienil katalog
        # i nie przepuscil generatora. Bez tego testu pismo cicho sie starzeje.
        import importlib.util
        from pathlib import Path

        korzen = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "pytania", korzen / "scripts" / "pytania_do_bgk.py"
        )
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        na_dysku = (korzen / "PYTANIA_DO_BGK.md").read_text(encoding="utf-8")
        assert na_dysku == modul.zbuduj(), (
            "PYTANIA_DO_BGK.md rozjechalo sie z katalogiem — uruchom "
            "`python3 scripts/pytania_do_bgk.py`"
        )

    def test_kody_wtorne_wskazuja_istniejace_pytanie_glowne(self):
        for z in zalozenia.KATALOG:
            if z.idzie_do_pisma:
                continue
            glowne = zalozenia.zalozenie(z.duplikat_pytania)
            assert glowne.idzie_do_pisma, (
                f"{z.kod} wskazuje na {glowne.kod}, ktore samo jest wtorne"
            )

    def test_kolejnosc_pytan_idzie_za_priorytetem(self):
        priorytety = [z.priorytet for z in zalozenia.wedlug_priorytetu()]
        assert priorytety == sorted(priorytety)
        assert priorytety[0] == 1

    def test_pytania_najwyzszego_priorytetu_to_te_ktore_odwracaja_werdykt(self):
        pierwsze = {z.kod for z in zalozenia.KATALOG if z.priorytet == 1}
        assert "ZALOZENIE_PROG_TOLERANCJI_DWA_INSTRUMENTY" in pierwsze
        assert "ZALOZENIE_BUFOR_OBSLUGI_DLUGU" in pierwsze
        assert "ZALOZENIE_GRUNT_9_2" in pierwsze


class TestWidocznosciWWyniku:
    def test_api_podaje_katalog_zalozen(self):
        z = api.zakresy_json(przelicz(wspolne.wejscie()))
        katalog = z["zalozenia"]
        assert len(katalog) == len(zalozenia.KATALOG)
        aktywne = [w for w in katalog if w["aktywne"]]
        assert aktywne, "co najmniej jedno zalozenie dziala w scenariuszu wzorcowym"
        for wpis in katalog:
            assert wpis["pytanie_do_bgk"]
            assert wpis["kod"] in zalozenia.WEDLUG_KODU
