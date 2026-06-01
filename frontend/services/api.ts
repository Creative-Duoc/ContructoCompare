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
  id_tipo_usuario: number;
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

export interface CotizacionDetalleApi {
  id_detalle: number;
  id_producto_maestro: number;
  id_retailer: number;
  cantidad: number;
}

export interface CotizacionApi {
  id_cotizacion: number;
  id_usuario: number;
  nombre_proyecto: string;
  fecha_creacion: string;
  estado: string;
  detalles: CotizacionDetalleApi[];
}

export interface UFData {
  valor: number;
  fecha: string;
  fuente: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001/api/v1';
const QUOTES_API_BASE_URL = process.env.NEXT_PUBLIC_QUOTES_API_BASE_URL || 'http://localhost:8002/api/v1';

const RETAILER_ID_BY_NAME: Record<string, number> = {
  Sodimac: 1,
  Easy: 2,
  Imperial: 3,
};

const RETAILER_NAME_BY_ID: Record<number, TiendaPrecio['tienda']> = {
  1: 'Sodimac',
  2: 'Easy',
  3: 'Imperial',
};

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

export function formatProductName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function handleSessionExpired() {
  sessionStorage.removeItem('cc_token');
  sessionStorage.removeItem('cc_user');
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
    if (response.status === 401) {
      handleSessionExpired();
      throw new Error('Sesión expirada. Por favor, inicia sesión nuevamente.');
    }
    const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    if (Array.isArray(errorData.detail)) {
      const msg = errorData.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join(', ');
      throw new Error(msg);
    }
    throw new Error(errorData.detail || 'Error en la petición');
  }
  return response.json();
}

async function apiFetchQuotes(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${QUOTES_API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401) {
      handleSessionExpired();
      throw new Error('Sesión expirada. Por favor, inicia sesión nuevamente.');
    }
    const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    if (Array.isArray(errorData.detail)) {
      const msg = errorData.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join(', ');
      throw new Error(msg);
    }
    throw new Error(errorData.detail || 'Error en la petición');
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
    
    const grouped = new Map<string, Producto>();

    const latestByStore = new Map<string, { tienda: TiendaPrecio; fecha: Date }>();

    data.forEach(item => {
      const id = String(item.id_producto);
      const storeKey = `${id}__${item.retailer}`;
      const fecha = new Date(item.fecha_captura);
      const existing = latestByStore.get(storeKey);
      if (!existing || fecha > existing.fecha) {
        latestByStore.set(storeKey, {
          tienda: {
            tienda: item.retailer as any,
            precio_real: Number(item.precio_clp),
            precio_oferta: null,
            stock: Boolean(item.disponibilidad),
            url_producto: item.link_producto,
            fecha_actualizacion: fecha.toLocaleDateString('es-CL'),
          },
          fecha,
        });
      }

      if (!grouped.has(id)) {
        grouped.set(id, {
          id,
          nombre: item.nombre_producto,
          marca: item.marca || 'Genérico',
          categoria: item.categoria,
          foto_url: item.foto_url || '',
          sku: item.sku_tienda ? String(item.sku_tienda) : 'S/N',
          unidad: item.valor_medida ? `${item.valor_medida} ${item.abreviatura_unidad || ''}` : 'unidad',
          tiendas: [],
        });
      }
    });

    grouped.forEach((producto, id) => {
      producto.tiendas = ['Sodimac', 'Easy', 'Imperial']
        .map(store => latestByStore.get(`${id}__${store}`)?.tienda)
        .filter((t): t is TiendaPrecio => t !== undefined);
    });

    const productos = Array.from(grouped.values());
    const q = query.toLowerCase();
    const cat = categoria || 'Todos';

    return productos.filter(p => {
      const matchQuery = !q || p.nombre.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || p.marca.toLowerCase().includes(q);
      let matchChip = cat === 'Todos';
      if (!matchChip) {
        const keyword = cat.toLowerCase().replace(/s$/, '').split(' ')[0];
        matchChip = p.nombre.toLowerCase().includes(keyword) || p.categoria.toLowerCase().includes(keyword);
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
        id_tipo_usuario: userRes.id_tipo_usuario,
      };
      return { success: true, user };
    }
    return { success: false, error: 'Token no recibido' };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

export async function registerUser(nombre: string, email: string, pass: string, idTipoUsuario: number): Promise<{ success: boolean; error?: string }> {
  try {
    await apiFetch('/users/register', {
      method: 'POST',
      body: JSON.stringify({ 
        nombre_completo: nombre, 
        correo_electronico: email, 
        password: pass,
        id_tipo_usuario: idTipoUsuario
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
      tienda: RETAILER_NAME_BY_ID[item.id_retailer] ?? 'Sodimac',
    }));
  } catch (error) {
    console.error('Error fetchPriceHistory:', error);
    return [];
  }
}

export function retailerIdToName(id: number): TiendaPrecio['tienda'] | undefined {
  return RETAILER_NAME_BY_ID[id];
}

export function retailerNameToId(name: string): number | undefined {
  return RETAILER_ID_BY_NAME[name];
}

export async function createQuote(nombre: string, items: QuoteItem[]): Promise<CotizacionApi> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) {
    throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  }
  const detalles = items.map(item => {
    const retailerId = RETAILER_ID_BY_NAME[item.tienda_seleccionada.tienda];
    if (!retailerId) {
      throw new Error(`Retailer no soportado: ${item.tienda_seleccionada.tienda}`);
    }
    return {
      id_producto_maestro: Number(item.producto.id),
      id_retailer: retailerId,
      cantidad: item.cantidad,
    };
  });

  return apiFetchQuotes('/cotizaciones', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ nombre_proyecto: nombre, detalles }),
  });
}

export async function fetchQuotes(): Promise<CotizacionApi[]> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) {
    throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  }
  return apiFetchQuotes('/cotizaciones', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function deleteQuote(id: number): Promise<void> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) {
    throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  }
  await apiFetchQuotes(`/cotizaciones/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updatePassword(contrasenaActual: string, nuevaContrasena: string): Promise<void> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  await apiFetch('/users/password', {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ contrasena_actual: contrasenaActual, nueva_contrasena: nuevaContrasena }),
  });
}

export async function deleteAccount(): Promise<void> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  await apiFetch('/users/me', {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  sessionStorage.removeItem('cc_token');
}

export async function updateQuote(
  id: number,
  payload: { nombre_proyecto?: string; estado?: string; detalles?: Array<{ id_producto_maestro: number; id_retailer: number; cantidad: number }> }
): Promise<CotizacionApi> {
  const token = sessionStorage.getItem('cc_token');
  if (!token) {
    throw new Error('Sesion expirada. Inicia sesión nuevamente.');
  }
  return apiFetchQuotes(`/cotizaciones/${id}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

