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
