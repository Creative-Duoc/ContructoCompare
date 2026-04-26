# ConstructoCompare - Frontend

Este directorio contiene la interfaz web del proyecto. La app está construida con Next.js y TypeScript y consume la API del backend para mostrar productos, comparar precios y gestionar proyectos.

## Cuándo usarlo

- Para levantar la interfaz local y validar pantallas.
- Para probar la integración con el backend.
- Para desarrollar vistas de comparación, historial de precios y proyectos.

## Requisitos

- Node.js
- pnpm
- El backend ejecutándose en `http://localhost:8001`

## Instalación

```bash
pnpm install
```

## Cómo ejecutar

Modo desarrollo:

```bash
pnpm dev
```

Construcción para producción:

```bash
pnpm build
```

Arranque en producción:

```bash
pnpm start
```

Validación de lint:

```bash
pnpm lint
```

## Qué hace la app

- Busca productos por nombre o categoría.
- Compara precios entre retailers.
- Muestra historial de precios.
- Permite gestionar proyectos y cotizaciones.

## Conexión con el backend

La app consume la API de FastAPI en `http://localhost:8001/api/v1`. Si cambias el puerto o el host, ajusta la configuración de API en el frontend y revisa los permisos de CORS en el backend.

## Estructura útil

- `pages/`: rutas principales de Next.js.
- `components/`: componentes reutilizables.
- `hooks/`: lógica compartida de autenticación y cotización.
- `services/api.ts`: cliente para hablar con la API.
- `styles/`: estilos globales y por vista.
