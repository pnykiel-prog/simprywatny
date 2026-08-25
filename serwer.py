#!/usr/bin/env python3
"""Lokalny serwer HTTP dla kalkulatora montazu SIM.

UI wola API, API wola silnik. Po stronie przegladarki nie ma zadnej logiki
obliczeniowej — dwa silniki liczace to samo rozjada sie i nikt tego nie zauwazy.

Ten serwer i funkcje serverless w katalogu `api/` korzystaja z tej samej
warstwy `sim_kalkulator.api`, wiec lokalnie i na wdrozeniu liczy sie to samo.

Uzycie:
    python3 serwer.py [--wejscie przyklady/wzorcowy.yaml] [--port 8000]
"""

from __future__ import annotations

import argparse
import base64
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Mapping

from sim_kalkulator import api as _api
from sim_kalkulator.dane import BladWalidacji, zbuduj

KORZEN = Path(__file__).resolve().parent
WEB = KORZEN / "web"
WYNIKI = KORZEN / "wyniki"


class Stan:
    """Parametry bazowe wczytane z pliku. Czytane, nigdy nadpisywane w locie.

    Warstwa API jest bezstanowa — kazde zadanie dostaje kopie parametrow
    i wlasny zestaw zmian. Dzieki temu lokalny serwer zachowuje sie tak samo
    jak funkcja serverless, ktora zadnego stanu miedzy wywolaniami nie ma.
    """

    def __init__(self, sciezka: Path) -> None:
        self.sciezka_wejscia = Path(sciezka)
        self._bazowe = _api.wczytaj_parametry(self.sciezka_wejscia)

    def kopia(self) -> Dict[str, Any]:
        return _api.zastosuj_zmiany(self._bazowe, {})

    def podmien(self, zmiany: Mapping[str, Any]) -> Dict[str, Any]:
        return _api.zastosuj_zmiany(self._bazowe, zmiany)


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
            json.dumps(dane, ensure_ascii=False, default=_api.serializowalne).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _cialo(self) -> Dict[str, Any]:
        dlugosc = int(self.headers.get("Content-Length") or 0)
        if dlugosc <= 0:
            return {}
        if dlugosc > 2_000_000:
            raise BladWalidacji("Zadanie zbyt duze.")
        return json.loads(self.rfile.read(dlugosc).decode("utf-8"))

    def _bezpiecznie(self, akcja) -> None:
        """Kazde zadanie musi dostac odpowiedz — nawet gdy silnik rzuci czyms nieoczekiwanym.

        Zerwane polaczenie bez odpowiedzi zostawia UI z pustym ekranem i bez powodu,
        a to jest dokladnie ten stan, ktorego rozdz. 9.2 zabrania.
        """
        try:
            akcja()
        except Exception as exc:  # noqa: BLE001 — celowo szeroko
            import traceback

            traceback.print_exc()
            self._json(
                {"ok": False, "typ": "serwer", "powod": f"{type(exc).__name__}: {exc}"},
                kod=500,
            )

    # --- routing ---

    def do_GET(self) -> None:
        self._bezpiecznie(self._routing_get)

    def do_POST(self) -> None:
        self._bezpiecznie(self._routing_post)

    def _routing_get(self) -> None:
        if self.path in ("/", "/index.html"):
            self._plik(WEB / "index.html", "text/html; charset=utf-8")
        elif self.path == "/favicon.ico":
            self._odpowiedz(200, b"", "image/x-icon")
        elif self.path.startswith("/api/"):
            self._api_akcja(self.path[len("/api/"):], {})
        else:
            self._json({"ok": False, "powod": "Nie ma takiego zasobu."}, kod=404)

    def _routing_post(self) -> None:
        try:
            cialo = self._cialo()
        except (ValueError, BladWalidacji) as exc:
            return self._json({"ok": False, "typ": "zadanie", "powod": str(exc)}, kod=400)
        if not self.path.startswith("/api/"):
            return self._json({"ok": False, "powod": "Nie ma takiego zasobu."}, kod=404)
        self._api_akcja(self.path[len("/api/"):], cialo.get("zmiany") or {})

    def _plik(self, sciezka: Path, typ: str) -> None:
        if not sciezka.exists():
            return self._json({"ok": False, "powod": f"Brak pliku {sciezka.name}."}, kod=404)
        self._odpowiedz(200, sciezka.read_bytes(), typ)

    def _api_akcja(self, akcja: str, zmiany: Mapping[str, Any]) -> None:
        kod, dane = _api.obsluz(akcja, self.stan.kopia(), zmiany)
        if kod == 200 and akcja == "arkusz":
            dane = self._zapisz_lokalnie(dane)
        self._json(dane, kod=kod)

    def _zapisz_lokalnie(self, dane: Dict[str, Any]) -> Dict[str, Any]:
        """Dodatkowo odklada arkusz i uzyte parametry na dysk.

        Wylacznie lokalnie — na wdrozeniu serverless system plikow jest tylko do
        odczytu, wiec tam pliki wracaja do przegladarki i tam sa zapisywane.
        Sens jest ten sam: ma dac sie odtworzyc, na czym liczono.
        """
        try:
            WYNIKI.mkdir(parents=True, exist_ok=True)
            xlsx = WYNIKI / f"{dane['nazwa']}.xlsx"
            yml = WYNIKI / f"{dane['nazwa']}.yaml"
            xlsx.write_bytes(base64.b64decode(dane["arkusz_base64"]))
            yml.write_text(dane["parametry_yaml"], encoding="utf-8")
            dane = dict(dane)
            dane["arkusz"] = str(xlsx)
            dane["parametry"] = str(yml)
            dane["komunikat"] = (
                f"Zapisano arkusz {xlsx.name} oraz zestaw parametrow {yml.name} "
                f"w katalogu {WYNIKI.name}/. Przed wydaniem przelicz arkusz: "
                f"python3 scripts/recalc.py {xlsx}"
            )
        except OSError as exc:
            dane = dict(dane)
            dane["komunikat"] = (
                f"{dane['komunikat']} (Zapis na dysk sie nie powiodl: {exc} — "
                "pobierz pliki z przegladarki.)"
            )
        return dane


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
        wejscie = zbuduj(stan.kopia())
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
