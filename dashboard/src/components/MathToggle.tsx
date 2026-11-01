"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

function newProblem() {
  const a = Math.floor(Math.random() * 9) + 2;
  const b = Math.floor(Math.random() * 9) + 2;
  return { a, b };
}

export function MathToggle({
  targetHref,
  label,
  theme = "green",
}: {
  targetHref: string;
  label: string;
  theme?: "green" | "white";
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState(newProblem);
  const [answer, setAnswer] = useState("");
  const [shake, setShake] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const handleOpen = useCallback(() => {
    setProblem(newProblem());
    setAnswer("");
    setShake(false);
    setOpen(true);
  }, []);

  const handleClose = useCallback(() => setOpen(false), []);

  const handleSubmit = useCallback(() => {
    if (parseInt(answer) === problem.a * problem.b) {
      setOpen(false);
      router.push(targetHref);
    } else {
      setShake(true);
      setTimeout(() => {
        setShake(false);
        setProblem(newProblem());
        setAnswer("");
      }, 550);
    }
  }, [answer, problem, targetHref, router]);

  const btnStyle: React.CSSProperties =
    theme === "green"
      ? {
          background: "#4caf50",
          color: "white",
          border: "none",
        }
      : {
          background: "rgba(255,255,255,0.7)",
          color: "#1b5e20",
          border: "1.5px solid rgba(0,0,0,0.12)",
        };

  return (
    <>
      <button
        onClick={handleOpen}
        style={{
          ...btnStyle,
          position: "fixed",
          bottom: "clamp(1.5rem, 4vh, 3rem)",
          right: "1.5rem",
          borderRadius: "999px",
          padding: "0.55rem 1.3rem",
          fontSize: "0.78rem",
          fontWeight: 600,
          cursor: "pointer",
          backdropFilter: "blur(8px)",
          boxShadow: "0 2px 14px rgba(0,0,0,0.13)",
          zIndex: 50,
          letterSpacing: "0.02em",
          transition: "opacity 0.15s",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = "0.85")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = "1")}
      >
        {label} →
      </button>

      {open && (
        <div
          onClick={handleClose}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0,0,0,0.35)",
            backdropFilter: "blur(4px)",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "white",
              borderRadius: "1.25rem",
              padding: "2rem 2rem 1.75rem",
              minWidth: "270px",
              textAlign: "center",
              boxShadow: "0 8px 40px rgba(0,0,0,0.18)",
              animation: shake ? "mathShake 0.5s ease" : undefined,
            }}
          >
            <p
              style={{
                fontSize: "0.7rem",
                fontWeight: 700,
                color: "#aaa",
                letterSpacing: "0.07em",
                textTransform: "uppercase",
                marginBottom: "0.6rem",
              }}
            >
              Parent check
            </p>
            <p
              style={{
                fontSize: "2.25rem",
                fontWeight: 800,
                color: "#1a1a1a",
                marginBottom: "1.25rem",
                letterSpacing: "-0.02em",
              }}
            >
              {problem.a} × {problem.b} = ?
            </p>
            <input
              ref={inputRef}
              type="number"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="your answer"
              style={{
                width: "100%",
                border: "2px solid #e0e0e0",
                borderRadius: "0.75rem",
                padding: "0.65rem 1rem",
                fontSize: "1.2rem",
                textAlign: "center",
                outline: "none",
                marginBottom: "0.85rem",
                boxSizing: "border-box",
              }}
            />
            <button
              onClick={handleSubmit}
              style={{
                width: "100%",
                background: "#4caf50",
                color: "white",
                border: "none",
                borderRadius: "0.75rem",
                padding: "0.65rem",
                fontWeight: 700,
                fontSize: "0.95rem",
                cursor: "pointer",
              }}
            >
              Go
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes mathShake {
          0%,100% { transform: translateX(0); }
          20%     { transform: translateX(-10px); }
          40%     { transform: translateX(10px); }
          60%     { transform: translateX(-7px); }
          80%     { transform: translateX(7px); }
        }
      `}</style>
    </>
  );
}
