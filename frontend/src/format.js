const date = (value) =>
  new Date(value).toLocaleString("pl-PL", {
    dateStyle: "medium",
    timeStyle: "short",
  });
const size = (value) =>
  value < 1024 ** 2
    ? `${(value / 1024).toFixed(1)} KB`
    : `${(value / 1024 ** 2).toFixed(1)} MB`;

export { date, size };
