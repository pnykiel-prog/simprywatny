"""Warstwa API — wspolna dla serwera lokalnego i funkcji serverless.

Ten modul nie wie nic o HTTP ani o srodowisku uruchomieniowym. Przyjmuje
parametry, wola silnik i zwraca dane do serializacji. Dzieki temu serwer
lokalny (`serwer.py`) i funkcje na Vercelu (`api/*.py`) korzystaja z tej samej
sciezki obliczeniowej — nie ma drugiego silnika, ktory moglby sie rozjechac.

Warstwa jest bezstanowa. Kazde zadanie dostaje komplet parametrow bazowych
i zestaw zmian; nic nie jest pamietane miedzy wywolaniami.
"""

from __future__ import annotations

import base64
import copy
import datetime as _dt
import io
import re
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import yaml

from . import arkusz as _arkusz
from . import prawo
from . import wrazliwosc as _wrazliwosc
from .dane import BladObliczenia, BladWalidacji, TrybKredytu, zbuduj
from .silnik import Wynik, przelicz
from .waluta import bezpieczny_iloraz, zl

SCIEZKA_PARAMETRU = re.compile(r"[a-z_]+(\.[a-z_0-9]+)*")


def serializowalne(wartosc: Any) -> Any:
    """Domyka typy, ktorych JSON nie zna — daty z YAML i Decimale z silnika."""
    if isinstance(wartosc, (_dt.date, _dt.datetime)):
        return wartosc.isoformat()
    if isinstance(wartosc, Decimal):
        return float(wartosc)
    raise TypeError(f"Nie umiem zserializowac {type(wartosc).__name__}: {wartosc!r}")


def wczytaj_parametry(sciezka: Path | str) -> Dict[str, Any]:
    with Path(sciezka).open("r", encoding="utf-8") as plik:
        return yaml.safe_load(plik)


def zastosuj_zmiany(
    bazowe: Mapping[str, Any], zmiany: Mapping[str, Any]
) -> Dict[str, Any]:
    """Naklada zmiany podane sciezkami 'sekcja.pole' na kopie parametrow.

    Oryginal zostaje nietkniety — warstwa jest bezstanowa.
    """
    dane = copy.deepcopy(dict(bazowe))
    for sciezka, wartosc in (zmiany or {}).items():
        if not SCIEZKA_PARAMETRU.fullmatch(str(sciezka)):
            raise BladWalidacji(f"Niepoprawna sciezka parametru: {sciezka!r}")
        czesci = str(sciezka).split(".")
        wezel = dane
        for czesc in czesci[:-1]:
            if czesc not in wezel or not isinstance(wezel[czesc], dict):
                raise BladWalidacji(f"Nieznana sekcja parametru: {sciezka!r}")
            wezel = wezel[czesc]
        if czesci[-1] not in wezel:
            raise BladWalidacji(f"Nieznany parametr: {sciezka!r}")
        wezel[czesci[-1]] = wartosc
    return dane


def _liczba(wartosc: Decimal | float | int | None) -> Optional[float]:
    if wartosc is None:
        return None
    return float(wartosc)


def _werdykt_json(t) -> Dict[str, Any]:
    return {
        "numer": t.numer,
        "nazwa": t.nazwa,
        "przechodzi": t.przechodzi,
        "status": t.status,
        "wiazace_ograniczenie": t.wiazace_ograniczenie,
        "luka_opis": t.luka_opis,
        "luka_kwota": _liczba(t.luka_kwota),
        "luka_jednostka": t.luka_jednostka,
        "szczegoly": dict(t.szczegoly),
    }


