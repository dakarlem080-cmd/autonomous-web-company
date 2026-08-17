import { NextRequest, NextResponse } from "next/server";

const TOKEN_URL = "https://github.com/login/oauth/access_token";
const USER_URL = "https://api.github.com/user";
const API = process.env.NEXT_PUBLIC_API_URL || "https://autonomous-web-company-production.up.railway.app";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const returnedState = request.nextUrl.searchParams.get("state");
  const denied = request.nextUrl.searchParams.get("error");
  const cookie = request.cookies.get("awc_github_oauth")?.value;
  const dashboard = request.nextUrl.origin;

  let saved: { state: string; projectId: string } | null = null;
  try { saved = cookie ? JSON.parse(cookie) : null; } catch { saved = null; }

  if (denied) return NextResponse.redirect(`${dashboard}/settings?tab=connections&github=denied`);
  if (!code || !returnedState || !saved || saved.state !== returnedState) {
    return NextResponse.redirect(`${dashboard}/settings?tab=connections&github=error&reason=invalid_state`);
  }

  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    return NextResponse.redirect(`${dashboard}/settings?tab=connections&github=error&reason=not_configured`);
  }

  try {
    const redirectUri = `${request.nextUrl.origin}/api/github/callback`;
    const tokenResponse = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret, code, redirect_uri: redirectUri }),
      cache: "no-store",
    });
    const token = await tokenResponse.json();
    if (!tokenResponse.ok || token.error || !token.access_token) throw new Error(token.error_description || token.error || "github_token_exchange_failed");

    const profileResponse = await fetch(USER_URL, {
      headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token.access_token}`, "X-GitHub-Api-Version": "2022-11-28" },
      cache: "no-store",
    });
    const profile = profileResponse.ok ? await profileResponse.json() : {};

    const stored = JSON.stringify({ access_token: token.access_token, token_type: token.token_type, scope: token.scope, github_login: profile.login || "", github_name: profile.name || "" });
    const save = await fetch(`${API}/api/projects/${saved.projectId}/secrets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "github_oauth", value: stored }),
      cache: "no-store",
    });
    if (!save.ok) throw new Error(`backend_save_failed_${save.status}`);

    const response = NextResponse.redirect(`${dashboard}/settings?tab=connections&github=connected&account=${encodeURIComponent(profile.login || "GitHub")}`);
    response.cookies.delete("awc_github_oauth");
    return response;
  } catch (error) {
    console.error("GitHub OAuth callback failed", error);
    return NextResponse.redirect(`${dashboard}/settings?tab=connections&github=error`);
  }
}
