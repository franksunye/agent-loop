/**
 * 最简 Console 登录：固定账号（环境变量）+ HttpOnly Cookie。
 * 不设 CONSOLE_AUTH_PASSWORD 则全站免登录（本地开发）。
 * 生产：设密码后列表/运营页需登录；企微深链路径见 isPublicPath。
 */

export const AUTH_COOKIE = "aol_console_session";

/** 管家从企微点进来的处置页及提交 API，试点阶段免登录。 */
export function isPublicPath(pathname: string): boolean {
  if (pathname.startsWith("/suggestions/")) return true;
  if (pathname === "/api/blockers" || pathname === "/api/outcomes") return true;
  return false;
}

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
