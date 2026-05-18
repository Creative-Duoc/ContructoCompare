import { Producto, TiendaPrecio, getBestPrice, getPrecioFinal, formatCLP, formatUF, getTiendaColor, formatProductName } from '../../services/api';
import { useQuote } from '../../hooks/useQuote';
import s from './ProductCard.module.css';

interface Props {
  producto: Producto;
  ufValue: number;
  showUF: boolean;
  onShowHistory: (producto: Producto) => void;
  animDelay?: number;
}

export default function ProductCard({ producto, ufValue, showUF, onShowHistory, animDelay = 0 }: Props) {
  const { addItem } = useQuote();
  const best = getBestPrice(producto);
  const maxPrecio = Math.max(...producto.tiendas.map(t => getPrecioFinal(t)));

  return (
    <article className={s.card} style={{ animationDelay: animDelay + 's' }}>

      {/* Header — HU1 AC2 */}
      <div className={s.cardHeader}>
        <span className={s.categoryBadge}>{producto.categoria}</span>
        <span className={s.sku}>{producto.sku}</span>
      </div>

      {/* Imagen del Producto */}
      <div className={s.imageContainer}>
        <img 
          src={producto.foto_url || 'https://via.placeholder.com/200x200?text=Sin+Foto'} 
          alt={producto.nombre}
          className={s.productImage}
          loading="lazy"
        />
      </div>

      <div>
        <a 
          href={best.url_producto} 
          target="_blank" 
          rel="noopener noreferrer" 
          className={s.nameLink}
          title={`Ver mejor precio en ${best.tienda}`}
        >
          <div className={s.name}>{formatProductName(producto.nombre)}</div>
        </a>
        <div className={s.brand}>{formatProductName(producto.marca)} · Por {producto.unidad}</div>
      </div>

      {/* Tabla comparativa multitienda — HU2 */}
      <div className={s.compareTable}>
        {producto.tiendas.map(tienda => {
          const final = getPrecioFinal(tienda);
          const isBest = tienda.tienda === best.tienda && final === getPrecioFinal(best); // HU3
          const saving = maxPrecio - final;
          const savingPct = Math.round((saving / maxPrecio) * 100);

          return (
            <div
              key={tienda.tienda}
              className={[s.compareRow, isBest && s.bestPrice, !tienda.stock && s.noStock].filter(Boolean).join(' ')}
            >
              {/* HU3 — Badge MEJOR PRECIO */}
              {isBest && <span className={s.bestBadge}>✓ Mejor Precio</span>}

              {/* Todo el contenido de la tienda es un Link — HU2-AC4 */}
              <a 
                href={tienda.url_producto} 
                target="_blank" 
                rel="noopener noreferrer" 
                className={s.retailerLink}
                title={`Ir a la tienda ${tienda.tienda}`}
              >
                <span className={s.tiendaDot} style={{ background: getTiendaColor(tienda.tienda) }} />
                <span className={s.tiendaName}>{tienda.tienda}</span>

                {!tienda.stock && <span className={s.noStockTag}>Sin stock</span>}

                {/* HU2-AC2 — diferencia vs más caro */}
                {tienda.stock && saving > 0 && !isBest && (
                  <span className={s.savingsTag}>−{savingPct}%</span>
                )}

                <div className={s.tiendaPrices}>
                  {tienda.precio_oferta && (
                    <span className={s.precioOriginal}>{formatCLP(tienda.precio_real)}</span>
                  )}
                  <span className={[s.precioFinal, tienda.precio_oferta && s.oferta].filter(Boolean).join(' ')}>
                    {showUF ? formatUF(final, ufValue) : formatCLP(final)}
                  </span>
                  {!showUF && ufValue > 0 && (
                    <span className={s.precioUF}>{formatUF(final, ufValue)}</span>
                  )}
                </div>
              </a>

              {/* Botón dedicado para agregar a cotización */}
              {tienda.stock && (
                <button 
                  className={s.addToQuoteBtn}
                  onClick={() => addItem(producto, tienda)}
                  title="Agregar a mi cotización"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* HU2-AC3 — fecha actualización */}
      <div className={s.updatedAt}>
        Actualizado: {producto.tiendas[0].fecha_actualizacion}
      </div>

      {/* HU9 — Ver historial */}
      <button className={s.historyBtn} onClick={() => onShowHistory(producto)}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Ver historial de precios
      </button>

    </article>
  );
}
