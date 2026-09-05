"use client";

import { MorphIcon as BaseMorphIcon, type MorphIconProps } from "morphicons/react";

/**
 * SenseMu's motion policy is explicit: respect the user's reduced-motion
 * preference while keeping the static Lucide geometry and sizing contract.
 */
export function MorphIcon(props: Omit<MorphIconProps, "reducedMotion">) {
  return <BaseMorphIcon {...props} reducedMotion="user" />;
}
