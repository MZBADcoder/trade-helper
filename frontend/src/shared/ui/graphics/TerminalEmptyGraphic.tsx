import React from "react";

export function TerminalEmptyGraphic() {
  return (
    <div className="terminalEmptyGraphic" aria-hidden="true">
      <svg viewBox="0 0 420 240" role="img">
        <defs>
          <linearGradient id="emptyPanel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(116,184,255,0.28)" />
            <stop offset="100%" stopColor="rgba(89,214,176,0.16)" />
          </linearGradient>
        </defs>

        <rect x="24" y="26" width="372" height="188" rx="14" fill="rgba(7,12,22,0.84)" stroke="rgba(116,184,255,0.24)" />
        <rect x="24" y="26" width="372" height="34" rx="14" fill="url(#emptyPanel)" />

        <circle cx="46" cy="43" r="4" fill="rgba(255,118,159,0.9)" />
        <circle cx="62" cy="43" r="4" fill="rgba(250,213,106,0.9)" />
        <circle cx="78" cy="43" r="4" fill="rgba(89,214,176,0.9)" />

        <g stroke="rgba(116,184,255,0.22)">
          {Array.from({ length: 8 }).map((_, idx) => (
            <line key={idx} x1="42" x2="378" y1={72 + idx * 18} y2={72 + idx * 18} />
          ))}
        </g>

        <path
          d="M52 188 C102 178 130 168 164 162 C200 156 238 126 282 124 C322 122 352 134 378 102"
          fill="none"
          stroke="rgba(89,214,176,0.9)"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <path
          d="M52 170 C97 172 118 145 152 148 C196 151 232 179 274 172 C311 166 334 141 378 138"
          fill="none"
          stroke="rgba(255,118,159,0.82)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="4 4"
        />
      </svg>
    </div>
  );
}
