import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl", className)} {...props} />;
}
