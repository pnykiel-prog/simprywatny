#!/usr/bin/env python3
"""Lokalny serwer HTTP dla kalkulatora montazu SIM.

UI wola API, API wola silnik. Po stronie przegladarki nie ma zadnej logiki
obliczeniowej — dwa silniki liczace to samo rozjada sie i nikt tego nie zauwazy.

Uzycie:
    python3 serwer.py [--wejscie przyklady/wzorcowy.yaml] [--port 8000]
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import re
import threading
import webbrowser
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from sim_kalkulator import arkusz as _arkusz
from sim_kalkulator import wrazliwosc as _wrazliwosc
from sim_kalkulator.dane import BladObliczenia, BladWalidacji, zbuduj
from sim_kalkulator.silnik import Wynik, przelicz

KORZEN = Path(__file__).resolve().parent
WEB = KORZEN / "web"
WYNIKI = KORZEN / "wyniki"


def _serializowalne(wartosc: Any) -> Any:
    """Domyka typy, ktorych JSON nie zna — daty z YAML i Decimale z silnika."""
    if isinstance(wartosc, (_dt.date, _dt.datetime)):
        return wartosc.isoformat()
    if isinstance(wartosc, Decimal):
        return float(wartosc)
    raise TypeError(f"Nie umiem zserializowac {type(wartosc).__name__}: {wartosc!r}")


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


def _wynik_json(r: Wynik) -> Dict[str, Any]:
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


def _sweep_json(w) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Stan serwera
# ---------------------------------------------------------------------------

class Stan:
    """Aktualny zestaw parametrow. Modyfikowany przez UI, czytany przez silnik."""

    def __init__(self, sciezka: Path) -> None:
        self.sciezka_wejscia = sciezka
        with sciezka.open("r", encoding="utf-8") as plik:
            self.surowe: Dict[str, Any] = yaml.safe_load(plik)
        self._blokada = threading.Lock()

    def kopia(self) -> Dict[str, Any]:
        with self._blokada:
            return copy.deepcopy(self.surowe)

    def podmien(self, zmiany: Mapping[str, Any]) -> Dict[str, Any]:
        """Nakłada zmiany podane sciezkami 'sekcja.pole' na kopie parametrow."""
        dane = self.kopia()
        for sciezka, wartosc in zmiany.items():
            if not re.fullmatch(r"[a-z_]+(\.[a-z_0-9]+)*", sciezka):
                raise BladWalidacji(f"Niepoprawna sciezka parametru: {sciezka!r}")
            czesci = sciezka.split(".")
            wezel = dane
            for czesc in czesci[:-1]:
                if czesc not in wezel or not isinstance(wezel[czesc], dict):
                    raise BladWalidacji(f"Nieznana sekcja parametru: {sciezka!r}")
                wezel = wezel[czesc]
            if czesci[-1] not in wezel:
                raise BladWalidacji(f"Nieznany parametr: {sciezka!r}")
            wezel[czesci[-1]] = wartosc
        return dane

    def zapisz(self, dane: Dict[str, Any]) -> None:
        with self._blokada:
            self.surowe = copy.deepcopy(dane)


def _zbuduj(dane: Mapping[str, Any]):
    return zbuduj(dane)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Uchwyt(BaseHTTPRequestHandler):
    stan: Stan = None            # ustawiane przy starcie
    server_version = "KalkulatorSIM/1.0"
    # HTTP/1.1 z jawnym Content-Length przy kazdej odpowiedzi — bez tego
    # przegladarka gubi polaczenia otwarte spekulacyjnie i pierwsze wywolanie
    # API potrafi wrocic puste.
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"  {self.address_string()} — {format % args}")

    # --- pomocnicze ---

    def _odpowiedz(self, kod: int, tresc: bytes, typ: str) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(tresc)

    def _json(self, dane: Mapping[str, Any], kod: int = 200) -> None:
        self._odpowiedz(
            kod,
            json.dumps(dane, ensure_ascii=False, default=_serializowalne).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _blad(self, wyjatek: Exception, typ: str) -> None:
        self._json({"ok": False, "typ": typ, "powod": str(wyjatek)}, kod=400)

    def _cialo(self) -> Dict[str, Any]:
        dlugosc = int(self.headers.get("Content-Length") or 0)
        if dlugosc <= 0:
            return {}
        if dlugosc > 2_000_000:
            raise BladWalidacji("Zadanie zbyt duze.")
        return json.loads(self.rfile.read(dlugosc).decode("utf-8"))

    # --- routing ---

    def _bezpiecznie(self, akcja) -> None:
        """Kazde zadanie musi dostac odpowiedz — nawet gdy silnik rzuci czyms nieoczekiwanym.

        Zerwane polaczenie bez odpowiedzi zostawia UI z pustym ekranem i bez powodu,
        a to jest dokladnie ten stan, ktorego rozdz. 9.2 zabrania.
        """
        try:
            akcja()
        except (BladWalidacji, BladObliczenia):
            raise
        except Exception as exc:  # noqa: BLE001 — celowo szeroko
            import traceback

            traceback.print_exc()
            self._json(
                {
                    "ok": False,
                    "typ": "serwer",
                    "powod": f"{type(exc).__name__}: {exc}",
                },
                kod=500,
            )

    def do_GET(self) -> None:
        self._bezpiecznie(lambda: self._routing_get())

    def do_POST(self) -> None:
        self._bezpiecznie(lambda: self._routing_post())

    def _routing_get(self) -> None:
        if self.path in ("/", "/index.html"):
            self._plik(WEB / "index.html", "text/html; charset=utf-8")
        elif self.path == "/favicon.ico":
            self._odpowiedz(200, b"", "image/x-icon")
        elif self.path == "/api/parametry":
            self._json({"ok": True, "parametry": self.stan.kopia()})
        elif self.path == "/api/przelicz":
            self._przelicz({})
        elif self.path == "/api/sweep":
            self._sweep({})
        else:
            self._json({"ok": False, "powod": "Nie ma takiego zasobu."}, kod=404)

    def _routing_post(self) -> None:
        try:
            cialo = self._cialo()
        except (ValueError, BladWalidacji) as exc:
            return self._blad(exc, "zadanie")
        zmiany = cialo.get("zmiany") or {}
        if self.path == "/api/przelicz":
            self._przelicz(zmiany)
        elif self.path == "/api/sweep":
            self._sweep(zmiany)
        elif self.path == "/api/arkusz":
            self._arkusz(zmiany)
        else:
            self._json({"ok": False, "powod": "Nie ma takiego zasobu."}, kod=404)

    # --- akcje ---

    def _plik(self, sciezka: Path, typ: str) -> None:
        if not sciezka.exists():
            return self._json({"ok": False, "powod": f"Brak pliku {sciezka.name}."}, kod=404)
        self._odpowiedz(200, sciezka.read_bytes(), typ)

    def _przelicz(self, zmiany: Mapping[str, Any]) -> None:
        try:
            dane = self.stan.podmien(zmiany)
            wynik = przelicz(_zbuduj(dane))
        except BladWalidacji as exc:
            return self._blad(exc, "walidacja")
        except BladObliczenia as exc:
            return self._blad(exc, "obliczenie")
        self._json(_wynik_json(wynik))

    def _sweep(self, zmiany: Mapping[str, Any]) -> None:
        try:
            dane = self.stan.podmien(zmiany)
            self._json(_sweep_json(_zbuduj(dane)))
        except BladWalidacji as exc:
            return self._blad(exc, "walidacja")
        except BladObliczenia as exc:
            return self._blad(exc, "obliczenie")

    def _arkusz(self, zmiany: Mapping[str, Any]) -> None:
        """Generuje arkusz i zapisuje uzyty zestaw parametrow jako YAML z data.

        Zeby dalo sie odtworzyc, na czym liczono.
        """
        try:
            dane = self.stan.podmien(zmiany)
            w = _zbuduj(dane)
            wynik = przelicz(w)
            analiza = _wrazliwosc.build(w)
        except BladWalidacji as exc:
            return self._blad(exc, "walidacja")
        except BladObliczenia as exc:
            return self._blad(exc, "obliczenie")

        WYNIKI.mkdir(parents=True, exist_ok=True)
        znacznik = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        rdzen = re.sub(r"[^a-zA-Z0-9_-]+", "_", w.projekt.nazwa)[:48] or "wariant"
        sciezka_xlsx = WYNIKI / f"{znacznik}_{rdzen}.xlsx"
        sciezka_yaml = WYNIKI / f"{znacznik}_{rdzen}.yaml"

        _arkusz.eksportuj(wynik, sciezka_xlsx, analiza)
        with sciezka_yaml.open("w", encoding="utf-8") as plik:
            plik.write(
                f"# Zestaw parametrow uzyty do wygenerowania {sciezka_xlsx.name}\n"
                f"# Wygenerowano: {_dt.datetime.now().isoformat(timespec='seconds')}\n"
                "# Ten plik odtwarza dokladnie ten sam wynik — wczytaj go serwerem\n"
                "# albo przelicz przez sim_kalkulator.silnik.przelicz().\n\n"
            )
            yaml.safe_dump(dane, plik, allow_unicode=True, sort_keys=False, default_flow_style=False)

        self.stan.zapisz(dane)
        self._json({
            "ok": True,
            "arkusz": str(sciezka_xlsx),
            "parametry": str(sciezka_yaml),
            "komunikat": (
                f"Zapisano arkusz {sciezka_xlsx.name} oraz zestaw parametrow "
                f"{sciezka_yaml.name}. Przed wydaniem przelicz arkusz: "
                f"python3 scripts/recalc.py {sciezka_xlsx}"
            ),
        })


def main() -> int:
    parser = argparse.ArgumentParser(description="Lokalny serwer kalkulatora montazu SIM.")
    parser.add_argument("--wejscie", type=Path, default=KORZEN / "przyklady" / "wzorcowy.yaml")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--bez-przegladarki", action="store_true")
    args = parser.parse_args()

    if not args.wejscie.exists():
        print(f"Nie ma pliku wejsciowego {args.wejscie}")
        return 2

    try:
        stan = Stan(args.wejscie)
        wejscie = _zbuduj(stan.kopia())
    except BladWalidacji as exc:
        print(f"Dane wejsciowe nie przechodza walidacji:\n  {exc}")
        return 1

    print(f"Wejscie: {args.wejscie}")
    print(f"Projekt: {wejscie.projekt.nazwa}")
    if wejscie.ostrzezenia:
        print("Ostrzezenia:")
        for o in wejscie.ostrzezenia:
            print(f"  [{o.kod}] {o.tresc[:120]}")

    Uchwyt.stan = stan
    adres = f"http://{args.host}:{args.port}/"
    serwer = ThreadingHTTPServer((args.host, args.port), Uchwyt)
    print(f"\nSerwer: {adres}  (Ctrl+C konczy)")
    if not args.bez_przegladarki:
        threading.Timer(0.7, lambda: webbrowser.open(adres)).start()
    try:
        serwer.serve_forever()
    except KeyboardInterrupt:
        print("\nKoniec.")
    finally:
        serwer.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
