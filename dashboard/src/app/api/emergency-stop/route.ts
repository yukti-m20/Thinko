import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST(req: NextRequest) {
  try {
    const { child_id, session_id, transcript } = await req.json();
    if (!child_id || !transcript) {
      return NextResponse.json({ error: "child_id and transcript required" }, { status: 400 });
    }

    const supabase = createAdminClient();
    const { error } = await supabase.from("emergency_stops").insert({
      child_id,
      session_id: session_id ?? null,
      transcript,
    });

    if (error) {
      console.error("emergency_stop insert error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
