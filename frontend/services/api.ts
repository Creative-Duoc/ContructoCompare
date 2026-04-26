/**
 * ConstructoCompare PRO — Capa de Servicio (Microservicio FastAPI mock)
 *
 * Esta capa abstrae todas las llamadas al backend FastAPI.
 * Cuando el backend esté disponible, cada función reemplaza su
 * implementación mock por un fetch() al endpoint documentado.
 *
 * Estructura REST del microservicio:
 *   POST   /api/v1/auth/register   → Registro de usuario
 *   POST   /api/v1/auth/login      → Login JWT
 *   GET    /api/v1/auth/me         → Sesión activa
 *   GET    /api/v1/products        → Búsqueda de productos ?q=&tienda=
 *   GET    /api/v1/products/:id    → Detalle producto
 *   GET    /api/v1/products/:id/history → Historial de precios
 *   GET    /api/v1/uf/current      → Valor UF del día
 *   POST   /api/v1/quotes          → Crear cotización
 *   GET    /api/v1/quotes          → Listar cotizaciones del usuario
 *   DELETE /api/v1/quotes/:id      → Eliminar cotización
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

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  tipo: 'particular' | 'profesional' | 'empresa';
}

export interface UFData {
  valor: number;
  fecha: string;
  fuente: string;
}

// ── DATOS MOCK ────────────────────────────────────────────────

const API_BASE_URL = 'http://localhost:8001/api/v1';

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

/**
 * GET /api/v1/uf/current
 */
export async function fetchUF(): Promise<UFData> {
  try {
    const res = await fetch('https://mindicador.cl/api/uf');
    if (!res.ok) throw new Error('Error fetching UF');
    const data = await res.json();
    return { 
      valor: data.serie[0].valor, 
      fecha: data.serie[0].fecha.split('T')[0], 
      fuente: 'mindicador.cl' 
    };
  } catch (error) {
    console.error('Error obteniendo UF:', error);
    // Fallback de seguridad en caso de que la API de mindicador falle
    return { valor: 39847.23, fecha: new Date().toISOString().split('T')[0], fuente: 'mindicador.cl (fallback)' };
  }
}

/**
 * GET /api/v1/inventory/sodimac/productos
 * Adaptamos la respuesta del backend al formato que espera el frontend
 */
export const CATEGORIAS = [
  'Todos', 'Taladros', 'Cemento y Hormigón', 'Fierro y Acero', 'Madera y Tableros',
  'Pintura', 'Cerámicos y Porcelanato', 'Tuberías y Sanitarios',
  'Electricidad', 'Aislación',
];

/**
 * GET /api/v1/inventory/sodimac/productos
 */
export async function searchProducts(query: string, categoria?: string): Promise<Producto[]> {
  try {
    const data: any[] = await apiFetch('/inventory/sodimac/productos');
    
    const productos: Producto[] = data.map(item => ({
      id: String(item.id_producto || Math.random()),
      nombre: item.nombre_producto || 'Producto sin nombre',
      marca: 'Sodimac', 
      categoria: item.categoria || 'General',
      foto_url: '',
      sku: String(item.sku_maestro || ''),
      unidad: 'unidad',
      tiendas: [
        {
          tienda: 'Sodimac',
          precio_real: Number(item.precio_clp) || 0,
          precio_oferta: null,
          stock: Boolean(item.disponibilidad),
          url_producto: item.link_producto || '#',
          fecha_actualizacion: item.fecha_captura || new Date().toISOString()
        }
      ]
    }));

    const q = query.trim().toLowerCase();
    const cat = categoria || 'Todos';

    return productos.filter(p => {
      // El nombre o SKU debe coincidir con la búsqueda (si hay búsqueda)
      const matchQuery = !q || 
        p.nombre.toLowerCase().includes(q) || 
        p.sku.toLowerCase().includes(q);
      
      // La categoría debe coincidir. 
      let matchCat = cat === 'Todos';
      if (!matchCat) {
        const catLower = cat.toLowerCase();
        
        // Obtenemos palabras clave de la categoría (ej: "Fierro y Acero" -> ["fierro", "acero"])
        // Filtramos conectores comunes como "y", "o", "en"
        const keywords = catLower
          .split(/[\s,y/]+/)
          .filter(k => k.length > 2)
          .map(k => k.replace(/s$/, '')); // Normalizamos plurales simples

        const prodNombre = p.nombre.toLowerCase();
        const prodCat = p.categoria.toLowerCase();

        // Si alguna de las palabras clave de la categoría seleccionada coincide 
        // con el nombre o la categoría del producto, lo mostramos.
        matchCat = keywords.some(keyword => 
          prodCat.includes(keyword) || prodNombre.includes(keyword)
        );
      }
      
      return matchQuery && matchCat;
    });
  } catch (error) {
    console.error('Error en searchProducts:', error);
    return [];
  }
}

/**
 * POST /api/v1/users/login
 */
export async function loginUser(email: string, pass: string): Promise<{ success: boolean; user?: Usuario; error?: string }> {
  try {
    const tokenRes = await apiFetch('/users/login', {
      method: 'POST',
      body: JSON.stringify({
        correo_electronico: email,
        password: pass,
      }),
    });

    if (tokenRes.access_token) {
      // Guardamos el token en sessionStorage para apiFetch (si lo usara con Bearer)
      sessionStorage.setItem('cc_token', tokenRes.access_token);

      // Obtenemos los datos del usuario logueado
      const userRes = await apiFetch('/users/me', {
        headers: {
          Authorization: `Bearer ${tokenRes.access_token}`,
        },
      });

      const user: Usuario = {
        id: String(userRes.id_usuario),
        nombre: userRes.nombre_completo,
        email: userRes.correo_electronico,
        tipo: 'particular', // Valor por defecto ya que el backend no lo maneja aún
      };

      return { success: true, user };
    }
    return { success: false, error: 'No se recibió token de acceso' };
  } catch (error: any) {
    return { success: false, error: error.message || 'Error al iniciar sesión' };
  }
}

/**
 * POST /api/v1/users/register
 */
export async function registerUser(nombre: string, email: string, pass: string, tipo: string): Promise<{ success: boolean; error?: string }> {
  try {
    await apiFetch('/users/register', {
      method: 'POST',
      body: JSON.stringify({
        nombre_completo: nombre,
        correo_electronico: email,
        password: pass,
        // tipo no es aceptado por el backend actual según UsuarioCreate
      }),
    });
    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message || 'Error al registrar usuario' };
  }
}

