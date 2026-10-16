const num2 = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num0 = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
const fechaLarga = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const fechaCorta = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", timeZone: "UTC" });
const mesAño = new Intl.DateTimeFormat("es-CO", { month: "short", year: "numeric", timeZone: "UTC" });

export const pct = (x: number | null | undefined) => (x == null ? "—" : `${num2.format(x)}%`);
export const pesos = (x: number | null | undefined) => (x == null ? "—" : `$${num2.format(x)}`);
export const pesos0 = (x: number | null | undefined) => (x == null ? "—" : `$${num0.format(x)}`);

/** Cambio en puntos porcentuales con flecha. La flecha es tinta, no color: subir es bueno o malo según quién mire. */
export function pp(x: number | null | undefined): string {
  if (x == null) return "—";
  if (Math.abs(x) < 0.005) return "sin cambio";
  return `${x > 0 ? "▲" : "▼"} ${num2.format(Math.abs(x))} p.p.`;
}

export const fecha = (iso: string | null | undefined) => (iso ? fechaLarga.format(new Date(iso + "T00:00:00Z")) : "—");
export const fechaC = (iso: string) => fechaCorta.format(new Date(iso + "T00:00:00Z"));
export const mes = (d: Date) => mesAño.format(d);

export function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
