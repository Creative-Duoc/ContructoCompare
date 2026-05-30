import Head from 'next/head';
import { useRouter } from 'next/router';
import { useAuth } from '../hooks/useAuth';
import { useQuote } from '../hooks/useQuote';
import Navbar from '../components/Layout/Navbar';
import s from '../styles/Proyectos.module.css'; 
import { useEffect, useState } from 'react';
import { CotizacionApi, fetchQuotes, searchProducts, Producto, retailerIdToName, QuoteItem, deleteQuote, updatePassword, deleteAccount } from '../services/api';

export default function Perfil() {
  const { user, loading, logout } = useAuth();
  const { setItems, setActiveQuoteId, setInitialSnapshot } = useQuote();
  const router = useRouter();

  const [savedQuotes, setSavedQuotes] = useState<CotizacionApi[]>([]);
  const [productMap, setProductMap] = useState<Map<string, Producto>>(new Map());
  const [loadingSaved, setLoadingSaved] = useState(true);

  const [showPassModal, setShowPassModal] = useState(false);
  const [oldPass, setOldPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [passError, setPassError] = useState('');
  const [passSuccess, setPassSuccess] = useState('');
  const [passLoading, setPassLoading] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);

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

  function openPassModal() {
    setOldPass(''); setNewPass(''); setConfirmPass('');
    setPassError(''); setPassSuccess('');
    setShowPassModal(true);
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPassError(''); setPassSuccess('');
    if (newPass !== confirmPass) { setPassError('Las contraseñas nuevas no coinciden.'); return; }
    setPassLoading(true);
    try {
      await updatePassword(oldPass, newPass);
      setPassSuccess('Contraseña actualizada correctamente.');
      setOldPass(''); setNewPass(''); setConfirmPass('');
      setTimeout(() => setShowPassModal(false), 1500);
    } catch (err: any) {
      setPassError(err.message || 'Error al actualizar la contraseña.');
    } finally {
      setPassLoading(false);
    }
  }

  async function handleDeleteAccount() {
    if (!confirm('¿Estás seguro? Esta acción eliminará tu cuenta y todas tus cotizaciones de forma permanente. No se puede deshacer.')) return;
    setDeletingAccount(true);
    try {
      await deleteAccount();
      logout();
      router.replace('/');
    } catch (err: any) {
      alert(err.message || 'Error al eliminar la cuenta.');
      setDeletingAccount(false);
    }
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

      {/* Modal cambio de contraseña */}
      {showPassModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{ background: '#fff', borderRadius: '12px', padding: '32px', width: '100%', maxWidth: '420px', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <h2 style={{ margin: '0 0 24px 0', color: 'var(--blue-dark)' }}>Cambiar contraseña</h2>
            <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.9rem' }}>Contraseña actual</label>
                <input
                  type="password" value={oldPass} onChange={e => setOldPass(e.target.value)}
                  required placeholder="••••••••"
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '1rem', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.9rem' }}>Nueva contraseña</label>
                <input
                  type="password" value={newPass} onChange={e => setNewPass(e.target.value)}
                  required placeholder="Mínimo 8 caracteres"
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '1rem', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.9rem' }}>Confirmar nueva contraseña</label>
                <input
                  type="password" value={confirmPass} onChange={e => setConfirmPass(e.target.value)}
                  required placeholder="••••••••"
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '1rem', boxSizing: 'border-box' }}
                />
              </div>
              {passError && <p style={{ color: '#D32F2F', margin: 0, fontSize: '0.9rem' }}>{passError}</p>}
              {passSuccess && <p style={{ color: '#2E7D32', margin: 0, fontSize: '0.9rem' }}>{passSuccess}</p>}
              <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                <button type="button" onClick={() => setShowPassModal(false)}
                  style={{ flex: 1, padding: '10px', border: '1px solid #d1d5db', borderRadius: '8px', background: '#fff', cursor: 'pointer', fontWeight: '600' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={passLoading}
                  style={{ flex: 1, padding: '10px', border: 'none', borderRadius: '8px', background: 'var(--blue-dark)', color: '#fff', cursor: 'pointer', fontWeight: '600' }}>
                  {passLoading ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
                onClick={openPassModal}
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
                onClick={handleDeleteAccount}
                disabled={deletingAccount}
                style={{ background: '#fff', color: '#D32F2F', border: '1px solid #EF9A9A', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', transition: 'background 0.2s', marginTop: '8px' }}
                onMouseOver={e => e.currentTarget.style.background = '#FFEBEE'}
                onMouseOut={e => e.currentTarget.style.background = '#fff'}
              >
                {deletingAccount ? 'Eliminando...' : 'Eliminar cuenta'}
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
