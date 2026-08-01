import { UserManager, WebStorageStateStore } from "oidc-client-ts";


export const oidcEnabled = import.meta.env.VITE_OIDC_ENABLED === "true";

export const userManager = oidcEnabled
  ? new UserManager({
      authority: import.meta.env.VITE_OIDC_AUTHORITY ?? "",
      client_id: import.meta.env.VITE_OIDC_CLIENT_ID ?? "",
      redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI ?? window.location.origin,
      post_logout_redirect_uri:
        import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI ?? window.location.origin,
      response_type: "code",
      scope: import.meta.env.VITE_OIDC_SCOPE ?? "openid profile email",
      automaticSilentRenew: true,
      userStore: new WebStorageStateStore({ store: window.localStorage }),
    })
  : null;


export async function getAccessToken(): Promise<string | null> {
  if (!userManager) return null;
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}


export async function signOut(): Promise<void> {
  window.localStorage.removeItem("bugsignal_project_id");
  if (userManager) await userManager.signoutRedirect();
}
