import { useEffect, useState } from 'react';
import { Producto, PrecioHistorico, fetchPriceHistory, formatCLP, getTiendaColor } from '../../services/api';
import s from './PriceHistoryModal.module.css';

interface Props {
  producto: Producto;
  onClose: () => void;
}

const STORES = ['Sodimac', 'Easy', 'Imperial'] as const;

const SVG_W = 600;
const SVG_H = 220;
const PAD = { l: 16, r: 16, t: 48, b: 36 };
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

  useEffect(() => {
    fetchPriceHistory(producto.id).then(h => {
      h.sort((a, b) => toUTCDay(a.fecha) - toUTCDay(b.fecha));
      setHistory(h);
      setLoading(false);
    });
  }, [producto.id]);

  const allPrices = history.map(h => h.precio);
  const maxPrecio = allPrices.length ? Math.max(...allPrices) : 1;
  const minPrecio = allPrices.length ? Math.min(...allPrices) : 0;
  const priceRange = maxPrecio - minPrecio;

  const allTimes = history.map(h => toUTCDay(h.fecha));
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
    STORES.map(store => [store, history.filter(h => h.tienda === store)])
  ) as Record<string, PrecioHistorico[]>;

  const uniqueDayMs = [...new Set(allTimes)].sort((a, b) => a - b);

  // Variación calculada por tienda (no entre tiendas)
  const tableRows = (() => {
    const last: Record<string, number> = {};
    const rows = [...history].sort((a, b) => toUTCDay(a.fecha) - toUTCDay(b.fecha)).map(h => {
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
              <div className={s.chartWrap}>
                <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className={s.chart}>
                  {/* Rejilla horizontal */}
                  {[0, 0.5, 1].map(pct => (
                    <line key={pct}
                      x1={PAD.l} y1={PAD.t + pct * CH}
                      x2={SVG_W - PAD.r} y2={PAD.t + pct * CH}
                      stroke="#e1e8f0" strokeWidth="1" strokeDasharray="4"
                    />
                  ))}

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
                            <g key={i}>
                              <circle cx={x} cy={y} r="6" fill={color} opacity="0.15" />
                              <circle cx={x} cy={y} r="3.5" fill={color} stroke="#fff" strokeWidth="1.5" />
                              <text x={x} y={y - 10} textAnchor="middle"
                                fontSize="9" fontWeight="700" fill={color}
                                fontFamily="JetBrains Mono,monospace">
                                {formatCLP(h.precio)}
                              </text>
                            </g>
                          );
                        })}
                      </g>
                    );
                  })}

                  {/* Eje X: fechas únicas a su posición proporcional */}
                  {uniqueDayMs.map(ms => (
                    <text key={ms}
                      x={singleDate ? PAD.l + CW / 2 : PAD.l + ((ms - minTime) / timeRange) * CW}
                      y={SVG_H - 4}
                      textAnchor="middle" fontSize="9" fill="#9BA8BA" fontFamily="sans-serif">
                      {utcDayLabel(ms)}
                    </text>
                  ))}
                </svg>
              </div>

              {/* Leyenda — solo tiendas con datos */}
              <div className={s.legend}>
                {STORES.filter(t => byStore[t].length > 0).map(t => (
                  <span key={t} className={s.legendItem}>
                    <span className={s.legendDot} style={{ background: getTiendaColor(t) }} />
                    {t}
                  </span>
                ))}
              </div>

              {/* Tabla con variación por tienda */}
              <table className={s.table}>
                <thead>
                  <tr><th>Fecha</th><th>Tienda</th><th>Precio</th><th>Variación</th></tr>
                </thead>
                <tbody>
                  {tableRows.map((row, i) => (
                    <tr key={i}>
                      <td className={s.monoCell}>{row.fecha.split('T')[0]}</td>
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
            </>
          )}
        </div>
      </div>
    </>
  );
}
