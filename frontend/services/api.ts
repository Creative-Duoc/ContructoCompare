/**
 * ConstructoCompare — Capa de Servicio API
 */

// ── TIPOS ────────────────────────────────────────────────────

export interface TiendaPrecio {
  tienda: 'Sodimac' | 'Easy' | 'Imperial';
  precio_real: number;
  precio_oferta: number | null;
  stock: boolean;
  url_producto: string;
  fecha_actualizacion: string;
}

export interface Producto {
  id: string;
  nombre: string;
  marca: string;
  categoria: string;
  foto_url: string;
  sku: string;
  unidad: string;
  tiendas: TiendaPrecio[];
}

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  tipo: 'particular' | 'profesional' | 'empresa';
}

export interface PrecioHistorico {
  fecha: string;
  precio: number;
  tienda: 'Sodimac' | 'Easy' | 'Imperial';
}

export interface QuoteItem {
  producto: Producto;
  tienda_seleccionada: TiendaPrecio;
  cantidad: number;
}

export interface Cotizacion {
  id: string;
  nombre_proyecto: string;
  fecha_creacion: string;
  items: QuoteItem[];
  total_clp: number;
  total_uf: number;
}

export interface UFData {
  valor: number;
  fecha: string;
  fuente: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001/api/v1';

// ── HELPERS ──────────────────────────────────────────────────

export function getBestPrice(producto: Producto): TiendaPrecio {
  const disponibles = producto.tiendas.filter(t => t.stock);
  if (!disponibles.length) return producto.tiendas[0];
  return disponibles.reduce((a, b) => {
    const pa = a.precio_oferta ?? a.precio_real;
    const pb = b.precio_oferta ?? b.precio_real;
    return pa < pb ? a : b;
  });
}

export function getPrecioFinal(tienda: TiendaPrecio): number {
  return tienda.precio_oferta ?? tienda.precio_real;
}

export function formatCLP(valor: number): string {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', minimumFractionDigits: 0 }).format(valor);
}

export function formatUF(valorCLP: number, ufValue: number): string {
  return (valorCLP / ufValue).toFixed(4) + ' UF';
}

export function getTiendaColor(tienda: string): string {
  const colors: Record<string, string> = { Sodimac: '#E53935', Easy: '#43A047', Imperial: '#1565C0' };
  return colors[tienda] ?? '#748194';
}

async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || 'Error en la petición');
  }
  return response.json();
}

// ── API FUNCTIONS ─────────────────────────────────────────────

export async function fetchUF(): Promise<UFData> {
  try {
    const res = await fetch('https://mindicador.cl/api/uf');
    const data = await res.json();
    return { 
      valor: data.serie[0].valor, 
      fecha: data.serie[0].fecha.split('T')[0], 
      fuente: 'mindicador.cl' 
    };
  } catch (error) {
    return { valor: 38000, fecha: new Date().toISOString().split('T')[0], fuente: 'fallback' };
  }
}

export const CATEGORIAS = [
  'Todos', 'Taladros', 'Cemento y Hormigón', 'Fierro y Acero', 'Madera y Tableros',
  'Pintura', 'Cerámicos y Porcelanato', 'Tuberías y Sanitarios',
  'Electricidad', 'Aislación',
];

export async function searchProducts(query: string, categoria?: string): Promise<Producto[]> {
  try {
    const data: any[] = await apiFetch('/inventory/all/productos');
    
    const productos: Producto[] = data.map(item => ({
      id: String(item.id_producto),
      nombre: item.nombre_producto,
      marca: 'Estandarizada', // La marca ahora es canónica en el ProductoMaestro
      categoria: item.categoria,
      foto_url: item.foto_url || 'https://via.placeholder.com/200x200?text=Sin+Foto',
      sku: String(item.sku_maestro),
      unidad: 'unidad',
      tiendas: item.tiendas.map((t: any) => ({
          tienda: t.tienda as any,
          precio_real: Number(t.precio_clp),
          precio_oferta: null,
          stock: Boolean(t.disponibilidad),
          url_producto: t.link_producto,
          fecha_actualizacion: new Date(t.fecha_captura).toLocaleDateString()
      }))
    }));

    const q = query.toLowerCase();
    const cat = categoria || 'Todos';

    return productos.filter(p => {
      const matchQuery = !q || p.nombre.toLowerCase().includes(q) || p.sku.includes(q);
      let matchChip = cat === 'Todos';
      if (!matchChip) {
        const keyword = cat.toLowerCase().replace(/s$/, '').split(' ')[0];
        matchChip = p.nombre.toLowerCase().includes(keyword);
      }
      return matchQuery && matchChip;
    });
  } catch (error) {
    console.error('Error searchProducts:', error);
    return [];
  }
}

export async function loginUser(email: string, pass: string): Promise<{ success: boolean; user?: Usuario; error?: string }> {
  try {
    const tokenRes = await apiFetch('/users/login', {
      method: 'POST',
      body: JSON.stringify({ correo_electronico: email, password: pass }),
    });

    if (tokenRes.access_token) {
      sessionStorage.setItem('cc_token', tokenRes.access_token);
      const userRes = await apiFetch('/users/me', {
        headers: { Authorization: `Bearer ${tokenRes.access_token}` },
      });
      const user: Usuario = {
        id: String(userRes.id_usuario),
        nombre: userRes.nombre_completo,
        email: userRes.correo_electronico,
        tipo: 'particular',
      };
      return { success: true, user };
    }
    return { success: false, error: 'Token no recibido' };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

export async function registerUser(nombre: string, email: string, pass: string, tipo: string): Promise<{ success: boolean; error?: string }> {
  try {
    await apiFetch('/users/register', {
      method: 'POST',
      body: JSON.stringify({ 
        nombre_completo: nombre, 
        correo_electronico: email, 
        password: pass 
      }),
    });
    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

export async function fetchPriceHistory(idProducto: string): Promise<PrecioHistorico[]> {
  try {
    const data: any[] = await apiFetch(`/inventory/productos/${idProducto}/historial`);
    return data.map(item => ({
      fecha: item.fecha_captura,
      precio: Number(item.precio_clp),
      tienda: 'Sodimac'
    }));
  } catch (error) {
    console.error('Error fetchPriceHistory:', error);
    return [];
  }
}

export async function createQuote(quote: Omit<Cotizacion, 'id' | 'fecha_creacion'>): Promise<Cotizacion> {
  const token = sessionStorage.getItem('cc_token');
  return apiFetch('/quotes', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(quote),
  });
}

export async function fetchQuotes(): Promise<Cotizacion[]> {
  const token = sessionStorage.getItem('cc_token');
  return apiFetch('/quotes', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function deleteQuote(id: string): Promise<void> {
  const token = sessionStorage.getItem('cc_token');
  await apiFetch(`/quotes/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function saveLocalCotizacion(userEmail: string, cotizacion: Cotizacion) {
  const key = `cc_quotes_${userEmail}`;
  const existing = getLocalCotizaciones(userEmail);
  localStorage.setItem(key, JSON.stringify([cotizacion, ...existing]));
}

export function getLocalCotizaciones(userEmail: string): Cotizacion[] {
  const key = `cc_quotes_${userEmail}`;
  try {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function deleteLocalCotizacion(userEmail: string, id: string) {
  const key = `cc_quotes_${userEmail}`;
  const existing = getLocalCotizaciones(userEmail);
  const updated = existing.filter(c => c.id !== id);
  localStorage.setItem(key, JSON.stringify(updated));
}
