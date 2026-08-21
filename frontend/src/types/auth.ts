export interface UserProfile {
  user_id: string;
  email: string;
  full_name?: string;
  phone?: string;
  role: string;
  google_user_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  isAuthenticated: boolean;
  signUp: (email: string, password: string, fullName: string) => Promise<{ error: string | null }>;
  login: (email: string, password: string) => Promise<{ error: string | null }>;
  loginWithGoogleCredential: (credential: string) => Promise<{ error: string | null }>;
  loginWithGoogle: () => void;
  logout: () => void;
}

export interface AuthFormError {
  email?: string;
  password?: string;
  confirmPassword?: string;
  fullName?: string;
  general?: string;
}
