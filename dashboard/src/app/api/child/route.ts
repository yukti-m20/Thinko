import { NextResponse } from "next/server";
import { SELECTED_CHILD_COOKIE } from "@/lib/data";

export async function POST(request: Request) {
  const body = (await request.json()) as { childId?: string };
  const res = NextResponse.json({ ok: true });
  if (body.childId) {
    res.cookies.set(SELECTED_CHILD_COOKIE, body.childId, {
      path: "/",
      httpOnly: true,
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365,
    });
  }
  return res;
}
