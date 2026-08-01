import { ReactNode, useEffect, useState } from "react";
import { User } from "oidc-client-ts";

import { oidcEnabled, userManager } from "../auth";
import { getCurrentUser } from "../api/client";


export function AuthGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(oidcEnabled);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userManager) return;
    const manager = userManager;
    const finishAuthentication = async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        if (params.has("code") && params.has("state")) {
          await manager.signinRedirectCallback();
          window.history.replaceState({}, document.title, window.location.pathname);
        }
        const authenticatedUser = await manager.getUser();
        setUser(authenticatedUser);
        if (authenticatedUser && !authenticatedUser.expired) await getCurrentUser();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "OIDC sign-in failed.");
      } finally {
        setLoading(false);
      }
    };
    void finishAuthentication();
  }, []);

  if (!oidcEnabled) return <>{children}</>;
  if (loading) return <CenteredMessage>Completing secure sign-in…</CenteredMessage>;
  if (error) return <CenteredMessage>{error}</CenteredMessage>;
  if (!user || user.expired) {
    return (
      <CenteredMessage>
        <button
          type="button"
          className="rounded bg-signal px-4 py-2 font-semibold text-white"
          onClick={() => void userManager?.signinRedirect()}
        >
          Sign in with OIDC
        </button>
      </CenteredMessage>
    );
  }
  return <>{children}</>;
}


function CenteredMessage({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-panel p-6">
      <div className="rounded-lg border border-line bg-white p-8 text-center text-slate-700 shadow-sm">
        {children}
      </div>
    </main>
  );
}
