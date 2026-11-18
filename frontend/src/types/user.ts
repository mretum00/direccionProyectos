export interface User {
  id: number;
  username: string;
  created_at: string;
}

/** Respuesta de POST /api/auth/login. */
export interface LoginResponse {
  token: string;
  user: User;
}
