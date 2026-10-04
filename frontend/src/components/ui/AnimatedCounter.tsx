import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  format?: (v: number) => string;
  className?: string;
}

export function AnimatedCounter({
  value,
  duration = 1.2,
  format,
  className,
}: AnimatedCounterProps) {
  const spring = useSpring(0, { duration: duration * 1000 });
  const display = useTransform(spring, (v) =>
    format ? format(v) : Math.round(v).toLocaleString()
  );
  const [rendered, setRendered] = useState("0");
  const ref = useRef(false);

  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  useEffect(() => {
    const unsub = display.on("change", (v) => setRendered(v));
    return unsub;
  }, [display]);

  useEffect(() => {
    ref.current = true;
  }, []);

  return (
    <motion.span
      className={cn("tabular-nums", className)}
      initial={ref.current ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {rendered}
    </motion.span>
  );
}
