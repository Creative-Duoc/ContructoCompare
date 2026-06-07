import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import s from '../styles/Auth.module.css';

export default function LoginPage() {
  const { user, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [pass, setPass]   = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (user) router.replace('/app'); }, [user]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!email || !pass) { setError('Completa todos los campos.'); return; }
    setLoading(true);
    const res = await login(email, pass);
    setLoading(false);
    if (res.error === 'EMAIL_NOT_FOUND') setError('No encontramos una cuenta con ese correo.');
    else if (res.error === 'WRONG_PASSWORD') setError('Contraseña incorrecta. Verifica e intenta nuevamente.');
    else if (res.error) setError('Error al iniciar sesión. Intenta de nuevo.');
  }

  return (
    <div className={s.layout}>
      {/* Panel izquierdo */}
      <div className={s.left}>
        <div className={s.leftLogo}>
          <span className={s.logoIcon}>CC</span>
          <div className={s.logoText}>ConstructoCompare <span>PRO</span></div>
        </div>
        <h2>Bienvenido de<br/><em>vuelta</em> 👋</h2>
        <p className={s.leftDesc}>
          Inicia sesión para comparar precios de materiales entre
          Sodimac, Easy e Imperial y generar cotizaciones en CLP y UF.
        </p>
        {[
          { icon: '📊', title: 'Comparación multitienda', sub: 'Sodimac, Easy e Imperial en una sola vista' },
          { icon: '💲', title: 'Conversión automática a UF', sub: 'Valor actualizado diariamente desde Mindicador' },
          { icon: '📄', title: 'Cotizaciones en PDF', sub: 'Exporta presupuestos profesionales al instante' },
        ].map(b => (
          <div key={b.title} className={s.benefit}>
            <span className={s.benefitIcon}>{b.icon}</span>
            <div>
              <strong>{b.title}</strong>
              <span>{b.sub}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Panel derecho */}
      <div className={s.right}>
        <div className={s.formWrap}>
          <div className={s.formHeader}>
            <h1>Iniciar sesión</h1>
            <p>Ingresa tus credenciales para continuar</p>
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
              <label>Correo electrónico</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="tu@email.cl" autoComplete="email" />
              </div>
            </div>

            <div className={s.field}>
              <label>Contraseña</label>
              <div className={s.inputWrap}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input type="password" value={pass} onChange={e => setPass(e.target.value)}
                  placeholder="••••••••" autoComplete="current-password" />
              </div>
            </div>

            <button type="submit" className={s.submitBtn} disabled={loading}>
              {loading ? <span className={s.btnSpinner} /> : 'Ingresar'}
            </button>
          </form>

          <p className={s.footer}>
            ¿No tienes cuenta? <Link href="/register">Regístrate gratis</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
