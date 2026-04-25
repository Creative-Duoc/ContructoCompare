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

const MOCK_PRODUCTOS: Producto[] = [
  {
    id: 'P001', nombre: 'Cemento Melón Resistencia 25 Kg', marca: 'Melón',
    categoria: 'Cemento y Hormigón', foto_url: '', sku: 'CEM-ML-25', unidad: 'saco',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 7990, precio_oferta: 6990, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 7490, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 8190, precio_oferta: null, stock: false,url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P002', nombre: 'Fierro Corrugado Acma 8mm × 6m', marca: 'Acma',
    categoria: 'Fierro y Acero', foto_url: '', sku: 'FIE-AC-8', unidad: 'barra',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 4590, precio_oferta: null, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 4290, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 4490, precio_oferta: 4190,stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P003', nombre: 'Tabla Pino Cepillado 1×3" × 3m', marca: 'Arauco',
    categoria: 'Madera y Tableros', foto_url: '', sku: 'MAD-AR-13', unidad: 'unidad',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 2990, precio_oferta: 2490, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 2790, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 2890, precio_oferta: null, stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P004', nombre: 'Pintura Látex Sherwin Williams Blanco 1GL', marca: 'Sherwin Williams',
    categoria: 'Pintura', foto_url: '', sku: 'PIN-SW-B1', unidad: 'galón',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 18990, precio_oferta: null, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 17490, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 18290, precio_oferta:16990,stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P005', nombre: 'Porcelanato Gris Oscuro 60×60cm m²', marca: 'Lourdes',
    categoria: 'Cerámicos y Porcelanato', foto_url: '', sku: 'POR-LO-G1', unidad: 'm²',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 12990, precio_oferta: 9990, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 11990, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 13490, precio_oferta: null, stock: false,url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P006', nombre: 'Tubo PVC Presión 110mm × 3m', marca: 'Tigre',
    categoria: 'Tuberías y Sanitarios', foto_url: '', sku: 'TUB-TI-110', unidad: 'unidad',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 8490, precio_oferta: null, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 7990, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 8290, precio_oferta: 7490, stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P007', nombre: 'Cemento Polpaico Gris 25 Kg', marca: 'Polpaico',
    categoria: 'Cemento y Hormigón', foto_url: '', sku: 'CEM-PO-25', unidad: 'saco',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 8290, precio_oferta: 7490, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 7890, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 7990, precio_oferta: null, stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P008', nombre: 'Volcanita Estándar 8mm 1.2×2.4m', marca: 'Volcán',
    categoria: 'Aislación', foto_url: '', sku: 'VOL-VC-8', unidad: 'plancha',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 9490, precio_oferta: 8490, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 8990, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 9190, precio_oferta: null, stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P009', nombre: 'Cable THW 12 AWG Rollo 100m', marca: 'Conduit',
    categoria: 'Electricidad', foto_url: '', sku: 'CAB-CO-12', unidad: 'rollo',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 47990, precio_oferta: null, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 44990, precio_oferta: null, stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 45990, precio_oferta:43990, stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P010', nombre: 'Tablero OSB 11mm 1.22×2.44m', marca: 'Arauco',
    categoria: 'Madera y Tableros', foto_url: '', sku: 'OSB-AR-11', unidad: 'plancha',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 14990, precio_oferta: 12990, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 13990, precio_oferta: null,  stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 14490, precio_oferta: null,  stock: false,url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P011', nombre: 'Mortero Cola Marrón 25 Kg', marca: 'Volcán',
    categoria: 'Cemento y Hormigón', foto_url: '', sku: 'MOR-VC-25', unidad: 'saco',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 9490, precio_oferta: null,  stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 8790, precio_oferta: null,  stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 9190, precio_oferta: 8490,  stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
  {
    id: 'P012', nombre: 'Pintura Esmalte Glidden Negro Satinado 1GL', marca: 'Glidden',
    categoria: 'Pintura', foto_url: '', sku: 'PIN-GL-N1', unidad: 'galón',
    tiendas: [
      { tienda: 'Sodimac', precio_real: 15490, precio_oferta: 13990, stock: true, url_producto: 'https://sodimac.cl', fecha_actualizacion: '2026-04-25' },
      { tienda: 'Easy',    precio_real: 14990, precio_oferta: null,  stock: true, url_producto: 'https://easy.cl',    fecha_actualizacion: '2026-04-25' },
      { tienda: 'Imperial',precio_real: 15990, precio_oferta: null,  stock: true, url_producto: 'https://imperial.cl',fecha_actualizacion: '2026-04-25' },
    ],
  },
];

// Historial de precios mock (HU9)
const MOCK_HISTORIAL: Record<string, PrecioHistorico[]> = {
  P001: [
    { fecha: '2026-01-25', precio: 8490, tienda: 'Sodimac' },
    { fecha: '2026-02-01', precio: 8290, tienda: 'Sodimac' },
    { fecha: '2026-02-15', precio: 7990, tienda: 'Sodimac' },
    { fecha: '2026-03-01', precio: 7490, tienda: 'Easy' },
    { fecha: '2026-03-15', precio: 7290, tienda: 'Easy' },
    { fecha: '2026-04-01', precio: 6990, tienda: 'Sodimac' },
    { fecha: '2026-04-25', precio: 6990, tienda: 'Sodimac' },
  ],
  P002: [
    { fecha: '2026-01-25', precio: 4990, tienda: 'Sodimac' },
    { fecha: '2026-02-10', precio: 4790, tienda: 'Sodimac' },
    { fecha: '2026-03-01', precio: 4590, tienda: 'Sodimac' },
    { fecha: '2026-03-20', precio: 4290, tienda: 'Easy' },
    { fecha: '2026-04-10', precio: 4190, tienda: 'Imperial' },
    { fecha: '2026-04-25', precio: 4190, tienda: 'Imperial' },
  ],
};

// Usuarios demo
const MOCK_USERS: Array<Usuario & { password: string }> = [
  { id: 'U001', nombre: 'Usuario Demo', email: 'usuario@demo.cl', tipo: 'profesional', password: 'demo123' },
  { id: 'U002', nombre: 'Administrador', email: 'admin@constructo.cl', tipo: 'empresa', password: 'admin123' },
];

// ── HELPERS ──────────────────────────────────────────────────

const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

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

// ── API FUNCTIONS ─────────────────────────────────────────────

/**
 * GET /api/v1/uf/current
 * Futura integración: https://mindicador.cl/api/uf
 */
export async function fetchUF(): Promise<UFData> {
  await delay(300);
  return { valor: 39847.23, fecha: '2026-04-25', fuente: 'mindicador.cl (mock)' };
}

/**
 * GET /api/v1/products?q=&tienda=&categoria=
 * HU1 + HU2 — Búsqueda y comparación multitienda
 */
export async function searchProducts(query: string, categoria?: string): Promise<Producto[]> {
  await delay(700);
  const q = query.trim().toLowerCase();
  if (!q) return [];

  let results = MOCK_PRODUCTOS.filter(p =>
    p.nombre.toLowerCase().includes(q) ||
    p.marca.toLowerCase().includes(q) ||
    p.categoria.toLowerCase().includes(q) ||
    p.sku.toLowerCase().includes(q)
  );

  if (categoria && categoria !== 'Todos') {
    results = results.filter(p => p.categoria === categoria);
  }

  return results;
}

/**
 * GET /api/v1/products/:id/history
 * HU9 — Historial de precios (últimos 3 meses)
 */
export async function fetchPriceHistory(productId: string): Promise<PrecioHistorico[]> {
  await delay(500);
  return MOCK_HISTORIAL[productId] ?? [];
}

/**
 * POST /api/v1/auth/register
 * HU8 — Registro de usuario
 */
export async function registerUser(
  nombre: string, email: string, password: string, tipo: string
): Promise<{ success: boolean; error?: string }> {
  await delay(850);
  if (MOCK_USERS.find(u => u.email === email)) {
    return { success: false, error: 'EMAIL_EXISTS' };
  }
  MOCK_USERS.push({ id: 'U' + Date.now(), nombre, email, tipo: tipo as any, password });
  return { success: true };
}

/**
 * POST /api/v1/auth/login
 * HU8 — Login JWT (mock: devuelve usuario)
 */
export async function loginUser(
  email: string, password: string
): Promise<{ success: boolean; user?: Usuario; error?: string }> {
  await delay(850);
  const user = MOCK_USERS.find(u => u.email === email);
  if (!user) return { success: false, error: 'EMAIL_NOT_FOUND' };
  if (user.password !== password) return { success: false, error: 'WRONG_PASSWORD' };
  const { password: _, ...userData } = user;
  return { success: true, user: userData };
}

/**
 * POST /api/v1/quotes
 * HU7 — Guardar cotización
 */
export async function saveCotizacion(
  nombre_proyecto: string, items: QuoteItem[], ufValue: number
): Promise<{ success: boolean; id: string }> {
  await delay(400);
  const total_clp = items.reduce((s, i) => s + getPrecioFinal(i.tienda_seleccionada) * i.cantidad, 0);
  return { success: true, id: 'COT-' + Date.now() };
}

/**
 * GET /api/v1/quotes (localStorage mock para sprint)
 * HU7 — Listar cotizaciones
 */
export function getLocalCotizaciones(userEmail: string): Cotizacion[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem('cc_quotes_' + userEmail) ?? '[]');
  } catch { return []; }
}

export function saveLocalCotizacion(userEmail: string, cot: Cotizacion): void {
  if (typeof window === 'undefined') return;
  const existing = getLocalCotizaciones(userEmail);
  existing.unshift(cot);
  localStorage.setItem('cc_quotes_' + userEmail, JSON.stringify(existing));
}

export function deleteLocalCotizacion(userEmail: string, id: string): void {
  if (typeof window === 'undefined') return;
  const existing = getLocalCotizaciones(userEmail).filter(c => c.id !== id);
  localStorage.setItem('cc_quotes_' + userEmail, JSON.stringify(existing));
}

export const CATEGORIAS = [
  'Todos', 'Cemento y Hormigón', 'Fierro y Acero', 'Madera y Tableros',
  'Pintura', 'Cerámicos y Porcelanato', 'Tuberías y Sanitarios',
  'Electricidad', 'Aislación',
];
