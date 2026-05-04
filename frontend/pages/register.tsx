import { useState, FormEvent } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import s from '../styles/Auth.module.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [nombre, setNombre] = useState('');
  const [email, setEmail]   = useState('');
  const [pass, setPass]     = useState('');
  const [tipo, setTipo]     = useState('1');
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    
    // Validaciones preventivas en Frontend
    if (!nombre || !email || !pass) { setError('Completa todos los campos.'); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('El formato del correo no es válido.'); return; }
    
    if (pass.length < 8) { 
      setError('La contraseña debe tener al menos 8 caracteres.'); 
      return; 
    }
    if (!/[a-zA-Z]/.test(pass)) {
      setError('La contraseña debe incluir al menos una letra.');
      return;
    }
    if (!/\d/.test(pass)) {
      setError('La contraseña debe incluir al menos un número.');
      return;
    }

    setLoading(true);
    const res = await register(nombre, email, pass, Number(tipo));
    setLoading(false);
    
    if (!res.success) {
      if (res.error === 'EMAIL_EXISTS') {
        setError('Ya existe una cuenta con ese correo.');
      } else {
        setError(res.error || 'Error al registrar el usuario.');
      }
      return;
    }
    
    router.push('/?registered=1');
  }

  return (
    <div className={s.layout}>
      <div className={s.left}>
        <div className={s.leftLogo}>
          <span className={s.logoIcon}>CC</span>
          <div className={s.logoText}>ConstructoCompare <span>PRO</span></div>
        </div>
        <h2>Crea tu cuenta <em>gratis</em></h2>
        <p className={s.leftDesc}>
          Accede al motor de comparación de precios y gestiona tus
          proyectos de construcción con cotizaciones en CLP y UF.
        </p>
        {[
          { icon: '🏗️', title: 'Para el sector construcción', sub: 'Diseñado para maestros, Pymes y contratistas' },
          { icon: '⚡', title: 'Resultados en segundos', sub: 'Motor de búsqueda multitienda optimizado' },
          { icon: '💼', title: 'Historial de proyectos', sub: 'Guarda y accede a tus cotizaciones' },
        ].map(b => (
          <div key={b.title} className={s.benefit}>
            <span className={s.benefitIcon}>{b.icon}</span>
            <div><strong>{b.title}</strong><span>{b.sub}</span></div>
          </div>
        ))}
      </div>

      <div className={s.right}>
        <div className={s.formWrap}>
          <div className={s.formHeader}>
            <h1>Crear cuenta</h1>
            <p>Completa tus datos para registrarte</p>
          </div>

          {error && (
            <div className={s.alert}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className={s.form}>
            <div className={s.field}>
              <label>Nombre completo</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
                <input type="text" value={nombre} onChange={e => setNombre(e.target.value)} placeholder="Tu nombre completo" />
              </div>
            </div>

            <div className={s.field}>
              <label>Correo electrónico</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="correo@ejemplo.cl" />
              </div>
            </div>

            <div className={s.field}>
              <label>Tipo de usuario</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
                <select value={tipo} onChange={e => setTipo(e.target.value)}>
                  <option value="1">Particular</option>
                  <option value="2">Profesional</option>
                  <option value="3">Empresa Constructora</option>
                </select>
              </div>
            </div>

            <div className={s.field}>
              <label>Contraseña</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input type="password" value={pass} onChange={e => setPass(e.target.value)} placeholder="Mínimo 8 caracteres" />
              </div>
            </div>

            <button type="submit" className={s.submitBtn} disabled={loading}>
              {loading ? <span className={s.btnSpinner} /> : 'Crear mi cuenta gratis'}
            </button>
          </form>

          <p className={s.footer}>
            ¿Ya tienes cuenta? <Link href="/">Inicia sesión</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
