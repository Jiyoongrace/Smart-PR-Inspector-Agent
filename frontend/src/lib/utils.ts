import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}초`;
  const min = Math.floor(seconds / 60);
  const sec = Math.round(seconds % 60);
  return `${min}분 ${sec}초`;
}

export function getRiskColor(risk: string): string {
  const colors: Record<string, string> = {
    low: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    medium: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    high: "text-orange-400 bg-orange-400/10 border-orange-400/20",
    critical: "text-red-400 bg-red-400/10 border-red-400/20",
  };
  return colors[risk] ?? "text-gray-400 bg-gray-400/10";
}

export function getRiskLabel(risk: string): string {
  const labels: Record<string, string> = {
    low: "낮음",
    medium: "보통",
    high: "높음",
    critical: "위험",
  };
  return labels[risk] ?? risk;
}

export function getNodeStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: "text-gray-500",
    running: "text-blue-400",
    success: "text-emerald-400",
    failed: "text-red-400",
    skipped: "text-gray-600",
  };
  return colors[status] ?? "text-gray-400";
}
