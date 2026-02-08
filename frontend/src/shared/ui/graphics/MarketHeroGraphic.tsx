import React from "react";

export function MarketHeroGraphic() {
  return (
    <div className="marketHeroGraphic" aria-hidden="true">
      <svg viewBox="0 0 680 440" role="img">
        <defs>
          <linearGradient id="heroGrid" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(116,184,255,0.25)" />
            <stop offset="100%" stopColor="rgba(116,184,255,0.02)" />
          </linearGradient>
          <linearGradient id="priceTrail" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(89,214,176,0.2)" />
            <stop offset="100%" stopColor="rgba(89,214,176,1)" />
          </linearGradient>
          <linearGradient id="volumeTrail" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(255,116,159,0.15)" />
            <stop offset="100%" stopColor="rgba(255,116,159,0.75)" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="0" y="0" width="680" height="440" fill="rgba(8,14,24,0.7)" />

        {Array.from({ length: 18 }).map((_, index) => (
          <line
            key={`h-${index}`}
            x1="20"
            x2="660"
            y1={30 + index * 22}
            y2={30 + index * 22}
            stroke="url(#heroGrid)"
            strokeWidth="1"
          />
        ))}
        {Array.from({ length: 16 }).map((_, index) => (
          <line
            key={`v-${index}`}
            y1="20"
            y2="420"
            x1={34 + index * 40}
            x2={34 + index * 40}
            stroke="rgba(116,184,255,0.08)"
            strokeWidth="1"
          />
        ))}

        <path
          d="M28 300 C80 260 120 250 162 252 C218 256 248 296 306 292 C352 289 386 236 433 228 C472 221 508 252 552 244 C592 237 618 193 654 168"
          fill="none"
          stroke="url(#priceTrail)"
          strokeWidth="4"
          strokeLinecap="round"
          filter="url(#glow)"
        />

        <path
          d="M28 346 C86 338 124 372 175 362 C233 352 270 314 322 316 C374 317 406 354 454 350 C510 344 552 306 616 296 C629 293 642 291 654 289"
          fill="none"
          stroke="url(#volumeTrail)"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {(
          [
          [92, 302, true],
          [138, 284, true],
          [184, 272, false],
          [230, 288, true],
          [276, 292, false],
          [322, 276, true],
          [368, 248, true],
          [414, 236, false],
          [460, 246, true],
          [506, 240, true],
          [552, 230, false],
          [598, 204, true]
          ] as Array<[number, number, boolean]>
        ).map(([x, y, up], idx) => (
          <g key={`c-${idx}`}>
            <line x1={x} x2={x} y1={Number(y) - 26} y2={Number(y) + 22} stroke={up ? "#59d6b0" : "#ff769f"} />
            <rect
              x={Number(x) - 7}
              y={Number(y) - (up ? 14 : 6)}
              width="14"
              height={up ? "20" : "22"}
              rx="2"
              fill={up ? "rgba(89,214,176,0.75)" : "rgba(255,118,159,0.78)"}
            />
          </g>
        ))}

        <rect x="468" y="30" width="180" height="86" rx="10" fill="rgba(8,14,24,0.92)" stroke="rgba(116,184,255,0.35)" />
        <text x="482" y="54" fill="#9eb4da" fontSize="11" fontFamily="JetBrains Mono, monospace" letterSpacing="1.3">
          MARKET SNAPSHOT
        </text>
        <text x="482" y="76" fill="#e8edf7" fontSize="20" fontFamily="IBM Plex Sans, sans-serif" fontWeight="700">
          +2.34%
        </text>
        <text x="482" y="98" fill="#8ddfc1" fontSize="12" fontFamily="JetBrains Mono, monospace">
          BREADTH 78/100
        </text>
      </svg>
    </div>
  );
}
