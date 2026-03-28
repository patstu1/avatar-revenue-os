import { create } from 'zustand';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  setAuth: (user, token) => {
    localStorage.setItem('aro_token', token);
    localStorage.setItem('aro_user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('aro_token');
    localStorage.removeItem('aro_user');
    set({ user: null, token: null, isAuthenticated: false });
  },
  hydrate: () => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('aro_token');
    const userStr = localStorage.getItem('aro_user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        set({ user, token, isAuthenticated: true });
      } catch {
        set({ user: null, token: null, isAuthenticated: false });
      }
    }
  },
}));

interface AppState {
  selectedBrandId: string | null;
  setSelectedBrandId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedBrandId: null,
  setSelectedBrandId: (id) => set({ selectedBrandId: id }),
}));
