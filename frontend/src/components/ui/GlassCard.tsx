import { motion, type HTMLMotionProps } from "framer-motion";
import { scaleIn, defaultTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";

interface GlassCardProps extends HTMLMotionProps<"div"> {
  glow?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function GlassCard({
  glow = false,
  children,
  className,
  ...props
}: GlassCardProps) {
  return (
    <motion.div
      variants={scaleIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={defaultTransition}
      className={cn(
        "rounded-2xl border border-slate-200 bg-white",
        "shadow-[0_1px_3px_rgba(15,23,42,0.04),0_4px_14px_rgba(15,23,42,0.05)]",
        "hover:border-violet-200 hover:shadow-[0_4px_14px_rgba(124,58,237,0.08),0_12px_24px_rgba(124,58,237,0.05)]",
        "transition-all duration-300",
        glow && "hover:shadow-[0_8px_28px_rgba(124,58,237,0.14)]",
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
