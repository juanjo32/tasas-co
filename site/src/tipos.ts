export type Punto = [string, number | null];

export interface EntidadTasa {
  entidad: string;
  tipo: string;
  tasa_ea: number | null;
  cambio_pp: number | null;
  participacion_pct: number | null;
}

export interface PlazoCDT {
  plazo_dias: number;
  nombre: string;
  promedio_sistema: number | null;
  cambio_pp: number | null;
  entidades: EntidadTasa[];
}

export interface ProductoCredito {
  producto: string;
  producto_fuente: string;
  tipo_credito: string;
  promedio_sistema: number | null;
  cambio_pp: number | null;
  entidades: EntidadTasa[];
}

export interface Movimiento extends EntidadTasa {
  grupo: string;
}

export interface Resumen {
  generado: string;
  fuente: string;
  trm: {
    fecha: string; valor: number; var_dia_pct: number | null; var_30d_pct: number | null; var_1a_pct: number | null;
    min_52s: number; max_52s: number; promedio_52s: number;
  } | null;
  usura: { vigente: Usura | null; vigente_bajo_monto: Usura | null };
  cdt: { fecha: string | null; ventana_dias?: number; plazos: PlazoCDT[] };
  credito: { fecha: string | null; comparado_con?: string | null; productos: ProductoCredito[] };
  movimientos: { subidas: Movimiento[]; bajadas: Movimiento[] };
}

export interface SeriesCDT {
  sistema: Record<string, Punto[]>;
  entidades: Record<string, Record<string, Punto[]>>;
}

export interface Usura { modalidad: string; desde: string; hasta: string | null; ibc_ea: number; usura_ea: number; resolucion: string }

export interface HistoricoUsura { consumo_y_ordinario: Punto[]; consumo_bajo_monto: Punto[] }
