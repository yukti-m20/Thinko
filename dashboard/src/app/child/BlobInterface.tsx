"use client";

import { useEffect, useRef, useCallback } from "react";
import gsap from "gsap";
import { MathToggle } from "@/components/MathToggle";

// ─── Blob path generator ─────────────────────────────────────────────────────
// Generates a smooth organic blob as an SVG path string.
// Uses a Catmull-Rom → cubic-bezier conversion for smooth curves.

type Pt = [number, number];

function catmullRomToBezier(pts: Pt[], closed: boolean): string {
  const n = pts.length;
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n];
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const p3 = pts[(i + 2) % n];
    if (!closed && (i === n - 1)) break;
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2[0]} ${p2[1]}`;
  }
  if (closed) d += " Z";
  return d;
}

function blobPath(cx: number, cy: number, r: number, variance: number, nPts: number, seed: number): string {
  const pts: Pt[] = [];
  for (let i = 0; i < nPts; i++) {
    const angle = (i / nPts) * Math.PI * 2 - Math.PI / 2;
    const wobble =
      Math.sin(seed + i * 2.1) * variance +
      Math.cos(seed * 0.7 + i * 1.4) * variance * 0.4 +
      Math.sin(seed * 1.3 + i * 3.7) * variance * 0.25;
    const radius = r + wobble;
    pts.push([cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius]);
  }
  return catmullRomToBezier(pts, true);
}

// ─── Component ────────────────────────────────────────────────────────────────

type State = "idle" | "agent_speaking" | "child_speaking";
type TranscriptEntry = { role: "user" | "assistant"; content: string };

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ??
  (typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8765`
    : "ws://localhost:8765");

const W = 500;
const H = 500;
const CX = W / 2;
const CY = H / 2;
const BASE_R = 130;
const VARIANCE = 18;
const N_PTS = 14;

