import { useState } from 'react';
import { useQuote } from '../../hooks/useQuote';
import { useAuth } from '../../hooks/useAuth';
import { formatCLP, formatUF, getPrecioFinal, getTiendaColor } from '../../services/api';
import s from './QuotePanel.module.css';

interface Props {
  onClose: () => void;
  ufValue: number;
  showUF: boolean;
  onToggleUF: () => void;
}

export default function QuotePanel({ onClose, ufValue, showUF, onToggleUF }: Props) {
  const { items, removeItem, updateQty, clearQuote, totalCLP, saveQuote } = useQuote();
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);

  // HU7 — Guardar cotización
  async function handleSave() {
    if (!user) return;
    const nombre = prompt('Nombre del proyecto (ej: Obra Casa Maipú):') ?? 'Cotización sin nombre';
    setSaving(true);
    saveQuote(nombre, user.email, ufValue);
    setSaving(false);
    alert('✓ Cotización guardada en "Mis Proyectos"');
    onClose();
  }

  // HU10 — Exportar PDF
  function handleExportPDF() {
    const date = new Date().toLocaleDateString('es-CL');
    const rows = items.map(item => {
      const final = getPrecioFinal(item.tienda_seleccionada);
      return `<tr>
        <td>${item.producto.nombre}</td>
        <td>${item.tienda_seleccionada.tienda}</td>
        <td style="text-align:center">${item.cantidad}</td>
        <td style="text-align:right">${formatCLP(final)}</td>
        <td style="text-align:right">${formatCLP(final * item.cantidad)}</td>
      </tr>`;
    }).join('');

    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"/>
    <title>Cotización ConstructoCompare PRO</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;color:#1E3A5F;}
      h1{color:#1E3A5F;} span.orange{color:#F57C00;}
      table{width:100%;border-collapse:collapse;margin-top:24px;}
      th{background:#1E3A5F;color:#fff;padding:10px 12px;text-align:left;}
      td{padding:9px 12px;border-bottom:1px solid #eee;}
      tr:nth-child(even) td{background:#f8f9fb;}
      .total td{font-weight:bold;background:#FFF3E0;color:#E65100;font-size:1.1em;}
      .footer{margin-top:32px;font-size:.85em;color:#888;}
    </style></head><body>
    <h1>ConstructoCompare <span class="orange">PRO</span></h1>
    <p><strong>Proyecto:</strong> Cotización</p>
    <p><strong>Fecha:</strong> ${date}</p>
    <p><strong>UF del día:</strong> ${formatCLP(ufValue)}</p>
    <table>
      <thead><tr><th>Producto</th><th>Tienda</th><th>Cant.</th><th>P. Unitario</th><th>Subtotal</th></tr></thead>
      <tbody>${rows}
        <tr class="total"><td colspan="4">TOTAL</td><td>${formatCLP(totalCLP)} / ${formatUF(totalCLP, ufValue)}</td></tr>
      </tbody>
    </table>
    <div class="footer">Cotización generada por ConstructoCompare PRO · DUOC UC TPY1101<br/>
    Los precios son referenciales. Verifique disponibilidad en cada tienda.</div>
    </body></html>`;

    const win = window.open('', '_blank');
    if (win) { win.document.write(html); win.document.close(); win.print(); }
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
                  <div className={s.itemName}>{item.producto.nombre}</div>
                  <div className={s.itemStore} style={{ color }}>{item.tienda_seleccionada.tienda}</div>
                  {/* HU5 — controles cantidad */}
                  <div className={s.qtyRow}>
                    <button className={s.qtyBtn} onClick={() => updateQty(i, -1)}>−</button>
                    <span className={s.qtyVal}>{item.cantidad}</span>
                    <button className={s.qtyBtn} onClick={() => updateQty(i, 1)}>+</button>
                    <span className={s.itemSubtotal}>{formatCLP(final * item.cantidad)}</span>
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
