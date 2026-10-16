import "./estilos.css";
import type { EntidadTasa, HistoricoUsura, Punto, Resumen, SeriesCDT, Usura } from "./tipos";
import { esc, fecha, pct, pesos, pp } from "./formato";
import { graficaLineas, recortar, type Serie } from "./grafica";

const REPO = "https://github.com/juanjo32/tasas-co";
const app = document.getElementById("app")!;

async function json<T>(ruta: string): Promise<T> {
  const r = await fetch(`data/${ruta}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
  return r.json() as Promise<T>;
}

function guardar(clave: string, valor: string) { try { localStorage.setItem(clave, valor); } catch { /* sin almacenamiento */ } }
function leer(clave: string): string | null { try { return localStorage.getItem(clave); } catch { return null; } }

/** Botones segmentados accesibles (radiogroup). */
function selector<T extends string | number>(etiqueta: string, opciones: { valor: T; texto: string }[], actual: T,
  alCambiar: (v: T) => void): HTMLElement {
  const g = document.createElement("div");
  g.className = "segmentos";
  g.setAttribute("role", "radiogroup");
  g.setAttribute("aria-label", etiqueta);
  const pintar = (v: T) => g.querySelectorAll("button").forEach((b, i) => {
    const sel = opciones[i].valor === v;
    b.setAttribute("aria-checked", String(sel));
    b.tabIndex = sel ? 0 : -1;
  });
  opciones.forEach((o, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "radio");
    b.textContent = o.texto;
    b.addEventListener("click", () => { pintar(o.valor); alCambiar(o.valor); });
    b.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      const sig = (i + d + opciones.length) % opciones.length;
      (g.children[sig] as HTMLButtonElement).focus();
      (g.children[sig] as HTMLButtonElement).click();
    });
    g.append(b);
  });
  pintar(actual);
  return g;
}

/** Tabla de ranking con barra horizontal desde cero (escala común a toda la tabla). */
function tablaRanking(entidades: EntidadTasa[], opciones: { maxFilas: number; tope?: number; promedio?: number | null;
  descripcion: string; ordenTexto: string }): HTMLElement {
  const cont = document.createElement("div");
  cont.className = "ranking";
  // Escala común que no arranca en cero: las diferencias entre entidades son de décimas, así que se usan
  // puntos (no barras, que exigen base cero para no exagerar).
  const valores = entidades.map((e) => e.tasa_ea).filter((v): v is number => v != null);
  if (opciones.tope) valores.push(opciones.tope);
  const lo = Math.min(...valores), hi = Math.max(...valores);
  const pad = (hi - lo) * 0.06 || 0.5;
  const a = lo - pad, b = hi + pad;
  const pos = (v: number) => ((v - a) / (b - a)) * 100;
  let mostrarTodas = false;
  const pintar = () => {
    const filas = mostrarTodas ? entidades : entidades.slice(0, opciones.maxFilas);
    cont.innerHTML = `
      <table>
        <caption class="solo-lectores">${esc(opciones.descripcion)}</caption>
        <thead><tr>
          <th scope="col">Entidad</th>
          <th scope="col" class="num">Tasa E.A.</th>
          <th scope="col" class="barra-col ocultar-movil" aria-hidden="true"><span class="escala"><span style="left:${pos(lo)}%">${pct(lo)}</span><span style="left:${pos(hi)}%">${pct(hi)}</span></span></th>
          <th scope="col" class="num">4 semanas</th>
          <th scope="col" class="num ocultar-movil">Participación</th>
        </tr></thead>
        <tbody>${filas.map((e) => `
          <tr>
            <th scope="row"><span class="ent">${esc(e.entidad)}</span><span class="tipo">${esc(e.tipo)}</span></th>
            <td class="num fuerte">${pct(e.tasa_ea)}</td>
            <td class="barra-col ocultar-movil" aria-hidden="true"><span class="pista">
              ${opciones.promedio != null ? `<span class="prom" style="left:${pos(opciones.promedio)}%"></span>` : ""}
              ${opciones.tope ? `<span class="tope" style="left:${pos(opciones.tope)}%"></span>` : ""}
              ${e.tasa_ea != null ? `<span class="punto" style="left:${pos(e.tasa_ea)}%"></span>` : ""}
            </span></td>
            <td class="num cambio">${pp(e.cambio_pp)}</td>
            <td class="num ocultar-movil tenue">${pct(e.participacion_pct)}</td>
          </tr>`).join("")}
        </tbody>
      </table>
      <p class="nota-tabla">${esc(opciones.ordenTexto)}${opciones.promedio != null ? " La raya gris es el promedio del sistema." : ""}${opciones.tope ? " La raya negra es la tasa de usura." : ""}</p>
      ${entidades.length > opciones.maxFilas ? `<button type="button" class="enlace-boton">${mostrarTodas ? "Ver menos" : `Ver las ${entidades.length} entidades`}</button>` : ""}`;
    cont.querySelector("button")?.addEventListener("click", () => { mostrarTodas = !mostrarTodas; pintar(); });
  };
  pintar();
  return cont;
}

const RANGOS = [{ valor: "365", texto: "1 año" }, { valor: "1095", texto: "3 años" }, { valor: "todo", texto: "Todo" }];
const diasRango = (v: string) => (v === "todo" ? null : Number(v));

function seccion(id: string, titulo: string): HTMLElement {
  const s = document.createElement("section");
  s.id = id;
  s.className = "seccion";
  s.setAttribute("aria-labelledby", `${id}-titulo`);
  s.innerHTML = `<h2 id="${id}-titulo">${esc(titulo)}</h2>`;
  return s;
}

// --------------------------------------------------------------------------------------------------- CDT

function renderCDT(r: Resumen, series: SeriesCDT) {
  const plazos = r.cdt.plazos.filter((p) => [90, 180, 360, 361].includes(p.plazo_dias));
  if (!plazos.length) return { hero: null as HTMLElement | null, seccion: null as HTMLElement | null };
  let plazo = Number(leer("plazo")) || 360;
  if (!plazos.some((p) => p.plazo_dias === plazo)) plazo = plazos[plazos.length - 1].plazo_dias;

  const hero = document.createElement("section");
  hero.className = "hero";
  hero.setAttribute("aria-live", "polite");
  const frase = document.createElement("h1");
  frase.className = "frase";
  const apoyo = document.createElement("p");
  apoyo.className = "apoyo";

  const sec = seccion("cdt", "¿Dónde rinde más un CDT?");
  const intro = document.createElement("p");
  intro.className = "intro";
  intro.innerHTML = `Tasa efectiva anual promedio de los CDT que cada entidad emitió en los últimos
    ${r.cdt.ventana_dias ?? 7} días al ${esc(fecha(r.cdt.fecha))}, ponderada por monto. Solo entran entidades con al menos
    0,3% del monto captado en ese plazo.`;
  const tablaCaja = document.createElement("div");
  const graficaCaja = document.createElement("div");
  const controles = document.createElement("div");
  controles.className = "controles";
  sec.append(intro, tablaCaja, document.createElement("h3"), controles, graficaCaja);
  (sec.querySelector("h3") as HTMLElement).textContent = "Promedio del sistema semana a semana";

  let rango = leer("rango-cdt") || "1095";
  let comparar = "";
  const selEntidad = document.createElement("select");
  selEntidad.setAttribute("aria-label", "Comparar con una entidad");
  const etqSel = document.createElement("label");
  etqSel.className = "comparar";
  etqSel.append("Comparar con ", selEntidad);

  const redibujar = graficaLineas(graficaCaja, [], { titulo: "Tasa promedio de CDT del sistema", formatoY: (v) => pct(v) });
  const actualizarGrafica = () => {
    const base = series.sistema[String(plazo)] ?? [];
    const s: Serie[] = [{ nombre: "Sistema", puntos: recortar(base, diasRango(rango)), clase: "s1" }];
    const ent = series.entidades[String(plazo)]?.[comparar];
    if (comparar && ent) s.push({ nombre: comparar, puntos: recortar(ent, diasRango(rango)), clase: "s2" });
    redibujar(s);
  };

  const pintar = () => {
    const p = plazos.find((x) => x.plazo_dias === plazo)!;
    const top = p.entidades[0];
    const nombrePlazo = p.plazo_dias === 361 ? "más de 360 días" : p.nombre;
    frase.innerHTML = top
      ? `Un CDT a ${esc(nombrePlazo)} paga hasta <strong>${pct(top.tasa_ea)}</strong> efectivo anual en ${esc(top.entidad)}.`
      : `Un CDT a ${esc(nombrePlazo)}: sin datos esta semana.`;
    apoyo.innerHTML = `El promedio del sistema es <b>${pct(p.promedio_sistema)}</b>${p.cambio_pp != null
      ? ` (${pp(p.cambio_pp)} frente a hace cuatro semanas)` : ""}. Datos de la Superintendencia Financiera al
      ${esc(fecha(r.cdt.fecha))}.`;
    tablaCaja.replaceChildren(tablaRanking(p.entidades, { maxFilas: 12, promedio: p.promedio_sistema, descripcion: `CDT a ${p.nombre}, de mayor a menor tasa`,
      ordenTexto: "Ordenado de mayor a menor tasa." }));
    const opciones = Object.keys(series.entidades[String(plazo)] ?? {}).sort();
    if (!opciones.includes(comparar)) comparar = "";
    selEntidad.innerHTML = `<option value="">Ninguna</option>` + opciones.map((o) =>
      `<option${o === comparar ? " selected" : ""}>${esc(o)}</option>`).join("");
    etqSel.hidden = !opciones.length;
    actualizarGrafica();
  };
  selEntidad.addEventListener("change", () => { comparar = selEntidad.value; actualizarGrafica(); });
  controles.append(selector("Rango de tiempo", RANGOS, rango, (v) => { rango = v; guardar("rango-cdt", v); actualizarGrafica(); }), etqSel);
  const control = document.createElement("div");
  control.className = "hero-control";
  control.append(selector("Plazo del CDT",
    plazos.map((x) => ({ valor: x.plazo_dias, texto: x.plazo_dias === 361 ? "Más de 360 días" : x.nombre })), plazo,
    (v) => { plazo = v; guardar("plazo", String(v)); pintar(); }));
  hero.append(control, frase, apoyo);
  pintar();
  return { hero, seccion: sec };
}

// --------------------------------------------------------------------------------------------------- Crédito

function renderCredito(r: Resumen, series: Record<string, Punto[]>, hu: HistoricoUsura): HTMLElement | null {
  const prods = r.credito.productos.filter((p) => p.entidades.length);
  if (!prods.length) return null;
  // Cada producto se compara con su propia usura: el consumo de bajo monto tiene un tope distinto
  const esBajoMonto = (prod: string) => prod.toLowerCase().includes("bajo monto");
  const usuraDe = (prod: string): { vig: Usura | null; hist: Punto[] } => esBajoMonto(prod)
    ? { vig: r.usura.vigente_bajo_monto, hist: hu.consumo_bajo_monto }
    : { vig: r.usura.vigente, hist: hu.consumo_y_ordinario };
  const sec = seccion("credito", "¿Cuánto cuesta endeudarse?");
  let actual = leer("producto") || prods[0].producto;
  if (!prods.some((p) => p.producto === actual)) actual = prods[0].producto;
  const frase = document.createElement("p");
  frase.className = "respuesta";
  const tablaCaja = document.createElement("div");
  const graficaCaja = document.createElement("div");
  const sub = document.createElement("h3");
  sub.textContent = "Promedio del sistema frente a la usura";
  const controles = document.createElement("div");
  controles.className = "controles";
  let rango = leer("rango-credito") || "1095";
  const redibujar = graficaLineas(graficaCaja, [], { titulo: "Tasa promedio de crédito y tasa de usura", formatoY: (v) => pct(v) });
  const nota = document.createElement("p");
  nota.className = "nota";
  const actualizarGrafica = () => {
    const usura = usuraDe(actual).hist;
    const s: Serie[] = [{ nombre: actual, puntos: recortar(series[actual] ?? [], diasRango(rango)), clase: "s1" }];
    const desde = s[0].puntos[0]?.[0];
    if (usura.length && desde) {
      const previo = [...usura].reverse().find((p) => p[0] <= desde);
      const u = [...(previo ? [[desde, previo[1]] as Punto] : []), ...usura.filter((p) => p[0] > desde)];
      s.push({ nombre: "Usura", puntos: u, clase: "s2", escalonada: true });
    }
    redibujar(s);
  };
  const pintar = () => {
    const p = prods.find((x) => x.producto === actual)!;
    const barato = p.entidades[0];
    const u = usuraDe(actual).vig;
    const tope = u?.usura_ea;
    frase.innerHTML = `En <b>${esc(p.producto)}</b>, la tasa más baja de la semana al ${esc(fecha(r.credito.fecha))}
      la cobró <b>${esc(barato.entidad)}</b>: ${pct(barato.tasa_ea)} E.A. El promedio del sistema fue ${pct(p.promedio_sistema)}
      ${p.cambio_pp != null ? `(${pp(p.cambio_pp)} en cuatro semanas)` : ""}${tope ? ` y el tope legal es ${pct(tope)}` : ""}.`;
    tablaCaja.replaceChildren(tablaRanking(p.entidades, { maxFilas: 12, tope, promedio: p.promedio_sistema, descripcion: `${p.producto}, de menor a mayor tasa`,
      ordenTexto: "Ordenado de menor a mayor tasa: la primera es la más barata. Es la tasa promedio que la entidad cobró en los créditos que desembolsó esa semana, no la que te ofrecerá a ti." }));
    nota.innerHTML = u ? `La tasa de usura para ${esBajoMonto(actual) ? "consumo de bajo monto" : "consumo y ordinario"} vigente desde el
      ${esc(fecha(u.desde))} es <b>${pct(u.usura_ea)}</b> efectivo anual: 1,5 veces el interés bancario corriente (${pct(u.ibc_ea)})
      que certifica la Superfinanciera. Cobrar por encima es delito.` : "";
    actualizarGrafica();
  };
  const selProd = selector("Producto de crédito", prods.map((p) => ({ valor: p.producto, texto: p.producto })), actual,
    (v) => { actual = v; guardar("producto", v); pintar(); });
  selProd.classList.add("envolver");
  controles.append(selector("Rango de tiempo", RANGOS, rango, (v) => { rango = v; guardar("rango-credito", v); actualizarGrafica(); }));
  sec.append(selProd, frase, tablaCaja, sub, controles, graficaCaja, nota);
  pintar();
  return sec;
}

// --------------------------------------------------------------------------------------------------- TRM

function renderTRM(r: Resumen, trm: Punto[]): HTMLElement | null {
  if (!r.trm) return null;
  const t = r.trm;
  const sec = seccion("trm", "El dólar oficial");
  const posicion = t.max_52s > t.min_52s ? (t.valor - t.min_52s) / (t.max_52s - t.min_52s) : 0.5;
  sec.insertAdjacentHTML("beforeend", `
    <p class="respuesta">La TRM del ${esc(fecha(t.fecha))} es <b>${pesos(t.valor)}</b>.
      En 30 días ${variacion(t.var_30d_pct)} y en un año ${variacion(t.var_1a_pct)}.</p>
    <div class="rango52" role="img" aria-label="En las últimas 52 semanas la TRM osciló entre ${pesos(t.min_52s)} y ${pesos(t.max_52s)}; hoy está ${posicion < 0.34 ? "cerca del mínimo" : posicion > 0.66 ? "cerca del máximo" : "en la mitad del rango"}.">
      <span class="r-min">${pesos(t.min_52s)}</span>
      <span class="r-pista"><span class="r-hoy" style="left:${posicion * 100}%"></span></span>
      <span class="r-max">${pesos(t.max_52s)}</span>
      <span class="r-texto">Rango de las últimas 52 semanas</span>
    </div>`);
  const controles = document.createElement("div");
  controles.className = "controles";
  const caja = document.createElement("div");
  let rango = leer("rango-trm") || "1095";
  const redibujar = graficaLineas(caja, [], { titulo: "TRM diaria", formatoY: (v) => `$${Math.round(v).toLocaleString("es-CO")}`, formatoTooltip: (v) => pesos(v) });
  const act = () => redibujar([{ nombre: "TRM", puntos: recortar(trm, diasRango(rango)), clase: "s1" }]);
  controles.append(selector("Rango de tiempo", [...RANGOS.slice(0, 2), { valor: "todo", texto: "Desde 2015" }], rango,
    (v) => { rango = v; guardar("rango-trm", v); act(); }));
  sec.append(controles, caja);
  act();
  return sec;
}

function variacion(x: number | null): string {
  if (x == null) return "no hay comparación";
  if (Math.abs(x) < 0.005) return "no cambió";
  return `${x > 0 ? "subió" : "bajó"} ${pct(Math.abs(x))}`;
}

// --------------------------------------------------------------------------------------------------- Movimientos y datos

function renderMovimientos(r: Resumen): HTMLElement | null {
  const { subidas, bajadas } = r.movimientos;
  if (!subidas.length && !bajadas.length) return null;
  const sec = seccion("movimientos", "Quién movió sus tasas en el último mes");
  const lista = (titulo: string, xs: typeof subidas) => xs.length ? `
    <div class="mov"><h3>${titulo}</h3><ol>${xs.map((m) => `
      <li><span class="ent">${esc(m.entidad)}</span><span class="grupo">${esc(m.grupo)}</span>
      <span class="num">${pct(m.tasa_ea)}</span><span class="num cambio">${pp(m.cambio_pp)}</span></li>`).join("")}</ol></div>` : "";
  sec.insertAdjacentHTML("beforeend", `
    <p class="intro">Cambios de las últimas cuatro semanas entre entidades con al menos 1% del monto del plazo o producto.
      En un CDT, subir es bueno para quien ahorra; en un crédito, para quien presta.</p>
    <div class="movs">${lista("Subieron", subidas)}${lista("Bajaron", bajadas)}</div>
    <p class="nota">El resumen semanal en texto está en <a href="${REPO}/blob/main/MOVIMIENTOS.md">MOVIMIENTOS.md</a>.</p>`);
  return sec;
}

function renderDatos(r: Resumen): HTMLElement {
  const sec = seccion("datos", "Datos abiertos");
  const base = new URL("data/", location.href).href;
  sec.insertAdjacentHTML("beforeend", `
    <p class="intro">Todo lo que ves aquí sale de archivos públicos que puedes usar en tus propios proyectos, sin registro.
      Se actualizan dos veces al día desde las fuentes de la Superintendencia Financiera.</p>
    <dl class="api">
      <dt><a href="${base}resumen.json">resumen.json</a></dt><dd>Rankings de CDT y crédito, usura vigente, TRM y movimientos.</dd>
      <dt><a href="${base}cdt_series.json">cdt_series.json</a></dt><dd>Promedio semanal del sistema por plazo y de las 12 entidades más grandes.</dd>
      <dt><a href="${base}credito_series.json">credito_series.json</a></dt><dd>Promedio semanal del sistema por producto de crédito.</dd>
      <dt><a href="${base}trm.json">trm.json</a></dt><dd>TRM diaria desde 2015.</dd>
      <dt><a href="${base}usura.json">usura.json</a></dt><dd>Histórico de la tasa de usura: consumo y ordinario, y consumo de bajo monto.</dd>
      <dt><a href="${REPO}/tree/main/data">data/ en GitHub</a></dt><dd>Datos crudos en CSV: CDT diario por entidad y plazo desde 2022, crédito semanal por entidad y producto desde julio de 2022, TRM desde 1991.</dd>
    </dl>
    <h3>Cómo se calcula</h3>
    <ul class="metodo">
      <li>Todas las tasas son efectivas anuales, tal como las reportan las entidades a la Superfinanciera.</li>
      <li>Los promedios se ponderan por monto: un CDT de $10.000 millones pesa más que uno de $1 millón.</li>
      <li>Son tasas de operaciones ya hechas (CDT emitidos y créditos desembolsados), no tasas ofrecidas en vitrina.</li>
      <li>Fuentes: <a href="https://www.datos.gov.co/d/axk9-g2nh">captación y CDT</a>,
        <a href="https://www.datos.gov.co/d/w9zh-vetq">tasas activas por tipo de crédito</a>,
        <a href="https://www.datos.gov.co/d/pare-7x5i">interés bancario corriente</a> y
        <a href="https://www.datos.gov.co/d/32sa-8pi3">TRM</a>.</li>
    </ul>
    <p class="tenue">Última actualización: ${esc(new Date(r.generado).toLocaleString("es-CO", { timeZone: "America/Bogota", dateStyle: "long", timeStyle: "short" })).replace(/\.$/, "")}.</p>`);
  return sec;
}

// --------------------------------------------------------------------------------------------------- arranque

async function iniciar() {
  try {
    const [r, cdtS, credS, trm, usura] = await Promise.all([
      json<Resumen>("resumen.json"), json<SeriesCDT>("cdt_series.json"), json<Record<string, Punto[]>>("credito_series.json"),
      json<Punto[]>("trm.json"), json<HistoricoUsura>("usura.json"),
    ]);
    const { hero, seccion: secCDT } = renderCDT(r, cdtS);
    app.replaceChildren(...[hero, secCDT, renderCredito(r, credS, usura), renderTRM(r, trm), renderMovimientos(r), renderDatos(r)]
      .filter((x): x is HTMLElement => !!x));
  } catch (e) {
    app.innerHTML = `<section class="hero"><p class="frase">No se pudieron cargar los datos.</p>
      <p class="apoyo">Recarga la página. Si el problema sigue, revisa el estado de la última actualización en
      <a href="${REPO}/actions">GitHub Actions</a>.</p></section>`;
    console.error(e);
  } finally {
    app.removeAttribute("aria-busy");
  }
}

iniciar();
