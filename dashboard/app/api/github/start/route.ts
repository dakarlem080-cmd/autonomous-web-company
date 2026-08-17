import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL || "https://autonomous-web-company-production.up.railway.app";

export async function GET(request: NextRequest) {
  const projectId = request.nextUrl.searchParams.get("project_id");
  if (!projectId || !/^\d+$/.test(projectId)) {
    return NextResponse.json({ error: "project_id_required" }, { status: 400 });
  }

  // OAuth credentials belong only to Railway. Vercel is a redirect proxy.
  const target = new URL(`${API}/api/projects/${projectId}/github/oauth/start`);
  return NextResponse.redirect(target, { status: 307 });
}
