import { NextRequest, NextResponse } from "next/server";

const GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize";

export async function GET(request: NextRequest) {
  const projectId = request.nextUrl.searchParams.get("project_id");
  if (!projectId || !/^\d+$/.test(projectId)) {
    return NextResponse.json({ error: "project_id_required" }, { status: 400 });
  }

  const clientId = process.env.GITHUB_CLIENT_ID;
  if (!clientId) {
    return NextResponse.json({ error: "github_oauth_not_configured" }, { status: 503 });
  }

  const state = crypto.randomUUID();
  const callback = `${request.nextUrl.origin}/api/github/callback`;
  const url = new URL(GITHUB_AUTHORIZE);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", callback);
  url.searchParams.set("scope", "read:user user:email repo read:org workflow");
  url.searchParams.set("state", state);
  url.searchParams.set("allow_signup", "true");

  const response = NextResponse.redirect(url);
  response.cookies.set("awc_github_oauth", JSON.stringify({ state, projectId }), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 600,
    path: "/",
  });
  return response;
}
