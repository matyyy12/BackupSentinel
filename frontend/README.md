# Frontend BackupSentinel

Osobny projekt React w JavaScript (JSX), uruchamiany przez Vite. Panel korzysta z rzeczywistego API i zawiera:

- podsumowanie liczby i statusów backupów,
- listę plików z wyszukiwaniem i filtrem statusu,
- formularz przesłania pliku z wersją PostgreSQL,
- historię weryfikacji, ostatni wynik, pobieranie pliku i zlecanie kolejnej próby,
- usuwanie kopii z potwierdzeniem i blokadą podczas aktywnej weryfikacji,
- listę aktywnych alertów, ich szczegóły i oznaczanie jako rozwiązane.

Interfejs ma stały ciemny motyw z turkusowym akcentem. Backupy i aktywne alerty mają wspólny układ eksploratora: lista po lewej, szczegóły wybranej pozycji po prawej. Na mniejszych ekranach panele układają się pionowo.

Dane odświeżają się co 10 sekund. Weryfikacja po dodaniu pliku wymaga działających workerów i publisherów backendu.

## Uruchomienie

Z głównego katalogu repozytorium przez Docker Compose:

```sh
docker compose up -d --build frontend
```

Frontend będzie dostępny pod http://127.0.0.1:5173. Compose uruchomi też wymagane API, ich bazy i Redis. Pozostałe procesy, w tym workery, uruchamiaj tak jak dotychczas dla pełnego działania systemu.

Zmiany w `src`, `index.html` i `vite.config.js` są widoczne bez przebudowy obrazu. Po zmianie zależności przebuduj frontend tym samym poleceniem. To konfiguracja developerska z Vite.

Alternatywnie bez Dockera:

```sh
cd frontend
npm install
npm run dev
```

Otwórz http://127.0.0.1:5173. Przy kolejnych instalacjach zgodnych z lockfile można użyć `npm ci`.

## Struktura

- `src/main.jsx` — uruchomienie Reacta.
- `src/App.jsx` — główny komponent aplikacji.
- `src/BackupExplorer.jsx`, `src/AlertExplorer.jsx` — eksploratory backupów i alertów.
- `src/Explorer.css` — wspólny układ listy i szczegółów.
- `src/App.css`, `src/index.css` — style okien, nawigacji i globalna paleta.
- `src/api.js`, `src/format.js`, `src/ui.jsx` — komunikacja z API, formatowanie i wspólne elementy.
- `vite.config.js` — konfiguracja developmentu i proxy do API.
- `package.json`, `package-lock.json` — zależności i polecenia projektu.

## API

W kodzie frontendu używaj względnych adresów, np. `fetch('/api/backups/')` oraz `fetch('/api/alerts/')`. Lokalny serwer Vite przekazuje je odpowiednio do portów 8000 i 8002. Mikroserwisy muszą działać osobno; `npm run dev` ich nie uruchamia.

W Compose proxy korzysta z nazw kontenerów `backup-service:8000` i `monitoring-service:8000`, ustawianych przez zmienne środowiskowe. Przeglądarka nadal wysyła żądania pod adresem frontendu na porcie 5173.

Domyślne adresy można zmienić, kopiując `.env.example` do `.env.local`. Po zmianie uruchom Vite ponownie. Dzięki proxy podczas developmentu przeglądarka komunikuje się z tym samym originem i nie trzeba dodawać CORS do backendu.

Proxy dotyczy serwera developerskiego. Wdrożenie plików `dist` będzie wymagało osobnego routingu `/api` albo konfiguracji adresów API i CORS.

## Sprawdzenie i build

```sh
npm run lint
npm run build
```
