import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '../hooks/useAuth';
import { searchProducts, fetchUF, CATEGORIAS, Producto } from '../services/api';
import Navbar from '../components/Layout/Navbar';
import ProductCard from '../components/ProductCard/ProductCard';
import QuotePanel from '../components/QuotePanel/QuotePanel';
import PriceHistoryModal from '../components/PriceHistoryModal/PriceHistoryModal';
import s from '../styles/App.module.css';

export default function AppPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [query, setQuery]           = useState('');
  const [categoria, setCategoria]   = useState('Todos');
  const [productos, setProductos]   = useState<Producto[]>([]);
  const [searching, setSearching]   = useState(false);
  const [searched, setSearched]     = useState(false);
  const [ufValue, setUfValue]       = useState(0);
  const [showUF, setShowUF]         = useState(false);  // HU6
  const [quoteOpen, setQuoteOpen]   = useState(false);
  const [historyProduct, setHistoryProduct] = useState<Producto | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/');
  }, [user, authLoading]);

  useEffect(() => { fetchUF().then(d => setUfValue(d.valor)); }, []);

  const doSearch = useCallback(async (q: string, cat: string) => {
    if (!q.trim()) return;
    setSearching(true); setSearched(false);
    const results = await searchProducts(q, cat);
    setProductos(results);
    setSearching(false); setSearched(true);
  }, []);

  function handleSearch() { doSearch(query, categoria); }
  function handleCategoryChange(cat: string) {
    setCategoria(cat);
    if (query) doSearch(query, cat);
  }

  if (authLoading || !user) return null;

  return (
    <div className={s.page}>
      <Navbar ufValue={ufValue} onOpenQuote={() => setQuoteOpen(true)} />

      {/* Barra de búsqueda — HU1 */}
      <div className={s.searchSection}>
        <div className={s.searchInner}>
          <h1 className={s.searchTitle}>Compara precios de materiales</h1>
          <p className={s.searchSub}>Sodimac · Easy · Imperial — 3 tiendas en una sola búsqueda</p>

          <div className={s.searchBar}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Buscar material… ej: cemento, fierro, pintura"
              autoFocus
            />
            <button className={s.searchBtn} onClick={handleSearch}>Buscar</button>
          </div>

          {/* Filtros de categoría */}
          <div className={s.chips}>
            {CATEGORIAS.map(cat => (
              <button
                key={cat}
                className={[s.chip, categoria === cat && s.chipActive].filter(Boolean).join(' ')}
                onClick={() => handleCategoryChange(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Resultados */}
      <main className={s.main}>

        {/* HU6 — Switch UF en la barra de resultados */}
        {searched && !searching && (
          <div className={s.resultsBar}>
            <span className={s.resultCount}>
              <strong>{productos.length}</strong> {productos.length === 1 ? 'resultado' : 'resultados'}
              {query && <> para <em>"{query}"</em></>}
            </span>
            <label className={s.ufToggle}>
              <span>Ver en UF</span>
              <span className={s.switchWrap}>
                <input type="checkbox" checked={showUF} onChange={() => setShowUF(v => !v)} />
                <span className={s.switchSlider} />
              </span>
            </label>
          </div>
        )}

        {/* Loading */}
        {searching && (
          <div className={s.stateWrap}>
            <div className={s.spinner} />
            <p>Buscando en Sodimac, Easy e Imperial…</p>
          </div>
        )}

        {/* HU1-AC3 — Sin resultados */}
        {searched && !searching && productos.length === 0 && (
          <div className={s.stateWrap}>
            <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity=".3">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <h3>No se encontraron productos que coincidan con su búsqueda</h3>
            <p>Intenta con otro término o cambia el filtro de categoría.</p>
          </div>
        )}

        {/* Vacío inicial */}
        {!searching && !searched && (
          <div className={s.stateWrap}>
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" opacity=".25">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            <h3>Ingresa un material para comenzar</h3>
            <p>Busca por nombre, marca, categoría o código SKU.</p>
          </div>
        )}

        {/* Grid de productos — HU2 HU3 */}
        {!searching && productos.length > 0 && (
          <div className={s.grid}>
            {productos.map((p, i) => (
              <ProductCard
                key={p.id}
                producto={p}
                ufValue={ufValue}
                showUF={showUF}
                onShowHistory={setHistoryProduct}
                animDelay={i * 0.05}
              />
            ))}
          </div>
        )}
      </main>

      {/* Panel de cotización — HU4 HU5 HU7 HU10 */}
      {quoteOpen && (
        <QuotePanel
          onClose={() => setQuoteOpen(false)}
          ufValue={ufValue}
          showUF={showUF}
          onToggleUF={() => setShowUF(v => !v)}
        />
      )}

      {/* Modal historial — HU9 */}
      {historyProduct && (
        <PriceHistoryModal
          producto={historyProduct}
          onClose={() => setHistoryProduct(null)}
        />
      )}
    </div>
  );
}
