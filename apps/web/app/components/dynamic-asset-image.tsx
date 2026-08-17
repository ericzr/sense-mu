"use client";

import { forwardRef, type ComponentPropsWithoutRef } from "react";

type DynamicAssetImageProps = ComponentPropsWithoutRef<"img">;

// Browser-created Blob URLs and authenticated artifact URLs cannot use the
// framework image optimizer, but still need native image sizing and load events.
export const DynamicAssetImage = forwardRef<HTMLImageElement, DynamicAssetImageProps>(
  function DynamicAssetImage({ alt = "", ...props }, ref) {
    // eslint-disable-next-line @next/next/no-img-element -- See the component contract above.
    return <img ref={ref} alt={alt} {...props} />;
  },
);
