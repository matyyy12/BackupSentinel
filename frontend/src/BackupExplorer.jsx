import { useEffect, useState } from "react";
import { Icon, Badge } from "./ui.jsx";
import { date, size } from "./format.js";
import "./Explorer.css";

function History({ backupId }) {
  const [resource, setResource] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/backups/${backupId}/verifications`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Nie udało się pobrać historii.");
        return response.json();
      })
      .then((items) => setResource({ id: backupId, items }))
      .catch((error) => {
        if (!controller.signal.aborted)
          setResource({ id: backupId, error: error.message });
      });
    return () => controller.abort();
  }, [backupId]);
  if (resource?.id !== backupId)
    return <p className="workspace-muted">Pobieranie historii…</p>;
  if (resource.error) return <p role="alert">{resource.error}</p>;
  if (!resource.items.length)
    return <p className="workspace-muted">Brak zapisanych prób.</p>;
  return (
    <ol className="attempt-timeline">
      {resource.items.map((attempt) => (
        <li key={attempt.id}>
          <span className="timeline-dot" />
          <div>
            <strong>
              Próba weryfikacji <span>#{attempt.id.slice(0, 8)}</span>
            </strong>
            <small>Zlecono {date(attempt.requested_at)}</small>
            <Badge status={attempt.status} />
          </div>
        </li>
      ))}
    </ol>
  );
}
function ExplorerHeading({ open }) {
  return (
    <div className="workspace-heading">
      <div>
        <span className="workspace-kicker">REPOZYTORIUM POSTGRESQL</span>
        <h1>Eksplorator backupów</h1>
        <p>Wybierz plik i sprawdź jego historię bez opuszczania listy.</p>
      </div>
      <button className="button primary" onClick={() => open("upload")}>
        <Icon name="arrow" size={17} />
        Dodaj backup
      </button>
    </div>
  );
}
function Empty({ loading }) {
  return (
    <div className="workspace-empty">
      <Icon name="box" size={26} />
      <p>
        {loading
          ? "Pobieranie danych…"
          : "Brak backupów. Dodaj pierwszą kopię, aby rozpocząć."}
      </p>
    </div>
  );
}

export default function BackupExplorer({
  backups,
  loading,
  updated,
  open,
  refresh,
}) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState("all");
  const visible = backups.filter(
    (backup) =>
      backup.filename.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "pending"
          ? !["VERIFIED", "FAILED"].includes(backup.status)
          : backup.status === filter)),
  );
  const selected =
    visible.find((backup) => backup.id === selectedId) || visible[0];
  const foot = (
    <div className="workspace-foot">
      <span>
        <i />
        Odświeżanie co 10 s
      </span>
      <span>
        {updated
          ? `Aktualizacja ${updated.toLocaleTimeString("pl-PL")}`
          : "Oczekiwanie na API"}
      </span>
    </div>
  );

  return (
    <section className="backup-explorer">
      <ExplorerHeading open={open} />
      <div className="explorer-frame">
        <div className="explorer-toolbar">
          <span>
            <Icon name="box" size={17} />
            Repozytorium <b>{backups.length}</b>
          </span>
          <label>
            <Icon name="search" size={16} />
            <input
              aria-label="Szukaj w eksploratorze"
              placeholder="Znajdź kopię…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <select
            aria-label="Filtruj backupy po statusie"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">Wszystkie statusy</option>
            <option value="VERIFIED">Zweryfikowane</option>
            <option value="pending">W toku</option>
            <option value="FAILED">Błędy</option>
          </select>
          <button
            className="icon-button"
            onClick={refresh}
            aria-label="Odśwież eksplorator"
          >
            <Icon name="refresh" size={17} />
          </button>
        </div>
        <div className="explorer-columns">
          <div className="explorer-files">
            <div className="explorer-list-heading">
              PLIKI BACKUPÓW <span>STATUS</span>
            </div>
            {visible.map((backup) => (
              <button
                key={backup.id}
                className={`explorer-file ${selected?.id === backup.id ? "selected" : ""}`}
                aria-pressed={selected?.id === backup.id}
                onClick={() => setSelectedId(backup.id)}
              >
                <span className="explorer-file-icon">
                  <Icon name="file" size={23} />
                </span>
                <span className="explorer-file-name">
                  <strong>{backup.filename}</strong>
                  <small>
                    {size(backup.size)} · PostgreSQL {backup.postgres_version}
                  </small>
                </span>
                <Badge status={backup.status} />
                <Icon name="chevron" size={14} />
              </button>
            ))}
            {!visible.length &&
              (backups.length ? (
                <div className="workspace-empty">Brak pasujących plików.</div>
              ) : (
                <Empty loading={loading} />
              ))}
          </div>
          <aside
            className="explorer-details"
            aria-label="Szczegóły wybranego backupu"
          >
            {selected ? (
              <>
                <div className="detail-file-icon">
                  <Icon name="file" size={32} />
                </div>
                <span className="workspace-kicker">WYBRANY BACKUP</span>
                <h2>{selected.filename}</h2>
                <Badge status={selected.status} />
                <dl>
                  <div>
                    <dt>Rozmiar</dt>
                    <dd>{size(selected.size)}</dd>
                  </div>
                  <div>
                    <dt>PostgreSQL</dt>
                    <dd>{selected.postgres_version}</dd>
                  </div>
                  <div>
                    <dt>Dodano</dt>
                    <dd>{date(selected.upload_date)}</dd>
                  </div>
                </dl>
                <div className="explorer-actions">
                  <a
                    className="button primary"
                    href={`/api/backups/${selected.id}/download`}
                  >
                    <Icon name="download" size={16} />
                    Pobierz
                  </a>
                  <button
                    className="button secondary"
                    onClick={() => open("backup", selected)}
                  >
                    Wynik i działania
                    <Icon name="chevron" size={15} />
                  </button>
                </div>
                <div className="detail-history">
                  <h3>Historia prób</h3>
                  <History
                    key={`${selected.id}-${selected.status}`}
                    backupId={selected.id}
                  />
                </div>
                <code className="detail-id">ID / {selected.id}</code>
              </>
            ) : (
              <div className="workspace-empty">Wybierz kopię z listy.</div>
            )}
          </aside>
        </div>
      </div>
      {foot}
    </section>
  );
}
