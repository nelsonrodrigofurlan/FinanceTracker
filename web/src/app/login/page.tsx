import { AuthShell } from "@/components/auth-shell";

import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <AuthShell title="Entrar" description="Acesso restrito. Login com verificação em duas etapas.">
      <LoginForm />
    </AuthShell>
  );
}
