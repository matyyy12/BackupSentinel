import { useEffect, useState } from "react";
import { Icon, Badge } from "./ui.jsx";
import { date } from "./format.js";
import { api } from "./api.js";

export default function AlertExplorer({
  alerts,
  loading,
  updated,
  refresh,
  onResolve,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [resource, setResource] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const selected = alerts.find((alert) => alert.id === selectedId) || alerts[0];
  const id = selected?.id;
  useEffect(() => {
    if (id === undefined) return;
    const controller = new AbortController();
    api(`/api/alerts/${id}`, { signal: controller.signal })
      .then((item) => {
        if (!controller.signal.aborted) setResource({ id, item });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResource({ id, error: error.message });
      });
    return () => controller.abort();
  }, [id, updated]);
  const detail = resource?.id === id ? resource : null;
  async function resolve() {
    setBusy(true);
    setActionError(null);
    try {
      await onResolve(id);
    } catch (error) {
      setActionError({ id, message: error.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="alert-explorer">
      <div className="workspace-heading">
        <div>
          <span className="workspace-kicker">MONITORING BACKUPÓW</span>
          <h1>Eksplorator alertów</h1>
          <p>Wybierz alert, sprawdź problem i oznacz go jako rozwiązany.</p>
        </div>
        <button className="button secondary" onClick={refresh}>
          <Icon name="refresh" size={17} />
          Odśwież
        </button>
      </div>
      <div className="explorer-frame">
        <div className="explorer-toolbar">
          <span>
            <Icon name="bell" size={17} />
            Aktywne alerty <b>{alerts.length}</b>
          </span>
          <span className="toolbar-caption">
            Błędy i przekroczenia czasu weryfikacji
          </span>
        </div>
        <div className="explorer-columns">
          <div className="explorer-files">
            <div className="explorer-list-heading">
              OTWARTE PROBLEMY <span>UTWORZONO</span>
            </div>
            {alerts.map((alert) => (
              <button
                key={alert.id}
                className={`explorer-file ${id === alert.id ? "selected" : ""}`}
                aria-pressed={id === alert.id}
                disabled={busy}
                onClick={() => setSelectedId(alert.id)}
              >
                <span
                  className={`alert-symbol ${alert.type === "VERIFICATION_TIMEOUT" ? "amber" : "red"}`}
                >
                  <Icon
                    name={
                      alert.type === "VERIFICATION_TIMEOUT" ? "clock" : "bell"
                    }
                    size={19}
                  />
                </span>
                <span className="explorer-file-name">
                  <strong>
                    {alert.type === "VERIFICATION_TIMEOUT"
                      ? "Przekroczony czas weryfikacji"
                      : "Nieudane odtworzenie"}
                  </strong>
                  <small>
                    Alert #{alert.id} · {date(alert.created_at)}
                  </small>
                </span>
                <Icon name="chevron" size={14} />
              </button>
            ))}
            {!alerts.length && (
              <div className="workspace-empty">
                <span className="all-clear">
                  <Icon name="check" size={27} />
                </span>
                <strong>
                  {loading ? "Pobieranie alertów…" : "Brak otwartych alertów"}
                </strong>
                <p>Wykryte problemy pojawią się w tym miejscu.</p>
              </div>
            )}
          </div>
          <aside
            className="explorer-details"
            aria-label="Szczegóły wybranego alertu"
          >
            {selected ? (
              <>
                <div className="detail-file-icon">
                  <Icon name="bell" size={30} />
                </div>
                <span className="workspace-kicker">WYBRANY ALERT</span>
                <h2>Alert #{id}</h2>
                <Badge status={selected.type} />
                {detail?.error ? (
                  <p className="error" role="alert">
                    {detail.error}
                  </p>
                ) : detail?.item ? (
                  <>
                    <dl>
                      <div>
                        <dt>Utworzono</dt>
                        <dd>{date(detail.item.created_at)}</dd>
                      </div>
                    </dl>
                    <div className="alert-message">
                      <h3>Szczegóły problemu</h3>
                      <pre>{detail.item.message}</pre>
                    </div>
                    <div className="detail-id">
                      Backup / {detail.item.backup_id}
                    </div>
                    {detail.item.verification_id && (
                      <div className="detail-id">
                        Weryfikacja / {detail.item.verification_id}
                      </div>
                    )}
                    {actionError?.id === id && (
                      <p className="error" role="alert">
                        {actionError.message}
                      </p>
                    )}
                    <button
                      className="button primary resolve-button"
                      disabled={busy || !!detail.item.resolved_at}
                      onClick={resolve}
                    >
                      <Icon name="check" size={17} />
                      {busy
                        ? "Zapisywanie…"
                        : detail.item.resolved_at
                          ? "Alert rozwiązany"
                          : "Oznacz jako rozwiązany"}
                    </button>
                  </>
                ) : (
                  <p className="workspace-muted">Pobieranie szczegółów…</p>
                )}
              </>
            ) : (
              <div className="workspace-empty">
                <Icon name="shield" size={30} />
                <p>Nie ma alertów do sprawdzenia.</p>
              </div>
            )}
          </aside>
        </div>
      </div>
      <div className="workspace-foot">
        <span>
          <i />
          Monitoring · odświeżanie co 10 s
        </span>
        <span>
          {updated
            ? `Aktualizacja ${updated.toLocaleTimeString("pl-PL")}`
            : "Oczekiwanie na API"}
        </span>
      </div>
    </section>
  );
}
