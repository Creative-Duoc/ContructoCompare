import Link from 'next/link';
import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useQuote } from '../../hooks/useQuote';
import s from './Navbar.module.css';

interface NavbarProps {
  ufValue: number;
  onOpenQuote: () => void;
}

export default function Navbar({ ufValue, onOpenQuote }: NavbarProps) {
  const { user, logout } = useAuth();
  const { items } = useQuote();

  const initials = user?.nombre?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() ?? 'U';
  const clpFormat = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', minimumFractionDigits: 0 });


  return (
    <nav className={s.navbar}>
      <Link href="/app" className={s.brand}>
        <span className={s.brandIcon}>CC</span>
        ConstructoCompare PRO
      </Link>

      <div className={s.right}>
        {ufValue > 0 && (
          <div className={s.ufChip}>
            UF hoy: <strong>{clpFormat.format(ufValue)}</strong>
          </div>
        )}

        <button className={s.quoteBtn} onClick={onOpenQuote}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <span className={s.quoteBtnText}>Mi cotización</span>
          {items.length > 0 && <span className={s.quoteBadge}>{items.length}</span>}
        </button>

        {user ? (
          <>
            <Link href="/perfil" style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className={s.userChip} style={{ cursor: 'pointer', transition: 'background 0.2s' }}>
                <div className={s.avatar}>{initials}</div>
                <span>{user.nombre?.split(' ')[0]}</span>
              </div>
            </Link>
            <button className={s.logoutBtn} onClick={logout}>Salir</button>
          </>
        ) : (
          <Link href="/login" className={s.loginBtn}>Iniciar sesión</Link>
        )}
      </div>
    </nav>
  );
}
