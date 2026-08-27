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
from .dane import BladObliczenia, BladWalidacji, FormaGruntu, TrybKredytu, zbuduj
from .silnik import Wynik, przelicz
from . import porownanie as _porownanie
from .waluta import ZERO, bezpieczny_iloraz, zl

# Jak blisko progu z tabeli art. 7c trzeba byc, zeby skok limitu byl informacja
# decyzyjna. To wybor prezentacyjny, nie prog ustawowy.
PROG_BLISKOSCI_7C = Decimal("0.05")

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
        "wklad_wymagany": _liczba(max(ZERO, r.finansowanie.wklad_gotowkowy_wymagany)),
        "wklad_rzeczowy": _liczba(r.finansowanie.wklad_rzeczowy_laczny),
        "nadwyzka_rzeczowa": _liczba(r.finansowanie.nadwyzka_wkladu_rzeczowego),
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
    jest odpowiedzia narzedzia: wymagana gotowka inwestora. Grunt wniesiony
    rzeczowo jest osobnym slupkiem, bo domyka koszty, nie wymagajac zlotowki.

    Przy formach nieodblokowujacych pasma dotacji slupek dotacji niesie szara
    czesc "utracone" — rozdz. 7.3 uzupelnienia nr 2.
    """
    f = r.finansowanie
    g = r.granty.spoleczna
    wymagany = max(ZERO, f.wklad_gotowkowy_wymagany)
    nadwyzka = f.nadwyzka_wkladu_rzeczowego
    dostepny = r.wejscie.inwestor.dostepny_wklad_wlasny
    udzial = _liczba(bezpieczny_iloraz(wymagany, f.koszty_laczne))

    dotacja = {
        "etykieta": "Dotacja",
        "kwota": _liczba(-f.grant_laczny),
        "rodzaj": "odjecie",
    }
    if g.utracony_przez_forme_gruntu:
        dotacja["utracone"] = _liczba(g.grant_utracony)
        dotacja["utracone_powod"] = (
            f"Przy tej formie gruntu dotacja zatrzymuje się na "
            f"{prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} kosztów zamiast "
            f"{g.stawka_nominalna:.0%}. Na tej podstawie kosztowej to "
            f"{_kwota_slownie(g.grant_utracony)}."
        )

    kroki = [
        {"etykieta": "Koszt inwestycji", "kwota": _liczba(f.koszty_laczne), "rodzaj": "suma"},
        dotacja,
        {"etykieta": "Kredyt", "kwota": _liczba(-f.kredyt_laczny), "rodzaj": "odjecie"},
        {"etykieta": "Partycypacja", "kwota": _liczba(-f.partycypacja_laczna),
         "rodzaj": "odjecie"},
    ]
    if f.wklad_rzeczowy_inwestora_laczny > ZERO:
        kroki.append({
            "etykieta": "Grunt, który wnosisz",
            "kwota": _liczba(-f.wklad_rzeczowy_inwestora_laczny),
            "rodzaj": "odjecie",
            "podpis": "Wartość działki w kosztach — nie wykładasz na nią gotówki.",
        })
    if f.wklad_rzeczowy_gminy_laczny > ZERO:
        kroki.append({
            "etykieta": "Grunt wniesiony przez gminę",
            "kwota": _liczba(-f.wklad_rzeczowy_gminy_laczny),
            "rodzaj": "odjecie",
            "podpis": "Gmina obejmuje za to udziały w spółce.",
        })
    kroki.append({"etykieta": "Twój wkład", "kwota": _liczba(wymagany), "rodzaj": "wynik"})

    if nadwyzka > ZERO:
        zdanie = (
            f"Nie musisz dokładać gotówki. Dotacja i wniesiony grunt domykają montaż "
            f"z zapasem {_kwota_slownie(nadwyzka)}."
        )
    else:
        zdanie = (
            f"Żeby zrealizować tę inwestycję, musisz wyłożyć własnych "
            f"{_kwota_slownie(wymagany)}, czyli {udzial:.0%} kosztów."
        )

    return {
        "kroki": kroki,
        "wymagany": _liczba(wymagany),
        "nadwyzka_rzeczowa": _liczba(nadwyzka),
        "udzial_w_kosztach": udzial,
        "dostepny": _liczba(dostepny),
        "roznica": _liczba(dostepny - wymagany) if dostepny is not None else None,
        "zdanie": zdanie,
    }


def _wiersz_czynszu(
    nazwa: str, etykieta: str, przyjety: Decimal, limity, wymagany: Optional[Decimal],
    rynkowy: Optional[Decimal],
) -> Dict[str, Any]:
    """Jeden wiersz wykresu czynszowego — errata nr 1, rozdz. 6.2.

    Sufity: prawny (wyliczany przez silnik) i — wylacznie w puli spolecznej —
    faktyczny, czyli poziom akceptowany przez rynek. Wiaze nizszy z nich.
    """
    sufity = [(limity.limit_wiazacy_m2_mies, "prawny")]
    sasiedni = _sasiedni_prog_7c(limity)
    if rynkowy is not None:
        sufity.append((rynkowy, "rynkowy"))
    najnizszy, rodzaj = min(sufity, key=lambda para: para[0])

    if wymagany is None:
        miesci = None
    else:
        miesci = wymagany <= najnizszy
    return {
        "pula": nazwa,
        "etykieta": etykieta,
        "przyjety": _liczba(przyjety),
        "wymagany": _liczba(wymagany),
        "limit": _liczba(limity.limit_wiazacy_m2_mies),
        "limit_zrodlo": limity.limit_wiazacy_zrodlo,
        "rynkowy": _liczba(rynkowy),
        "sufit_najnizszy": _liczba(najnizszy),
        "sufit_rodzaj": rodzaj,
        "miesci_sie": miesci,
        "prog_sasiedni": sasiedni,
    }


def _sasiedni_prog_7c(limity) -> Optional[Dict[str, Any]]:
    """Najblizszy prog z tabeli art. 7c i limit czynszu po jego przekroczeniu.

    Tabela dziala skokowo: przy udziale wsparcia 44,9% limit wynosi 4,0% wartosci
    odtworzeniowej rocznie, przy 45,0% juz 3,5%. Roznica kilkunastu procent stawki
    czynszu bierze sie z jednej dziesiatej punktu procentowego dotacji, a przy
    udziale blisko progu jest to informacja decyzyjna — inaczej niewidoczna.

    Zwraca None, gdy udzial wsparcia nie jest blisko zadnego progu.
    """
    udzial = limity.udzial_wsparcia
    if udzial is None or limity.podstawa_wiazaca_m2 <= ZERO:
        return None
    kandydaci = [
        prog for prog, _ in prawo.LIMIT_CZYNSZU_ART_7C
        if prog > udzial and prog - udzial <= PROG_BLISKOSCI_7C
    ]
    if not kandydaci:
        return None
    prog = min(kandydaci)
    stawka = prawo.limit_czynszu_art_7c(prog)
    limit_po = limity.podstawa_wiazaca_m2 * stawka / Decimal(12)
    if limit_po >= limity.limit_wiazacy_m2_mies:
        return None
    return {
        "udzial_progu": _liczba(prog),
        "brakuje_pp": _liczba((prog - udzial) * Decimal(100)),
        "limit_po_progu": _liczba(limit_po),
        "opis": (
            f"Przy dotacji {prog:.0%} kosztów limit czynszu spada z "
            f"{_dziesietnie(limity.limit_wiazacy_m2_mies)} zł do "
            f"{_dziesietnie(limit_po)} zł. Dzieli Cię od tego "
            f"{_dziesietnie((prog - udzial) * Decimal(100), 1)} punktu procentowego dotacji."
        ),
    }


def _czynsz_poziomy(r: Wynik) -> Dict[str, Any]:
    """Zestawienie czynszow — jeden wykres, jedna skala, dwa wiersze.

    Errata nr 1, rozdz. 6. Cale pytanie brzmi: czy podloga miesci sie pod
    najnizszym z sufitow. Wiersze na wspolnej skali, zeby roznica limitow byla
    widoczna. Zadnego uśredniania miedzy pulami — wyszlaby liczba, ktorej nie da
    sie pobrac w zadnej z nich.
    """
    rynek = r.wejscie.rynek
    rynkowy = rynek.czynsz_rynkowy_m2_mies
    wymagany_s = r.czynsz_domykajacy_m2_mies

    wiersze = []
    if r.projekcja.spoleczna.aktywna:
        wiersze.append(_wiersz_czynszu(
            "spoleczna", "Mieszkania społeczne",
            r.limity_spoleczna.czynsz_zakladany_m2_mies, r.limity_spoleczna,
            wymagany_s, rynkowy,
        ))
    if r.projekcja.komunalna.aktywna:
        # Sufit rynkowy w puli komunalnej NIE WYSTEPUJE — najemca jest gmina,
        # a oplaty podnajemcow sa ustawione na poziomie zasobu komunalnego.
        wiersze.append(_wiersz_czynszu(
            "komunalna", "Mieszkania komunalne",
            r.limity_komunalna.czynsz_zakladany_m2_mies, r.limity_komunalna,
            r.czynsz_wymagany_komunalna, None,
        ))

    # Stawka domykajaca nie domyka wszystkiego: luka puli komunalnej zostaje poza
    # zasiegiem czynszu, bo tam nie ma kredytu, ktory zamienilby przyszly czynsz
    # na kapital poczatkowy. Etykieta "wymagany" bez tego zastrzezenia obiecuje
    # wiecej, niz stawka moze dac.
    poza_zasiegiem = r.luka_poza_zasiegiem_czynszu
    return {
        "wiersze": wiersze,
        "poza_zasiegiem_czynszu": _liczba(poza_zasiegiem),
        "czynsz_domykajacy_hipotetyczny": r.czynsz_domykajacy_jest_hipotetyczny,
        "zastrzezenie_do_wymaganego": _zastrzezenie_do_wymaganego(r, poza_zasiegiem),
        "rynek_podano": rynek.podano,
        "rynek_zrodlo": rynek.zrodlo,
        "rynek_data": rynek.data.isoformat() if rynek.data else None,
        "pytanie": _pytanie_rynkowe(wymagany_s) if not rynek.podano else "",
        "ocena_rynkowa": _ocena_rynkowa(wymagany_s, rynkowy),
        "zdanie": _zdanie_czynszowe(wiersze),
    }


def _zastrzezenie_do_wymaganego(r: Wynik, poza_zasiegiem: Decimal) -> str:
    """Co "czynsz wymagany" znaczy naprawde i czego nie obejmuje."""
    if r.czynsz_domykajacy_jest_hipotetyczny:
        return (
            "Kredyt ustawiasz samodzielnie, więc podniesienie czynszu go nie zmieni — "
            "stawka wymagana opisuje wariant, w którym kredyt dopasowałby się do luki. "
            "Przełącz kredyt na automatyczny, żeby ta liczba była osiągalna."
        )
    if poza_zasiegiem > ZERO:
        return (
            f"Nawet przy tej stawce zostaje {_kwota_slownie(poza_zasiegiem)} do wyłożenia: "
            "mieszkania komunalne nie mają kredytu, więc ich brakującego kapitału nie da "
            "się zamienić na czynsz."
        )
    return ""


def _pytanie_rynkowe(wymagany: Optional[Decimal]) -> str:
    """Gdy stawki rynkowej nie podano — pytanie zamiast wymyslonej liczby.

    Errata nr 1, rozdz. 3.2. Zamienia brakujaca dana w decyzje, ktora uzytkownik
    i tak musi podjac — a on te odpowiedz zna, tylko nie ma jej w arkuszu.
    """
    if wymagany is None:
        return (
            "Żadna stawka czynszu nie domknęłaby tej inwestycji sama. Nie wiemy też, "
            "ile płaci się za najem w tej miejscowości — podaj stawkę rynkową, żeby "
            "narzędzie mogło sprawdzić także ten sufit."
        )
    return (
        f"Żeby inwestycja spłacała się sama, czynsz musiałby wynosić "
        f"{_dziesietnie(wymagany)} zł za metr. Czy w tej miejscowości ktoś tyle "
        f"zapłaci? Jeśli nie — różnicę pokryje kapitał albo wyższa dotacja."
    )


def _ocena_rynkowa(wymagany: Optional[Decimal], rynkowy: Optional[Decimal]) -> str:
    """Zdanie oceniajace, gdy stawka rynkowa zostala podana — rozdz. 3.3."""
    if rynkowy is None:
        return ""
    if wymagany is None:
        return (
            "Żadna stawka czynszu nie domknęłaby tej inwestycji sama, więc porównanie "
            "z rynkiem niczego nie ratuje — potrzebny kredyt przekracza ustawowy pułap."
        )
    if wymagany <= rynkowy:
        return (
            "Czynsz potrzebny do domknięcia mieści się poniżej poziomu rynkowego. "
            "Popyt nie powinien być barierą."
        )
    return (
        f"Czynsz potrzebny do domknięcia jest o {_dziesietnie(wymagany - rynkowy)} zł "
        f"wyższy niż rynkowy. Na tym rynku takich stawek się nie uzyska — montaż wymaga "
        f"większego kapitału, wyższej partycypacji albo MNIEJSZEGO udziału mieszkań "
        f"komunalnych."
    )


def _zdanie_czynszowe(wiersze: list) -> str:
    """Jedno zdanie opisujace stan wiazacy — rozdz. 6.3.

    Rozroznienie, KTORY sufit wiaze, jest kluczowe dla decyzji: sufit prawny
    przesuwa sie zmiana udzialu dotacji, sufitu rynkowego nie przesunie nic.
    """
    if not wiersze:
        return ""

    przekraczajace = [w for w in wiersze if w["miesci_sie"] is False]
    nieosiagalne = [w for w in wiersze if w["wymagany"] is None]

    if not przekraczajace and not nieosiagalne:
        czesci = []
        for w in wiersze:
            czesc = (
                f"{w['etykieta'].lower()}: czynsz {_dziesietnie(w['przyjety'])} zł "
                f"mieści się pod limitem ustawowym {_dziesietnie(w['limit'])} zł"
            )
            if w["rynkowy"] is not None:
                czesc += f" i pod stawką rynkową {_dziesietnie(w['rynkowy'])} zł"
            czesci.append(czesc)
        return (
            "Wszystko mieści się pod sufitami. "
            + "; ".join(czesci).capitalize()
            + "."
        )

    if nieosiagalne:
        w = nieosiagalne[0]
        return (
            f"W wierszu „{w['etykieta'].lower()}" + "” nie ma stawki, która domknęłaby "
            "montaż — brakującego kapitału nie da się zamienić na czynsz. Pokryje go wkład "
            "własny albo wyższa dotacja."
        )

    w = przekraczajace[0]
    if w["sufit_rodzaj"] == "rynkowy":
        return (
            f"W wierszu „{w['etykieta'].lower()}" + "” czynsz musiałby wynosić "
            f"{_dziesietnie(w['wymagany'])} zł. Przepisy na to pozwalają, ale na tym rynku "
            f"płaci się {_dziesietnie(w['rynkowy'])} zł — takich stawek się nie uzyska."
        )
    return (
        f"W wierszu „{w['etykieta'].lower()}" + "” czynsz musiałby wynosić "
        f"{_dziesietnie(w['wymagany'])} zł, a przepisy pozwalają najwyżej na "
        f"{_dziesietnie(w['limit'])} zł. Tę różnicę pokryje kapitał."
    )


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
    # "114% dopuszczalnej pomocy" czyta sie jak wskaznik pokrycia finansowania —
    # sugeruje nadmiar srodkow, a oznacza przekroczenie limitu. Podajemy wiec
    # osobno zapas (gdy miesci sie) i przekroczenie (gdy nie), a skala konczy
    # sie na limicie zamiast miec go posrodku.
    przekroczenie = max(ZERO, (wykorzystanie or ZERO) - Decimal(1))
    zapas = max(ZERO, Decimal(1) - (wykorzystanie or ZERO))
    return {
        "wykorzystanie": _liczba(wykorzystanie),
        "przekroczenie": _liczba(przekroczenie),
        "zapas": _liczba(zapas),
        "etykieta": (
            f"Przekroczenie limitu o {przekroczenie:.0%}"
            if przekroczenie > ZERO
            else f"Zapas do limitu {zapas:.0%}"
        ),
        "liczba_glowna": _liczba(przekroczenie if przekroczenie > ZERO else zapas),
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


def _grunt_json(r: Wynik) -> Dict[str, Any]:
    """Dwupoziomowy wybor gruntu — rozdz. 7 uzupelnienia nr 2.

    Poziom 1 to trzy przyciski (czyja jest dzialka), poziom 2 to lista form
    z jednozdaniowym opisem SKUTKU przy kazdej. Opis jedzie razem z opcja, zeby
    uzytkownik zobaczyl konsekwencje PRZED wyborem, a nie po.
    """
    w = r.wejscie
    u = r.grunt

    def opcja(nazwa: str) -> Dict[str, Any]:
        skutki = prawo.skutki_gruntu(nazwa)
        dostepna, powod = True, ""
        if skutki.wnoszony_aportem and w.grunt.obciazony_hipoteka:
            dostepna = False
            powod = (
                "Nieruchomość obciążona hipoteką nie może być wniesiona aportem — "
                "wariant jest niedopuszczalny (§ 12 ust. 6 rozp. Dz.U. 2021 poz. 766)."
            )
        # Krotka etykieta skutku na przycisku. Skladana tutaj, bo niesie progi
        # ustawowe — w JavaScripcie nie ma prawa byc zadnej stalej z ustawy.
        if not skutki.pasmo_45:
            skutek = (
                f"dotacja {prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} zamiast "
                f"{prawo.GRANT_SPOLECZNY_LIMIT_PODSTAWOWY:.0%}"
            )
        elif skutki.gmina_wspolnikiem:
            skutek = "gmina wspólnikiem spółki"
        else:
            skutek = ""
        return {
            "klucz": nazwa,
            "etykieta": skutki.etykieta,
            "podpis": skutki.podpis,
            "skutek_krotki": skutek,
            "dostepna": dostepna,
            "powod_niedostepnosci": powod,
            "pasmo_45": skutki.pasmo_45,
            "gmina_wspolnikiem": skutki.gmina_wspolnikiem,
            "wymaga_oplaty_rocznej": skutki.z_oplata_roczna,
            "rozlicza_lokalami": nazwa == FormaGruntu.LOKAL_ZA_GRUNT.value,
            "wymaga_potwierdzenia": skutki.wymaga_potwierdzenia,
            "podstawa": skutki.podstawa,
        }

    # Pola negocjowane z gmina. Widoczne przy formie, ktorej dotycza, ale
    # edytowalne zawsze — bez nich widok porownawczy nie policzy tych wariantow.
    pola = [
        {
            "klucz": "grunt.oplata_roczna",
            "etykieta": "Opłata roczna za grunt",
            "wartosc": _liczba(w.grunt.oplata_roczna),
            "jednostka": "zl/rok",
            "podpis": "Czynsz dzierżawny albo opłata za użytkowanie wieczyste. "
                      "Obciąża wynik co roku, przez cały okres.",
            "dotyczy_form": sorted(prawo.FORMY_Z_OPLATA_ROCZNA),
        },
        {
            "klucz": "grunt.liczba_lokali_dla_gminy",
            "etykieta": "Lokale dla gminy — liczba",
            "wartosc": w.grunt.liczba_lokali_dla_gminy or None,
            "jednostka": "szt.",
            "podpis": "Uchwała rady gminy określa minimum i maksimum, więc to "
                      "przedmiot negocjacji, a nie dana z góry.",
            "dotyczy_form": [FormaGruntu.LOKAL_ZA_GRUNT.value],
        },
        {
            "klucz": "grunt.pum_lokali_dla_gminy",
            "etykieta": "Lokale dla gminy — powierzchnia",
            "wartosc": _liczba(w.grunt.pum_lokali_dla_gminy) or None,
            "jednostka": "m2",
            "podpis": "Ta powierzchnia nie przyniesie czynszu, ale trzeba ją wybudować.",
            "dotyczy_form": [FormaGruntu.LOKAL_ZA_GRUNT.value],
        },
    ]

    # Zdania o skutkach biezacej formy — skladane po stronie silnika, bo niosa
    # kwoty i progi ustawowe.
    opisy = []
    if u.wklad_rzeczowy_laczny > ZERO:
        opisy.append("Grunt wnosisz rzeczowo — nie wykładasz na niego gotówki.")
    if u.wydatek_gotowkowy > ZERO:
        opisy.append(f"Za działkę płacisz {_kwota_slownie(u.wydatek_gotowkowy)} w gotówce.")
    if r.alokacja.grunt_obciety_limitem > ZERO:
        opisy.append(
            f"Do kosztów weszło o {_kwota_slownie(r.alokacja.grunt_obciety_limitem)} mniej — "
            f"grunt z aportu liczy się w ścieżce kredytowej do "
            f"{prawo.GRUNT_APORT_LIMIT_W_KOSZTACH_KREDYT:.0%} kosztów przedsięwzięcia."
        )
    if u.przychod_uoig:
        opisy.append(
            "Wartość działki liczy się jako Twój przychód i obniża limit pomocy publicznej."
        )
    if u.oplata_roczna > ZERO:
        opisy.append(
            f"Opłata roczna {_kwota_slownie(u.oplata_roczna)} obciąża wynik co roku."
        )
    if u.rozliczany_lokalami:
        opisy.append(
            f"Gminie oddajesz {_dziesietnie(u.pum_dla_gminy, 0)} m² — to "
            f"{_dziesietnie(w.grunt.koszt_lokali_dla_gminy_na_m2)} zł za metr wobec "
            f"{_dziesietnie(w.koszty.koszt_budowy_na_m2)} zł kosztu budowy."
        )
    if r.granty.spoleczna.utracony_przez_forme_gruntu:
        # Kwota liczona na TEJ podstawie kosztowej — to ubytek wzgledem stawki
        # ustawowej, a nie roznica wzgledem innej formy gruntu. Porownanie miedzy
        # formami przelicza caly model i daje inna, wlasciwa dla siebie kwote.
        opisy.append(
            f"Dotacja wychodzi o {_kwota_slownie(r.granty.spoleczna.grant_utracony)} niższa "
            f"od ustawowego maksimum. Ile tracisz względem innej formy gruntu — "
            f"pokaże porównanie form."
        )

    biezace = {
        "opisy": opisy,
        "pasmo_45": u.pasmo_45,
        "wartosc_w_kosztach": _liczba(u.wartosc_w_kosztach),
        "wartosc_do_pasma": _liczba(u.wartosc_do_pasma),
        "obciete_limitem": _liczba(r.alokacja.grunt_obciety_limitem),
        "przychod_uoig": u.przychod_uoig,
        "wydatek_gotowkowy": _liczba(u.wydatek_gotowkowy),
        "wklad_rzeczowy": _liczba(u.wklad_rzeczowy_laczny),
        "oplata_roczna": _liczba(u.oplata_roczna),
        "gmina_wspolnikiem": u.gmina_wspolnikiem,
        "pum_dla_gminy": _liczba(u.pum_dla_gminy),
        "grant_utracony": _liczba(r.granty.spoleczna.grant_utracony),
        "utracony_przez_forme": r.granty.spoleczna.utracony_przez_forme_gruntu,
        "opis": u.opis_kanalow,
    }
    if u.rozliczany_lokalami:
        biezace["koszt_metra_oddanych_lokali"] = _liczba(
            w.grunt.koszt_lokali_dla_gminy_na_m2
        )
        biezace["koszt_budowy_metra"] = _liczba(w.koszty.koszt_budowy_na_m2)

    return {
        "pochodzenie": w.grunt.pochodzenie.value,
        "forma": w.grunt.forma.value,
        "poziom1": [
            {
                "klucz": pochodzenie,
                "etykieta": prawo.ETYKIETY_POCHODZENIA[pochodzenie],
                "formy": list(prawo.formy_dla_pochodzenia(pochodzenie)),
            }
            for pochodzenie in prawo.POCHODZENIA_GRUNTU
        ],
        "poziom2": {
            pochodzenie: [opcja(f) for f in prawo.formy_dla_pochodzenia(pochodzenie)]
            for pochodzenie in prawo.POCHODZENIA_GRUNTU
        },
        "pola": pola,
        # Formy swiadomie poza zakresem — pokazane, nie przemilczane.
        "wylaczone": _formy_poza_zakresem(w.grunt.pochodzenie.value),
        "biezace": biezace,
    }


def _formy_poza_zakresem(pochodzenie: str) -> list:
    """Warianty usuniete z zakresu narzedzia, z powodem i alternatywa.

    Pakiet naprawczy nr 2, rozdz. 11.4: nie kasowac po cichu. Gmina zaproponuje
    aport, bo dla niej to najprostsze rozwiazanie — inwestor przy stole ma wtedy
    dostac gotowa odpowiedz wraz z alternatywa, zamiast pustego miejsca.
    """
    if pochodzenie != prawo.POCHODZENIE_GMINA:
        return []
    return [
        "Aport działki przez gminę nie jest liczony — gmina obejmuje wtedy udziały "
        "i przestaje to być prywatny SIM. Ten sam grunt bez tego skutku daje tryb "
        "„lokal za grunt”."
    ]


def _uwagi_wariantu(w) -> list:
    """Krotkie uwagi pod slupkiem wariantu. Progi ustawowe skladane tu, nie w UI."""
    uwagi = []
    if not w.pasmo_45:
        uwagi.append(
            f"dotacja ścięta do {prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} kosztów"
        )
    if w.gmina_wspolnikiem:
        uwagi.append("gmina wspólnikiem spółki")
    if w.oplata_roczna > ZERO:
        uwagi.append(f"opłata {_kwota_slownie(w.oplata_roczna)} rocznie")
    if not w.domyka_sie:
        uwagi.append("montaż się nie domyka")
    return uwagi


def porownanie_json(r: Wynik) -> Dict[str, Any]:
    """Widok porownawczy form gruntu — rozdz. 4.3."""
    p = _porownanie.buduj(r.wejscie)
    return {
        "ok": True,
        "forma_wybrana": r.wejscie.grunt.forma.value,
        "warianty": [
            {
                "forma": w.forma,
                "etykieta": w.etykieta,
                "podpis": w.podpis,
                "wybrany": w.wybrany,
                "policzalny": w.policzalny,
                "powod": w.powod,
                "wklad_gotowkowy": _liczba(w.wklad_gotowkowy),
                "grant": _liczba(w.grant_laczny),
                "dopuszczalna_pomoc": _liczba(w.dopuszczalna_pomoc),
                "pum_przychodowe": _liczba(w.pum_przychodowe),
                "oplata_roczna": _liczba(w.oplata_roczna),
                "domyka_sie": w.domyka_sie,
                "gmina_wspolnikiem": w.gmina_wspolnikiem,
                "pasmo_45": w.pasmo_45,
                "uwagi": _uwagi_wariantu(w),
            }
            for w in p.wedlug_wkladu() + tuple(x for x in p.warianty if not x.policzalny)
        ],
        "wnioski": [
            {
                "kod": wn.kod,
                "tresc": wn.tresc,
                "forma_polecana": wn.forma_polecana,
                "kwota": _liczba(wn.kwota),
            }
            for wn in p.wnioski
        ],
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
        # Wybor formy gruntu nalezy do skali projektu, nie do dzwigni — jest
        # decyzja strukturalna, nie parametrem do przesuwania (rozdz. 7.1).
        "grunt": _grunt_json(r),
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
            {"klucz": "rynek.czynsz_rynkowy_m2_mies",
             "etykieta": "Czynsz rynkowy w tej miejscowości (opcjonalnie)",
             "wartosc": _liczba(w.rynek.czynsz_rynkowy_m2_mies), "jednostka": "zl/m2/mies.",
             "podpis": "Przeciętny czynsz najmu w tej miejscowości. Najprościej: przejrzyj "
                       "kilkanaście aktualnych ofert mieszkań o podobnym metrażu i weź "
                       "medianę. Zapisz, skąd wzięta — będzie potrzebne przy weryfikacji "
                       "założeń. Bez tej wartości narzędzie zadaje pytanie zamiast zgadywać."},
            {"klucz": "rynek.zrodlo", "etykieta": "Skąd ta stawka", "typ": "tekst",
             "wartosc": w.rynek.zrodlo, "jednostka": "",
             "podpis": "Wymagane, gdy podajesz stawkę. Np. „mediana z 15 ofert 40–55 m², "
                       "portal ogłoszeniowy”."},
            {"klucz": "inwestor.dostepny_wklad_wlasny", "etykieta": "Twój kapitał (opcjonalnie)",
             "wartosc": _liczba(w.inwestor.dostepny_wklad_wlasny), "jednostka": "zl",
             "podpis": "Punkt odniesienia. Zostaw puste, a narzędzie po prostu poda "
                       "wymaganą kwotę."},
        ],
        # Rozdz. 4 erraty: lokalizacja sluzy WYLACZNIE do opisu. Nazwa gminy
        # i wojewodztwo trafiaja na naglowek arkusza i do nazwy zestawu zalozen.
        # Nic z nich nie jest liczone i narzedzie niczego z nich nie wyprowadza.
        "lokalizacja": {
            "gmina": w.projekt.gmina,
            "wojewodztwo": w.projekt.wojewodztwo,
            "podpis": "Gmina i województwo służą wyłącznie do opisu — trafiają na nagłówek "
                      "arkusza i do nazwy zapisywanego zestawu założeń. Narzędzie nie "
                      "wyprowadza z nich żadnej wartości.",
        },
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
                 "wartosc": _liczba(w.parametry_zewnetrzne.wartosc_odtworzeniowa_m2),
                 "podpis": "Wskaźnik przeliczeniowy kosztu odtworzenia 1 m² — z obwieszczenia "
                           "wojewody dla Twojego województwa. Ogłaszany co pół roku."},
            ],
        },
    }


def _dzwignia_poza_osia(w, numer: Optional[int]) -> Dict[str, Any]:
    """Co ruszyc, gdy proporcja mieszkan nie jest dzwignia.

    Wskazuje sekcje interfejsu, a nie ogolna rade — uzytkownik ma wiedziec,
    gdzie kliknac. Forma gruntu jest tu najczestsza przyczyna, bo dziala na
    wynik czterema kanalami naraz i zadnego z nich nie widac na osi udzialu pul.
    """
    if numer is None:
        return {}
    if numer == 3:
        return {
            "opis": (
                "Limit pomocy publicznej nie zależy od proporcji mieszkań. Ruszają go "
                "sposób rozliczenia nakładu, forma gruntu i wysokość dotacji."
            ),
            "dzialanie": "Zmień formę działki",
            "cel": "grunt",
        }
    if numer == 2:
        return {
            "opis": (
                "Czynsz nie pokrywa kosztów w żadnym wariancie proporcji. Ruszają to "
                "stawki czynszu, koszty eksploatacji i warunki kredytu."
            ),
            "dzialanie": "Przejdź do dźwigni",
            "cel": "dzwignie",
        }
    return {
        "opis": (
            "Kapitału brakuje przy każdej proporcji mieszkań. Ruszają to koszt budowy, "
            "partycypacja i forma gruntu."
        ),
        "dzialanie": "Przejdź do dźwigni",
        "cel": "dzwignie",
    }


def sweep_json(w) -> Dict[str, Any]:
    analiza = _wrazliwosc.build(w)
    return {
        "ok": True,
        "podsumowanie": analiza.podsumowanie,
        "maksymalny_udzial": _liczba(analiza.sweep.maksymalny_udzial_komunalny),
        "punkt_graniczny": _liczba(analiza.sweep.punkt_graniczny),
        # Drugi punkt graniczny — ten, w ktorym wymagany czynsz spoleczny przebija
        # stawke rynkowa. Bywa wczesniejszy niz kapitalowy i jest calkowicie
        # niewidoczny, jesli sledzi sie wylacznie limity ustawowe. None, gdy
        # stawki rynkowej nie podano — narzedzie go wtedy nie wymysla.
        "punkt_graniczny_rynkowy": _liczba(analiza.sweep.punkt_graniczny_rynkowy),
        "punkt_graniczny_wiazacy": _liczba(analiza.sweep.punkt_graniczny_wiazacy),
        "rodzaj_punktu_wiazacego": analiza.sweep.rodzaj_punktu_wiazacego,
        "test_blokujacy": analiza.sweep.test_blokujacy,
        # Test oblany w kazdym punkcie osi znaczy, ze przesuwanie tego pokretla
        # nic nie da. Wykres ma wtedy powiedziec to wprost i wskazac dzwignie,
        # ktora dziala, zamiast swiecic na czerwono na calej szerokosci.
        "blokada_niezalezna_od_osi": analiza.sweep.blokada_niezalezna_od_osi,
        "dzwignia_poza_osia": _dzwignia_poza_osia(w, analiza.sweep.blokada_niezalezna_od_osi),
        "punkty": [
            {
                "udzial": _liczba(p.udzial),
                "policzalny": p.policzalny,
                "domyka_sie": p.domyka_sie,
                "werdykty": list(p.werdykty),
                "wiazace_ograniczenie": p.wiazace_ograniczenie,
                "wklad_wymagany": _liczba(p.wklad_wymagany),
                "czynsz_domykajacy": _liczba(p.czynsz_domykajacy),
                "miesci_sie_w_rynku": p.miesci_sie_w_rynku,
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
        if akcja == "porownanie":
            dane, _ = dociagnij_czynsze(dane)
            return 200, porownanie_json(przelicz(zbuduj(dane)))
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