def wynik_json(r: Wynik) -> Dict[str, Any]:
    """Serializacja wyniku. UI tylko formatuje — nie liczy niczego."""
    pule = []
    for proj, limity, fin in (
        (r.projekcja.spoleczna, r.limity_spoleczna, r.finansowanie.spoleczna),
        (r.projekcja.komunalna, r.limity_komunalna, r.finansowanie.komunalna),
    ):
        if not proj.aktywna:
            continue
        pule.append({
            "nazwa": proj.nazwa,
            "sciezka": proj.sciezka,
            "pum": _liczba(proj.pum),
            "okres_powierzenia_lat": proj.okres_powierzenia_lat,
            "grant": _liczba(fin.grant),
            "kredyt": _liczba(fin.kredyt),
            "partycypacja": _liczba(fin.partycypacja),
            "wklad_wlasny": _liczba(fin.wklad_wlasny),
            "limit_czynszu": _liczba(limity.limit_wiazacy_m2_mies),
            "limit_zrodlo": limity.limit_wiazacy_zrodlo,
            "stawka_art_7c": _liczba(limity.stawka_art_7c),
            "podstawa_m2": _liczba(limity.podstawa_wiazaca_m2),
            "podstawa_zrodlo": limity.podstawa_wiazaca_zrodlo,
            "czynsz": _liczba(limity.czynsz_zakladany_m2_mies),
            "zapas_do_limitu": _liczba(limity.zapas_do_limitu_m2_mies),
            "oplaty_poza_czynszem": _liczba(limity.limit_oplat_poza_czynszem_m2_mies),
            "udzial_wsparcia": _liczba(limity.udzial_wsparcia),
            "min_dscr": _liczba(proj.minimalny_dscr),
            "pierwszy_rok_naruszenia": proj.pierwszy_rok_naruszenia,
            "lata": [
                {
                    "rok": rok.rok,
                    "czynsz": _liczba(rok.czynsz_m2_mies),
                    "przychod_netto": _liczba(rok.przychod_czynszowy_netto),
                    "wymagane_pokrycie": _liczba(rok.wymagane_pokrycie),
                    "obsluga_dlugu": _liczba(rok.obsluga_dlugu),
                    "rezerwa_partycypacji": _liczba(rok.rezerwa_zwrot_partycypacji),
                    "dscr": _liczba(rok.dscr),
                    "saldo": _liczba(rok.saldo),
                }
                for rok in proj.lata
            ],
        })

    rekompensata = [
        {
            "nazwa": p.nazwa,
            "sciezka": p.sciezka,
            "kn": _liczba(p.kn),
            "rz": _liczba(p.rz),
            "ruoig": _liczba(p.ruoig),
            "dopuszczalna": _liczba(p.dopuszczalna),
            "nadwyzka": _liczba(p.nadwyzka),
            "nadwyzka_wzgledna": _liczba(p.nadwyzka_wzgledna),
            "prog_tolerancji": _liczba(p.prog_tolerancji),
            "kwota_do_zwrotu": _liczba(p.kwota_do_zwrotu),
            "przechodzi": p.przechodzi,
            "grunt_ujecie": p.grunt_ujecie,
        }
        for p in r.rekompensata.badane
    ]

    zapas = _zapas_rekompensaty(r)
    return {
        "ok": True,
        "wykresy": {
            "kaskada": _kaskada(r),
            "czynsz_poziomy": _czynsz_poziomy(r),
            "rekompensata_zapas": zapas,
            "przeplywy": _przeplywy(r),
        },
        "projekt": r.wejscie.projekt.nazwa,
        "gmina": r.wejscie.projekt.gmina,
        "udzial_komunalny": _liczba(r.wejscie.powierzchnie.udzial_puli_komunalnej),
        "domyka_sie": r.domyka_sie,
        "wiazace_ograniczenie": r.werdykty.wiazace_ograniczenie,
        "werdykty": [_werdykt_json(t) for t in r.werdykty.wszystkie],
        "koszty_laczne": _liczba(r.alokacja.koszty_laczne),
        "na_m2": {
            "koszt": _liczba(r.koszt_na_m2),
            "grant": _liczba(r.grant_na_m2),
            "kredyt": _liczba(r.kredyt_na_m2),
            "partycypacja": _liczba(r.partycypacja_na_m2),
            "wklad_wlasny": _liczba(r.wklad_wlasny_na_m2),
            "luka_kapitalowa": _liczba(r.luka_kapitalowa_na_m2),
        },
        "wklad_wymagany": _liczba(r.finansowanie.wklad_wlasny_wymagany),
        "wklad_dostepny": _liczba(r.wejscie.inwestor.dostepny_wklad_wlasny),
        "edb_kredytu": _liczba(r.edb_kredytu),
        "pule": pule,
        "rekompensata": rekompensata,
        # Rozdz. 5.3: najpierw te, ktore zmieniaja werdykt, potem kwote, potem reszta.
        "ostrzezenia": [
            {
                "kod": o.kod,
                "tresc": o.dla_ekranu,
                "tresc_techniczna": o.tresc,
                "podstawa": o.podstawa,
                "waga": int(o.waga),
            }
            for o in sorted(r.ostrzezenia, key=lambda o: -int(o.waga))
        ],
    }


