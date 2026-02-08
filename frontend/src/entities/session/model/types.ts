export type SessionUser = {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
};

export type AccessToken = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type AuthPayload = {
  email: string;
  password: string;
};

export type SessionStatus = "checking" | "anonymous" | "authenticated";
