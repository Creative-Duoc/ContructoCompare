import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { loginUser, registerUser, Usuario } from '../services/api';

interface AuthCtx {
  user: Usuario | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<{ success: boolean; error?: string }>;
  register: (nombre: string, email: string, pass: string, tipo: number) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({} as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('cc_user');
      if (stored) setUser(JSON.parse(stored));
    } catch {}
    setLoading(false);
  }, []);

  async function login(email: string, pass: string) {
    const res = await loginUser(email, pass);
    if (res.success && res.user) {
      setUser(res.user);
      sessionStorage.setItem('cc_user', JSON.stringify(res.user));
      return { success: true };
    }
    return { success: false, error: res.error };
  }

  async function register(nombre: string, email: string, pass: string, tipo: number) {
    const res = await registerUser(nombre, email, pass, tipo);
    if (res.success) return { success: true };
    return { success: false, error: res.error };
  }

  function logout() {
    setUser(null);
    sessionStorage.removeItem('cc_user');
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
