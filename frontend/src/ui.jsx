const labels = {
  VERIFICATION_FAILED: "Nieudane odtworzenie",
  VERIFICATION_TIMEOUT: "Przekroczony czas",
  VERIFIED: "Zweryfikowany",
  FAILED: "Błąd weryfikacji",
  QUEUED: "W kolejce",
  VERIFYING: "Weryfikacja",
  RECEIVED: "Odebrany",
};
const paths = {
  shield: "M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z M8 12l3 3 5-6",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  box: "M4 7h16v14H4z M3 3h18v4H3z M9 11h6",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4",
  arrow: "M12 4v16 M4 12l8-8 8 8",
  search: "M20 20l-5-5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  check: "M5 12l4 4L19 6",
  clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  refresh:
    "M20 7v5h-5 M4 17v-5h5 M5 7a8 8 0 0 1 14-1l1 6 M4 12l1 6a8 8 0 0 0 14-1",
  file: "M6 2h8l4 4v16H6z M14 2v5h4 M9 12h6 M9 16h6",
  close: "M6 6l12 12 M18 6 6 18",
  download: "M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5",
  chevron: "m9 5 7 7-7 7",
};
function Icon({ name, size = 20 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
function Badge({ status }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      <span />
      {labels[status] || status}
    </span>
  );
}

export { Icon, Badge };
