import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const formData = await request.formData();
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/work");
  const configuredPassword = process.env.ASSISTANT_WEB_PASSWORD ?? "";

  if (!configuredPassword || password !== configuredPassword) {
    return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
  }

  cookies().set("assistant_session", configuredPassword, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  });

  return NextResponse.redirect(new URL(next, request.url), { status: 303 });
}

export async function DELETE() {
  cookies().delete("assistant_session");
  return NextResponse.json({ ok: true });
}
