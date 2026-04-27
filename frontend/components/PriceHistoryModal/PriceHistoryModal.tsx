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
              {/* Gráfico de línea SVG — HU9-AC1 */}
              <div className={s.chartWrap}>
                <svg viewBox={`0 0 ${history.length * 80} 150`} className={s.chart}>
                  {/* Líneas de fondo (rejilla) */}
                  <line x1="0" y1="120" x2={history.length * 80} y2="120" stroke="#e1e8f0" strokeWidth="1" strokeDasharray="4" />
                  <line x1="0" y1="40" x2={history.length * 80} y2="40" stroke="#e1e8f0" strokeWidth="1" strokeDasharray="4" />
                  
                  {/* Dibujar la línea de tendencia */}
                  {(() => {
                    const points = history.map((h, i) => {
                      const x = i * 80 + 40;
                      const y = 120 - ((h.precio - minPrecio) / (maxPrecio - minPrecio || 1)) * 80;
                      return `${x},${y}`;
                    }).join(' ');
                    
                    return (
                      <polyline
                        fill="none"
                        stroke="#1565C0"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        points={points}
                      />
                    );
                  })()}

                  {/* Dibujar los puntos y etiquetas */}
                  {history.map((h, i) => {
                    const x = i * 80 + 40;
                    const y = 120 - ((h.precio - minPrecio) / (maxPrecio - minPrecio || 1)) * 80;
                    const color = getTiendaColor(h.tienda);
                    
                    return (
                      <g key={i}>
                        {/* Sombra del punto */}
                        <circle cx={x} cy={y} r="6" fill={color} opacity="0.2" />
                        {/* Punto principal */}
                        <circle cx={x} cy={y} r="4" fill={color} stroke="#fff" strokeWidth="2" />
                        
                        {/* Etiqueta de precio */}
                        <text x={x} y={y - 12} textAnchor="middle"
                          fontSize="10" fontWeight="700" fill="#2d3748" fontFamily="JetBrains Mono,monospace">
                          {formatCLP(h.precio)}
                        </text>
                        
                        {/* Fecha en el eje X */}
                        <text x={x} y={145} textAnchor="middle"
                          fontSize="9" fill="#9BA8BA" fontFamily="sans-serif">
                          {new Date(h.fecha).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' })}
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
