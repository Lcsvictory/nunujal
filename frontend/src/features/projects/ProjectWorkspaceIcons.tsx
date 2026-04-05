import type { ReactNode } from "react";

type IconProps = {
  className?: string;
};

function IconBase({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function OverviewIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5v10h13v-10" />
      <path d="M9.5 19.5v-5h5v5" />
    </IconBase>
  );
}

export function TodoIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="M9 11.5 11 13.5 15.5 9" />
      <rect x="4" y="4" width="16" height="16" rx="3" />
    </IconBase>
  );
}

export function MembersIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="M16 19.5v-1a3.5 3.5 0 0 0-3.5-3.5h-1A3.5 3.5 0 0 0 8 18.5v1" />
      <circle cx="12" cy="8" r="3" />
      <path d="M18.5 19.5v-.5a2.7 2.7 0 0 0-2-2.6" />
      <path d="M5.5 19.5v-.5a2.7 2.7 0 0 1 2-2.6" />
    </IconBase>
  );
}

export function ContributionIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="M5 18.5h14" />
      <path d="M7.5 15.5V10" />
      <path d="M12 15.5V6.5" />
      <path d="M16.5 15.5V12" />
    </IconBase>
  );
}

export function ProfileIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 19.5a6.5 6.5 0 0 1 13 0" />
    </IconBase>
  );
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="M14 7.5V5.8A1.8 1.8 0 0 0 12.2 4H6.8A1.8 1.8 0 0 0 5 5.8v12.4A1.8 1.8 0 0 0 6.8 20h5.4a1.8 1.8 0 0 0 1.8-1.8v-1.7" />
      <path d="M10.5 12h8" />
      <path d="m15.5 8 4 4-4 4" />
    </IconBase>
  );
}

export function BackIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="m14.5 6.5-5 5 5 5" />
      <path d="M9.5 11.5h10" />
    </IconBase>
  );
}

export function CollapseIcon({ className }: IconProps) {
  return (
    <IconBase className={className}>
      <path d="m14 7-5 5 5 5" />
      <path d="M19 5v14" />
    </IconBase>
  );
}
