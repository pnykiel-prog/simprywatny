# Instrukcja robocza — kalkulator montażu SIM

Źródłem prawdy dla wymagań jest `SPEC_kalkulator_SIM.md`. Ten plik opisuje **jak pracować**, nie co zbudować.

---

## Zasada nadrzędna

**Nie zgaduj liczb pochodzących z przepisów.** Jeżeli implementacja wymaga wartości, której nie ma w specyfikacji — zatrzymaj się i zgłoś brak. Wpisanie prawdopodobnej stawki jest gorsze niż przerwanie pracy, bo błąd wsiąka w wyniki i przestaje być widoczny.

To samo dotyczy interpretacji przepisu. Kwestie z rozdziału 10 specyfikacji są nierozstrzygnięte celowo — implementuj je jako przełącznik z jawnym oznaczeniem założenia.

---

## Kolejność budowy

Każdy etap kończy się działającym, przetestowanym fragmentem. Nie przechodź dalej z czerwonymi testami.

**Etap 1 — `prawo.py` i testy stałych.** Wszystkie stałe z rozdziału 3 specyfikacji, każda z podstawą prawną w komentarzu. Testy z rozdziału 11 dotyczące progów. Nic poza tym.

**Etap 2 — `dane.py` i walidacja wejścia.** Dataclasses, parser YAML, komplet walidacji: kredyt w puli komunalnej, bonus przy kredycie, PUM poza przedziałem 25–80 m², parametry starsze niż 6 miesięcy, czynsz ponad limit.

**Etap 3 — `alokacja.py`, `grant.py`, `czynsz.py`.** Statyczne wyliczenia bez projekcji. Testy brzegowe grantu i limitów czynszu muszą przechodzić przed etapem 4.

**Etap 4 — `kredyt.py` z EDB.** Harmonogram spłat i wzór z § 4 pkt 5 lit. e. Asercja `0 < EDB < S`. Test `rp = r` dający zero jest tu najważniejszy — jeżeli nie wychodzi dokładnie zero, wzór jest źle przepisany.

**Etap 5 — `projekcja.py`.** Przepływy rok po rok przez okres powierzenia. Indeksacja kosztów i czynszu, pustostany, rezerwa na zwrot partycypacji.

**Etap 6 — `rekompensata.py`.** KN, RZ, test nadwyżki. Tu wchodzi asymetria gruntu — grunt JST jako przychód. Test porównawczy dwóch identycznych wariantów różniących się tylko formą wniesienia gruntu.

**Etap 7 — `testy_montazu.py`.** Trzy werdykty, wiążące ograniczenie, luki liczbowe.

**Etap 8 — `wrazliwosc.py`.** Sweep i punkt graniczny. Dopiero gdy pojedyncze przeliczenie jest wiarygodne.

**Etap 9 — `arkusz.py`.** Eksport z formułami. Obowiązkowo przeliczenie i zero błędów.

**Etap 10 — serwer i UI.** Ostatni. Interfejs bez działającego silnika to atrapa.

---

## Reguły implementacyjne

**Jeden silnik.** Logika obliczeniowa wyłącznie w Pythonie. UI nie liczy niczego poza formatowaniem wyświetlania.

**Stałe tylko w `prawo.py`.** Jeżeli liczba z ustawy pojawia się w innym module, jest to błąd do naprawienia, nawet gdy wynik jest poprawny.

**Wszystko per m² PUM.** Wskaźniki wyjściowe liczone na metr powierzchni użytkowej mieszkań, nie na lokal. Porównania między wariantami o różnej strukturze mieszkań inaczej się zniekształcają.

**Kwoty jako `Decimal`, nie `float`.** Model operuje na pieniądzach przez 30 lat. Stopy i wskaźniki mogą pozostać `float`.

**Żadnych milczących wartości domyślnych dla parametrów zewnętrznych.** Brak stopy referencyjnej ma zatrzymać obliczenie, nie podstawić ostatnią znaną.

---

## Czego nie robić

Nie upraszczaj testu rekompensaty do wskaźnika rocznego. Cały sens pełnej projekcji polega na tym, że nadwyżka ujawnia się w perspektywie okresu powierzenia, a nie w pierwszym roku.

Nie łącz pul w jeden model ze średnią ważoną. Pula komunalna nie może mieć kredytu, więc uśrednienie da wynik pozornie poprawny i całkowicie fałszywy.

Nie licz wartości gruntu dwa razy — raz w każdej puli. Wartość dzieli się kluczem PUM razem z resztą kosztów wspólnych.

Nie dodawaj opłat z art. 28 ust. 4 do czynszu. To osobny strumień z własnym limitem 1% wartości odtworzeniowej rocznie.

Nie generuj arkusza z wklejonymi wynikami. Arkusz bez formuł jest nieweryfikowalny i nie nadaje się do dokumentacji wniosku.

---

## Kryteria ukończenia

Narzędzie jest gotowe, gdy:

1. Komplet testów z rozdziału 11 specyfikacji przechodzi.
2. Przeliczenie arkusza zwraca zero błędów formuł, a wyrywkowa kontrola 2–3 formuł w każdej zakładce projekcji potwierdza poprawne odwołania.
3. Zmiana dowolnego założenia w zakładce wejściowej arkusza przelicza cały skoroszyt.
4. Suwak udziału puli komunalnej w UI przelicza trzy werdykty bez przeładowania strony.
5. Każdy werdykt negatywny podaje wiążące ograniczenie i lukę w liczbach.
6. Zastrzeżenia z rozdziału 13 specyfikacji są widoczne w README, w UI i w arkuszu.

---

## Po zbudowaniu

Silnik powstaje na wartościach przykładowych. Kolejny krok to wprowadzenie realnych projektów jako przypadków kalibracyjnych — każdy z zamrożonym wynikiem jako test regresji.

Rozbieżność z wyliczeniem BGK traktuj jako błąd krytyczny w silniku i wyjaśnij przed dalszym rozwojem.
