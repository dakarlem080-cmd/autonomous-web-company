import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL || "https://autonomous-web-company-production.up.railway.app";

export async function GET(request: NextRequest) {
  const projectId = request.nextUrl.searchParams.get("project_id");
  if (!projectId || !/^\d+$/.test(projectId)) {
    return NextResponse.json({ error: "project_id_required" }, { status: 400 });
  }

  // GitHub OAuth credentials live only in the Railway backend.
  // The browser must never require GITHUB_CLIENT_ID/SECRET in Vercel.
  return NextResponse.redirect(`${API}/api/projects/${projectId}/github/oauth/start`);
}
