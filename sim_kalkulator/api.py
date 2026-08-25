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
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import yaml

from . import arkusz as _arkusz
from . import wrazliwosc as _wrazliwosc
from .dane import BladObliczenia, BladWalidacji, zbuduj
from .silnik import Wynik, przelicz

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

    return {
        "ok": True,
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
        "ostrzezenia": [
            {"kod": o.kod, "tresc": o.tresc, "podstawa": o.podstawa} for o in r.ostrzezenia
        ],
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
            return 200, wynik_json(przelicz(zbuduj(dane)))
        if akcja == "sweep":
            return 200, sweep_json(zbuduj(dane))
        if akcja == "arkusz":
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
