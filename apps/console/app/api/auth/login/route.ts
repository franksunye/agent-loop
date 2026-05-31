import { NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  isAuthEnabled,
  sessionSecret,
  verifyCredentials,
  SESSION_MAX_AGE,
} from "@/lib/auth";

export async function POST(req: Request) {
  if (!isAuthEnabled()) {
    return NextResponse.json({ ok: true, auth: "disabled" });
  }

  let body: { username?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const username = body.username ?? "";
  const password = body.password ?? "";
  if (!verifyCredentials(username, password)) {
    return NextResponse.json({ error: "invalid credentials" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, sessionSecret(), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}
