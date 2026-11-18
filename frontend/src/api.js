export async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(
      new Error(
        typeof body.detail === "string"
          ? body.detail
          : `Nie udało się wykonać operacji (HTTP ${response.status}).`,
      ),
      { status: response.status },
    );
  }
  return response.status === 204 ? null : response.json();
}
