# ContructoCompare
Para instalar librerías faltantes utilizar ->

`pip install fastapi uvicorn sqlalchemy asyncpg pydantic python-dotenv passlib bcrypt==4.0.1 python-jose`  
`pip install "pydantic[email]"`

http://127.0.0.1:8000/docs revisar documentación y probar

## Variables privadas y conexión a BD

1. Copia el archivo `backend/.env.example` a `backend/.env`.
2. Reemplaza usuario, contraseña, host y base de datos.
3. `backend/.env` queda fuera de Git por seguridad.

Ejemplo de URL para PostgreSQL local:

`DATABASE_URL=postgresql+asyncpg://constructo_user:tu_password@localhost:5432/constructo_db`

Variables recomendadas para desarrollo:

- `AUTO_CREATE_TABLES=true`
- `JWT_SECRET_KEY=tu_clave_local`
- `JWT_ALGORITHM=HS256`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`

## Flujo de autenticacion basico

1. `POST /api/v1/users/register` para crear usuario.
2. `POST /api/v1/users/login` con correo y password para obtener `access_token`.
3. `GET /api/v1/users/me` con header `Authorization: Bearer <token>` para obtener el usuario autenticado.