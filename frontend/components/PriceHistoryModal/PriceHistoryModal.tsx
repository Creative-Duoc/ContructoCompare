import { useEffect, useState, useMemo } from 'react';
import { Producto, PrecioHistorico, fetchPriceHistory, formatCLP, getTiendaColor } from '../../services/api';
import s from './PriceHistoryModal.module.css';

interface Props {
  producto: Producto;
  onClose: () => void;
}

const STORES = ['Sodimac', 'Easy', 'Imperial'] as const;

type DateRange = '7d' | '30d' | '90d' | 'all';

const SVG_W = 640;
const SVG_H = 240;
const PAD = { l: 70, r: 20, t: 20, b: 40 };
const CW = SVG_W - PAD.l - PAD.r;
const CH = SVG_H - PAD.t - PAD.b;

function toUTCDay(fecha: string): number {
  const d = new Date(fecha);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

function utcDayLabel(ms: number): string {
  const d = new Date(ms);
  return new Date(
    d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 12
  ).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
}

export default function PriceHistoryModal({ producto, onClose }: Props) {
  const [history, setHistory] = useState<PrecioHistorico[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState<DateRange>('all');
  const [hoveredPoint, setHoveredPoint] = useState<{
    x: number;
    y: number;
    data: PrecioHistorico;
  } | null>(null);

  useEffect(() => {
    fetchPriceHistory(producto.id).then(h => {
      h.sort((a, b) => toUTCDay(a.fecha) - toUTCDay(b.fecha));
      setHistory(h);
      setLoading(false);
    });
  }, [producto.id]);

  const filteredHistory = useMemo(() => {
    if (dateRange === 'all') return history;
    const days = dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : 90;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    return history.filter(h => new Date(h.fecha) >= cutoff);
  }, [history, dateRange]);

  const allPrices = filteredHistory.map(h => h.precio);
  const maxPrecio = allPrices.length ? Math.max(...allPrices) : 1;
  const minPrecio = allPrices.length ? Math.min(...allPrices) : 0;
  const priceRange = maxPrecio - minPrecio;

  const allTimes = filteredHistory.map(h => toUTCDay(h.fecha));
  const minTime = allTimes.length ? Math.min(...allTimes) : 0;
  const maxTime = allTimes.length ? Math.max(...allTimes) : 0;
  const timeRange = maxTime - minTime;
  const singleDate = timeRange === 0;

  function toX(fecha: string): number {
    if (singleDate) return PAD.l + CW / 2;
    return PAD.l + ((toUTCDay(fecha) - minTime) / timeRange) * CW;
  }

  function toY(precio: number): number {
    if (!priceRange) return PAD.t + CH / 2;
    return PAD.t + CH - ((precio - minPrecio) / priceRange) * CH;
  }

  const byStore = Object.fromEntries(
    STORES.map(store => [store, filteredHistory.filter(h => h.tienda === store)])
  ) as Record<string, PrecioHistorico[]>;

  const uniqueDayMs = [...new Set(allTimes)].sort((a, b) => a - b);

  const yTicks = useMemo(() => {
    if (!allPrices.length) return [];
    const steps = 4;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const v = minPrecio + (priceRange * i) / steps;
      return Math.round(v);
    });
  }, [minPrecio, maxPrecio, allPrices.length]);

  const xTickMs = useMemo(() => {
    if (uniqueDayMs.length <= 5) return uniqueDayMs;
    const step = Math.floor(uniqueDayMs.length / 4);
    const ticks = [uniqueDayMs[0]];
    for (let i = 1; i < 4; i++) ticks.push(uniqueDayMs[i * step]);
    ticks.push(uniqueDayMs[uniqueDayMs.length - 1]);
    return ticks;
  }, [uniqueDayMs]);

  const tableRows = (() => {
    const last: Record<string, number> = {};
    const rows = [...filteredHistory].sort((a, b) => toUTCDay(a.fecha) - toUTCDay(b.fecha)).map(h => {
      const prev = last[h.tienda];
      const diff = prev !== undefined ? h.precio - prev : null;
      last[h.tienda] = h.precio;
      return { ...h, diff };
    });
    return rows.reverse();
  })();

  return (
    <>
      <div className={s.overlay} onClick={onClose} />
      <div className={s.modal}>
        <div className={s.header}>
          <div>
            <h2 className={s.title}>Historial de Precios</h2>
            <p className={s.subtitle}>{producto.nombre}</p>
          </div>
          <button className={s.closeBtn} onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className={s.body}>
          {loading ? (
            <div className={s.loading}>
              <div className={s.spinner} />
              <p>Cargando historial…</p>
            </div>
          ) : history.length === 0 ? (
            <div className={s.empty}>
              <p>Datos históricos en proceso de recolección.</p>
              <p className={s.emptyHint}>Este producto aún no tiene suficiente historial de precios registrado.</p>
            </div>
          ) : (
            <>
              {/* Filtros de rango de fecha — HU-I5.1 */}
              <div className={s.filters}>
                {([
                  { v: '7d', label: '7 días' },
                  { v: '30d', label: '30 días' },
                  { v: '90d', label: '90 días' },
                  { v: 'all', label: 'Todo' },
                ] as const).map(opt => (
                  <button
                    key={opt.v}
                    className={[s.filterBtn, dateRange === opt.v && s.filterActive].filter(Boolean).join(' ')}
                    onClick={() => setDateRange(opt.v)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              {filteredHistory.length === 0 ? (
                <div className={s.empty}>
                  <p>Sin datos en este rango.</p>
                  <p className={s.emptyHint}>Prueba seleccionando un rango mayor.</p>
                </div>
              ) : (
                <>
                  {/* Gráfico SVG multi-tienda — HU9-AC1 + HU-I5.1 */}
                  <div className={s.chartWrap}>
                    <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className={s.chart}>
                      {/* Grid horizontal + etiquetas eje Y */}
                      {yTicks.map((tick, i) => {
                        const y = toY(tick);
                        return (
                          <g key={`y-${i}`}>
                            <line
                              x1={PAD.l} y1={y}
                              x2={SVG_W - PAD.r} y2={y}
                              stroke="#e1e8f0" strokeWidth="1"
                              strokeDasharray={i === 0 ? '0' : '3'}
                            />
                            <text
                              x={PAD.l - 8} y={y + 4}
                              textAnchor="end" fontSize="9" fill="#748194"
                              fontFamily="JetBrains Mono, monospace"
                            >
                              {formatCLP(tick)}
                            </text>
                          </g>
                        );
                      })}

                      {/* Línea base eje X */}
                      <line
                        x1={PAD.l} y1={SVG_H - PAD.b}
                        x2={SVG_W - PAD.r} y2={SVG_H - PAD.b}
                        stroke="#cbd5e1" strokeWidth="1"
                      />

                      {/* Una polyline + puntos por tienda */}
                      {STORES.map(store => {
                        const entries = byStore[store];
                        if (!entries.length) return null;
                        const color = getTiendaColor(store);
                        const pts = entries.map(h => `${toX(h.fecha)},${toY(h.precio)}`).join(' ');

                        return (
                          <g key={store}>
                            {entries.length > 1 && (
                              <polyline
                                fill="none" stroke={color} strokeWidth="2.5"
                                strokeLinecap="round" strokeLinejoin="round"
                                points={pts}
                              />
                            )}
                            {entries.map((h, i) => {
                              const x = toX(h.fecha);
                              const y = toY(h.precio);
                              return (
                                <circle
                                  key={i}
                                  cx={x} cy={y} r="4.5"
                                  fill={color} stroke="#fff" strokeWidth="2"
                                  className={s.point}
                                  onMouseEnter={() => setHoveredPoint({ x, y, data: h })}
                                  onMouseLeave={() => setHoveredPoint(null)}
                                />
                              );
                            })}
                          </g>
                        );
                      })}

                      {/* Etiquetas eje X */}
                      {xTickMs.map(ms => (
                        <text key={ms}
                          x={singleDate ? PAD.l + CW / 2 : PAD.l + ((ms - minTime) / timeRange) * CW}
                          y={SVG_H - PAD.b + 18}
                          textAnchor="middle" fontSize="9" fill="#9BA8BA"
                        >
                          {utcDayLabel(ms)}
                        </text>
                      ))}

                      {/* Tooltip hover */}
                      {hoveredPoint && (
                        <g pointerEvents="none">
                          <rect
                            x={Math.min(Math.max(hoveredPoint.x - 60, 5), SVG_W - 125)}
                            y={Math.max(hoveredPoint.y - 56, 5)}
                            width="120" height="46" rx="6"
                            fill="#1e3a5f" opacity="0.96"
                          />
                          <text
                            x={Math.min(Math.max(hoveredPoint.x, 65), SVG_W - 65)}
                            y={Math.max(hoveredPoint.y - 38, 23)}
                            textAnchor="middle" fontSize="10" fontWeight="700"
                            fill={getTiendaColor(hoveredPoint.data.tienda)}
                          >
                            {hoveredPoint.data.tienda}
                          </text>
                          <text
                            x={Math.min(Math.max(hoveredPoint.x, 65), SVG_W - 65)}
                            y={Math.max(hoveredPoint.y - 23, 38)}
                            textAnchor="middle" fontSize="11" fontWeight="700"
                            fill="#fff" fontFamily="JetBrains Mono, monospace"
                          >
                            {formatCLP(hoveredPoint.data.precio)}
                          </text>
                          <text
                            x={Math.min(Math.max(hoveredPoint.x, 65), SVG_W - 65)}
                            y={Math.max(hoveredPoint.y - 10, 51)}
                            textAnchor="middle" fontSize="9" fill="#cbd5e1"
                          >
                            {utcDayLabel(toUTCDay(hoveredPoint.data.fecha))}
                          </text>
                        </g>
                      )}
                    </svg>
                  </div>

                  {/* Leyenda con contador por tienda */}
                  <div className={s.legend}>
                    {STORES.map(t => {
                      const count = byStore[t].length;
                      return (
                        <span
                          key={t}
                          className={[s.legendItem, count === 0 && s.legendInactive].filter(Boolean).join(' ')}
                        >
                          <span className={s.legendDot} style={{ background: getTiendaColor(t) }} />
                          {t} <span className={s.legendCount}>({count})</span>
                        </span>
                      );
                    })}
                  </div>

                  {/* Tabla con variación por tienda */}
                  <div className={s.tableWrap}>
                  <table className={s.table}>
                    <thead>
                      <tr><th>Fecha</th><th>Tienda</th><th>Precio</th><th>Variación</th></tr>
                    </thead>
                    <tbody>
                      {tableRows.map((row, i) => (
                        <tr key={i}>
                          <td className={s.monoCell}>{utcDayLabel(toUTCDay(row.fecha))}</td>
                          <td>
                            <span style={{ color: getTiendaColor(row.tienda), fontWeight: 600 }}>
                              {row.tienda}
                            </span>
                          </td>
                          <td className={s.monoCell}>{formatCLP(row.precio)}</td>
                          <td>
                            {row.diff !== null && row.diff !== 0 && (
                              <span className={row.diff > 0 ? s.up : s.down}>
                                {row.diff > 0 ? '↑' : '↓'} {formatCLP(Math.abs(row.diff))}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
