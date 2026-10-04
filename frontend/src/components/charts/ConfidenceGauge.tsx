import { motion } from "framer-motion";
import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";
import { scaleIn, defaultTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";
import { CHART_TRACK } from "./chartTheme";

interface ConfidenceGaugeProps {
  value: number;
  label?: string;
  size?: number;
  className?: string;
}

export function ConfidenceGauge({
  value,
  label = "Confidence",
  size = 180,
  className,
}: ConfidenceGaugeProps) {
  const clamped = Math.min(100, Math.max(0, value));

  const colorClass =
    clamped >= 80
      ? "text-emerald-600"
      : clamped >= 60
      ? "text-amber-600"
      : "text-red-600";

  const fill =
    clamped >= 80 ? "#10B981" : clamped >= 60 ? "#F59E0B" : "#EF4444";

  const data = [
    { name: "score", value: clamped, fill },
  ];

  return (
    <motion.div
      variants={scaleIn}
      initial="initial"
      animate="animate"
      transition={defaultTransition}
      className={cn(
        "relative flex flex-col items-center justify-center",
        className
      )}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="75%"
            outerRadius="100%"
            startAngle={225}
            endAngle={-45}
            data={data}
            barSize={8}
          >
            <defs>
              <linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#4F46E5" />
                <stop offset="100%" stopColor="#EC4899" />
              </linearGradient>
            </defs>
            <RadialBar
              dataKey="value"
              cornerRadius={10}
              background={{ fill: CHART_TRACK }}
              animationDuration={1400}
              animationEasing="ease-out"
            />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className={cn("text-3xl font-bold", colorClass)}
          >
            {Math.round(clamped)}%
          </motion.span>
          <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
            {label}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
