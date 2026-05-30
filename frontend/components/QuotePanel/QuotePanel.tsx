import { useState } from 'react';
import { useQuote, serializeQuoteItems } from '../../hooks/useQuote';
import { useAuth } from '../../hooks/useAuth';
import { formatCLP, formatUF, getPrecioFinal, getTiendaColor, updateQuote, formatProductName, QuoteItem } from '../../services/api';
import s from './QuotePanel.module.css';

interface Props {
  onClose: () => void;
  ufValue: number;
  showUF: boolean;
  onToggleUF: () => void;
}

export default function QuotePanel({ onClose, ufValue, showUF, onToggleUF }: Props) {
  const { 
    items, removeItem, updateQty, clearQuote, saveQuote, setItems, totalCLP, 
    activeQuoteId, setActiveQuoteId, initialSnapshot, setInitialSnapshot 
  } = useQuote();
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);

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
    if (!user || saving) return; // Guard de seguridad extra contra dobles clics
    
    setSaving(true);

    try {
      if (activeQuoteId) {
        const detalles = items.map(i => {
          let retailerId = 1;
          const tName = i.tienda_seleccionada.tienda.toLowerCase();
          if (tName.includes('easy')) retailerId = 2;
          if (tName.includes('imperial')) retailerId = 3;

          return {
            id_producto_maestro: Number(i.producto.id),
            id_retailer: retailerId,
            cantidad: i.cantidad
          };
        });

        await updateQuote(activeQuoteId, { detalles });
        
        // Actualizamos la "foto" global después de guardar
        setInitialSnapshot(serializeQuoteItems(items));
        // No mostramos alerta ni cerramos el panel para que el usuario pueda seguir editando
      } else {
        const nombre = prompt('Nombre del proyecto (ej: Obra Casa Maipú):', 'Cotización sin nombre');
        if (nombre === null) {
          setSaving(false);
          return;
        }
        
        const finalName = nombre.trim() || 'Cotización sin nombre';
        
        const result = await saveQuote(finalName);
        if (!result.success) {
          alert(result.error || 'No se pudo guardar la cotización.');
          return;
        }
        // Al crear una nueva, el carrito se vacía automáticamente, así que cerramos el panel
        onClose();
      }
    } catch (err: any) {
      alert(err.message || 'Error al guardar la cotización');
    } finally {
      setSaving(false);
    }
  }

  function handleStopEditing() {
    if (activeQuoteId) {
      const currentItemsStr = serializeQuoteItems(items);
      const hasChanges = currentItemsStr !== initialSnapshot;

      if (hasChanges) {
        const confirmStop = window.confirm('Tienes cambios sin guardar en esta cotización. ¿Seguro que quieres dejar de editar y vaciar el carrito?');
        if (!confirmStop) return;
      }
    } else if (items.length > 0) {
       // Comportamiento normal si está creando una nueva (no tiene ID) pero tiene items
       const confirmStop = window.confirm('Tienes productos en el carrito que no has guardado. ¿Seguro que quieres vaciarlo?');
       if (!confirmStop) return;
    }
    
    clearQuote();
  }

  // HU10 — Exportar PDF (Abre pestaña y descarga)
  function handleExportPDF() {
    const date = new Date().toLocaleDateString('es-CL');
    const safeDate = date.replace(/\//g, '-');
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
      body{font-family:Arial,sans-serif;padding:32px;color:#1E3A5F;background:#f8f9fb;}
      .container { max-width: 800px; margin: 0 auto; background: #fff; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
      .pdf-content { padding: 20px; }
      h1{color:#1E3A5F;} span.orange{color:#F57C00;}
      table{width:100%;border-collapse:collapse;margin-top:24px;}
      th{background:#1E3A5F;color:#fff;padding:10px 12px;text-align:left;}
      td{padding:9px 12px;border-bottom:1px solid #eee;}
      tr:nth-child(even) td{background:#f8f9fb;}
      .total td{font-weight:bold;background:#FFF3E0;color:#E65100;font-size:1.1em;}
      .footer{margin-top:32px;font-size:.85em;color:#888;}
      .actions{display:flex;gap:10px;align-items:center;margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #eee;}
      .btn{border:1px solid #e5e7eb;background:#fff;border-radius:8px;padding:10px 16px;font-size:1rem;cursor:pointer;font-weight:bold;}
      .btn.primary{background:#1E3A5F;color:#fff;border-color:#1E3A5F;}
      .btn.primary:hover{background:#152a45;}
    </style></head><body>
    <div class="container">
      <div class="actions">
        <button class="btn primary" onclick="descargarPDF()">⬇ Descargar PDF</button>
        <button class="btn" onclick="window.close()">Cerrar Pestaña</button>
      </div>
      
      <div id="pdf-content" class="pdf-content">
        <h1>ConstructoCompare <span class="orange">PRO</span></h1>
        <p><strong>Proyecto:</strong> Cotización</p>
        <p><strong>Fecha:</strong> ${date}</p>
        <p><strong>UF del día:</strong> ${formatCLP(ufValue)}</p>
        
        <table>
          <thead><tr><th>Producto</th><th>Tienda</th><th>Cant.</th><th>P. Unitario (CLP/UF)</th><th>Subtotal (CLP/UF)</th></tr></thead>
          <tbody>${rows}
            <tr class="total"><td colspan="4">TOTAL</td><td style="text-align:right;">${formatCLP(totalCLP)}<br/><span style="font-size:0.85em;font-weight:normal;color:#E65100">${formatUF(totalCLP, ufValue)}</span></td></tr>
          </tbody>
        </table>
        <div class="footer">Cotización generada por ConstructoCompare PRO<br/>
        Los precios son referenciales. Verifique disponibilidad en cada tienda.</div>
      </div>
    </div>

    <script>
      function descargarPDF() {
        const element = document.getElementById('pdf-content');
        const opt = {
          margin:       0.5,
          filename:     'cotizacion_constructocompare_${safeDate}.pdf',
          image:        { type: 'jpeg', quality: 0.98 },
          html2canvas:  { scale: 2 },
          jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };
        html2pdf().set(opt).from(element).save();
      }
    </script>
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

        {activeQuoteId && (
          <div className={s.activeHint} style={{background:'#E3F2FD', color:'#1565C0', padding:'8px 16px', fontSize:'0.85rem', fontWeight:'bold'}}>
            Editando cotización cargada desde Perfil
          </div>
        )}

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
              {saving ? 'Guardando…' : (activeQuoteId ? 'Aplicar cambios' : 'Guardar como proyecto')}
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

            <button className={s.clearBtn} onClick={handleStopEditing}>
              {activeQuoteId ? 'Dejar de editar (Cerrar proyecto)' : 'Vaciar cotización'}
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
