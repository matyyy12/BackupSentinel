# verification-service

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
docker build -t restorecheck/verification-service:local .
docker run --rm -p 8000:8000 restorecheck/verification-service:local
```

Przy uruchamianiu kilku serwisów użyj różnych portów hosta, np. `8001:8000` i `8002:8000`.

## Lokalne testowanie weryfikacji

Z katalogu głównego, po świadomym zezwoleniu na dostęp do hosta Dockera: `docker compose -f compose.yaml -f compose.verification-local.yaml up --build -d verification-service`.
Dokumentacja: http://localhost:8001/docs, endpoint: `POST /api/verification`.
Przekaż UUID backupu jako `backup_id`, nazwę `<UUID>.dump` jako `storage_key` oraz `postgres_version: "17"`.

Opcjonalny plik `compose.verification-local.yaml` udostępnia tej usłudze socket Dockera. Zwykły `compose.yaml` go nie podłącza. Daje to szerokie uprawnienia do hosta Dockera; konfiguracja jest przeznaczona do lokalnego developmentu, z portem ograniczonym do localhost. Nie publikuj tego API w internecie. Kontenery odtwarzania nie dostają socketu, nie mają sieci i widzą backupy tylko do odczytu.

Proces API działa jako użytkownik app z dodatkową grupą `DOCKER_GID` (domyślnie 0 dla Docker Desktop). Na Linuksie ustaw w `.env` GID grupy socketa, odczytany przez `stat -c %g /var/run/docker.sock`. Nie zmieniaj socketa na publicznie zapisywalny.

Wolumen jest wybierany przez `BACKUP_VOLUME_NAME`. Obraz `postgres:17-bookworm` musi być dostępny na hoście Dockera; pobiera go również usługa backup-db. Funkcja restore usuwa swoje kontenery po zakończeniu testu. Status VERIFIED oznacza poprawne odtworzenie bez właścicieli i uprawnień, nie sprawdzenie kompletności danych biznesowych. Wynik nie aktualizuje jeszcze statusu w backup-service.
