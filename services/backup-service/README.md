# backup-service

Szkielet serwisu RestoreCheck.

Uruchomienie z katalogu tego serwisu:

```sh
uv sync --locked
uv run uvicorn main:app --reload
```

Dokumentacja API: http://localhost:8000/docs
Przy jednoczesnym uruchamianiu lokalnym wybierz osobne porty przez `--port`.

## Docker

Z katalogu tego serwisu:

```sh
docker build -t restorecheck/backup-service:local .
docker run --rm -p 8000:8000 restorecheck/backup-service:local
```

Przy uruchamianiu kilku serwisów użyj różnych portów hosta, np. `8001:8000` i `8002:8000`.

## Migracje Alembic

Z głównego katalogu repozytorium:

```sh
docker compose build backup-service
docker compose up -d backup-db
docker compose run --rm backup-service alembic upgrade head
docker compose run --rm backup-service alembic current
docker compose run --rm backup-service alembic check
```

Migracje czytają `DATABASE_URL` ze środowiska. Compose ustawia go automatycznie. Uruchamiaj migracje przed nową wersją aplikacji; nie są uruchamiane automatycznie przy starcie każdego procesu API.

Aby wygenerować kolejną migrację lokalnie, z katalogu serwisu, ustaw `DATABASE_URL` wskazujący dostępną bazę i wykonaj:

```sh
uv run alembic revision --autogenerate -m "opis zmiany"
```

Sprawdź wygenerowany plik przed wykonaniem migracji. Baza Compose nie publikuje portu na hoście; do generowania z dostępem do tej bazy możesz użyć kontenera i podpiąć katalog migracji:

```sh
docker compose run --rm -v "$(pwd)/services/backup-service/migrations:/service/migrations" backup-service alembic revision --autogenerate -m "opis zmiany"
```

Powyższe polecenie wykonuj z głównego katalogu repozytorium po przebudowaniu obrazu z aktualnymi modelami. Cofnięcie pierwszej migracji usuwa tabelę backupów i jej dane.

## API i workery Celery

Po zastosowaniu migracji, z głównego katalogu uruchom pełny przepływ:

```sh
docker compose -f compose.yaml -f compose.verification-local.yaml up --build -d backup-service backup-worker verification-worker
```

Compose uruchomi również PostgreSQL i Redis. `backup-worker` słucha kolejki `backup`, a `verification-worker` kolejki `verification`. Workery używają tych samych obrazów co API, ale uruchamiają Celery zamiast Uvicorna i nie publikują portów. Nie uruchamiaj równolegle starszych, ręcznie uruchomionych workerów tych kolejek.

Lokalny plik dodatkowy zapewnia workerowi weryfikacji dostęp do Dockera potrzebny do odtwarzania. Bez niego worker może połączyć się z Redis, ale nie wykona odtworzenia.

```sh
docker compose logs -f backup-worker verification-worker
```

Upload: `POST /api/backups/files`. Ostatni wynik: `GET /api/backups/status/{backup_id}`.


## Obsługa błędów HTTP

Globalne handlery są rejestrowane w `main.py`. Oczekiwane błędy aplikacji (`ApplicationError`, np. `NotFoundError`) zwracają JSON `{"detail": "..."}` z przypisanym statusem. Błędy operacyjne SQLAlchemy zwracają 503; nieoczekiwane wyjątki dają ogólne 500, ze szczegółami wyłącznie w logach. Domyślne odpowiedzi FastAPI dla `HTTPException` i walidacji 422 zostają zachowane.

W handlerze zwracamy odpowiedź HTTP, zamiast zgłaszać kolejny `HTTPException`. Handlery dotyczą wyłącznie żądań API, nie zmieniają wyjątków ani retry tasków Celery. Błędy pojawiające się już po rozpoczęciu przesyłania odpowiedzi (np. usunięcie pobieranego pliku w trakcie transferu) nie mogą zmienić wysłanego statusu HTTP.

## Próby weryfikacji

Pierwszy upload zapisuje backup, próbę `Verification` i zlecenie outbox w jednej transakcji. Status po uploadzie to `QUEUED`. Kolejna próba używa tego samego pliku i nowego UUID:

- `POST /api/backups/{backup_id}/verifications` — 202 z `id`, `backup_id`, `requested_at`, `status`; 409, jeśli istnieje aktywna próba; 404 przy braku backupu.
- `GET /api/backups/{backup_id}/verifications` — historia prób od najnowszej.
- `GET /api/backups/verifications` — próby dla monitoringu.

`QUEUED` obejmuje oczekiwanie i odtwarzanie do czasu odebrania wyniku; osobnego zdarzenia rozpoczęcia (`VERIFYING`) jeszcze nie wysyłamy. Wynik aktualizuje konkretną próbę, a status backupu zmienia tylko wynik jego najnowszej próby. Powtórzona wiadomość nie nadpisuje nowszego stanu.

Migracja `0005` odtwarza próby z historycznych wyników i najnowszych zleceń oczekujących backupów. Dla danych historycznych czas zlecenia jest przybliżony: start odtwarzania albo data uploadu. Nowe próby mają własne `requested_at`. Migracja nie usuwa historycznych wyników; downgrade usuwa wyłącznie ewidencję prób i nowy klucz obcy.

## Usuwanie backupu

`DELETE /api/backups/{backup_id}` zwraca 204 bez body. Usuwa plik, rekord backupu, jego wyniki, próby weryfikacji oraz wiadomości outbox w bazie backup-service. Przy aktywnej próbie (`QUEUED` lub `VERIFYING`) zwraca 409; przy nieistniejącym backupie 404, a niepoprawnym UUID 422. Brak samego pliku nie blokuje usunięcia pozostałych metadanych.

Usuwanie i zlecanie próby blokują ten sam rekord backupu, więc ich równoczesne wywołanie nie uruchamia weryfikacji usuniętego pliku. Plik jest najpierw przemianowywany na `.deleting-<token>-<storage_key>`. Przy błędzie transakcji zostaje przywrócony, a po commicie jest usuwany. Jeżeli końcowe usunięcie pliku tymczasowego się nie powiedzie, API nadal zwraca 204 (metadane zostały już usunięte), a ścieżka do sprzątnięcia trafia do logów.

Transakcja PostgreSQL i operacje plikowe nie są atomowe. Po nagłym zabiciu procesu plik tymczasowy wymaga sprawdzenia: gdy rekord backupu nadal istnieje, należy przywrócić jego plik; gdy rekordu już nie ma, można usunąć pozostałość. Automatyczne odzyskiwanie takich pozostałości nie jest jeszcze zaimplementowane.

Alerty w bazie monitoringu oraz zapisane wyniki outboxa verification-service pozostają historią niezależnych mikroserwisów; endpoint nie usuwa danych bezpośrednio z ich baz.
