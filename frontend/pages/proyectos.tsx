import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import { CotizacionApi, fetchQuotes, deleteQuote, formatCLP, fetchUF, getPrecioFinal, retailerIdToName, retailerNameToId, searchProducts, Producto, updateQuote, formatProductName } from '../services/api';
import s from '../styles/Proyectos.module.css';

export default function ProyectosPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [cotizaciones, setCotizaciones] = useState<CotizacionApi[]>([]);
  const [productMap, setProductMap] = useState<Map<string, Producto>>(new Map());
  const [ufValue, setUfValue] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Record<number, { nombre_proyecto: string; detalles: Array<{ id_producto_maestro: number; id_retailer: number; cantidad: number }> }>>({});
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    if (!user) { router.replace('/'); return; }

    async function loadData() {
      try {
        if (!sessionStorage.getItem('cc_token')) return;
        const [quotes, products, uf] = await Promise.all([
          fetchQuotes(),
          searchProducts('', 'Todos'),
          fetchUF(),
        ]);
        setCotizaciones(quotes);
        setProductMap(new Map(products.map(p => [p.id, p])));
        setUfValue(uf.valor);
      } catch (error) {
        console.error('Error cargando cotizaciones:', error);
      }
    }

    loadData();
  }, [user]);

  async function handleDelete(id: number) {
    if (!user || !confirm('¿Eliminar esta cotización?')) return;
    await deleteQuote(id);
    setCotizaciones(prev => prev.filter(c => c.id_cotizacion !== id));
  }

  function ensureDraft(cotizacion: CotizacionApi) {
    setDrafts(prev => {
      if (prev[cotizacion.id_cotizacion]) return prev;
      return {
        ...prev,
        [cotizacion.id_cotizacion]: {
          nombre_proyecto: cotizacion.nombre_proyecto,
          detalles: cotizacion.detalles.map(det => ({
            id_producto_maestro: det.id_producto_maestro,
            id_retailer: det.id_retailer,
            cantidad: det.cantidad,
          })),
        },
      };
    });
  }

  function toggleExpand(cotizacion: CotizacionApi) {
    if (expandedId === cotizacion.id_cotizacion) {
      setExpandedId(null);
      return;
    }
    ensureDraft(cotizacion);
    setExpandedId(cotizacion.id_cotizacion);
  }

  function updateDraftField(id: number, field: 'nombre_proyecto', value: string) {
    setDrafts(prev => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }));
  }

  function updateDraftDetail(id: number, index: number, patch: Partial<{ id_retailer: number; cantidad: number }>) {
    setDrafts(prev => {
      const draft = prev[id];
      if (!draft) return prev;
      const detalles = draft.detalles.map((det, idx) => idx === index ? { ...det, ...patch } : det);
      return { ...prev, [id]: { ...draft, detalles } };
    });
  }

  function removeDraftDetail(id: number, index: number) {
    setDrafts(prev => {
      const draft = prev[id];
      if (!draft) return prev;
      const detalles = draft.detalles.filter((_, idx) => idx !== index);
      return { ...prev, [id]: { ...draft, detalles } };
    });
  }

  async function handleSaveDraft(id: number) {
    const draft = drafts[id];
    if (!draft) return;
    setSavingId(id);
    try {
      const updated = await updateQuote(id, {
        nombre_proyecto: draft.nombre_proyecto,
        detalles: draft.detalles,
      });
      setCotizaciones(prev => prev.map(c => c.id_cotizacion === id ? updated : c));
      setExpandedId(null);
    } catch (error) {
      console.error('Error actualizando cotizacion:', error);
      alert('No se pudo guardar la cotizacion.');
    } finally {
      setSavingId(null);
    }
  }

  function resolveTotalCLP(cotizacion: CotizacionApi): number {
    return cotizacion.detalles.reduce((sum, det) => {
      const product = productMap.get(String(det.id_producto_maestro));
      const storeName = retailerIdToName(det.id_retailer);
      const store = product?.tiendas.find(t => t.tienda === storeName);
      if (!store) return sum;
      return sum + getPrecioFinal(store) * det.cantidad;
    }, 0);
  }

  return (
    <div className={s.page}>
      <nav className={s.nav}>
        <Link href="/app" className={s.brand}>← ConstructoCompare PRO</Link>
        <button className={s.logoutBtn} onClick={logout}>Salir</button>
      </nav>

      <div className={s.content}>
        <div className={s.header}>
          <h1>Mis Proyectos</h1>
          <p>{cotizaciones.length} cotización{cotizaciones.length !== 1 ? 'es' : ''} guardada{cotizaciones.length !== 1 ? 's' : ''}</p>
        </div>

        {cotizaciones.length === 0 ? (
          <div className={s.empty}>
            <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" opacity=".3">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <h3>Aún no tienes proyectos guardados</h3>
            <p>Busca materiales, arma tu cotización y guárdala como proyecto.</p>
            <Link href="/app" className={s.ctaBtn}>Ir al catálogo</Link>
          </div>
        ) : (
          <div className={s.list}>
            {cotizaciones.map(cot => {
              const totalCLP = resolveTotalCLP(cot);
              const totalUF = ufValue > 0 ? (totalCLP / ufValue).toFixed(4) : '-';
              const itemNames = cot.detalles
                .map(det => {
                  const name = productMap.get(String(det.id_producto_maestro))?.nombre;
                  return name ? formatProductName(name) : `Producto ${det.id_producto_maestro}`;
                });
              const draft = drafts[cot.id_cotizacion];
              const expanded = expandedId === cot.id_cotizacion;
              return (
              <div key={cot.id_cotizacion} className={s.card}>
                <div className={s.cardHeader}>
                  <div>
                    <h3 className={s.cardTitle}>{cot.nombre_proyecto}</h3>
                    <p className={s.cardMeta}>{new Date(cot.fecha_creacion).toLocaleDateString('es-CL')} · {cot.detalles.length} ítem{cot.detalles.length !== 1 ? 's' : ''}</p>
                  </div>
                  <div className={s.cardTotal}>
                    <span className={s.totalCLP}>{formatCLP(totalCLP)}</span>
                    <span className={s.totalUF}>{totalUF} UF</span>
                  </div>
                </div>
                <div className={s.itemsList}>
                  {itemNames.slice(0, 3).map((name, i) => (
                    <span key={i} className={s.itemTag}>{name}</span>
                  ))}
                  {itemNames.length > 3 && <span className={s.itemTag}>+{itemNames.length - 3} más</span>}
                </div>
                <div className={s.cardActions}>
                  <button className={s.editBtn} onClick={() => toggleExpand(cot)}>
                    {expanded ? 'Cerrar' : 'Ver / Editar'}
                  </button>
                  <button className={s.deleteBtn} onClick={() => handleDelete(cot.id_cotizacion)}>Eliminar</button>
                </div>
                {expanded && draft && (
                  <div className={s.detailsPanel}>
                    <div className={s.detailHeader}>
                      <label>
                        Nombre del proyecto
                        <input
                          className={s.detailInput}
                          value={draft.nombre_proyecto}
                          onChange={e => updateDraftField(cot.id_cotizacion, 'nombre_proyecto', e.target.value)}
                        />
                      </label>
                    </div>
                    <div className={s.detailList}>
                      {draft.detalles.map((det, idx) => {
                        const product = productMap.get(String(det.id_producto_maestro));
                        const storeName = retailerIdToName(det.id_retailer);
                        const store = product?.tiendas.find(t => t.tienda === storeName);
                        const unitPrice = store ? getPrecioFinal(store) : 0;
                        return (
                          <div key={`${det.id_producto_maestro}-${idx}`} className={s.detailRow}>
                            <div className={s.detailName}>
                              <strong>{product?.nombre || `Producto ${det.id_producto_maestro}`}</strong>
                              <span className={s.detailSku}>ID {det.id_producto_maestro}</span>
                            </div>
                            <select
                              className={s.detailSelect}
                              value={det.id_retailer}
                              onChange={e => updateDraftDetail(cot.id_cotizacion, idx, { id_retailer: Number(e.target.value) })}
                            >
                              {(product?.tiendas || []).map(t => {
                                const retailerId = retailerNameToId(t.tienda);
                                if (!retailerId) return null;
                                return (
                                  <option key={t.tienda} value={retailerId}>
                                    {t.tienda}
                                  </option>
                                );
                              })}
                              {(!product || product.tiendas.length === 0) && (
                                <option value={det.id_retailer}>Retailer {det.id_retailer}</option>
                              )}
                            </select>
                            <input
                              type="number"
                              min={1}
                              className={s.detailQty}
                              value={det.cantidad}
                              onChange={e => updateDraftDetail(cot.id_cotizacion, idx, { cantidad: Number(e.target.value) })}
                            />
                            <span className={s.detailSubtotal}>{formatCLP(unitPrice * det.cantidad)}</span>
                            <button className={s.detailRemove} onClick={() => removeDraftDetail(cot.id_cotizacion, idx)}>
                              Quitar
                            </button>
                          </div>
                        );
                      })}
                    </div>
                    <div className={s.detailActions}>
                      <button className={s.saveBtn} onClick={() => handleSaveDraft(cot.id_cotizacion)} disabled={savingId === cot.id_cotizacion}>
                        {savingId === cot.id_cotizacion ? 'Guardando…' : 'Guardar cambios'}
                      </button>
                      <button className={s.cancelBtn} onClick={() => setExpandedId(null)}>
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          </div>
        )}
      </div>
    </div>
  );
}
