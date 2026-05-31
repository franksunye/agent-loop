import { Suspense } from "react";
import { LoginForm } from "@/components/login-form";

export const dynamic = "force-dynamic";

export default function LoginPage() {
  return (
    <main className="flex min-h-full items-center justify-center px-6 py-12">
      <Suspense fallback={<div className="text-muted-foreground text-sm">加载中…</div>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
