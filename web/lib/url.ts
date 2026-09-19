export function safeExternalUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function displayHostname(value: string): string {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "Liên kết ngoài";
  }
}
