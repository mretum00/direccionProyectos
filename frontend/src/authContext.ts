
import { createContext } from 'react';
import type { User } from '@/types/user';

export type AuthStatus = 'checking' | 'anonymous' | 'authenticated';

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
