import { useEffect, useState } from 'react';
import { Producto, PrecioHistorico, fetchPriceHistory, formatCLP, getTiendaColor } from '../../services/api';
import s from './PriceHistoryModal.module.css';

interface Props {
  producto: Producto;
  onClose: () => void;
}

export default function PriceHistoryModal({ producto, onClose }: Props) {
  const [history, setHistory] = useState<PrecioHistorico[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPriceHistory(producto.id).then(h => { setHistory(h); setLoading(false); });
  }, [producto.id]);

  const maxPrecio = history.length ? Math.max(...history.map(h => h.precio)) : 1;
  const minPrecio = history.length ? Math.min(...history.map(h => h.precio)) : 0;

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
            // HU9-AC3
            <div className={s.empty}>
              <p>Datos históricos en proceso de recolección.</p>
              <p className={s.emptyHint}>Este producto aún no tiene suficiente historial de precios registrado.</p>
            </div>
          ) : (
            <>
              {/* Gráfico de barras simple SVG — HU9-AC1 */}
              <div className={s.chartWrap}>
                <svg viewBox={`0 0 ${history.length * 60} 120`} className={s.chart}>
                  {history.map((h, i) => {
                    const barH = ((h.precio - minPrecio) / (maxPrecio - minPrecio || 1)) * 80 + 10;
                    const y = 100 - barH;
                    const color = getTiendaColor(h.tienda);
                    return (
                      <g key={i}>
                        <rect x={i * 60 + 10} y={y} width={40} height={barH}
                          fill={color} rx={4} opacity={.85} />
                        <text x={i * 60 + 30} y={y - 4} textAnchor="middle"
                          fontSize="9" fill="#748194" fontFamily="JetBrains Mono,monospace">
                          ${Math.round(h.precio / 1000)}k
                        </text>
                        <text x={i * 60 + 30} y={114} textAnchor="middle"
                          fontSize="8" fill="#9BA8BA" fontFamily="sans-serif">
                          {h.fecha.slice(5)}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              </div>

              {/* Leyenda tiendas */}
              <div className={s.legend}>
                {['Sodimac','Easy','Imperial'].map(t => (
                  <span key={t} className={s.legendItem}>
                    <span className={s.legendDot} style={{ background: getTiendaColor(t) }} />
                    {t}
                  </span>
                ))}
              </div>

              {/* Tabla resumen — HU9-AC2 puntos alza/baja */}
              <table className={s.table}>
                <thead>
                  <tr><th>Fecha</th><th>Tienda</th><th>Precio</th><th>Variación</th></tr>
                </thead>
                <tbody>
                  {history.map((h, i) => {
                    const prev = history[i - 1];
                    const diff = prev ? h.precio - prev.precio : 0;
                    return (
                      <tr key={i}>
                        <td className={s.monoCell}>{h.fecha}</td>
                        <td><span style={{ color: getTiendaColor(h.tienda), fontWeight: 600 }}>{h.tienda}</span></td>
                        <td className={s.monoCell}>{formatCLP(h.precio)}</td>
                        <td>
                          {i > 0 && (
                            <span className={diff > 0 ? s.up : s.down}>
                              {diff > 0 ? '↑' : '↓'} {formatCLP(Math.abs(diff))}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </>
  );
}
