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

Wolumen jest wybierany przez `BACKUP_VOLUME_NAME`. Obraz `postgres:17-bookworm` musi być dostępny na hoście Dockera; pobiera go również usługa backup-db. Funkcja restore usuwa swoje kontenery po zakończeniu testu. Status VERIFIED oznacza poprawne odtworzenie bez właścicieli i uprawnień, nie sprawdzenie kompletności danych biznesowych. Endpoint HTTP zwraca wynik bez zapisu w backup-service. Zadanie Celery wysyła wynik do kolejki `backup`, a backup-worker zapisuje status i szczegóły w bazie.


## Worker Celery

Po zastosowaniu migracji backup-service uruchom z głównego katalogu:

```sh
docker compose -f compose.yaml -f compose.verification-local.yaml up --build -d backup-service backup-worker verification-worker
```

Worker `verification-worker` słucha kolejki `verification`. Dodatkowy plik lokalny podłącza socket Dockera również do workera, z grupą `DOCKER_GID`. API weryfikacji nie musi działać, żeby zadania Celery były wykonywane.

## Osobna baza i migracje wyników

`verification-db` to PostgreSQL z własną bazą i użytkownikiem `verification`, bez kluczy obcych do baz innych serwisów. Dane przechowuje wolumen `verification_data`. Hasło ustawia `VERIFICATION_POSTGRES_PASSWORD`; wartość domyślna służy lokalnemu developmentowi. Compose przekazuje `DATABASE_URL` do API i workera.

Z głównego katalogu projektu lub katalogu verification-service:

```sh
docker compose build verification-service
docker compose up -d --wait verification-db
docker compose run --rm --no-deps verification-service alembic upgrade head
docker compose run --rm --no-deps verification-service alembic current
docker compose run --rm --no-deps verification-service alembic check
```

Migracja `0001` tworzy `verification_result_outbox`, klucz główny `verification_id` i indeks `backup_id`. `created_at` ustawia baza, a `sent_at` pozostaje NULL do wysłania. Cofnięcie migracji usuwa tabelę i zapisane wyniki. Migracje wykonuj przed startem nowej wersji aplikacji; nie uruchamiają się automatycznie.

Task sprawdza outbox po `verification_id` przed odtworzeniem. Jeżeli wynik już istnieje, nie wykonuje odtwarzania ponownie. Nowy wynik zapisuje w PostgreSQL; publisher wysyła go jako `backup_results` i ustawia `sent_at` po udanym wysłaniu. Błąd wysyłania cofa transakcję i pozostawia wynik do kolejnej próby.

```sh
docker compose -f compose.yaml -f compose.verification-local.yaml up --build -d verification-worker verification-result-publisher
```

Publisher potrzebuje bazy, ale nie wymaga gotowości Redis przy starcie ani dostępu do socketa Dockera. Awaria po wysłaniu, a przed commitem może spowodować powtórzenie wiadomości; backup-service pomija duplikaty według `verification_id`. Wywołania samego odtwarzania nie mają gwarancji pojedynczego wykonania: równoległe zadania lub awaria przed zapisaniem wyniku mogą powtórzyć odtworzenie. Brak dostępności PostgreSQL nadal kończy task błędem — zapis wyniku musi się udać, żeby uznać zadanie za zakończone.


## Obsługa błędów HTTP

Globalne handlery są rejestrowane w `main.py`. Oczekiwane błędy aplikacji (`ApplicationError`, np. `NotFoundError`) zwracają JSON `{"detail": "..."}` z przypisanym statusem. Błędy operacyjne SQLAlchemy zwracają 503; nieoczekiwane wyjątki dają ogólne 500, ze szczegółami wyłącznie w logach. Domyślne odpowiedzi FastAPI dla `HTTPException` i walidacji 422 zostają zachowane.

W handlerze zwracamy odpowiedź HTTP, zamiast zgłaszać kolejny `HTTPException`. Handlery dotyczą wyłącznie żądań API, nie zmieniają wyjątków ani retry tasków Celery. Błędy pojawiające się już po rozpoczęciu przesyłania odpowiedzi (np. usunięcie pobieranego pliku w trakcie transferu) nie mogą zmienić wysłanego statusu HTTP.
