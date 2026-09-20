type MotifProps = {
  className?: string;
};

/**
 * A code-native interpretation of the concentric geometry found on Dong Son drums.
 * It is decorative on purpose, so it never competes with the learning content.
 */
export function DongSonDrumMotif({ className = "" }: MotifProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      focusable="false"
      viewBox="0 0 200 200"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="100" cy="100" r="94" fill="none" stroke="currentColor" strokeWidth="2" />
      <circle cx="100" cy="100" r="82" fill="none" stroke="currentColor" strokeDasharray="2 7" strokeLinecap="round" strokeWidth="4" />
      <circle cx="100" cy="100" r="67" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="100" cy="100" r="48" fill="none" stroke="currentColor" strokeWidth="1.5" />
      {Array.from({ length: 12 }, (_, index) => (
        <g key={index} transform={`rotate(${index * 30} 100 100)`}>
          <path d="M96 20 100 12l4 8-4 8Z" fill="currentColor" />
          <path d="M96 43 100 34l4 9-4 7Z" fill="currentColor" opacity="0.72" />
        </g>
      ))}
      <path
        d="M100 52 108 82l25-18-15 27 31 9-31 9 15 27-25-18-8 30-8-30-25 18 15-27-31-9 31-9-15-27 25 18Z"
        fill="currentColor"
      />
      <circle cx="100" cy="100" r="8" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

/** Stylised Lac birds, inspired by the long-beaked birds on Dong Son artefacts. */
export function LacBirdMotif({ className = "" }: MotifProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      focusable="false"
      viewBox="0 0 360 120"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M21 84c37-1 55-22 75-47 6-8 14-13 24-14-8 9-13 18-14 28 20-6 39-4 55 7-25-1-47 7-65 23-13 11-29 18-48 17-11 0-20-5-27-14Z"
        fill="currentColor"
        opacity="0.22"
      />
      <path
        d="M85 61c22 7 38 20 49 40M106 51c-19 0-34-5-45-15M119 23l29-13-17 23"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="4"
        opacity="0.38"
      />
      <path
        d="M187 74c30 0 48-18 65-38 6-7 13-11 22-12-7 8-11 16-12 24 18-5 34-3 49 6-22 0-42 7-58 21-12 10-27 16-43 15-10 0-18-5-23-16Z"
        fill="currentColor"
        opacity="0.16"
      />
      <path
        d="M247 56c20 6 34 18 44 35M263 47c-16 0-30-4-40-13M274 24l25-12-14 21"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.5"
        opacity="0.3"
      />
      <path d="M10 108h340" stroke="currentColor" strokeDasharray="2 10" strokeLinecap="round" opacity="0.22" strokeWidth="3" />
    </svg>
  );
}

export function HeritageBackdrop() {
  return (
    <div className="heritage-backdrop" aria-hidden="true">
      <DongSonDrumMotif className="heritage-backdrop__drum heritage-backdrop__drum--left" />
      <DongSonDrumMotif className="heritage-backdrop__drum heritage-backdrop__drum--right" />
      <LacBirdMotif className="heritage-backdrop__birds" />
    </div>
  );
}