export default function BlobInterface() {
  const greenRef = useRef<SVGPathElement>(null);
  const yellowRef = useRef<SVGPathElement>(null);
  const wrapperRef = useRef<SVGGElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const transcriptRef = useRef<TranscriptEntry[]>([]);
  const seedRef = useRef(0);
  const stateRef = useRef<State>("idle");
  const animRef = useRef<gsap.core.Tween | null>(null);

  // Generate a new blob path at a given seed
  const nextPath = useCallback((seed: number, scale = 1) =>
    blobPath(CX, CY, BASE_R * scale, VARIANCE * scale, N_PTS, seed), []);

  // Morph the green blob to a new random shape
  const morphBlob = useCallback(() => {
    if (!greenRef.current) return;
    seedRef.current += 0.6;
    const to = nextPath(seedRef.current);
    gsap.to(greenRef.current, {
      attr: { d: to },
      duration: stateRef.current === "agent_speaking" ? 0.4 : 2.5,
      ease: stateRef.current === "agent_speaking" ? "power2.inOut" : "sine.inOut",
      onComplete: morphBlob,
    });
  }, [nextPath]);

  // Apply scale + colour tween based on speaking state
  const applyState = useCallback((state: State) => {
    stateRef.current = state;
    if (!wrapperRef.current || !greenRef.current || !yellowRef.current) return;

    // Kill any running scale tween
    gsap.killTweensOf(wrapperRef.current);
    gsap.killTweensOf(yellowRef.current);

    if (state === "agent_speaking") {
      // Green blob pulses larger, yellow hidden
      gsap.to(wrapperRef.current, {
        scale: 1.22,
        transformOrigin: "50% 50%",
        duration: 0.35,
        ease: "power2.out",
        yoyo: true,
        repeat: -1,
      });
      gsap.to(yellowRef.current, { opacity: 0, scale: 0.3, duration: 0.25 });
    } else if (state === "child_speaking") {
      // Green blob steady, yellow inner blob fully bright
      gsap.to(wrapperRef.current, { scale: 1, duration: 0.3, ease: "power2.out" });
      gsap.to(yellowRef.current, { opacity: 1, scale: 0.52, duration: 0.3, ease: "back.out(1.2)" });
    } else {
      // Idle — green blob breathes slowly, yellow softly glows to show it's listening
      gsap.to(wrapperRef.current, {
        scale: 1,
        transformOrigin: "50% 50%",
        duration: 0.6,
        ease: "power2.out",
        clearProps: "scale",
      });
      gsap.to(wrapperRef.current, {
        scale: 1.04,
        transformOrigin: "50% 50%",
        duration: 3,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 0.6,
      });
      // Soft yellow glow pulses in idle — indicates listening
      gsap.to(yellowRef.current, { opacity: 0.35, scale: 0.38, duration: 0.8, ease: "sine.inOut" });
      gsap.to(yellowRef.current, {
        opacity: 0.55,
        scale: 0.42,
        duration: 2.2,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 0.8,
      });
    }
  }, []);

  // Initial animation setup
  useEffect(() => {
    if (!greenRef.current || !yellowRef.current) return;

    // Set initial paths
    const initPath = nextPath(0);
    greenRef.current.setAttribute("d", initPath);
    yellowRef.current.setAttribute("d", initPath);

    // Start idle morph loop
    morphBlob();
    applyState("idle");

    // Connect to Python WebSocket bridge
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "state") {
            applyState(msg.value as State);
          } else if (msg.type === "transcript") {
            transcriptRef.current.push({ role: msg.role, content: msg.content });
          }
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        // Retry after 2s if disconnected
        setTimeout(connect, 2000);
      };
    }

    connect();
    return () => wsRef.current?.close();
  }, [morphBlob, applyState, nextPath]);

  const handleEmergencyStop = useCallback(async () => {
    const transcript = transcriptRef.current
      .map((t) => `${t.role.toUpperCase()}: ${t.content}`)
      .join("\n");

    // Signal Python side via WebSocket
    wsRef.current?.send(JSON.stringify({ type: "emergency_stop" }));

    // Also write directly to Supabase via API route
    const childId = new URLSearchParams(window.location.search).get("child_id") ?? "";
    const sessionId = new URLSearchParams(window.location.search).get("session_id") ?? "";

    await fetch("/api/emergency-stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ child_id: childId, session_id: sessionId || null, transcript }),
    }).catch(() => {});

    // Flash the button
    animRef.current?.kill();
  }, []);

  return (
    <div
      style={{
        background: "#e8f5e2",
        width: "100vw",
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        position: "relative",
        userSelect: "none",
      }}
    >
      {/* ── Blob SVG ── */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="min(70vw, 70vh)"
        height="min(70vw, 70vh)"
        style={{ overflow: "visible" }}
        aria-hidden="true"
      >
        <g ref={wrapperRef}>
          {/* Green outer blob */}
          <path
            ref={greenRef}
            fill="#4caf50"
            opacity={0.85}
          />
          {/* Yellow inner blob — same shape, smaller, child speaking indicator */}
          <path
            ref={yellowRef}
            fill="#ffd54f"
            opacity={0.35}
            style={{ transformOrigin: `${CX}px ${CY}px`, transform: "scale(0.38)" }}
          />
        </g>
      </svg>

      {/* ── Parent toggle ── */}
      <MathToggle targetHref="/" label="Parent view" theme="white" />

      {/* ── Emergency stop button ── */}
      <button
        onClick={handleEmergencyStop}
        aria-label="Emergency stop"
        style={{
          position: "absolute",
          bottom: "clamp(1.5rem, 4vh, 3rem)",
          left: "50%",
          transform: "translateX(-50%)",
          background: "rgba(255,255,255,0.55)",
          border: "1.5px solid rgba(0,0,0,0.12)",
          borderRadius: "999px",
          padding: "0.55rem 1.4rem",
          fontSize: "0.78rem",
          fontWeight: 600,
          color: "#c62828",
          cursor: "pointer",
          backdropFilter: "blur(8px)",
          letterSpacing: "0.03em",
          boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
          transition: "background 0.15s, box-shadow 0.15s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.85)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.55)";
        }}
      >
        stop
      </button>
    </div>
  );
}
