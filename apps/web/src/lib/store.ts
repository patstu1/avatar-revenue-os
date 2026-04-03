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
  hydrated: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  hydrated: false,
  setAuth: (user, token) => {
    localStorage.setItem('aro_token', token);
    localStorage.setItem('aro_user', JSON.stringify(user));
    document.cookie = `aro_token=${token}; path=/; max-age=${60 * 60 * 24}; SameSite=Lax`;
    set({ user, token, isAuthenticated: true, hydrated: true });
  },
  logout: () => {
    localStorage.removeItem('aro_token');
    localStorage.removeItem('aro_user');
    document.cookie = 'aro_token=; path=/; max-age=0';
    set({ user: null, token: null, isAuthenticated: false });
  },
  hydrate: () => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('aro_token');
    const userStr = localStorage.getItem('aro_user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        document.cookie = `aro_token=${token}; path=/; max-age=${60 * 60 * 24}; SameSite=Lax`;
        set({ user, token, isAuthenticated: true, hydrated: true });
      } catch {
        set({ user: null, token: null, isAuthenticated: false, hydrated: true });
      }
    } else {
      set({ hydrated: true });
    }
  },
}));

interface AppState {
  selectedBrandId: string | null;
  setSelectedBrandId: (id: string | null) => void;
  hydrateSelectedBrand: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedBrandId: typeof window !== 'undefined' ? localStorage.getItem('aro_brand_id') : null,
  setSelectedBrandId: (id) => {
    if (typeof window !== 'undefined') {
      if (id) {
        localStorage.setItem('aro_brand_id', id);
      } else {
        localStorage.removeItem('aro_brand_id');
      }
    }
    set({ selectedBrandId: id });
  },
  hydrateSelectedBrand: () => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('aro_brand_id');
      if (stored) set({ selectedBrandId: stored });
    }
  },
}));
