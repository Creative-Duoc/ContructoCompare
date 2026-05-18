import { useEffect, useState } from 'react';
import { useQuote } from '../../hooks/useQuote';
import { useAuth } from '../../hooks/useAuth';
import { CotizacionApi, Producto, QuoteItem, TiendaPrecio, fetchQuotes, formatCLP, formatUF, getPrecioFinal, getTiendaColor, retailerIdToName, retailerNameToId, searchProducts, updateQuote, formatProductName } from '../../services/api';
import s from './QuotePanel.module.css';

interface Props {
  onClose: () => void;
  ufValue: number;
  showUF: boolean;
  onToggleUF: () => void;
}

export default function QuotePanel({ onClose, ufValue, showUF, onToggleUF }: Props) {
  const { items, removeItem, updateQty, clearQuote, saveQuote, setItems, totalCLP } = useQuote();
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [savedQuotes, setSavedQuotes] = useState<CotizacionApi[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [productMap, setProductMap] = useState<Map<string, Producto>>(new Map());
  const [activeQuoteId, setActiveQuoteId] = useState<number | null>(null);

  useEffect(() => {
    if (!savedOpen || !user) return;

    async function loadSaved() {
      setLoadingSaved(true);
      try {
        const [quotes, products] = await Promise.all([
          fetchQuotes(),
          searchProducts('', 'Todos'),
        ]);
        setSavedQuotes(quotes);
        setProductMap(new Map(products.map(p => [p.id, p])));
      } catch (error) {
        console.error('Error cargando cotizaciones:', error);
      } finally {
        setLoadingSaved(false);
      }
    }

    loadSaved();
  }, [savedOpen, user]);

  function buildQuoteItems(detalles: CotizacionApi['detalles']): QuoteItem[] {
    const result: QuoteItem[] = [];

    detalles.forEach(det => {
      const product = productMap.get(String(det.id_producto_maestro));
      if (!product) return;
      const storeName = retailerIdToName(det.id_retailer);
      const store = product.tiendas.find(t => t.tienda === storeName) || product.tiendas[0];
      if (!store) return;
      result.push({ producto: product, tienda_seleccionada: store, cantidad: det.cantidad });
    });

    return result;
  }

  function handleLoadQuote(quote: CotizacionApi) {
    const nextItems = buildQuoteItems(quote.detalles);
    setItems(nextItems);
    setActiveQuoteId(quote.id_cotizacion);
  }

  function handleNewQuote() {
    clearQuote();
    setActiveQuoteId(null);
  }

  function handleRetailerChange(index: number, retailerName: string) {
    const selected = items[index];
    if (!selected) return;
    const candidate = selected.producto.tiendas.find(t => t.tienda === retailerName);
    if (!candidate) return;
    const nextItems = items.map((item, idx) =>
      idx === index ? { ...item, tienda_seleccionada: candidate } : item
    );
    setItems(nextItems);
  }

  // HU7 — Guardar cotización
  async function handleSave() {
    if (!user) return;
    const defaultName = activeQuoteId
      ? (savedQuotes.find(q => q.id_cotizacion === activeQuoteId)?.nombre_proyecto || 'Cotización sin nombre')
      : 'Cotización sin nombre';
    const nombre = prompt('Nombre del proyecto (ej: Obra Casa Maipú):', defaultName) ?? defaultName;
    setSaving(true);
    try {
      if (activeQuoteId) {
        const detalles = items.map(item => {
          const retailerId = retailerNameToId(item.tienda_seleccionada.tienda);
          if (!retailerId) {
            throw new Error(`Retailer no soportado: ${item.tienda_seleccionada.tienda}`);
          }
          return {
            id_producto_maestro: Number(item.producto.id),
            id_retailer: retailerId,
            cantidad: item.cantidad,
          };
        });
        const updated = await updateQuote(activeQuoteId, {
          nombre_proyecto: nombre,
          detalles,
        });
        setSavedQuotes(prev => prev.map(q => q.id_cotizacion === updated.id_cotizacion ? updated : q));
        alert('✓ Cotización actualizada');
      } else {
        const result = await saveQuote(nombre);
        if (!result.success) {
          alert(result.error || 'No se pudo guardar la cotización.');
          return;
        }
        setActiveQuoteId(null);
        alert('✓ Cotización guardada en "Mis Proyectos"');
      }
      onClose();
    } finally {
      setSaving(false);
    }
  }

  // HU10 — Exportar PDF
  function handleExportPDF() {
    const date = new Date().toLocaleDateString('es-CL');
    const rows = items.map(item => {
      const final = getPrecioFinal(item.tienda_seleccionada);
      const total = final * item.cantidad;
      return `<tr>
        <td>${formatProductName(item.producto.nombre)}</td>
        <td>${item.tienda_seleccionada.tienda}</td>
        <td style="text-align:center">${item.cantidad}</td>
        <td style="text-align:right">${formatCLP(final)}<br/><span style="color:#6b7280;font-size:.82em">${formatUF(final, ufValue)}</span></td>
        <td style="text-align:right">${formatCLP(total)}<br/><span style="color:#6b7280;font-size:.82em">${formatUF(total, ufValue)}</span></td>
      </tr>`;
    }).join('');

    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"/>
    <title>Cotización ConstructoCompare PRO</title>
    <style>
      body{font-family:Arial,sans-serif;padding:32px;color:#1E3A5F;}
      h1{color:#1E3A5F;} span.orange{color:#F57C00;}
      table{width:100%;border-collapse:collapse;margin-top:24px;}
      th{background:#1E3A5F;color:#fff;padding:10px 12px;text-align:left;}
      td{padding:9px 12px;border-bottom:1px solid #eee;}
      tr:nth-child(even) td{background:#f8f9fb;}
      .total td{font-weight:bold;background:#FFF3E0;color:#E65100;font-size:1.1em;}
      .footer{margin-top:32px;font-size:.85em;color:#888;}
      .actions{display:flex;gap:10px;align-items:center;margin:16px 0 8px;}
      .btn{border:1px solid #e5e7eb;background:#fff;border-radius:8px;padding:8px 12px;font-size:.85rem;cursor:pointer;}
      .btn.primary{background:#1E3A5F;color:#fff;border-color:#1E3A5F;}
      .note{font-size:.8rem;color:#6b7280;}
      @media print {.actions,.note{display:none;} body{padding:16px;}}
    </style></head><body>
    <h1>ConstructoCompare <span class="orange">PRO</span></h1>
    <p><strong>Proyecto:</strong> Cotización</p>
    <p><strong>Fecha:</strong> ${date}</p>
    <p><strong>UF del día:</strong> ${formatCLP(ufValue)}</p>
    <div class="actions">
      <button class="btn primary" onclick="window.print()">Imprimir / Guardar PDF</button>
      <button class="btn" onclick="window.close()">Cerrar</button>
    </div>
    <div class="note">Tip: usa "Imprimir" y elige "Guardar como PDF".</div>
    <table>
      <thead><tr><th>Producto</th><th>Tienda</th><th>Cant.</th><th>P. Unitario (CLP/UF)</th><th>Subtotal (CLP/UF)</th></tr></thead>
      <tbody>${rows}
        <tr class="total"><td colspan="4">TOTAL</td><td>${formatCLP(totalCLP)}<br/>${formatUF(totalCLP, ufValue)}</td></tr>
      </tbody>
    </table>
    <div class="footer">Cotización generada por ConstructoCompare PRO<br/>
    Los precios son referenciales. Verifique disponibilidad en cada tienda.</div>
    </body></html>`;

    const win = window.open('', '_blank');
    if (win) { win.document.write(html); win.document.close(); }
  }

  return (
    <>
      <div className={s.overlay} onClick={onClose} />
      <aside className={s.panel}>

        <div className={s.header}>
          <h2>Mi Cotización {items.length > 0 && `(${items.length})`}</h2>
          <button className={s.closeBtn} onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className={s.savedSection}>
          <button className={s.savedToggle} onClick={() => setSavedOpen(v => !v)}>
            <span>Mis cotizaciones</span>
            <span className={s.savedChevron}>{savedOpen ? '▾' : '▸'}</span>
          </button>
          {savedOpen && (
            <div className={s.savedPanel}>
              <div className={s.savedActions}>
                <button className={s.newQuoteBtn} onClick={handleNewQuote}>Nueva cotización</button>
                <button className={s.refreshBtn} onClick={() => setSavedOpen(false)}>Actualizar</button>
              </div>
              {loadingSaved && <div className={s.savedEmpty}>Cargando…</div>}
              {!loadingSaved && savedQuotes.length === 0 && (
                <div className={s.savedEmpty}>Aún no tienes cotizaciones guardadas.</div>
              )}
              {!loadingSaved && savedQuotes.map(quote => (
                <div key={quote.id_cotizacion} className={s.savedRow}>
                  <div>
                    <strong>{quote.nombre_proyecto}</strong>
                    <span>{new Date(quote.fecha_creacion).toLocaleDateString('es-CL')}</span>
                  </div>
                  <button className={s.loadBtn} onClick={() => handleLoadQuote(quote)}>Cargar</button>
                </div>
              ))}
            </div>
          )}
          {activeQuoteId && (
            <div className={s.activeHint}>Editando cotización #{activeQuoteId}</div>
          )}
        </div>

        {/* Items — HU4 */}
        <div className={s.items}>
          {items.length === 0 ? (
            <div className={s.empty}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <p>Tu cotización está vacía.<br/>Haz clic en una tienda para agregar productos.</p>
            </div>
          ) : items.map((item, i) => {
            const final = getPrecioFinal(item.tienda_seleccionada);
            const color = getTiendaColor(item.tienda_seleccionada.tienda);
            return (
              <div key={i} className={s.item}>
                <div className={s.itemInfo}>
                  <a
                    className={s.itemName}
                    href={item.tienda_seleccionada.url_producto}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Ver en ${item.tienda_seleccionada.tienda}`}
                  >
                    {formatProductName(item.producto.nombre)}
                  </a>
                  <div className={s.itemStore} style={{ color }}>{item.tienda_seleccionada.tienda}</div>
                  <select
                    className={s.itemSelect}
                    value={item.tienda_seleccionada.tienda}
                    onChange={e => handleRetailerChange(i, e.target.value)}
                  >
                    {item.producto.tiendas.map(tienda => (
                      <option key={tienda.tienda} value={tienda.tienda}>
                        {tienda.tienda}
                      </option>
                    ))}
                  </select>
                  {/* HU5 — controles cantidad */}
                  <div className={s.qtyRow}>
                    <button className={s.qtyBtn} onClick={() => updateQty(i, -1)}>−</button>
                    <span className={s.qtyVal}>{item.cantidad}</span>
                    <button className={s.qtyBtn} onClick={() => updateQty(i, 1)}>+</button>
                    <span className={s.itemSubtotal}>
                      {showUF ? formatUF(final * item.cantidad, ufValue) : formatCLP(final * item.cantidad)}
                    </span>
                  </div>
                </div>
                <button className={s.removeBtn} onClick={() => removeItem(i)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 6h18M19 6l-1 14H6L5 6M10 11v6M14 11v6M9 6V4h6v2"/>
                  </svg>
                </button>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className={s.footer}>
            {/* HU6 — Switch UF */}
            <div className={s.ufSwitch}>
              <span>Ver precios en UF (1 UF = {formatCLP(ufValue)})</span>
              <label className={s.switch}>
                <input type="checkbox" checked={showUF} onChange={onToggleUF} />
                <span className={s.slider} />
              </label>
            </div>

            {/* Totales */}
            <div className={s.totals}>
              <div className={s.totalRow}>
                <span className={s.totalLabel}>Total</span>
                <div>
                  <div className={s.totalCLP}>{formatCLP(totalCLP)}</div>
                  <div className={s.totalUF}>{formatUF(totalCLP, ufValue)}</div>
                </div>
              </div>
            </div>

            {/* HU7 — Guardar */}
            <button className={s.saveBtn} onClick={handleSave} disabled={saving || !user}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
              </svg>
              {saving ? 'Guardando…' : 'Guardar como proyecto'}
            </button>

            {/* HU10 — Exportar PDF */}
            <button className={s.pdfBtn} onClick={handleExportPDF}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
              Exportar PDF
            </button>

            <button className={s.clearBtn} onClick={clearQuote}>Vaciar cotización</button>
          </div>
        )}
      </aside>
    </>
  );
}
