"""Jeden silnik — pelne przeliczenie wariantu.

UI i arkusz wolaja to samo. Logika obliczeniowa nie ma prawa istniec nigdzie
indziej: dwa silniki liczace to samo rozjada sie i nikt tego nie zauwazy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional, Tuple

from . import alokacja as _alokacja
from . import czynsz as _czynsz
from . import grant as _grant
from . import kredyt as _kredyt
from . import projekcja as _projekcja
from . import rekompensata as _rekompensata
from . import testy_montazu as _testy
from .alokacja import Alokacja
from .czynsz import LimityCzynszu
from . import prawo
from . import grunt as _grunt
from .dane import BladWalidacji, Ostrzezenie, TrybKredytu, Waga, Wejscie
from .grunt import UjecieGruntu
from .grant import Granty
from .projekcja import Finansowanie, Projekcja
from .rekompensata import TestRekompensaty
from .testy_montazu import Werdykty
from .waluta import ZERO, na_m2, pelne_zlote_w_dol

JEDEN = Decimal(1)


def kredyt_maksymalny_obslugiwalny(
    w: Wejscie, a: Alokacja, g: Granty,
    limity_s: LimityCzynszu, limity_k: LimityCzynszu,
) -> Decimal:
    """Najwiekszy kredyt, ktory uniesie zakladany czynsz przez caly okres.

    Rozdz. 2.2 uzupelnienia specyfikacji: kredyt przestaje byc parametrem
    wpisywanym z reki. Dzieki temu wskaznik pokrycia obslugi dlugu wychodzi 1,0
    z konstrukcji, a cale napiecie montazu przenosi sie do wymaganego wkladu.

    Rozwiazanie jest zamkniete, bo rata jest liniowa wzgledem kwoty kredytu:
    w karencji wynosi S*rp, po karencji S*annuita. Warunek pokrycia w kazdym
    roku sprowadza sie wiec do S <= (przychod_i - koszty_i) / wspolczynnik_i,
    a wiazacy jest rok o najmniejszym ilorazie. Rata jest nominalnie stala,
    a przychod i koszty sa indeksowane roznymi wskaznikami, wiec waskie gardlo
    nie musi wypadac w pierwszym roku — dlatego badane sa wszystkie lata.

    Podstawa raty dostepnej to pelny mianownik testu 2, z ubezpieczeniem
    i kosztami zarzadu. Skrocony wzor ze specyfikacji pomija okolo polowy
    kosztow biezacych i dalby pokrycie ponizej jednosci, czyli dokladnie
    odwrotnie niz zapowiada rozdzial 2.2.

    Nadwyzka operacyjna nie idzie na rate w calosci. Pakiet naprawczy nr 2,
    rozdz. 1: przy pokryciu dokladnie 1,0 pierwsze odchylenie od zalozen daje
    niedobor na racie, wiec nadwyzka jest dzielona przez minimalny wskaznik
    pokrycia obslugi dlugu. Wskaznik jest zalozeniem podanym na wejsciu, nie
    odczytem z przepisu — patrz `prawo.WSKAZNIK_POKRYCIA_OBSLUGI_DLUGU_DOMYSLNY`.

    Kwota jest ograniczona z dwoch stron. Od gory ustawowym udzialem 80%
    (art. 15b ust. 2 ustawy z 26.10.1995) oraz tym, ile kredytu w ogole
    potrzeba: dotacja i partycypacja pokrywaja czesc kosztow, a nikt nie
    zaciaga kredytu wiekszego niz brakujaca reszta. Bez tego drugiego
    ograniczenia wymagany wklad wlasny wychodzilby ujemny.
    """
    if not a.spoleczna.aktywna:
        return ZERO
    k = w.pula_spoleczna.kredyt
    okresy_splaty = k.okres_lat - k.karencja_lat
    if k.okres_lat <= 0 or okresy_splaty <= 0:
        return ZERO
    # `udzial_docelowy` w trybie automatycznym nie wyznacza KWOTY — ta bierze sie
    # z udzwigu czynszu — ale nadal rozstrzyga, czy kredyt w ogole wchodzi w gre.
    # Bez tego warunku silnik przyjmowal kredyt, ktorego reszta modelu nie widziala:
    # `kredyt_aktywny` szedl za `udzial_docelowy`, wiec projekcja liczyla sciezke
    # grantowa, nie naliczala raty i skracala okres powierzenia. Kredyt obnizal
    # wymagany wklad, a nikt go nie splacal.
    if not k.aktywny:
        return ZERO

    # Projekcja bez kredytu daje przychody i koszty biezace — obie wielkosci
    # nie zaleza od kwoty kredytu, wiec wystarczy policzyc je raz.
    bez_kredytu = _projekcja.zbuduj_finansowanie(w, a, g, kwota_kredytu=ZERO)
    # Horyzont wymuszony na okres kredytu. Bez tego projekcja bez kredytu idzie
    # sciezka grantowa (25 lat), a udzwig bylby liczony z pominieciem lat 26-30
    # — czyli tych, ktore przy kosztach rosnacych szybciej od czynszu sa
    # najciasniejsze. Kredyt wychodzilby wtedy za duzy, a pokrycie w ostatnich
    # latach spadaloby ponizej zadanego bufora.
    proj = _projekcja.build(
        w, a, bez_kredytu, limity_s, limity_k, horyzont_spoleczna=k.okres_lat
    )

    # Rata przypadajaca na zlotowke kredytu, osobno w karencji i po niej.
    if k.oprocentowanie == ZERO:
        annuita_jednostkowa = JEDEN / Decimal(okresy_splaty)
    else:
        czynnik = (JEDEN + k.oprocentowanie) ** okresy_splaty
        annuita_jednostkowa = k.oprocentowanie * czynnik / (czynnik - JEDEN)

    bufor = w.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
    pulapy = []
    for rok in proj.spoleczna.lata:
        if rok.rok > k.okres_lat:
            continue                       # po splacie kredyt nie obciaza juz przeplywu
        nadwyzka = rok.przychod_czynszowy_netto - rok.koszty_operacyjne
        if nadwyzka <= ZERO:
            return ZERO                    # czynsz nie pokrywa nawet kosztow biezacych
        dostepne_na_rate = nadwyzka / bufor
        wspolczynnik = (
            k.oprocentowanie if rok.rok <= k.karencja_lat else annuita_jednostkowa
        )
        if wspolczynnik <= ZERO:
            continue                       # rok bez obciazenia — nie ogranicza kwoty
        pulapy.append(dostepne_na_rate / wspolczynnik)

    if not pulapy:
        return ZERO
    limit_ustawowy = a.spoleczna.koszty_przedsiewziecia * prawo.KREDYT_MAKSYMALNY_UDZIAL
    # Ile kredytu faktycznie potrzeba po dotacji i partycypacji.
    partycypacja = (
        a.spoleczna.koszty_przedsiewziecia
        * w.pula_spoleczna.partycypacja.stawka_procent_kosztu_lokalu
    )
    # Wklad rzeczowy w gruncie juz pokrywa czesc kosztow, wiec kredyt nie ma
    # czego za niego finansowac. Bez tego odjecia kredyt "doplacalby" do aportu,
    # a wynikowy wklad gotowkowy wychodzilby ujemny.
    #
    # Odejmuje sie wklad rzeczowy TEJ puli, nie obu. Przy odczycie domyslnym
    # hybryda to dwa odrebne przedsiewziecia, a kredyt finansuje przedsiewziecie
    # spoleczne — grunt wniesiony do puli komunalnej domyka pule komunalna
    # i nie zwalnia zdolnosci kredytowej po stronie spolecznej.
    rzeczowy = _projekcja.wklady_rzeczowe(w, a)
    rzeczowy_spoleczna = rzeczowy[0][0] + rzeczowy[1][0]
    potrzebny = (
        a.spoleczna.koszty_przedsiewziecia
        - g.spoleczna.kwota
        - partycypacja
        - rzeczowy_spoleczna
    )
    return pelne_zlote_w_dol(
        max(ZERO, min(min(pulapy), limit_ustawowy, potrzebny))
    )


def czynsz_domykajacy_bez_wkladu(
    w: Wejscie, a: Alokacja, g: Granty,
    limity_s: LimityCzynszu, limity_k: LimityCzynszu,
    kredyt_potrzebny: Decimal,
) -> Optional[Decimal]:
    """Stawka czynszu, przy ktorej kredyt uniesie caly brakujacy kapital.

    Odpowiada na pytanie z rozdz. 4.3 uzupelnienia: ile musialby wynosic czynsz,
    zeby inwestycja splacala sie sama, bez wkladu wlasnego. Rozjazd miedzy ta
    stawka a limitem ustawowym jest centralnym napieciem calego modelu.

    Rachunek jest odwroceniem wyliczenia maksymalnego kredytu. Przychod jest
    wprost proporcjonalny do stawki, a koszty biezace od niej nie zaleza, wiec
    warunek pokrycia w kazdym roku daje minimalna stawke dla tego roku;
    wiazaca jest najwieksza z nich.

    Bufor obslugi dlugu wchodzi tu tym samym wskaznikiem, co przy wymiarowaniu
    kredytu — inaczej obie funkcje opisywalyby dwa rozne banki i stawka
    domykajaca nie domykalaby kwoty, ktora silnik faktycznie przyjmuje.

    Zwraca None, gdy zadna stawka nie wystarczy — na przyklad gdy potrzebny
    kredyt przekracza ustawowe 80% kosztow.
    """
    if not a.spoleczna.aktywna:
        # Przy samych mieszkaniach komunalnych nie ma najemcow spolecznych,
        # wiec nie ma stawki, ktora cokolwiek domyka. To nie jest zero.
        return None
    if kredyt_potrzebny <= ZERO:
        return ZERO
    k = w.pula_spoleczna.kredyt
    okresy_splaty = k.okres_lat - k.karencja_lat
    if k.okres_lat <= 0 or okresy_splaty <= 0:
        return None
    if kredyt_potrzebny > a.spoleczna.koszty_przedsiewziecia * prawo.KREDYT_MAKSYMALNY_UDZIAL:
        return None

    # Projekcja przy stawce jednostkowej — przychod kazdego roku jest wprost
    # proporcjonalny do stawki, wiec wystarczy raz odczytac wspolczynnik.
    jednostkowe = replace(
        w, pula_spoleczna=replace(w.pula_spoleczna, czynsz_zakladany_m2_mies=JEDEN)
    )
    fin = _projekcja.zbuduj_finansowanie(jednostkowe, a, g, kwota_kredytu=ZERO)
    proj = _projekcja.build(
        jednostkowe, a, fin, limity_s, limity_k, horyzont_spoleczna=k.okres_lat
    )

    if k.oprocentowanie == ZERO:
        annuita_jednostkowa = JEDEN / Decimal(okresy_splaty)
    else:
        czynnik = (JEDEN + k.oprocentowanie) ** okresy_splaty
        annuita_jednostkowa = k.oprocentowanie * czynnik / (czynnik - JEDEN)

    bufor = w.parametry_zewnetrzne.minimalny_wskaznik_pokrycia_obslugi_dlugu
    stawki = []
    for rok in proj.spoleczna.lata:
        if rok.rok > k.okres_lat:
            continue
        przychod_na_zlotowke = rok.przychod_czynszowy_netto
        if przychod_na_zlotowke <= ZERO:
            return None
        wspolczynnik = (
            k.oprocentowanie if rok.rok <= k.karencja_lat else annuita_jednostkowa
        )
        potrzebny_przychod = (
            rok.koszty_operacyjne + kredyt_potrzebny * wspolczynnik * bufor
        )
        stawki.append(potrzebny_przychod / przychod_na_zlotowke)
    return max(stawki) if stawki else None


def czynsz_pokrywajacy_pule(proj_puli, czynsz_bazowy: Decimal) -> Optional[Decimal]:
    """Najnizsza stawka bazowa roku 1, przy ktorej pula pokrywa sie w kazdym roku.

    "Pokrywa sie" znaczy: przychod czynszowy netto wystarcza na koszty biezace
    i obsluge dlugu, bez doplacania z kapitalu w trakcie eksploatacji.

    Przychod jest wprost proporcjonalny do stawki bazowej, a wymagane pokrycie
    od niej nie zalezy, wiec kazdy rok daje wlasna minimalna stawke; wiazaca jest
    najwieksza z nich. Indeksacja czynszu i kosztow siedzi juz w projekcji, wiec
    wynik wraca sprowadzony do stawki roku 1 — porownywalnej z limitem i z rynkiem.

    Liczone OSOBNO dla kazdej puli. Jedna stawka wazona udzialem pul bylaby
    liczba, ktorej nie da sie pobrac w zadnej z nich: obie maja wlasne limity
    i wlasnych najemcow.
    """
    if proj_puli is None or not proj_puli.aktywna or czynsz_bazowy <= ZERO:
        return None
    stawki = []
    for rok in proj_puli.lata:
        if rok.przychod_czynszowy_netto <= ZERO:
            return None
        przychod_na_zlotowke = rok.przychod_czynszowy_netto / czynsz_bazowy
        stawki.append(rok.wymagane_pokrycie / przychod_na_zlotowke)
    return max(stawki) if stawki else None


@dataclass(frozen=True)
class Wynik:
    """Komplet wyniku dla jednego wariantu wejsciowego."""

    wejscie: Wejscie
    grunt: UjecieGruntu
    alokacja: Alokacja
    granty: Granty
    limity_spoleczna: LimityCzynszu
    limity_komunalna: LimityCzynszu
    finansowanie: Finansowanie
    projekcja: Projekcja
    edb_kredytu: Decimal
    rekompensata: TestRekompensaty
    werdykty: Werdykty

    @property
    def ostrzezenia(self) -> Tuple[Ostrzezenie, ...]:
        return (
            tuple(self.wejscie.ostrzezenia)
            + self.grunt.ostrzezenia
            + self.granty.ostrzezenia
            + self.rekompensata.ostrzezenia
        )

    @property
    def domyka_sie(self) -> bool:
        return self.werdykty.domyka_sie

    # --- wskazniki per m2 PUM — metodyka projektu wymaga metra, nie lokalu ---

    @property
    def koszt_na_m2(self) -> Decimal:
        return na_m2(self.alokacja.koszty_laczne, self.wejscie.powierzchnie.pum_laczne)

    @property
    def grant_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.grant_laczny, self.wejscie.powierzchnie.pum_laczne)

    @property
    def kredyt_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.kredyt_laczny, self.wejscie.powierzchnie.pum_laczne)

    @property
    def partycypacja_na_m2(self) -> Decimal:
        return na_m2(self.finansowanie.partycypacja_laczna, self.wejscie.powierzchnie.pum_laczne)

    @property
    def wklad_wlasny_na_m2(self) -> Decimal:
        """Wklad gotowkowy na m2 PUM — to, co inwestor musi realnie wylozyc."""
        return na_m2(
            self.finansowanie.wklad_gotowkowy_wymagany, self.wejscie.powierzchnie.pum_laczne
        )

    @property
    def luka_poza_zasiegiem_czynszu(self) -> Decimal:
        """Czesc luki kapitalowej, ktorej zaden czynsz nie domknie.

        Czynsz zamienia sie na kapital poczatkowy wylacznie przez kredyt, a ten
        przysluguje tylko puli spolecznej (art. 5a ust. 3) i tylko do wysokosci
        JEJ wlasnej potrzeby. Luka puli komunalnej zostaje wiec poza zasiegiem
        stawki czynszu — pokryje ja kapital albo wyzsza dotacja, i tyle zostanie
        do wylozenia nawet przy czynszu domykajacym.
        """
        laczna = (
            self.alokacja.koszty_laczne
            - self.finansowanie.grant_laczny
            - self.finansowanie.partycypacja_laczna
            - self.finansowanie.wklad_rzeczowy_laczny
        )
        # Wklad rzeczowy TEJ puli — dokladnie ta sama wielkosc, ktora ogranicza
        # kredyt w `kredyt_maksymalny_obslugiwalny`. Uzycie wkladu lacznego
        # zawyzyloby zasieg czynszu o czesc przypadajaca puli komunalnej.
        spoleczna = (
            self.alokacja.spoleczna.koszty_przedsiewziecia
            - self.finansowanie.spoleczna.grant
            - self.finansowanie.spoleczna.partycypacja
            - self.finansowanie.spoleczna.wklad_rzeczowy
        )
        return max(ZERO, laczna - max(ZERO, spoleczna))

    @property
    def czynsz_domykajacy_jest_hipotetyczny(self) -> bool:
        """Czy stawka domykajaca opisuje kredyt, ktorego model nie przyjmie.

        W trybie recznym kwote kredytu ustawia uzytkownik, wiec podniesienie
        czynszu jej nie zmieni i stawka domykajaca niczego nie domyka — opisuje
        wariant hipotetyczny. W trybie automatycznym jest osiagalna w czesci
        spolecznej, ale i tam zostaje `luka_poza_zasiegiem_czynszu`.
        """
        return self.wejscie.przelaczniki.tryb_kredytu is TrybKredytu.RECZNY

    @property
    def czynsz_wymagany_komunalna(self) -> Optional[Decimal]:
        """Podloga czynszowa puli komunalnej — stawka pokrywajaca koszty biezace.

        Pula komunalna nie ma kredytu (art. 5a ust. 3), wiec nie ma czym zamienic
        przyszlego czynszu na kapital poczatkowy. Zerowego wkladu wlasnego nie da
        sie w niej osiagnac zadna stawka — 20% kosztow poza dotacja to luka
        strukturalna, ktora pokrywa kapital. Podloga oznacza tu wiec: ponizej tej
        stawki pula dokłada do siebie co roku.
        """
        return czynsz_pokrywajacy_pule(
            self.projekcja.komunalna,
            self.wejscie.pula_komunalna.czynsz_placony_przez_gmine_m2_mies,
        )

    @property
    def czynsz_domykajacy_m2_mies(self) -> Optional[Decimal]:
        """Podloga czynszowa puli spolecznej — stawka przy zerowym wkladzie wlasnym.

        Errata nr 1, rozdz. 5: w wariancie hybrydowym rownanie ma dwie niewiadome
        i jedno rownanie, wiec trzeba przyjac, ktora stawke traktujemy jako dana.
        CZYNSZ KOMUNALNY JEST ZADANY, SPOLECZNY DOMYKA. Uzasadnienie jest
        praktyczne: stawke komunalna negocjuje sie z gmina i zapisuje w umowie,
        a limit przy dotacji 80% i tak przyciska ja do 2,5% wartosci odtworzeniowej
        rocznie. Czynsz spoleczny zostaje wielkoscia residualna — dokladnie tak
        jak wklad wlasny w warstwie kapitalowej.

        Silnik liczy wiec: przy tej stawce od gminy, ile musza placic najemcy
        spoleczni, zeby pula spoleczna obeszla sie bez wkladu wlasnego. I ta
        liczba idzie na test rynkowy.
        """
        # Luka kapitalowa CALEGO przedsiewziecia, nie samej puli spolecznej.
        # Kredyt jest jedynym instrumentem, ktory zamienia przyszly czynsz na
        # kapital poczatkowy, a przysluguje wylacznie puli spolecznej (art. 5a
        # ust. 3). Ciezar domkniecia obu pul spada wiec na czynsz spoleczny —
        # i dlatego rosnie on wraz z udzialem puli komunalnej, ktora wnosi mniej:
        # nizszy limit czynszu, brak kredytu, brak partycypacji.
        potrzebny = (
            self.alokacja.koszty_laczne
            - self.finansowanie.grant_laczny
            - self.finansowanie.partycypacja_laczna
            - self.finansowanie.wklad_rzeczowy_laczny
        )
        return czynsz_domykajacy_bez_wkladu(
            self.wejscie, self.alokacja, self.granty,
            self.limity_spoleczna, self.limity_komunalna, potrzebny,
        )

    @property
    def luka_kapitalowa_na_m2(self) -> Decimal:
        return na_m2(self.werdykty.montaz.luka_kwota, self.wejscie.powierzchnie.pum_laczne)


@dataclass(frozen=True)
class WynikNieobliczalny:
    """Wariant, ktorego silnik nie policzyl — z powodem, nie z liczba."""

    powod: str
    typ: str

    @property
    def domyka_sie(self) -> bool:
        return False


def przelicz(w: Wejscie) -> Wynik:
    """Pelne przeliczenie. Podnosi BladWalidacji / BladObliczenia zamiast zgadywac."""
    u = _grunt.rozstrzygnij(w)
    a = _alokacja.build(w, u)
    g = _grant.build(w, a)

    kredyt_aktywny = w.pula_spoleczna.kredyt.aktywny and a.spoleczna.aktywna

    limity_spoleczna = _czynsz.build(
        w, a.spoleczna, g.spoleczna,
        w.pula_spoleczna.czynsz_zakladany_m2_mies,
        finansowanie_zwrotne=kredyt_aktywny,
    )
    limity_komunalna = _czynsz.build(
        w, a.komunalna, g.komunalna,
        w.pula_komunalna.czynsz_placony_przez_gmine_m2_mies,
        finansowanie_zwrotne=False,
    )

    if w.przelaczniki.tryb_kredytu is TrybKredytu.AUTOMATYCZNY:
        kwota_kredytu = kredyt_maksymalny_obslugiwalny(
            w, a, g, limity_spoleczna, limity_komunalna
        )
    else:
        kwota_kredytu = None

    fin = _projekcja.zbuduj_finansowanie(w, a, g, kwota_kredytu=kwota_kredytu)
    proj = _projekcja.build(w, a, fin, limity_spoleczna, limity_komunalna)
    edb_kredytu = _kredyt.edb_dla_harmonogramu(fin.harmonogram_kredytu, w.parametry_zewnetrzne)
    rek = _rekompensata.build(w, a, fin, proj, edb_kredytu)
    werdykty = _testy.build(w, fin, proj, limity_spoleczna, limity_komunalna, rek)

    return Wynik(
        wejscie=w,
        grunt=u,
        alokacja=a,
        granty=g,
        limity_spoleczna=limity_spoleczna,
        limity_komunalna=limity_komunalna,
        finansowanie=fin,
        projekcja=proj,
        edb_kredytu=edb_kredytu,
        rekompensata=rek,
        werdykty=werdykty,
    )


def przelicz_udzial(w: Wejscie, udzial: Decimal):
    """Przelicza wariant przy zadanym udziale puli komunalnej, bezpiecznie.

    Przesuniecie pokretla przechodzi pelna walidacje, wiec punkt sprzeczny
    z przepisem (np. kredyt SBC przy 100% puli komunalnej) wraca jako
    `WynikNieobliczalny` z podana przyczyna, a nie jako cicha porazka testu.
    """
    from .dane import BladObliczenia

    try:
        wariant = w.z_udzialem_komunalnym(udzial)
    except BladWalidacji as exc:
        return WynikNieobliczalny(powod=str(exc), typ="walidacja")
    return przelicz_bezpiecznie(wariant)


def przelicz_bezpiecznie(w: Wejscie):
    """Jak `przelicz`, ale zwraca `WynikNieobliczalny` zamiast wyjatku.

    Uzywane w sweepie, gdzie pojedynczy niepoliczalny punkt nie moze przerwac
    calej analizy — ale musi zostac widoczny jako niepoliczalny, nie jako porazka.
    """
    from .dane import BladObliczenia

    try:
        return przelicz(w)
    except BladWalidacji as exc:
        return WynikNieobliczalny(powod=str(exc), typ="walidacja")
    except BladObliczenia as exc:
        return WynikNieobliczalny(powod=str(exc), typ="obliczenie")