def dociagnij_czynsze(dane: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
    """Sciaga stawki czynszu do limitu wiazacego dla tej konfiguracji.

    Limit zalezy od udzialu dotacji, ktory zalezy od udzialu puli komunalnej —
    przegladarka nie moze go znac, zanim przesunie pokretlo. Dlatego ograniczenie
    jest wbudowane w sterowanie po stronie serwera: stawka ponad limit zostaje
    sciagnieta i zakomunikowana, zamiast wracac jako blad (rozdz. 3.1 i 3.4).

    Twarda walidacja w silniku zostaje jako ostatnia linia obrony — model nie
    liczy scenariusza bezprawnego niezaleznie od tego, kto go podal.
    """
    from . import alokacja as _alokacja
    from . import czynsz as _czynsz
    from . import grant as _grant

    komunikaty = []
    wejscie = zbuduj(dane)
    a = _alokacja.build(wejscie)
    g = _grant.build(wejscie, a)
    kredyt_czynny = (
        wejscie.pula_spoleczna.kredyt.aktywny
        or wejscie.przelaczniki.tryb_kredytu is not TrybKredytu.RECZNY
    ) and a.spoleczna.aktywna

    for sciezka, pula_kosztow, grant_puli, zwrotne in (
        (("pula_spoleczna", "czynsz_zakladany_m2_mies"), a.spoleczna, g.spoleczna, kredyt_czynny),
        (("pula_komunalna", "czynsz_placony_przez_gmine_m2_mies"), a.komunalna, g.komunalna, False),
    ):
        if not pula_kosztow.aktywna:
            continue
        # Limit liczymy przy stawce zerowej, zeby samo jego ustalenie nie moglo
        # sie wywrocic o stawke, ktora wlasnie chcemy sprawdzic.
        limity = _czynsz.build(wejscie, pula_kosztow, grant_puli, Decimal(0), zwrotne)
        biezaca = zl(dane[sciezka[0]][sciezka[1]])
        if biezaca > limity.limit_wiazacy_m2_mies:
            nowa = limity.limit_wiazacy_m2_mies.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            dane[sciezka[0]][sciezka[1]] = float(nowa)
            komunikaty.append(
                f"Czynsz obniżony do {_dziesietnie(nowa)} zł — przy dotacji "
                f"{limity.udzial_wsparcia:.0%} to maksimum dopuszczone przepisami."
            )
    return dane, komunikaty


def _kaskada(r: Wynik) -> Dict[str, Any]:
    """Kaskada montazu — skad biora sie pieniadze (rozdz. 4.1).

    Od calkowitego kosztu odejmowane sa kolejno zrodla obce; to, co zostaje,
    jest odpowiedzia narzedzia: wymaganym wkladem inwestora.
    """
    f = r.finansowanie
    wymagany = f.wklad_wlasny_wymagany
    dostepny = r.wejscie.inwestor.dostepny_wklad_wlasny
    udzial = _liczba(bezpieczny_iloraz(wymagany, f.koszty_laczne))
    return {
        "kroki": [
            {"etykieta": "Koszt inwestycji", "kwota": _liczba(f.koszty_laczne),
             "rodzaj": "suma"},
            {"etykieta": "Dotacja", "kwota": _liczba(-f.grant_laczny), "rodzaj": "odjecie"},
            {"etykieta": "Kredyt", "kwota": _liczba(-f.kredyt_laczny), "rodzaj": "odjecie"},
            {"etykieta": "Partycypacja", "kwota": _liczba(-f.partycypacja_laczna),
             "rodzaj": "odjecie"},
            {"etykieta": "Twój wkład", "kwota": _liczba(wymagany), "rodzaj": "wynik"},
        ],
        "wymagany": _liczba(wymagany),
        "udzial_w_kosztach": udzial,
        "dostepny": _liczba(dostepny),
        "roznica": _liczba(dostepny - wymagany) if dostepny is not None else None,
        "zdanie": (
            f"Żeby zrealizować tę inwestycję, musisz wyłożyć własnych "
            f"{_kwota_slownie(wymagany)}, czyli {udzial:.0%} kosztów."
        ),
    }


def _czynsz_poziomy(r: Wynik) -> Dict[str, Any]:
    """Trzy poziomy czynszu na wspolnej skali (rozdz. 4.3)."""
    limit = r.limity_spoleczna.limit_wiazacy_m2_mies
    potrzebny = r.czynsz_domykajacy_m2_mies
    rynkowy = r.wejscie.pula_spoleczna.czynsz_rynkowy_m2_mies
    zdanie = ""
    if potrzebny is None:
        zdanie = (
            "Żadna stawka czynszu nie domknęłaby tej inwestycji sama — potrzebny kredyt "
            "przekracza ustawowe 80% kosztów. Różnicę musi pokryć kapitał albo dotacja."
        )
    elif potrzebny > limit:
        zdanie = (
            f"Żeby inwestycja spłacała się sama, czynsz musiałby wynosić "
            f"{_dziesietnie(potrzebny)} zł. Przepisy pozwalają najwyżej na "
            f"{_dziesietnie(limit)} zł. "
            "Tę różnicę musi pokryć kapitał albo wyższa dotacja."
        )
    else:
        zdanie = (
            f"Czynsz domykający inwestycję bez wkładu własnego to "
            f"{_dziesietnie(potrzebny)} zł i mieści się w limicie "
            f"{_dziesietnie(limit)} zł."
        )
    return {
        "potrzebny": _liczba(potrzebny),
        "limit": _liczba(limit),
        "rynkowy": _liczba(rynkowy),
        "zakladany": _liczba(r.limity_spoleczna.czynsz_zakladany_m2_mies),
        "zdanie": zdanie,
    }


def _zapas_rekompensaty(r: Wynik) -> Dict[str, Any]:
    """Jaka czesc dopuszczalnej pomocy publicznej zajmuje planowana (rozdz. 4.4)."""
    najciasniej, wykorzystanie = None, None
    for pula in r.rekompensata.badane:
        udzial = bezpieczny_iloraz(pula.ruoig, pula.dopuszczalna) if pula.dopuszczalna > 0 else None
        if udzial is None:
            continue
        if wykorzystanie is None or udzial > wykorzystanie:
            wykorzystanie, najciasniej = udzial, pula
    if najciasniej is None:
        return {"wykorzystanie": None, "zdanie": "Brak pul do zbadania."}

    if r.rekompensata.przechodzi:
        zapas = Decimal(1) - (wykorzystanie or Decimal(0))
        zdanie = (
            f"Pomoc publiczna mieści się w dopuszczalnym limicie z zapasem {zapas:.0%}."
            if zapas > 0 else
            "Pomoc publiczna mieści się w dopuszczalnym limicie."
        )
    else:
        zdanie = (
            f"Pomoc publiczna przekracza dopuszczalny limit o "
            f"{_kwota_slownie(r.rekompensata.kwota_do_zwrotu)}. Tę kwotę trzeba będzie zwrócić."
        )
    return {
        "wykorzystanie": _liczba(wykorzystanie),
        "pula": najciasniej.nazwa,
        "przechodzi": r.rekompensata.przechodzi,
        "do_zwrotu": _liczba(r.rekompensata.kwota_do_zwrotu),
        "zdanie": zdanie,
    }


def _przeplywy(r: Wynik) -> Dict[str, Any]:
    """Przeplywy rok po rok przez okres powierzenia (rozdz. 4.5)."""
    proj = r.projekcja.spoleczna if r.projekcja.spoleczna.aktywna else r.projekcja.komunalna
    lata = [
        {
            "rok": rok.rok,
            "przychody": _liczba(rok.przychod_czynszowy_netto),
            "koszty": _liczba(rok.koszty_operacyjne),
            "rata": _liczba(rok.obsluga_dlugu),
            "saldo": _liczba(rok.saldo),
        }
        for rok in proj.lata
    ]
    pierwszy_ujemny = next((p["rok"] for p in lata if p["saldo"] is not None and p["saldo"] < 0), None)
    return {"pula": proj.nazwa, "lata": lata, "pierwszy_rok_ujemny": pierwszy_ujemny}


def _dziesietnie(wartosc, miejsca: int = 2) -> str:
    """Liczba z polskim separatorem dziesietnym."""
    if wartosc is None:
        return "—"
    return f"{Decimal(wartosc):.{miejsca}f}".replace(".", ",")


def _kwota_slownie(kwota) -> str:
    """Kwota w zapisie, ktory czyta sie na glos: 8,4 mln zl."""
    if kwota is None:
        return "—"
    kwota = Decimal(kwota)
    if abs(kwota) >= 1_000_000:
        return f"{kwota / Decimal(1_000_000):.1f} mln zł".replace(".", ",")
    if abs(kwota) >= 1_000:
        return f"{kwota / Decimal(1000):.0f} tys. zł"
    return f"{kwota:.0f} zł"


def _suwak(
    klucz: str, etykieta: str, podpis: str, wartosc, minimum, maksimum, krok,
    jednostka: str = "", znaczniki=(), format_wartosci: str = "liczba",
    powod_granicy: str = "", rozwiniecie: str = "",
) -> Dict[str, Any]:
    """Opis jednego sterowania: etykieta, podpis, zakres i uzasadnienie granicy.

    Trzy poziomy opisu wg rozdz. 6 uzupelnienia — etykieta bez zargonu, podpis
    zawsze widoczny, rozwiniecie dla tych, ktorzy chca sprawdzic podstawe.
    """
    return {
        "klucz": klucz,
        "etykieta": etykieta,
        "podpis": podpis,
        "wartosc": _liczba(wartosc),
        "min": _liczba(minimum),
        "max": _liczba(maksimum),
        "krok": _liczba(krok),
        "jednostka": jednostka,
        "znaczniki": [
            {"wartosc": _liczba(w), "opis": o} for w, o in znaczniki
        ],
        "format": format_wartosci,
        "powod_granicy": powod_granicy,
        "rozwiniecie": rozwiniecie,
    }


def zakresy_json(r: Wynik) -> Dict[str, Any]:
    """Zakresy sterowan. Ograniczenie ustawowe jest granica suwaka, nie bledem.

    Limity czynszu zaleza od udzialu dotacji, ktory zalezy od udzialu puli
    komunalnej — dlatego wracaja z kazdym przeliczeniem i UI przestawia maksima
    na zywo (rozdz. 3.4).
    """
    w = r.wejscie
    ps, pk = r.limity_spoleczna, r.limity_komunalna
    komunalna_aktywna = r.projekcja.komunalna.aktywna
    spoleczna_aktywna = r.projekcja.spoleczna.aktywna

    suwaki = [
        _suwak(
            "powierzchnie.udzial_puli_komunalnej", "Udział mieszkań komunalnych",
            "Jaka część mieszkań trafi do gminy jako komunalne. "
            "To główne pokrętło rozmowy z gminą.",
            w.powierzchnie.udzial_puli_komunalnej, 0, 1, Decimal("0.05"),
            jednostka="%", format_wartosci="procent",
        ),
        _suwak(
            "koszty.koszt_budowy_na_m2", "Koszt budowy",
            "Koszt wybudowania metra powierzchni mieszkań, bez gruntu.",
            w.koszty.koszt_budowy_na_m2, 4000, 12000, 100, jednostka="zl/m2",
        ),
        _suwak(
            "pula_spoleczna.czynsz_zakladany_m2_mies", "Czynsz — mieszkania społeczne",
            "Ile płaci najemca za metr miesięcznie. Suwak zatrzymuje się na maksimum "
            "dopuszczonym przy tym poziomie dotacji.",
            ps.czynsz_zakladany_m2_mies, 0,
            ps.limit_wiazacy_m2_mies if spoleczna_aktywna else 0,
            Decimal("0.50"), jednostka="zl/m2/mies.",
            znaczniki=((ps.limit_wiazacy_m2_mies, "limit ustawowy"),),
            format_wartosci="stawka",
            powod_granicy=(
                f"Przy dotacji {ps.udzial_wsparcia:.0%} czynsz nie może przekroczyć "
                f"{_dziesietnie(ps.limit_wiazacy_m2_mies)} zł za metr miesięcznie."
            ),
            rozwiniecie=f"{ps.limit_wiazacy_zrodlo}; stawka {ps.stawka_art_7c:.1%} rocznie "
                        f"od podstawy {ps.podstawa_wiazaca_m2:,.2f} zl/m2 "
                        f"({ps.podstawa_wiazaca_zrodlo}).".replace(",", " "),
        ),
        _suwak(
            "pula_komunalna.czynsz_placony_przez_gmine_m2_mies", "Czynsz — mieszkania komunalne",
            "Ile płaci gmina za metr miesięcznie. Wyższa dotacja oznacza niższy "
            "dopuszczalny czynsz.",
            pk.czynsz_zakladany_m2_mies, 0,
            pk.limit_wiazacy_m2_mies if komunalna_aktywna else 0,
            Decimal("0.50"), jednostka="zl/m2/mies.",
            znaczniki=((pk.limit_wiazacy_m2_mies, "limit ustawowy"),),
            format_wartosci="stawka",
            powod_granicy=(
                f"Przy dotacji {pk.udzial_wsparcia:.0%} czynsz nie może przekroczyć "
                f"{_dziesietnie(pk.limit_wiazacy_m2_mies)} zł za metr miesięcznie."
            ),
            rozwiniecie=f"{pk.limit_wiazacy_zrodlo}; stawka {pk.stawka_art_7c:.1%} rocznie "
                        f"od podstawy {pk.podstawa_wiazaca_m2:,.2f} zl/m2.".replace(",", " "),
        ),
        _suwak(
            "pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu", "Partycypacja najemców",
            "Wpłata najemcy na poczet budowy, zwracana przy wyprowadzce. Obniża potrzebny "
            "kapitał, ale trzeba ją kiedyś oddać.",
            w.pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu,
            0, prawo.PARTYCYPACJA_MAKSIMUM, Decimal("0.01"), jednostka="%",
            znaczniki=(
                (prawo.PARTYCYPACJA_PROG_UMOWA_BEZTERMINOWA, "10%"),
                (prawo.PARTYCYPACJA_PROG_WYLACZENIA_ART_7B, "15%"),
            ),
            format_wartosci="procent",
            powod_granicy="Wyżej przepisy nie pozwalają przy kredycie preferencyjnym.",
        ),
        _suwak(
            "pula_spoleczna.kredyt.oprocentowanie", "Oprocentowanie kredytu",
            "Oprocentowanie kredytu preferencyjnego BGK.",
            w.pula_spoleczna.kredyt.oprocentowanie, 0, Decimal("0.08"), Decimal("0.001"),
            jednostka="%", format_wartosci="procent_dokladny",
        ),
        _suwak(
            "pula_spoleczna.kredyt.okres_lat", "Okres kredytowania",
            "Na ile lat rozłożona jest spłata, wliczając karencję.",
            w.pula_spoleczna.kredyt.okres_lat, 5, prawo.KREDYT_MAKSYMALNY_OKRES_LAT, 1,
            jednostka="lat",
            znaczniki=((Decimal(prawo.KREDYT_MAKSYMALNY_OKRES_LAT), "maksimum ustawowe"),),
            powod_granicy="Dłużej niż 30 lat przepisy nie pozwalają.",
        ),
        _suwak(
            "pula_spoleczna.kredyt.karencja_lat", "Karencja",
            "Ile lat bez spłaty kapitału, w trakcie budowy i rozruchu.",
            w.pula_spoleczna.kredyt.karencja_lat, 0, 5, 1, jednostka="lat",
        ),
        _suwak(
            "eksploatacja.pustostany_procent", "Pustostany",
            "Jaka część mieszkań stoi pusta w przeciętnym roku.",
            w.eksploatacja.pustostany_procent, 0, Decimal("0.20"), Decimal("0.01"),
            jednostka="%", format_wartosci="procent",
        ),
        _suwak(
            "eksploatacja.koszt_eksploatacji_m2_rok", "Koszt eksploatacji",
            "Roczny koszt utrzymania metra: administracja, przeglądy, części wspólne.",
            w.eksploatacja.koszt_eksploatacji_m2_rok, 5, 30, 1, jednostka="zl/m2/rok",
        ),
        _suwak(
            "eksploatacja.odpis_remontowy_m2_rok", "Odpis remontowy",
            "Ile rocznie odkładane jest na przyszłe remonty.",
            w.eksploatacja.odpis_remontowy_m2_rok, 5, 25, 1, jednostka="zl/m2/rok",
        ),
        _suwak(
            "eksploatacja.indeksacja_kosztow_rocznie", "Indeksacja kosztow",
            "O ile rocznie rosną koszty utrzymania.",
            w.eksploatacja.indeksacja_kosztow_rocznie, 0, Decimal("0.08"), Decimal("0.005"),
            jednostka="%/rok", format_wartosci="procent_dokladny",
        ),
        _suwak(
            "eksploatacja.indeksacja_czynszu_rocznie", "Indeksacja czynszu",
            "O ile rocznie rośnie czynsz. Nie może wyprowadzić stawki ponad limit ustawowy.",
            w.eksploatacja.indeksacja_czynszu_rocznie, 0, Decimal("0.08"), Decimal("0.005"),
            jednostka="%/rok", format_wartosci="procent_dokladny",
        ),
    ]
    if w.przelaczniki.tryb_kredytu is TrybKredytu.RECZNY:
        suwaki.insert(4, _suwak(
            "pula_spoleczna.kredyt.udzial_docelowy", "Kredyt — udział w kosztach",
            "Jaka część inwestycji finansuje kredyt. Tryb ręczny: kwota nie jest "
            "dopasowywana do czynszu.",
            w.pula_spoleczna.kredyt.udzial_docelowy, 0, prawo.KREDYT_MAKSYMALNY_UDZIAL,
            Decimal("0.01"), jednostka="%", format_wartosci="procent",
            powod_granicy="Wyżej niż 80% kosztów przepisy nie pozwalają.",
        ))

    return {
        "suwaki": suwaki,
        # Kredyt znika ze sterowania przy 100% puli komunalnej — przepisy go tam
        # wykluczaja, wiec nie ma czym sterowac (rozdz. 5.1).
        "kredyt_dostepny": spoleczna_aktywna,
        "pola_liczbowe": [
            {"klucz": "powierzchnie.pum_laczne", "etykieta": "Łączna powierzchnia mieszkań",
             "wartosc": _liczba(w.powierzchnie.pum_laczne), "jednostka": "m2",
             "podpis": "Suma powierzchni użytkowej wszystkich mieszkań."},
            {"klucz": "powierzchnie.liczba_lokali", "etykieta": "Liczba mieszkań",
             "wartosc": w.powierzchnie.liczba_lokali, "jednostka": "szt.",
             "podpis": "Ile mieszkań powstanie. Średnia wielkość musi mieścić się "
                       "między 25 a 80 m²."},
            {"klucz": "powierzchnie.liczba_kondygnacji", "etykieta": "Liczba kondygnacji",
             "wartosc": w.powierzchnie.liczba_kondygnacji, "jednostka": "szt.",
             "podpis": "Od trzech kondygnacji winda jest obowiązkowa."},
            {"klucz": "grunt.wartosc", "etykieta": "Wartość gruntu z operatu",
             "wartosc": _liczba(w.grunt.wartosc), "jednostka": "zl",
             "podpis": "Im droższy grunt, tym wyższa dopuszczalna dotacja."},
            {"klucz": "inwestor.dostepny_wklad_wlasny", "etykieta": "Twój kapitał (opcjonalnie)",
             "wartosc": _liczba(w.inwestor.dostepny_wklad_wlasny), "jednostka": "zl",
             "podpis": "Punkt odniesienia. Zostaw puste, a narzędzie po prostu poda "
                       "wymaganą kwotę."},
        ],
        "parametry_rynkowe": {
            "data": w.parametry_zewnetrzne.data_parametrow.isoformat(),
            "przeterminowane": any(
                o.kod == "PARAMETRY_PRZETERMINOWANE" for o in r.ostrzezenia
            ),
            "pozycje": [
                {"klucz": "parametry_zewnetrzne.stopa_referencyjna_ke",
                 "etykieta": "Stopa referencyjna KE",
                 "wartosc": _liczba(w.parametry_zewnetrzne.stopa_referencyjna_ke)},
                {"klucz": "parametry_zewnetrzne.stopa_dyskontowa",
                 "etykieta": "Stopa dyskontowa",
                 "wartosc": _liczba(w.parametry_zewnetrzne.stopa_dyskontowa)},
                {"klucz": "parametry_zewnetrzne.stopa_bazowa_ke",
                 "etykieta": "Stopa bazowa KE",
                 "wartosc": _liczba(w.parametry_zewnetrzne.stopa_bazowa_ke)},
                {"klucz": "parametry_zewnetrzne.stopa_irs_bgk",
                 "etykieta": "Stopa IRS BGK",
                 "wartosc": _liczba(w.parametry_zewnetrzne.stopa_irs_bgk)},
                {"klucz": "parametry_zewnetrzne.wartosc_odtworzeniowa_m2",
                 "etykieta": "Wartość odtworzeniowa 1 m²",
                 "wartosc": _liczba(w.parametry_zewnetrzne.wartosc_odtworzeniowa_m2)},
            ],
        },
    }


def sweep_json(w) -> Dict[str, Any]:
    analiza = _wrazliwosc.build(w)
    return {
        "ok": True,
        "podsumowanie": analiza.podsumowanie,
        "maksymalny_udzial": _liczba(analiza.sweep.maksymalny_udzial_komunalny),
        "punkt_graniczny": _liczba(analiza.sweep.punkt_graniczny),
        "test_blokujacy": analiza.sweep.test_blokujacy,
        "punkty": [
            {
                "udzial": _liczba(p.udzial),
                "policzalny": p.policzalny,
                "domyka_sie": p.domyka_sie,
                "werdykty": list(p.werdykty),
                "wiazace_ograniczenie": p.wiazace_ograniczenie,
                "wklad_wymagany": _liczba(p.wklad_wymagany),
                "powod": p.powod_niepoliczalnosci,
                "luki": [
                    {"opis": o, "kwota": _liczba(k), "jednostka": j} for o, k, j in p.luki
                ],
            }
            for p in analiza.sweep.punkty
        ],
        "ranking": [
            {
                "nazwa": r.nazwa,
                "wartosc_bazowa": _liczba(r.wartosc_bazowa),
                "granica_dol": _liczba(r.maks_udzial_dol),
                "granica_gora": _liczba(r.maks_udzial_gora),
                "sila_wplywu": _liczba(r.sila_wplywu),
                "kierunek": r.kierunek_korzystny,
                "dzwignia": r.opis_dzwigni,
                "przelamuje": r.przelamuje,
                "przelamanie_wartosc": _liczba(r.przelamanie_wartosc),
                "przelamanie_zmiana": _liczba(r.przelamanie_zmiana),
                "przelamanie_maks_udzial": _liczba(r.przelamanie_maks_udzial),
                "zmienia_werdykt": r.zmienia_werdykt,
            }
            for r in analiza.ranking
        ],
    }


def nazwa_pliku(nazwa_projektu: str, teraz: Optional[_dt.datetime] = None) -> str:
    teraz = teraz or _dt.datetime.now()
    rdzen = re.sub(r"[^a-zA-Z0-9_-]+", "_", nazwa_projektu)[:48] or "wariant"
    return f"{teraz.strftime('%Y%m%d-%H%M%S')}_{rdzen}"


def zbuduj_arkusz(dane: Mapping[str, Any]) -> Tuple[bytes, str, str]:
    """Zwraca (bajty XLSX, tekst YAML z uzytymi parametrami, rdzen nazwy pliku).

    Nic nie zapisuje na dysk — decyzje o zapisie podejmuje warstwa transportowa.
    Na Vercelu system plikow jest tylko do odczytu, wiec arkusz wraca strumieniem.
    """
    w = zbuduj(dane)
    wynik = przelicz(w)
    analiza = _wrazliwosc.build(w)

    rdzen = nazwa_pliku(w.projekt.nazwa)
    bufor = io.BytesIO()
    _arkusz.eksportuj_do_strumienia(wynik, bufor, analiza)

    naglowek = (
        f"# Zestaw parametrow uzyty do wygenerowania {rdzen}.xlsx\n"
        f"# Wygenerowano: {_dt.datetime.now().isoformat(timespec='seconds')}\n"
        "# Ten plik odtwarza dokladnie ten sam wynik — wczytaj go serwerem\n"
        "# albo przelicz przez sim_kalkulator.silnik.przelicz().\n\n"
    )
    tresc_yaml = naglowek + yaml.safe_dump(
        dict(dane), allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    return bufor.getvalue(), tresc_yaml, rdzen


# ---------------------------------------------------------------------------
# Routing — wspolny dla obu srodowisk
# ---------------------------------------------------------------------------

def obsluz(
    akcja: str, bazowe: Mapping[str, Any], zmiany: Mapping[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    """Wykonuje akcje API i zwraca (kod HTTP, dane do serializacji).

    Bledy dziedzinowe wracaja jako odpowiedz z powodem, nie jako wyjatek —
    UI ma pokazac, dlaczego wariant jest niepoliczalny.
    """
    try:
        dane = zastosuj_zmiany(bazowe, zmiany)
        if akcja == "parametry":
            return 200, {"ok": True, "parametry": dane}
        if akcja == "przelicz":
            dane, sciagniete = dociagnij_czynsze(dane)
            wynik = przelicz(zbuduj(dane))
            odpowiedz = wynik_json(wynik)
            # Limity czynszu zaleza od udzialu dotacji, wiec zakresy suwakow wracaja
            # z kazdym przeliczeniem — UI przestawia maksima na zywo (rozdz. 3.4).
            odpowiedz["zakresy"] = zakresy_json(wynik)
            odpowiedz["sciagniete"] = sciagniete
            return 200, odpowiedz
        if akcja == "sweep":
            dane, _ = dociagnij_czynsze(dane)
            return 200, sweep_json(zbuduj(dane))
        if akcja == "arkusz":
            dane, _ = dociagnij_czynsze(dane)
            xlsx, tresc_yaml, rdzen = zbuduj_arkusz(dane)
            return 200, {
                "ok": True,
                "nazwa": rdzen,
                "arkusz_base64": base64.b64encode(xlsx).decode("ascii"),
                "parametry_yaml": tresc_yaml,
                "komunikat": (
                    f"Arkusz {rdzen}.xlsx i zestaw parametrow {rdzen}.yaml sa gotowe "
                    "do pobrania. Przed wydaniem przelicz arkusz: "
                    "python3 scripts/recalc.py <plik.xlsx>"
                ),
            }
    except BladWalidacji as exc:
        return 400, {"ok": False, "typ": "walidacja", "powod": str(exc)}
    except BladObliczenia as exc:
        return 400, {"ok": False, "typ": "obliczenie", "powod": str(exc)}
    return 404, {"ok": False, "powod": f"Nie ma takiej akcji: {akcja!r}"}
