/** 最简 Console 登录：固定账号（环境变量）+ HttpOnly Cookie。 */

export const AUTH_COOKIE = "aol_console_session";

export function isAuthEnabled(): boolean {
  return Boolean(process.env.CONSOLE_AUTH_PASSWORD?.trim());
}

export function authUser(): string {
  return (process.env.CONSOLE_AUTH_USER ?? "admin").trim();
}

export function sessionSecret(): string {
  const explicit = process.env.CONSOLE_SESSION_SECRET?.trim();
  if (explicit) return explicit;
  const password = process.env.CONSOLE_AUTH_PASSWORD?.trim();
  if (password) return password;
  return "dev-insecure-session";
}

export function verifyCredentials(username: string, password: string): boolean {
  if (!isAuthEnabled()) return true;
  const u = username.trim();
  const p = password;
  return u === authUser() && p === process.env.CONSOLE_AUTH_PASSWORD;
}

export function verifySessionCookie(value: string | undefined): boolean {
  if (!isAuthEnabled()) return true;
  if (!value) return false;
  return value === sessionSecret();
}

export const SESSION_MAX_AGE = 60 * 60 * 24 * 7; // 7 days
