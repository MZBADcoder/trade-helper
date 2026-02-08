import { apiRequest } from "@/shared/api";

import { type AccessToken, type AuthPayload, type SessionUser } from "../model/types";

export async function login(payload: AuthPayload): Promise<AccessToken> {
  return apiRequest<AccessToken>("/auth/login", {
    method: "POST",
    body: payload
  });
}

export async function register(payload: AuthPayload): Promise<SessionUser> {
  return apiRequest<SessionUser>("/auth/register", {
    method: "POST",
    body: payload
  });
}

export async function getCurrentUser(token: string): Promise<SessionUser> {
  return apiRequest<SessionUser>("/auth/me", { token });
}
