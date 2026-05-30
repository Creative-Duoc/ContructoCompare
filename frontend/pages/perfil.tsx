import Head from 'next/head';
import { useRouter } from 'next/router';
import { useAuth } from '../hooks/useAuth';
import { useQuote } from '../hooks/useQuote';
import Navbar from '../components/Layout/Navbar';
import s from '../styles/Proyectos.module.css'; 
import { useEffect, useState } from 'react';
import { CotizacionApi, fetchQuotes, searchProducts, Producto, retailerIdToName, QuoteItem, deleteQuote } from '../services/api';

export default function Perfil() {
  const { user, loading, logout } = useAuth();
  const { setItems, setActiveQuoteId, setInitialSnapshot } = useQuote();
  const router = useRouter();

  const [savedQuotes, setSavedQuotes] = useState<CotizacionApi[]>([]);
  const [productMap, setProductMap] = useState<Map<string, Producto>>(new Map());
  const [loadingSaved, setLoadingSaved] = useState(true);

  useEffect(() => {
    if (!user) return;

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
  }, [user]);

  // Protección de ruta
  if (loading) return null;
  if (!user) {
    if (typeof window !== 'undefined') router.replace('/');
    return null;
  }

  function handleLoadQuote(quote: CotizacionApi) {
    const nextItems: QuoteItem[] = [];
    quote.detalles.forEach(det => {
      const product = productMap.get(String(det.id_producto_maestro));
      if (!product) return;
      const storeName = retailerIdToName(det.id_retailer);
      const store = product.tiendas.find(t => t.tienda === storeName) || product.tiendas[0];
      if (!store) return;
      nextItems.push({ producto: product, tienda_seleccionada: store, cantidad: det.cantidad });
    });

    setItems(nextItems);
    setActiveQuoteId(quote.id_cotizacion);
    
    // Guardamos la foto inicial usando el hook global que ya destruimos arriba
    setInitialSnapshot(JSON.stringify(nextItems.map(i => ({
      id: i.producto.id,
      store: i.tienda_seleccionada.tienda,
      qty: i.cantidad
    }))));
    
    router.push('/app'); // Redirigir a la app principal para editar
  }

  async function handleDeleteQuote(id: number) {
    if (!confirm('¿Estás seguro de que quieres eliminar este proyecto? Esta acción no se puede deshacer.')) return;
    try {
      await deleteQuote(id);
      // Forzar a string para evitar problemas de tipado entre number y string desde la API
      setSavedQuotes(prev => prev.filter(q => String(q.id_cotizacion) !== String(id)));
    } catch (err: any) {
      alert(err.message || 'Error al eliminar el proyecto');
    }
  }

  return (
    <div className={s.layout}>
      <Head>
        <title>Mi Perfil | ConstructoCompare PRO</title>
      </Head>

      <Navbar ufValue={0} onOpenQuote={() => {
        router.push('/app');
      }} />

      <main className={s.main}>
        <div className={s.header}>
          <h1>Mi Perfil</h1>
          <p>Gestiona tu cuenta y tus proyectos guardados.</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '32px', alignItems: 'start' }}>
          
          {/* Panel Izquierdo: Datos de Usuario */}
          <div style={{ background: '#fff', padding: '32px', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '16px' }}>
              <div style={{ 
                width: '100px', height: '100px', borderRadius: '50%', 
                background: 'var(--blue-light)', color: 'var(--blue-dark)', 
                display: 'flex', alignItems: 'center', justifyContent: 'center', 
                fontSize: '2.5rem', fontWeight: 'bold' 
              }}>
                {user.nombre?.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase() ?? 'U'}
              </div>
              <div>
                <h2 style={{ margin: 0, color: 'var(--blue-dark)' }}>{user.nombre}</h2>
                <p style={{ margin: '4px 0 0 0', color: 'var(--gray-500)' }}>{user.email}</p>
                <span style={{ 
                  display: 'inline-block', marginTop: '12px', padding: '4px 12px', 
                  background: '#E3F2FD', color: '#1976D2', fontSize: '0.8rem', 
                  borderRadius: '16px', fontWeight: '600' 
                }}>
                  {user.rol || 'Usuario Estándar'}
                </span>
              </div>
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid #eee', margin: '32px 0' }} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
              <button 
                onClick={() => alert('Funcionalidad de cambio de contraseña en desarrollo.')}
                style={{ background: '#fff', color: 'var(--gray-700)', border: '1px solid var(--gray-300)', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', transition: 'background 0.2s' }}
                onMouseOver={e => e.currentTarget.style.background = '#f8f9fb'}
                onMouseOut={e => e.currentTarget.style.background = '#fff'}
              >
                Cambiar contraseña
              </button>
              <button 
                onClick={logout}
                style={{ background: '#fff', color: 'var(--gray-700)', border: '1px solid var(--gray-300)', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', transition: 'background 0.2s' }}
                onMouseOver={e => e.currentTarget.style.background = '#f8f9fb'}
                onMouseOut={e => e.currentTarget.style.background = '#fff'}
              >
                Cerrar sesión
              </button>
              <button 
                onClick={() => {
                  if (confirm('¿Estás seguro de que quieres solicitar la eliminación de tu cuenta? Esta acción es irreversible.')) {
                    alert('Se ha enviado una solicitud al administrador para eliminar tu cuenta.');
                  }
                }}
                style={{ background: '#fff', color: '#D32F2F', border: '1px solid #EF9A9A', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', transition: 'background 0.2s', marginTop: '8px' }}
                onMouseOver={e => e.currentTarget.style.background = '#FFEBEE'}
                onMouseOut={e => e.currentTarget.style.background = '#fff'}
              >
                Eliminar cuenta
              </button>
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid #eee', margin: '32px 0' }} />

            <div style={{ background: '#f8f9fb', padding: '20px', borderRadius: '8px', border: '1px dashed #ddd', width: '100%' }}>
              <p style={{ color: 'var(--gray-600)', fontSize: '0.9rem', margin: 0, lineHeight: '1.5' }}>
                <strong>🚧 Preferencias (Próximamente):</strong><br/>
                Tiendas favoritas, alertas de bajadas de precios y cálculo de tarjetas de crédito.
              </p>
            </div>
          </div>

          {/* Panel Derecho: Cotizaciones Guardadas */}
          <div style={{ background: '#fff', padding: '32px', borderRadius: '12px', border: '1px solid #e5e7eb' }}>
             <h2 style={{ margin: '0 0 24px 0', color: 'var(--blue-dark)', fontSize: '1.5rem' }}>Mis Proyectos Guardados</h2>
             
             {loadingSaved ? (
               <p style={{ color: 'var(--gray-500)' }}>Cargando tus proyectos...</p>
             ) : savedQuotes.length === 0 ? (
               <div style={{ textAlign: 'center', padding: '40px 20px', background: '#f8f9fb', borderRadius: '8px' }}>
                 <p style={{ color: 'var(--gray-500)', marginBottom: '16px' }}>No tienes proyectos guardados aún.</p>
                 <button onClick={() => router.push('/app')} style={{ background: 'var(--blue-dark)', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
                   Crear nueva cotización
                 </button>
               </div>
             ) : (
               <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                 {savedQuotes.map(quote => (
                   <div key={quote.id_cotizacion} style={{ 
                     display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                     padding: '20px', border: '1px solid #eee', borderRadius: '8px',
                     transition: 'border-color 0.2s'
                   }}>
                     <div>
                       <h3 style={{ margin: '0 0 4px 0', fontSize: '1.1rem', color: 'var(--blue-dark)' }}>{quote.nombre_proyecto}</h3>
                       <span style={{ fontSize: '0.85rem', color: 'var(--gray-500)' }}>
                         Creado el: {new Date(quote.fecha_creacion).toLocaleDateString('es-CL')} • {quote.detalles.length} productos
                       </span>
                     </div>
                     <div style={{ display: 'flex', gap: '8px' }}>
                       <button 
                         onClick={() => handleLoadQuote(quote)}
                         style={{ 
                           background: '#fff', color: 'var(--blue-dark)', border: '1px solid var(--blue-dark)', 
                           padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold',
                           transition: 'background 0.2s'
                         }}
                         onMouseOver={e => e.currentTarget.style.background = '#f0f4f8'}
                         onMouseOut={e => e.currentTarget.style.background = '#fff'}
                       >
                         Cargar y Editar
                       </button>
                       <button 
                         onClick={() => handleDeleteQuote(quote.id_cotizacion)}
                         style={{ 
                           background: '#fff', color: '#D32F2F', border: '1px solid #EF9A9A', 
                           padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold',
                           transition: 'background 0.2s'
                         }}
                         onMouseOver={e => e.currentTarget.style.background = '#FFEBEE'}
                         onMouseOut={e => e.currentTarget.style.background = '#fff'}
                         title="Eliminar proyecto"
                       >
                         <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ display: 'block' }}>
                           <path d="M3 6h18M19 6l-1 14H6L5 6M10 11v6M14 11v6M9 6V4h6v2"/>
                         </svg>
                       </button>
                     </div>
                   </div>
                 ))}
               </div>
             )}
          </div>

        </div>
      </main>
    </div>
  );
}
