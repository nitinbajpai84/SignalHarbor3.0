import type { ReactNode } from "react";

// 24px stroke icons. Paths copied from the pulse canvas artboards; Activity and Home have no artboard drawing (see report).
// Colour comes from the parent through currentColor. Decorative: the text next to an icon carries the meaning.

export interface IconProps { size?: number }

function Svg({ size = 24, children }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

export const PeopleIcon = (p: IconProps) => <Svg {...p}><circle cx="9" cy="8" r="3.5" /><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6" /><circle cx="17" cy="9" r="2.5" /><path d="M16 14c3 0 6 2 6 5" /></Svg>;
export const CheckIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M8 12l3 3 5-6" /></Svg>;
export const DatabaseIcon = (p: IconProps) => <Svg {...p}><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></Svg>;
export const ActivityIcon = (p: IconProps) => <Svg {...p}><path d="M4 20V12M10 20V6M16 20v-9M22 20H2" /></Svg>;
export const ClockIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Svg>;
export const DocumentIcon = (p: IconProps) => <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 12h8M8 8h8M8 16h5" /></Svg>;
export const WarningIcon = (p: IconProps) => <Svg {...p}><path d="M12 3l9 16H3z" /><path d="M12 10v4M12 17v1" /></Svg>;
export const PenIcon = (p: IconProps) => <Svg {...p}><path d="M4 20l4-1 10-10-3-3L5 16z" /><path d="M13 7l3 3" /></Svg>;
export const ChatIcon = (p: IconProps) => <Svg {...p}><path d="M4 5h16v11H8l-4 4z" /></Svg>;
export const TableIcon = (p: IconProps) => <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M9 4v16" /></Svg>;
export const MapIcon = (p: IconProps) => <Svg {...p}><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="8" r="2.5" /><circle cx="12" cy="18" r="2.5" /><path d="M8 7l8 1M7 8l4 8M17 10l-4 6" /></Svg>;
export const PulseIcon = (p: IconProps) => <Svg {...p}><path d="M3 12h4l3-8 4 16 3-8h4" /></Svg>;
export const HomeIcon = (p: IconProps) => <Svg {...p}><path d="M3 11l9-7 9 7v9H3z" /><path d="M10 20v-5h4v5" /></Svg>;
export const IntentIcon = (p: IconProps) => <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M8 4v16M3 10h18" /></Svg>;
export const BuildIcon = (p: IconProps) => <Svg {...p}><path d="M4 7l8-4 8 4-8 4z" /><path d="M4 7v10l8 4 8-4V7" /></Svg>;
export const ConsumeIcon = (p: IconProps) => <Svg {...p}><path d="M4 19V9l8-5 8 5v10z" /></Svg>;
