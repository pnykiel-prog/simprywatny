#!/usr/bin/env python3
"""Generuje PYTANIA_DO_BGK.md z katalogu zalozen — pakiet nr 2, rozdz. 9.

Pismo nie jest pisane recznie, tylko skladane z `sim_kalkulator.zalozenia`.
Powod jest prosty: lista pisana obok kodu rozjezdza sie z nim po drugiej
zmianie. Tutaj zmiana rozstrzygniecia dotyka jednego miejsca, a pismo idzie
za nia samo.

Uruchomienie:  python3 scripts/pytania_do_bgk.py
"""

from __future__ import annotations

import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

from sim_kalkulator import zalozenia  # noqa: E402

CEL = KORZEN / "PYTANIA_DO_BGK.md"

NAGLOWEK = """# Pytania do BGK — lista skonsolidowana

**Dokument generowany.** Zrodlem jest `sim_kalkulator/zalozenia.py`; po zmianie
katalogu uruchom `python3 scripts/pytania_do_bgk.py`. Recznych poprawek w tym
pliku nie wprowadzac — zostana nadpisane.

Wszystkie pytania dotycza jednego montazu i wzajemnie sie zazebiaja, wiec warto
zadac je jednym pismem. Kolejnosc idzie za waga dla wyniku: najpierw te, ktore
odwracaja werdykt, potem te, ktore przesuwaja kwote.

Kazde pytanie odpowiada jednemu ZALOZENIU w modelu. Dopoki odpowiedzi nie ma,
kalkulator liczy wariant oznaczony jako domyslny i zglasza to ostrzezeniem przy
kazdym przeliczeniu. Po odpowiedzi wystarczy zmienic wskazana wartosc — poza
jednym przypadkiem, w ktorym trzeba wejsc w kod, i ten przypadek jest oznaczony.

"""

STOPKA = """
---

## Jak czytac kolumne „gdzie to zmienic"

Sciezka wskazuje pole w pliku YAML z zalozeniami. Zmiana wartosci i ponowne
przeliczenie wystarcza — silnik, arkusz i interfejs ida za nia razem.

`brak przelacznika` znaczy, ze odczyt alternatywny nie jest wpiety w wejscie.
Silnik liczy wtedy obie wartosci i podaje roznice w ostrzezeniu, ale przyjecie
odczytu przeciwnego wymaga zmiany w kodzie.

## Kody bez osobnego pytania

Niektore watpliwosci maja w modelu dwa kody ostrzezen — po jednym na kazdy
odczyt. Do Banku idzie wtedy jedno pytanie. Kody wtorne:

{WTORNE}

## Czego na tej liscie nie ma

Pytanie o wycene aportu na potrzeby objecia udzialow przez gmine zostalo
skreslone wraz z usunieciem tego wariantu z zakresu narzedzia — patrz LUKI.md
rozdz. 17.
"""


def tabela() -> str:
    wiersze = [
        "| Nr | Pytanie | Co sie zmienia | Priorytet |",
        "|---|---|---|---|",
    ]
    for i, z in enumerate(zalozenia.do_pisma(), start=1):
        pytanie = z.tytul.replace("|", "/")
        wiersze.append(
            f"| {i} | {pytanie} | {z.waga_dla_wyniku} | {z.priorytet} |"
        )
    return "\n".join(wiersze)


def szczegoly() -> str:
    czesci = []
    for i, z in enumerate(zalozenia.do_pisma(), start=1):
        gdzie = z.sciezka if z.ma_przelacznik else "brak przelacznika — patrz stopka"
        czesci.append(
            f"### {i}. {z.tytul}\n\n"
            f"> {z.pytanie_do_bgk}\n\n"
            f"| | |\n|---|---|\n"
            f"| Podstawa | {z.podstawa} |\n"
            f"| Model przyjmuje | {z.domyslnie} |\n"
            f"| Odczyt alternatywny | {z.alternatywa} |\n"
            f"| Co sie zmienia | {z.waga_dla_wyniku} |\n"
            f"| Gdzie to zmienic | `{gdzie}` |\n"
            f"| Kod ostrzezenia | `{z.kod}` |\n"
        )
    return "\n".join(czesci)


def wtorne() -> str:
    wiersze = [
        f"- `{z.kod}` — patrz pytanie o: {zalozenia.zalozenie(z.duplikat_pytania).tytul}"
        for z in zalozenia.wedlug_priorytetu()
        if not z.idzie_do_pisma
    ]
    return "\n".join(wiersze) if wiersze else "- brak"


def zbuduj() -> str:
    return (
        NAGLOWEK
        + tabela()
        + "\n\n---\n\n## Pytania w pelnym brzmieniu\n\n"
        + szczegoly()
        + STOPKA.replace("{WTORNE}", wtorne())
    )


def main() -> int:
    tresc = zbuduj()
    stary = CEL.read_text(encoding="utf-8") if CEL.exists() else ""
    if stary == tresc:
        print(f"{CEL.name}: bez zmian")
        return 0
    CEL.write_text(tresc, encoding="utf-8")
    print(f"{CEL.name}: zapisano {len(zalozenia.do_pisma())} pytan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
