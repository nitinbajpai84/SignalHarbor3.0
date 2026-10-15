// Ported from the earlier prototype's js/ui.js icon(): the same line-icon paths, as a React component. Decorative only.
const PATHS = {
  grid: "M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z",
  chat: "M4 5h16v10H9l-4 4V5Z",
  scroll: "M6 3h9l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm9 0v4h4",
  rooms: "M4 5h9v7H4V5Zm11 4h5v7h-5V9ZM6 12v6h5",
  layers: "M12 3 3 8l9 5 9-5-9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  agents: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20c0-3 3-5 6-5s6 2 6 5m0 0c0-2.5 2.4-4.5 6-4.5s6 2 6 4.5",
  check: "M4 12l5 5L20 6",
  clock: "M12 7v5l3 3M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  close: "M5 5l14 14M19 5 5 19",
  spark: "M12 2 9 9l-7 3 7 3 3 7 3-7 7-3-7-3-3-7Z",
  target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 4a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z",
  send: "M4 12 20 4l-4 16-4-7-8-1Z",
  mic: "M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Zm-7 9a7 7 0 0 0 14 0M12 19v3M9 22h6",
  speaker: "M4 9v6h4l5 5V4L8 9H4Zm12.5-1.5a5 5 0 0 1 0 9M19 5a9 9 0 0 1 0 14",
  plus: "M12 5v14M5 12h14",
} as const;

export type IconName = keyof typeof PATHS;

export default function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
