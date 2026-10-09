# BackupSentinel

## Uruchomienie lokalne

W głównym katalogu projektu:

```sh
docker compose build
docker compose up -d backup-db
docker compose run --rm backup-service alembic upgrade head
docker compose up -d
```

Dokumentacja API:
- Backup: http://localhost:8000/docs
- Weryfikacja: http://localhost:8001/docs
- Monitoring: http://localhost:8002/docs

Compose uruchamia również PostgreSQL 17. Baza jest dostępna wewnątrz sieci Compose jako `backup-db:5432`, bez publikowania portu na komputerze.
Domyślne hasło służy tylko do lokalnego developmentu. Opcjonalnie skopiuj `.env.example` do `.env` i ustaw hasło złożone ze znaków bezpiecznych dla URL. Zmiana hasła w konfiguracji nie zmienia hasła już zainicjalizowanej bazy.

## Trwałe dane

- `backup_files`: magazyn plików pod `/data/backups`. Backup-service ma prawo zapisu, verification-service dostęp tylko do odczytu.
- `postgres_data`: dane PostgreSQL.

To nazwane wolumeny Dockera, nie katalogi projektu. Kod zapisu powinien odczytywać `BACKUP_STORAGE_PATH` ze środowiska. Samo podłączenie wolumenu nie implementuje uploadu.

```sh
docker compose logs -f backup-service
docker compose down
```

`down` zachowuje dane. `docker compose down -v` usuwa również wolumeny wraz z backupami i bazą.

## Stan projektu

Kontenery uruchamiają aktualne szkielety aplikacji. Pierwsza migracja Alembic tworzy tabelę backupów. Pełny przepływ uploadu i weryfikacji rozwijany jest osobno.
