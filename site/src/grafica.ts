import type { Punto } from "./tipos";
import { esc, fechaC, mes } from "./formato";

export interface Serie {
  nombre: string;
  puntos: Punto[];
  clase: "s1" | "s2" | "s3";
  escalonada?: boolean; // para la usura: el valor rige hasta el siguiente cambio
}

export interface OpcionesLinea {
  formatoY: (v: number) => string;
  formatoTooltip?: (v: number) => string;
  alto?: number;
  titulo: string; // para lectores de pantalla
}

const NS = "http://www.w3.org/2000/svg";

function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

function niceTicks(min: number, max: number, n = 5): number[] {
  const span = max - min || 1;
  const paso0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => span / p <= n) ?? mag * 10;
  const ticks: number[] = [];
  for (let v = Math.ceil(min / paso) * paso; v <= max + 1e-9; v += paso) ticks.push(+v.toFixed(10));
  return ticks;
}

/** Dibuja una gráfica de líneas con cruz y tooltip. Devuelve una función para redibujar con otras series. */
export function graficaLineas(contenedor: HTMLElement, series: Serie[], op: OpcionesLinea): (s: Serie[]) => void {
  contenedor.classList.add("grafica");
  const lienzo = document.createElement("div");
  lienzo.className = "grafica-lienzo";
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.setAttribute("role", "status");
  tip.hidden = true;
  const leyenda = document.createElement("ul");
  leyenda.className = "leyenda";
  contenedor.append(leyenda, lienzo, tip);

  let actuales = series;
  let ancho = 0;

  function dibujar() {
    ancho = lienzo.clientWidth || 600;
    const estrecho = ancho < 560;
    const alto = op.alto ?? (estrecho ? 240 : 300);
    const m = { t: 12, r: estrecho ? 12 : 132, b: 28, l: 48 };
    lienzo.replaceChildren();
    tip.hidden = true;

    const visibles = actuales.map((s) => ({ ...s, puntos: s.puntos.filter((p): p is [string, number] => p[1] != null) }))
      .filter((s) => s.puntos.length > 1);
    leyenda.innerHTML = visibles.length > 1
      ? visibles.map((s) => `<li><span class="muestra ${s.clase}"></span>${esc(s.nombre)}</li>`).join("")
      : "";
    if (!visibles.length) {
      lienzo.innerHTML = `<p class="vacio">Aún no hay datos suficientes para esta gráfica.</p>`;
      return;
    }

    const t = (iso: string) => Date.parse(iso + "T00:00:00Z");
    const todos = visibles.flatMap((s) => s.puntos);
    const x0 = Math.min(...todos.map((p) => t(p[0]))), x1 = Math.max(...todos.map((p) => t(p[0])));
    let y0 = Math.min(...todos.map((p) => p[1])), y1 = Math.max(...todos.map((p) => p[1]));
    const pad = (y1 - y0) * 0.08 || Math.abs(y1) * 0.05 || 1;
    y0 -= pad; y1 += pad;
    const ticksY = niceTicks(y0, y1, estrecho ? 4 : 5);
    y0 = Math.min(y0, ticksY[0]); y1 = Math.max(y1, ticksY[ticksY.length - 1]);

    const X = (ms: number) => m.l + ((ms - x0) / (x1 - x0 || 1)) * (ancho - m.l - m.r);
    const Y = (v: number) => m.t + (1 - (v - y0) / (y1 - y0 || 1)) * (alto - m.t - m.b);

    const svg = el("svg", { viewBox: `0 0 ${ancho} ${alto}`, width: ancho, height: alto, role: "img", tabindex: 0,
      "aria-label": `${op.titulo}. Usa las flechas izquierda y derecha para recorrer los valores.` });

    // Rejilla y eje Y (recesivos)
    for (const v of ticksY) {
      svg.append(el("line", { x1: m.l, x2: ancho - m.r, y1: Y(v), y2: Y(v), class: "rejilla" }));
      const tx = el("text", { x: m.l - 8, y: Y(v), class: "eje", "text-anchor": "end", "dominant-baseline": "middle" });
      tx.textContent = op.formatoY(v);
      svg.append(tx);
    }
    // Eje X: años si el rango es largo, meses si no
    const dias = (x1 - x0) / 864e5;
    const inicio = new Date(x0);
    const marcas: Date[] = [];
    if (dias > 900) {
      for (let a = inicio.getUTCFullYear() + 1; Date.UTC(a, 0, 1) <= x1; a++) marcas.push(new Date(Date.UTC(a, 0, 1)));
    } else {
      const salto = dias > 400 ? 3 : dias > 120 ? 2 : 1;
      for (let d = new Date(Date.UTC(inicio.getUTCFullYear(), inicio.getUTCMonth() + 1, 1)); d.getTime() <= x1;
        d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + salto, 1))) marcas.push(d);
    }
    const maxMarcas = Math.max(2, Math.floor((ancho - m.l - m.r) / 70));
    const cada = Math.ceil(marcas.length / maxMarcas);
    marcas.filter((_, i) => i % cada === 0).forEach((d) => {
      const tx = el("text", { x: X(d.getTime()), y: alto - 8, class: "eje", "text-anchor": "middle" });
      tx.textContent = dias > 900 ? String(d.getUTCFullYear()) : mes(d).replace(".", "");
      svg.append(tx);
    });
    svg.append(el("line", { x1: m.l, x2: ancho - m.r, y1: alto - m.b, y2: alto - m.b, class: "base" }));

    // Líneas
    for (const s of visibles) {
      let d = "";
      s.puntos.forEach((p, i) => {
        const x = X(t(p[0])), y = Y(p[1]);
        if (i === 0) d += `M${x},${y}`;
        else d += s.escalonada ? `H${x}V${y}` : `L${x},${y}`;
      });
      if (s.escalonada) d += `H${X(x1)}`;
      svg.append(el("path", { d, class: `linea ${s.clase}` }));
    }

    // Etiquetas directas al final (evitando choques verticales)
    if (!estrecho) {
      const fin = visibles.map((s) => ({ s, y: Y(s.puntos[s.puntos.length - 1][1]), v: s.puntos[s.puntos.length - 1][1] }))
        .sort((a, b) => a.y - b.y);
      for (let i = 1; i < fin.length; i++) if (fin[i].y - fin[i - 1].y < 30) fin[i].y = fin[i - 1].y + 30;
      for (const f of fin) {
        const g = el("text", { x: ancho - m.r + 10, y: f.y, class: "etiqueta-fin", "dominant-baseline": "middle" });
        const a = el("tspan", { x: ancho - m.r + 10, dy: "-0.45em", class: "etq-nombre" });
        a.textContent = f.s.nombre.length > 18 ? f.s.nombre.slice(0, 17) + "…" : f.s.nombre;
        const b = el("tspan", { x: ancho - m.r + 10, dy: "1.2em", class: "etq-valor" });
        b.textContent = op.formatoY(f.v);
        g.append(a, b);
        svg.append(g);
      }
    }

    // Capa de interacción: cruz + puntos + tooltip
    const fechas = [...new Set(todos.map((p) => p[0]))].sort();
    const cruz = el("line", { y1: m.t, y2: alto - m.b, class: "cruz", visibility: "hidden" });
    const marcadores = visibles.map((s) => {
      const c = el("circle", { r: 5, class: `marcador ${s.clase}`, visibility: "hidden" });
      svg.append(c);
      return c;
    });
    svg.insertBefore(cruz, svg.firstChild);
    const zona = el("rect", { x: m.l, y: m.t, width: ancho - m.l - m.r, height: alto - m.t - m.b, class: "zona" });
    svg.append(zona);

    const valorEn = (s: (typeof visibles)[number], f: string): number | null => {
      // último valor conocido en o antes de f (sirve para series escalonadas y para fechas que no coinciden)
      let v: number | null = null;
      for (const p of s.puntos) { if (p[0] <= f) v = p[1]; else break; }
      return v;
    };
    let idx = fechas.length - 1;
    const mostrar = (i: number) => {
      idx = Math.max(0, Math.min(fechas.length - 1, i));
      const f = fechas[idx];
      const x = X(t(f));
      cruz.setAttribute("x1", String(x)); cruz.setAttribute("x2", String(x)); cruz.setAttribute("visibility", "visible");
      const filas: string[] = [];
      visibles.forEach((s, k) => {
        const v = valorEn(s, f);
        if (v == null) { marcadores[k].setAttribute("visibility", "hidden"); return; }
        marcadores[k].setAttribute("cx", String(x)); marcadores[k].setAttribute("cy", String(Y(v)));
        marcadores[k].setAttribute("visibility", "visible");
        filas.push(`<div class="tip-fila"><span class="muestra ${s.clase}"></span><span>${esc(s.nombre)}</span><b>${esc((op.formatoTooltip ?? op.formatoY)(v))}</b></div>`);
      });
      tip.innerHTML = `<div class="tip-fecha">${esc(fechaC(f))} ${f.slice(0, 4)}</div>${filas.join("")}`;
      tip.hidden = false;
      const izq = x + 14 + tip.offsetWidth > ancho ? x - tip.offsetWidth - 14 : x + 14;
      tip.style.transform = `translate(${Math.max(0, izq)}px, ${m.t}px)`;
    };
    const ocultar = () => {
      cruz.setAttribute("visibility", "hidden");
      marcadores.forEach((c) => c.setAttribute("visibility", "hidden"));
      tip.hidden = true;
    };
    const desdeEvento = (ev: PointerEvent) => {
      const r = svg.getBoundingClientRect();
      const ms = x0 + ((ev.clientX - r.left - m.l) / (ancho - m.l - m.r)) * (x1 - x0);
      let mejor = 0, dist = Infinity;
      fechas.forEach((f, i) => { const dd = Math.abs(t(f) - ms); if (dd < dist) { dist = dd; mejor = i; } });
      mostrar(mejor);
    };
    zona.addEventListener("pointermove", desdeEvento);
    zona.addEventListener("pointerdown", desdeEvento);
    zona.addEventListener("pointerleave", ocultar);
    svg.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowLeft") { mostrar(idx - 1); ev.preventDefault(); }
      else if (ev.key === "ArrowRight") { mostrar(idx + 1); ev.preventDefault(); }
      else if (ev.key === "Escape") ocultar();
    });
    svg.addEventListener("focus", () => mostrar(fechas.length - 1));
    svg.addEventListener("blur", ocultar);
    lienzo.append(svg);
  }

  new ResizeObserver(() => { if (Math.abs((lienzo.clientWidth || 0) - ancho) > 4) dibujar(); }).observe(lienzo);
  dibujar();
  return (s: Serie[]) => { actuales = s; dibujar(); };
}

/** Recorta una serie a los últimos `dias` días (o la deja completa si es null). */
export function recortar(puntos: Punto[], dias: number | null): Punto[] {
  if (!dias || !puntos.length) return puntos;
  const fin = Date.parse(puntos[puntos.length - 1][0] + "T00:00:00Z");
  const desde = new Date(fin - dias * 864e5).toISOString().slice(0, 10);
  return puntos.filter((p) => p[0] >= desde);
}
