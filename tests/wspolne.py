"""Wspolne narzedzia testowe — wczytywanie i modyfikowanie wejscia wzorcowego."""

from __future__ import annotations

import copy
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from sim_kalkulator.dane import Wejscie, zbuduj

KATALOG_PRZYKLADOW = Path(__file__).resolve().parent.parent / "przyklady"
WZORCOWY = KATALOG_PRZYKLADOW / "wzorcowy.yaml"

# Data odniesienia dla testow — zamrozona, zeby ostrzezenie o wieku parametrow
# nie zaczelo wyskakiwac samo z uplywem czasu i nie psulo testow.
DATA_ODNIESIENIA = _dt.date(2026, 8, 25)


def surowe() -> Dict[str, Any]:
    with WZORCOWY.open("r", encoding="utf-8") as plik:
        return yaml.safe_load(plik)


def zmien(**sciezki: Any) -> Dict[str, Any]:
    """Kopia wejscia wzorcowego z podmieniona wartoscia pod sciezka 'a.b.c'."""
    dane = copy.deepcopy(surowe())
    for sciezka, wartosc in sciezki.items():
        czesci = sciezka.split("__")
        wezel = dane
        for czesc in czesci[:-1]:
            wezel = wezel[czesc]
        if wartosc is _USUN:
            wezel.pop(czesci[-1], None)
        else:
            wezel[czesci[-1]] = wartosc
    return dane


class _Usun:
    def __repr__(self) -> str:
        return "<usun klucz>"


_USUN = _Usun()
USUN = _USUN


def wejscie(na_dzien: Optional[_dt.date] = None, **sciezki: Any) -> Wejscie:
    return zbuduj(zmien(**sciezki), na_dzien=na_dzien or DATA_ODNIESIENIA)
