import { copy } from "../copy";
import { useTheme } from "../theme";

/** The lighthouse mark; the on-dark artwork shows whenever the effective theme is dark. */
export default function BrandMark({ named, size }: { named: boolean; size: number }) {
  const { effective } = useTheme();
  const tail = effective === "dark" ? "-on-dark" : "";
  const base = "/brand/signal-harbor-mark-";
  return (
    <img
      className="brand-mark"
      src={`${base}64${tail}.png`}
      srcSet={`${base}128${tail}.png 2x`}
      width={size}
      height={size}
      alt={named ? copy.product : ""}
    />
  );
}
