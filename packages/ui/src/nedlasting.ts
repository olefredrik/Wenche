// Last ned base64-kodede filer fra dokument-endepunktene (delt mellom hostet og self-hosted).

export interface NedlastFil {
  filnavn: string;
  mime: string;
  base64: string;
}

export function lastNed(filer: NedlastFil[]): void {
  for (const f of filer) {
    const bin = atob(f.base64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([bytes], { type: f.mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = f.filnavn;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
}
