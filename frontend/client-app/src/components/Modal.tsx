"use client";

import { useEffect, useRef } from "react";

/** Accessible dialog: focuses itself on open, closes on Escape or backdrop, restores focus on close, traps Tab. */
export function Modal({ title, onClose, children, testId, wide = false }: { title: string; onClose: () => void; children: React.ReactNode; testId?: string; wide?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    box.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && box.current) {
        const f = box.current.querySelectorAll<HTMLElement>("a[href],button:not([disabled]),input,select,textarea,[tabindex='0']");
        if (f.length === 0) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" aria-label="Close dialog" tabIndex={-1} className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        className={`relative max-h-[90vh] w-full overflow-y-auto bg-white p-6 shadow-xl focus:outline-none ${wide ? "max-w-3xl" : "max-w-lg"}`} data-testid={testId}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="font-display text-2xl font-bold">{title}</h2>
          <button type="button" onClick={onClose} className="text-2xl leading-none" aria-label="Close">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}
