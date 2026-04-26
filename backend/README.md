# ConstructoCompare - Backend

El backend expone la API REST del proyecto. Aquí viven la autenticación, la persistencia de datos, los modelos de inventario y las rutas que consume el frontend.

## Cuándo usarlo

- Para levantar la API local y probar endpoints.
- Para registrar usuarios e iniciar sesión.
- Para consultar o extender la lógica de inventario y seguridad.

## Tecnologías

- FastAPI
- SQLAlchemy 2.0 asíncrono
- PostgreSQL
- JWT con `passlib` y `python-jose`
- Pydantic 2.x

## Instalación y configuración

1. Instala las dependencias (desde la raíz con el entorno virtual activo):

```bash
pip install -r requirement.txt
```

2. Crea el archivo de entorno:

```bash
cp backend/.env.example backend/.env
```

2. Completa las variables principales:

```env
DATABASE_URL=postgresql+asyncpg://usuario:password@localhost:5432/constructo_db
AUTO_CREATE_TABLES=true
JWT_SECRET_KEY=una_clave_secreta_muy_segura
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## Cómo ejecutar

Desde la raíz del proyecto, con el entorno virtual activo:

```bash
cd backend
python app/main.py
```

También puedes usar Uvicorn directamente:

```bash
uvicorn app.main:app --reload --port 8001
```

## Cómo probarlo

Una vez iniciado, abre:

- Swagger UI: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc

Endpoints base de usuarios:

- `POST /api/v1/users/register`
- `POST /api/v1/users/login`

Para rutas protegidas, envía el header:

```http
Authorization: Bearer <tu_token>
```

## Estructura

- `app/main.py`: punto de entrada de la API.
- `app/database.py`: conexión asíncrona a la base de datos.
- `app/security.py`: hash de contraseñas y JWT.
- `app/models/`: modelos de base de datos.
- `app/routes/`: endpoints de la API.
- `app/schemas/`: validación Pydantic.
