import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import { Cotizacion, getLocalCotizaciones, deleteLocalCotizacion, formatCLP } from '../services/api';
import s from '../styles/Proyectos.module.css';

export default function ProyectosPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [cotizaciones, setCotizaciones] = useState<Cotizacion[]>([]);

  useEffect(() => {
    if (!user) { router.replace('/'); return; }
    setCotizaciones(getLocalCotizaciones(user.email));
  }, [user]);

  function handleDelete(id: string) {
    if (!user || !confirm('¿Eliminar esta cotización?')) return;
    deleteLocalCotizacion(user.email, id);
    setCotizaciones(getLocalCotizaciones(user.email));
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
            {cotizaciones.map(cot => (
              <div key={cot.id} className={s.card}>
                <div className={s.cardHeader}>
                  <div>
                    <h3 className={s.cardTitle}>{cot.nombre_proyecto}</h3>
                    <p className={s.cardMeta}>{cot.fecha_creacion} · {cot.items.length} ítem{cot.items.length !== 1 ? 's' : ''}</p>
                  </div>
                  <div className={s.cardTotal}>
                    <span className={s.totalCLP}>{formatCLP(cot.total_clp)}</span>
                    <span className={s.totalUF}>{cot.total_uf} UF</span>
                  </div>
                </div>
                <div className={s.itemsList}>
                  {cot.items.slice(0, 3).map((item, i) => (
                    <span key={i} className={s.itemTag}>{item.producto.nombre}</span>
                  ))}
                  {cot.items.length > 3 && <span className={s.itemTag}>+{cot.items.length - 3} más</span>}
                </div>
                <div className={s.cardActions}>
                  <button className={s.deleteBtn} onClick={() => handleDelete(cot.id)}>Eliminar</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
