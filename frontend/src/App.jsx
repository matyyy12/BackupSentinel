import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { Icon, Badge } from "./ui.jsx";
import { date, size } from "./format.js";
import BackupExplorer from "./BackupExplorer.jsx";
import AlertExplorer from "./AlertExplorer.jsx";
import { api } from "./api.js";

function App() {
  const [backups, setBackups] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [updated, setUpdated] = useState(null);
  const [view, setView] = useState("backups");
  const [modal, setModal] = useState(null);
  const [details, setDetails] = useState(null);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef(null);
  const requestId = useRef(0);
  const refresh = useCallback(async () => {
    try {
      const [items, notices] = await Promise.all([
        api("/api/backups/"),
        api("/api/alerts/?resolved=false"),
      ]);
      setBackups(
        items.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date)),
      );
      setAlerts(notices);
      setError("");
      setUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const initial = setTimeout(refresh, 0);
    const timer = setInterval(refresh, 10000);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    if (modal) dialog.current?.showModal();
    else dialog.current?.close();
  }, [modal]);
  function close() {
    requestId.current++;
    setModal(null);
  }
  async function open(type, item) {
    const id = ++requestId.current;
    setDetails(null);
    setActionError("");
    setModal({ type, item });
    if (type === "upload" || type === "delete") return;
    try {
      const data = await api(`/api/backups/${item.id}/verifications`);
      if (requestId.current === id) setDetails(data);
    } catch (err) {
      if (requestId.current === id) setActionError(err.message);
    }
  }
  async function upload(event) {
    event.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      await api("/api/backups/files", {
        method: "POST",
        body: new FormData(event.currentTarget),
      });
      close();
      await refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function act(path, options) {
    setBusy(true);
    setActionError("");
    try {
      await api(path, options);
      close();
      await refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteBackup() {
    const backup = modal.item;
    setBusy(true);
    setActionError("");
    try {
      await api(`/api/backups/${backup.id}`, { method: "DELETE" });
      setBackups((items) => items.filter((item) => item.id !== backup.id));
      close();
      setNotice(`Usunięto backup „${backup.filename}”.`);
      await refresh();
    } catch (err) {
      setActionError(
        err.status === 409
          ? "Nie można usunąć backupu z aktywną weryfikacją. Poczekaj na jej zakończenie."
          : err.status === 404
            ? "Ten backup już nie istnieje. Zamknij okno i odśwież listę."
            : err.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          aria-label="BackupSentinel — strona główna"
        >
          <span className="brand-icon">
            <Icon name="shield" size={25} />
          </span>
          <span>
            backup<span className="brand-light">sentinel</span>
            <small>POSTGRESQL BACKUP CARE</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-avatar">B</span>
          <div>
            Moje środowisko<small>Lokalna przestrzeń robocza</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <p className="nav-label">PRZESTRZEŃ ROBOCZA</p>
        <nav>
          {[
            ["backups", "box", "Backupy"],
            ["alerts", "bell", "Alerty"],
          ].map(([id, icon, label]) => (
            <button
              key={id}
              className={view === id ? "nav-item active" : "nav-item"}
              onClick={() => setView(id)}
            >
              <Icon name={icon} />
              {label}
              {id === "alerts" && alerts.length > 0 && (
                <span className="nav-count">{alerts.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Icon name="shield" size={27} />
          <strong>Kopia to dopiero początek.</strong>
          <p>Pewność daje dopiero poprawne odtworzenie danych.</p>
          <span>
            Weryfikacja przez odtworzenie <Icon name="check" size={14} />
          </span>
        </div>
        <div className="sidebar-footer">
          <span className="avatar">LS</span>
          <div>
            Lokalny system<small>BackupSentinel · v0.1</small>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            Przestrzeń robocza <span className="slash">/</span>{" "}
            <strong>{{ backups: "Backupy", alerts: "Alerty" }[view]}</strong>
          </span>
          <div className="topbar-actions">
            <span className="connection">
              <i className={error ? "offline" : ""} />
              {loading
                ? "Łączenie z API"
                : error
                  ? "Problem z połączeniem"
                  : "Połączono z API"}
            </span>
          </div>
        </header>
        <div className="content">
          {notice && (
            <div className="notice" role="status">
              <span>{notice}</span>
              <button className="icon-button" aria-label="Zamknij komunikat" onClick={() => setNotice("")}><Icon name="close" size={16} /></button>
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              {error} <button onClick={refresh}>Spróbuj ponownie</button>
            </div>
          )}
          {view === "backups" ? (
            <BackupExplorer
              backups={backups}
              loading={loading}
              updated={updated}
              open={open}
              refresh={refresh}
            />
          ) : (
            <AlertExplorer
              alerts={alerts}
              loading={loading}
              updated={updated}
              refresh={refresh}
              onResolve={async (id) => {
                await api(`/api/alerts/${id}`, {
                  method: "PATCH",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ resolved: true }),
                });
                await refresh();
              }}
            />
          )}
        </div>
      </main>
      <dialog
        aria-labelledby="modal-title"
        ref={dialog}
        onCancel={(event) => {
          if (busy) event.preventDefault();
          else close();
        }}
        onClose={() => {
          if (!busy) close();
        }}
      >
        {modal && (
          <>
            <div className="dialog-heading">
              <div className="eyebrow">
                {modal.type === "upload" ? "NOWA KOPIA" : modal.type === "delete" ? "USUWANIE BACKUPU" : "SZCZEGÓŁY"}
              </div>
              <button
                className="icon-button"
                aria-label="Zamknij"
                disabled={busy}
                onClick={close}
              >
                <Icon name="close" />
              </button>
            </div>
            <h2 id="modal-title">
              {modal.type === "upload" ? "Dodaj backup" : modal.type === "delete" ? "Usunąć backup?" : modal.item.filename}
            </h2>
            {actionError && (
              <p role="alert" className="error">
                {actionError}
              </p>
            )}
            {modal.type === "delete" ? (
              <>
                <p>Czy chcesz trwale usunąć backup <strong className="delete-filename">{modal.item.filename}</strong>?</p>
                <p className="dialog-description">Usunięte zostaną plik kopii oraz jej historia weryfikacji i wyniki w repozytorium backupów. Tej operacji nie można cofnąć.</p>
                <div className="dialog-actions">
                  <button className="button secondary" disabled={busy} onClick={close}>Anuluj</button>
                  <button className="button danger" disabled={busy} onClick={deleteBackup}><Icon name="trash" size={16} />{busy ? "Usuwanie…" : "Usuń backup"}</button>
                </div>
              </>
            ) : modal.type === "upload" ? (
              <form onSubmit={upload}>
                <p className="dialog-description">
                  Prześlij plik kopii PostgreSQL. Weryfikacja odtworzenia
                  rozpocznie się automatycznie.
                </p>
                <label className="form-field">
                  Plik kopii
                  <input type="file" name="file" required />
                </label>
                <label className="form-field">
                  Wersja PostgreSQL
                  <input
                    name="postgres_version"
                    required
                    placeholder="np. 17"
                  />
                </label>
                <button className="button primary" disabled={busy}>
                  {busy ? "Przesyłanie…" : "Prześlij i zweryfikuj"}
                  <Icon name="arrow" size={17} />
                </button>
              </form>
            ) : (
              <>
                <div className="backup-meta">
                  <Badge status={modal.item.status} />
                  <span>
                    {size(modal.item.size)} · PostgreSQL{" "}
                    {modal.item.postgres_version}
                  </span>
                </div>
                <p className="identifier">{modal.item.id}</p>
                <div className="dialog-actions">
                  <a
                    className="button secondary"
                    href={`/api/backups/${modal.item.id}/download`}
                  >
                    <Icon name="download" size={17} />
                    Pobierz plik
                  </a>
                  <button
                    className="button primary"
                    disabled={
                      busy ||
                      !["VERIFIED", "FAILED"].includes(modal.item.status)
                    }
                    onClick={() =>
                      act(`/api/backups/${modal.item.id}/verifications`, {
                        method: "POST",
                      })
                    }
                  >
                    <Icon name="refresh" size={17} />
                    {busy ? "Zlecanie…" : "Sprawdź ponownie"}
                  </button>
                </div>
                <h3>Historia weryfikacji</h3>
                {details ? (
                  details.length ? (
                    details.map((item) => (
                      <div className="history-item" key={item.id}>
                        <span>{date(item.requested_at)}</span>
                        <Badge status={item.status} />
                      </div>
                    ))
                  ) : (
                    <p>Brak prób weryfikacji.</p>
                  )
                ) : (
                  !actionError && <p>Ładowanie historii…</p>
                )}
                <button
                  className="result-button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setActionError("");
                    setModal((previous) => ({ ...previous, result: undefined }));
                    try {
                      const result = await api(
                        `/api/backups/status/${modal.item.id}`,
                      );
                      setModal((previous) => ({ ...previous, result }));
                    } catch (err) {
                      if (err.status === 404) {
                        setModal((previous) => ({ ...previous, result: null }));
                      } else {
                        setActionError(err.message);
                      }
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Pokaż ostatni wynik odtworzenia{" "}
                  <Icon name="chevron" size={14} />
                </button>
                {modal.result === null && (
                  <p className="workspace-muted" role="status">
                    Brak zapisanego wyniku weryfikacji.
                  </p>
                )}
                {modal.result && (
                  <div className="result">
                    <Badge status={modal.result.status} />
                    <p>Zakończono: {date(modal.result.finished_at)}</p>
                    <pre>
                      {modal.result.error_message ||
                        "Kopia została pomyślnie odtworzona."}
                    </pre>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </dialog>
    </div>
  );
}
export default App;
