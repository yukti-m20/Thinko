import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireUser } from "@/lib/data";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const { supabase: userClient } = await requireUser();

    // Verify the parent owns this child before deleting
    const { data: child } = await userClient
      .from("children")
      .select("id")
      .eq("id", id)
      .maybeSingle();

    if (!child) {
      return NextResponse.json({ error: "Not found or not authorised" }, { status: 404 });
    }

    // Use service-role client to call the SQL function that cascades all deletes
    const admin = createAdminClient();
    const { error } = await admin.rpc("delete_child_data", { cid: id });

    if (error) {
      console.error("delete_child_data error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
