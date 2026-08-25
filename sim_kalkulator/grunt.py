"""Grunt — cztery kanaly oddzialywania na wynik.

Pochodzenie i forma wniesienia dzialki nie sa jednym parametrem. Ten sam grunt
o tej samej wartosci dziala na wynik czterema niezaleznymi kanalami, ktore nie
sumuja sie w jedna liczbe:

  A — pasmo dotacji.  Czy wsparcie moze przekroczyc prog gruntowy i siegnac
      limitu podstawowego. Art. 13 ust. 1 pkt 1 ustawy z 8.12.2006 mowi o
      wartosci prawa WLASNOSCI albo UZYTKOWANIA WIECZYSTEGO nieruchomosci
      bedacej we wladaniu inwestora. Dzierzawa nie jest zadnym z tych praw,
      wiec scina dotacje z limitu podstawowego do progu gruntowego — skokowo,
      niezaleznie od wartosci dzialki.

  B — koszt przedsiewziecia.  Czy i w jakiej wysokosci wartosc gruntu wchodzi
      do podstawy (art. 5 ust. 7 pkt 7 i ust. 8 ustawy; § 12 ust. 7 rozp. 766).

  C — przychod uslugi publicznej.  Czy grunt obniza koszty netto, a przez to
      dopuszczalna rekompensate (art. 5 ust. 9 pkt 4 ustawy).

  D — zapotrzebowanie na gotowke.  Czy wklad inwestora jest pieniezny, czy
      rzeczowy. Kanal poza przepisem — klasyfikacja na potrzeby montazu.

ASYMETRIA, ktora ten modul ma uczynic widoczna: ten sam grunt o tej samej
wartosci PODNOSI podstawe, gdy pochodzi od inwestora, i OBNIZA dopuszczalna
pomoc, gdy pochodzi od gminy. Kanaly B i C nie moga zadzialac naraz — grunt,
za ktory inwestor nie zaplacil, nie jest kosztem swiadczenia uslugi.

Kanal piaty, poza obliczeniami: aport gminy czyni ja wspolnikiem spolki. Dla
modelu prywatnego SIM to zmiana ustrojowa, nie finansowa, i musi byc
zakomunikowana.

Zadna liczba z przepisu nie jest tu zaszyta — matryca skutkow i limity siedza
w `prawo.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple

from . import prawo
from .dane import FormaGruntu, Ostrzezenie, PochodzenieGruntu, Waga, Wejscie
from .waluta import ZERO, bezpieczny_iloraz


@dataclass(frozen=True)
class UjecieGruntu:
    """Rozstrzygniecie wszystkich czterech kanalow dla jednego wejscia.

    Liczone raz, przed alokacja kosztow, i przekazywane dalej — zeby nigdzie
    indziej w silniku nie trzeba bylo pytac o nazwe formy gruntu.
    """

    forma: FormaGruntu
    pochodzenie: PochodzenieGruntu
    wartosc_operatu: Decimal

    # kanal A
    pasmo_45: bool
    wartosc_do_pasma: Decimal          # 0, gdy forma nie odblokowuje pasma

    # kanal B — wartosc przed limitem aportowym; limit jest per pula, bo zalezy
    # od sciezki finansowania tej puli (§ 12 ust. 7 dotyczy finansowania zwrotnego)
    wartosc_w_kosztach: Decimal
    limit_aportowy_dotyczy: bool

    # kanal C
    przychod_uoig: bool

    # kanal D
    wydatek: str
    wydatek_gotowkowy: Decimal
    wklad_rzeczowy_inwestora: Decimal
    wklad_rzeczowy_gminy: Decimal
    oplata_roczna: Decimal

    # kanal E i wariant lokalowy
    gmina_wspolnikiem: bool
    pum_dla_gminy: Decimal
    liczba_lokali_dla_gminy: int

    ostrzezenia: Tuple[Ostrzezenie, ...]

    @property
    def skutki(self) -> prawo.SkutkiFormyGruntu:
        return self.forma.skutki

    @property
    def wklad_rzeczowy_laczny(self) -> Decimal:
        return self.wklad_rzeczowy_inwestora + self.wklad_rzeczowy_gminy

    @property
    def rozliczany_lokalami(self) -> bool:
        return self.pum_dla_gminy > ZERO

    @property
    def opis_kanalow(self) -> str:
        """Jedno zdanie do arkusza i do warstwy diagnostycznej."""
        czesci = [
            "pasmo pelne" if self.pasmo_45 else "pasmo sciete do progu gruntowego",
            (
                "wartosc w kosztach"
                + (" z limitem aportowym" if self.limit_aportowy_dotyczy else "")
            )
            if self.wartosc_w_kosztach > ZERO
            else "wartosc poza kosztami",
            "przychod UOIG" if self.przychod_uoig else "bez przychodu UOIG",
            f"wydatek: {self.wydatek}",
        ]
        return "; ".join(czesci)


def _przychod_uoig(w: Wejscie) -> bool:
    """Kanal C z uwzglednieniem przelacznikow 9.1 i 9.2.

    Matryca niesie odczyt domyslny; tam, gdzie jest on oznaczony jako wymagajacy
    potwierdzenia w BGK, rozstrzyga przelacznik z `Przelaczniki`.
    """
    skutki = w.grunt.forma.skutki
    przelacznik = skutki.przelacznik_przychodu
    if not przelacznik:
        return skutki.przychod_uoig
    return bool(getattr(w.przelaczniki, przelacznik))


def _wartosc_do_pasma(w: Wejscie, ostrzezenia: List[Ostrzezenie]) -> Decimal:
    """Kanal A — wartosc prawa wchodzaca do limitu z art. 13 ust. 1 pkt 1.

    Kwestia 9.3: przy sprzedazy z bonifikata odczyt domyslny bierze wartosc
    z operatu, bo przepis mowi o wartosci prawa, a nie o cenie nabycia.
    """
    g = w.grunt
    if not g.forma.daje_pasmo_45:
        return ZERO
    if w.przelaczniki.pasmo_liczone_od_wartosci_z_operatu:
        return g.wartosc
    if g.forma is not FormaGruntu.NABYCIE_OD_GMINY:
        return g.wartosc
    # Walidacja w `dane.py` gwarantuje, ze cena jest podana i nie przewyzsza operatu.
    assert g.cena_nabycia is not None
    ostrzezenia.append(
        Ostrzezenie(
            kod="ZALOZENIE_PASMO_OD_CENY",
            tresc=(
                "Kwestia 9.3, odczyt alternatywny: pasmo dotacji liczone od ceny po "
                f"bonifikacie ({g.cena_nabycia:.2f} zl) zamiast od wartosci z operatu "
                f"({g.wartosc:.2f} zl). Odczyt domyslny bierze wartosc z operatu, bo "
                "art. 13 ust. 1 pkt 1 mowi o wartosci prawa, nie o cenie nabycia. "
                "ZALOZENIE do potwierdzenia w BGK."
            ),
            podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
            tresc_potoczna=(
                "Dotacja liczona od ceny po bonifikacie, a nie od wartości działki z operatu. "
                "To zaniża dotację — odczyt domyślny jest korzystniejszy."
            ),
            waga=Waga.ZMIENIA_KWOTE,
        )
    )
    return g.cena_nabycia


def rozstrzygnij(w: Wejscie) -> UjecieGruntu:
    """Rozklada grunt na cztery kanaly. Wolane raz, przed alokacja kosztow."""
    g = w.grunt
    skutki = g.forma.skutki
    ostrzezenia: List[Ostrzezenie] = []

    # --- kanal A -----------------------------------------------------------
    wartosc_do_pasma = _wartosc_do_pasma(w, ostrzezenia)

    # --- kanal B -----------------------------------------------------------
    wartosc_w_kosztach = g.wartosc if skutki.wartosc_w_kosztach else ZERO

    # --- kanal C -----------------------------------------------------------
    przychod = _przychod_uoig(w)

    # --- kanal D -----------------------------------------------------------
    # Gotowke wyklada sie tylko przy nabyciu. W pozostalych formach wartosc
    # gruntu siedzi w kosztach, ale nie jest wydatkiem pienieznym — pokrywa ja
    # wklad rzeczowy, ktory obniza zapotrzebowanie na kapital obrotowy.
    if skutki.wydatek == prawo.WYDATEK_PELNY:
        # Cena rzeczywiscie placona; bonifikata obniza wydatek niezaleznie od
        # tego, jak liczone jest pasmo dotacji.
        wydatek_gotowkowy = g.cena_nabycia if g.cena_nabycia is not None else g.wartosc
        wklad_inwestora = ZERO
        wklad_gminy = ZERO
    elif skutki.gmina_wspolnikiem:
        wydatek_gotowkowy = ZERO
        wklad_inwestora = ZERO
        wklad_gminy = wartosc_w_kosztach
    else:
        wydatek_gotowkowy = ZERO
        wklad_inwestora = wartosc_w_kosztach
        wklad_gminy = ZERO

    oplata_roczna = g.oplata_roczna_lub_zero if skutki.z_oplata_roczna else ZERO

    # --- ostrzezenia strukturalne -----------------------------------------
    if not skutki.pasmo_45:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GRUNT_BEZ_PASMA_45",
                tresc=(
                    f"Forma '{g.forma.value}' nie daje inwestorowi ani prawa wlasnosci, ani "
                    "uzytkowania wieczystego, wiec wsparcie nie moze przekroczyc progu "
                    f"{prawo.GRANT_SPOLECZNY_PROG_GRUNTOWY:.0%} kosztow przedsiewziecia. "
                    f"Wartosc dzialki ({g.wartosc:.2f} zl) nie ma tu znaczenia."
                ),
                podstawa="art. 13 ust. 1 pkt 1 ustawy z 8.12.2006",
                tresc_potoczna=(
                    "Przy tej formie gruntu dotacja zatrzymuje się na 35% kosztów zamiast 45%. "
                    "Wartość działki nic tu nie zmienia."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    if skutki.gmina_wspolnikiem:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GMINA_WSPOLNIKIEM_SPOLKI",
                tresc=(
                    "Grunt wniesiony przez gmine aportem oznacza objecie przez nia udzialow "
                    "w spolce. Dla modelu prywatnego SIM jest to zmiana ustrojowa, nie tylko "
                    "finansowa — gmina wchodzi do organow spolki i wspoldecyduje. "
                    "Wariant 'lokal za grunt' daje te sama dzialke bez tego skutku."
                ),
                podstawa="art. 5 ust. 9 pkt 4 ustawy z 8.12.2006 — skutek poza obliczeniami",
                tresc_potoczna=(
                    "Gmina obejmie udziały w spółce i stanie się wspólnikiem. To decyzja "
                    "ustrojowa, nie tylko finansowa."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    if przychod:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GRUNT_JAKO_PRZYCHOD_UOIG",
                tresc=(
                    f"Wartosc gruntu ({g.wartosc:.2f} zl) zaliczono do przychodow uslugi "
                    "publicznej, wiec obniza koszty netto, a przez to dopuszczalna "
                    "rekompensate. Grunt od gminy dziala odwrotnie niz grunt inwestora: "
                    "nie podnosi podstawy, tylko obniza limit pomocy."
                ),
                podstawa="art. 5 ust. 9 pkt 4 ustawy z 8.12.2006",
                tresc_potoczna=(
                    "Działka od gminy obniża limit dopuszczalnej pomocy publicznej — liczy się "
                    "jako Twój przychód, a nie jako koszt."
                ),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )

    for numer, przelacznik, domyslna, opis, podstawa in prawo.ZALOZENIA_GRUNTOWE_DO_POTWIERDZENIA:
        if przelacznik != skutki.przelacznik_przychodu:
            continue
        biezaca = bool(getattr(w.przelaczniki, przelacznik))
        ostrzezenia.append(
            Ostrzezenie(
                kod="ZALOZENIE_GRUNT_" + numer.replace(".", "_"),
                tresc=(
                    f"Kwestia {numer}: {opis} Ustawienie biezace: "
                    f"{'TAK' if biezaca else 'NIE'} (domyslne: {'TAK' if domyslna else 'NIE'}). "
                    "ZALOZENIE do potwierdzenia w BGK."
                ),
                podstawa=podstawa,
                tresc_potoczna=(
                    "Sposób rozliczenia tej formy gruntu w limicie pomocy publicznej nie jest "
                    "przesądzony w przepisach — przyjęto odczyt ostrożniejszy. Do potwierdzenia "
                    "w Banku."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    if skutki.wartosc_w_kosztach_pewnosc == prawo.PEWNOSC_DO_POTWIERDZENIA:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GRUNT_WARTOSC_W_KOSZTACH_DO_POTWIERDZENIA",
                tresc=(
                    f"Zaliczenie wartosci prawa ({g.wartosc:.2f} zl) do kosztow przedsiewziecia "
                    f"przy formie '{g.forma.value}' jest odczytem wymagajacym potwierdzenia "
                    "w BGK — przepis nie rozstrzyga, czy wartosc prawa ustanowionego przez "
                    "gmine jest kosztem inwestora."
                ),
                podstawa=skutki.podstawa,
                tresc_potoczna=(
                    "To, czy wartość prawa do gruntu wchodzi do kosztów, wymaga potwierdzenia "
                    "w Banku. Wpływa na wysokość dotacji."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    if skutki.z_oplata_roczna and oplata_roczna > ZERO:
        ostrzezenia.append(
            Ostrzezenie(
                kod="GRUNT_OPLATA_ROCZNA_W_KOSZTACH",
                tresc=(
                    f"Oplata roczna za grunt ({oplata_roczna:.2f} zl) obciaza koszty biezace "
                    "przez caly okres projekcji i wchodzi do wymaganego pokrycia w tescie "
                    "zdolnosci czynszowej. Model indeksuje ja tym samym wskaznikiem co "
                    "pozostale koszty operacyjne."
                ),
                podstawa="art. 5 ust. 7 ustawy z 8.12.2006",
                tresc_potoczna=(
                    "Opłata roczna za grunt obciąża wynik co roku — nie jest jednorazowym "
                    "wydatkiem, tylko stałym kosztem."
                ),
                waga=Waga.ZMIENIA_KWOTE,
            )
        )

    ostrzezenia.extend(_ostrzezenia_lokalowe(w))

    return UjecieGruntu(
        forma=g.forma,
        pochodzenie=g.pochodzenie,
        wartosc_operatu=g.wartosc,
        pasmo_45=skutki.pasmo_45,
        wartosc_do_pasma=wartosc_do_pasma,
        wartosc_w_kosztach=wartosc_w_kosztach,
        limit_aportowy_dotyczy=skutki.limit_aportowy,
        przychod_uoig=przychod,
        wydatek=skutki.wydatek,
        wydatek_gotowkowy=wydatek_gotowkowy,
        wklad_rzeczowy_inwestora=wklad_inwestora,
        wklad_rzeczowy_gminy=wklad_gminy,
        oplata_roczna=oplata_roczna,
        gmina_wspolnikiem=skutki.gmina_wspolnikiem,
        pum_dla_gminy=g.pum_lokali_dla_gminy,
        liczba_lokali_dla_gminy=g.liczba_lokali_dla_gminy,
        ostrzezenia=tuple(ostrzezenia),
    )


def _ostrzezenia_lokalowe(w: Wejscie) -> List[Ostrzezenie]:
    """Ostrzezenia wlasciwe wariantowi 'lokal za grunt' — rozdz. 6."""
    g = w.grunt
    if not g.rozliczany_lokalami:
        return []

    udzial = bezpieczny_iloraz(g.pum_lokali_dla_gminy, w.powierzchnie.pum_laczne)
    lista = [
        Ostrzezenie(
            kod="ZALOZENIE_LOKAL_ZA_GRUNT_PODZIAL_PUM",
            tresc=(
                f"Gminie przypada {g.liczba_lokali_dla_gminy} lokali o lacznej powierzchni "
                f"{g.pum_lokali_dla_gminy} m2, czyli {udzial:.1%} PUM przedsiewziecia. "
                "Specyfikacja nie rozstrzyga, z ktorej puli pochodza te lokale, wiec model "
                "pomniejsza powierzchnie przychodowa obu pul proporcjonalnie, kluczem PUM. "
                "Koszt przedsiewziecia pozostaje pelny — te lokale trzeba wybudowac. "
                "ZALOZENIE modelowe."
            ),
            podstawa="ustawa z 16.12.2020, Dz.U. 2021 poz. 223",
            tresc_potoczna=(
                f"Lokale dla gminy to {udzial:.0%} powierzchni. Nie przyniosą czynszu, ale "
                "trzeba je wybudować — koszt zostaje pełny."
            ),
            waga=Waga.ZMIENIA_WERDYKT,
        )
    ]

    # Rozdz. 6: efektywny koszt gruntu na m2 oddawanych lokali zestawiony
    # z kosztem budowy metra. Gmina zadajaca lokali wartych wiecej niz dzialka
    # czyni wariant niekorzystnym i ma to byc widoczne.
    efektywny = g.koszt_lokali_dla_gminy_na_m2
    koszt_budowy = w.koszty.koszt_budowy_na_m2
    if efektywny < koszt_budowy:
        lista.append(
            Ostrzezenie(
                kod="LOKAL_ZA_GRUNT_NIEKORZYSTNY",
                tresc=(
                    f"Za dzialke warta {g.wartosc:.2f} zl oddajesz {g.pum_lokali_dla_gminy} m2 "
                    f"lokali. Wychodzi {efektywny:.2f} zl za metr oddanej powierzchni przy "
                    f"koszcie budowy {koszt_budowy:.2f} zl/m2 — gmina zada lokali wartych "
                    "wiecej niz grunt."
                ),
                podstawa="ustawa z 16.12.2020, Dz.U. 2021 poz. 223 — uchwala rady gminy",
                tresc_potoczna=(
                    f"Oddajesz gminie lokale warte więcej niż działka: {efektywny:,.0f} zł za metr "
                    f"wobec {koszt_budowy:,.0f} zł kosztu budowy. Liczba i metraż lokali są "
                    "przedmiotem uchwały rady gminy, więc podlegają negocjacji."
                ).replace(",", " "),
                waga=Waga.ZMIENIA_WERDYKT,
            )
        )
    return lista
