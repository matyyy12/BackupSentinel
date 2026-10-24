# monitoring-service

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
docker build -t restorecheck/monitoring-service:local .
docker run --rm -p 8000:8000 restorecheck/monitoring-service:local
```

Przy uruchamianiu kilku serwisów użyj różnych portów hosta, np. `8001:8000` i `8002:8000`.

## Baza i migracje Alembic

Monitoring korzysta z osobnego PostgreSQL `monitoring-db`, bazy i użytkownika `monitoring` oraz wolumenu `monitoring_data`. Hasło ustawia `MONITORING_POSTGRES_PASSWORD`; wartość domyślna jest przeznaczona do lokalnego developmentu. `DATABASE_URL` przekazuje Compose.

Z głównego katalogu projektu (polecenia bez podpinania ścieżek działają również z katalogu serwisu):

```sh
docker compose build monitoring-service
docker compose up -d --wait monitoring-db
docker compose run --rm --no-deps monitoring-service alembic upgrade head
docker compose run --rm --no-deps monitoring-service alembic current
docker compose run --rm --no-deps monitoring-service alembic check
```

Migracje uruchamiaj przed nową wersją aplikacji. Nie wykonują się automatycznie przy starcie API. Migracja `0001` tworzy tabelę `alerts`, enum `alerttype`, indeks `backup_id` i unikalność pary `verification_id` + `type`. Cofnięcie `0001` usuwa alerty.

Generowanie następnej migracji z głównego katalogu repozytorium:

```sh
docker compose run --rm --no-deps \
  -v "$(pwd)/services/monitoring-service/migrations:/service/migrations" \
  monitoring-service alembic revision --autogenerate --rev-id 0002 -m "opis zmiany"
```

Przed generowaniem przebuduj obraz z aktualnym modelem. Po sprawdzeniu wygenerowanej migracji ponownie przebuduj obraz i zastosuj `alembic upgrade head`.

## Celery i harmonogram

Po zastosowaniu migracji uruchom workera i jedną instancję Beat:

```sh
docker compose up --build -d monitoring-worker monitoring-beat
```

Worker słucha kolejki `monitoring`. Beat co 30 sekund wysyła zadanie `monitoring`, które wywołuje funkcję `monitor()`. Oba procesy używają obrazu monitoring-service, bez publikowania dodatkowych portów. Stan harmonogramu zapisuje się w wolumenie `monitoring_beat_data`.

```sh
docker compose logs -f monitoring-worker monitoring-beat
```

Uruchamiaj tylko jedną instancję Beat dla tego harmonogramu. Migracje bazy pozostają osobnym krokiem przed uruchomieniem workera.


## Obsługa błędów HTTP

Globalne handlery są rejestrowane w `main.py`. Oczekiwane błędy aplikacji (`ApplicationError`, np. `NotFoundError`) zwracają JSON `{"detail": "..."}` z przypisanym statusem. Błędy operacyjne SQLAlchemy zwracają 503; nieoczekiwane wyjątki dają ogólne 500, ze szczegółami wyłącznie w logach. Domyślne odpowiedzi FastAPI dla `HTTPException` i walidacji 422 zostają zachowane.

W handlerze zwracamy odpowiedź HTTP, zamiast zgłaszać kolejny `HTTPException`. Handlery dotyczą wyłącznie żądań API, nie zmieniają wyjątków ani retry tasków Celery. Błędy pojawiające się już po rozpoczęciu przesyłania odpowiedzi (np. usunięcie pobieranego pliku w trakcie transferu) nie mogą zmienić wysłanego statusu HTTP.

Timeout próby weryfikacji jest liczony od `requested_at` pobieranego z `GET /api/backups/verifications`, a nie od daty przesłania pliku. Alert timeoutu zawiera `verification_id`. Wynik starej próby nie zamyka timeoutu nowszej; ponowne sprawdzenie nie odtwarza ręcznie rozwiązanego alertu tej samej próby. Starsze alerty bez `verification_id` nadal mogą zostać automatycznie zamknięte po wykryciu zakończonej próby.
