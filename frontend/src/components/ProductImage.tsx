// Фото хранятся в MinIO, а он подключается на этапе III.
// Пока вместо фото — вещь, разложенная на чёрном (как флэтлей у архивных магазинов):
// силуэт по названию товара, ткань с потёртой фактурой, цвет выбирается от названия.

type Kind = "tshirt" | "hoodie" | "jeans" | "jacket" | "unknown";

function kindOf(name: string): Kind {
  const n = name.toLowerCase();
  if (n.includes("футболк")) return "tshirt";
  if (n.includes("худи") || n.includes("свитшот")) return "hoodie";
  if (n.includes("джинс")) return "jeans";
  if (n.includes("куртк") || n.includes("бомбер")) return "jacket";
  return "unknown";
}

function hash(s: string): number {
  let h = 0;
  for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return Math.abs(h);
}

// Застиранные цвета: графит, почти чёрный, выцветший деним, бежевый, серый меланж
const CLOTH = ["#4f5458", "#1f2226", "#3f5679", "#a8987c", "#8b8d8c"];

const SHAPES: Record<Kind, string> = {
  tshirt: "M30 22 L42 16 Q50 22 58 16 L70 22 L84 38 L73 46 L68 41 L68 86 L32 86 L32 41 L27 46 L16 38 Z",
  hoodie: "M36 26 Q33 6 50 6 Q67 6 64 26 L76 30 L88 78 L78 80 L70 52 L70 90 L30 90 L30 52 L22 80 L12 78 L24 30 Z",
  jeans: "M30 12 L70 12 L75 92 L56 92 L50 40 L44 92 L25 92 Z",
  jacket:
    "M34 16 L50 22 L66 16 L80 26 L88 64 L78 66 L72 44 L72 88 L52 88 L50 30 L48 88 L28 88 L28 44 L22 66 L12 64 L20 26 Z",
  unknown: "M30 20 H70 V86 H30 Z",
};

// Швы, карманы, молнии
const DETAILS: Partial<Record<Kind, string>> = {
  tshirt: "M42 16 Q50 26 58 16",
  hoodie: "M40 26 Q50 36 60 26 M38 68 H62 L66 82 H34 Z M47 30 V44 M53 30 V44 M30 84 H70",
  jacket: "M50 22 V88 M28 80 H72 M34 50 H44 M56 50 H66",
  jeans: "M30 22 H70 M50 12 V40 M34 22 Q36 32 44 30 M66 22 Q64 32 56 30",
};

export default function ProductImage({ name }: { name: string; imageKey?: string | null }) {
  const h = hash(name);
  const kind = kindOf(name);
  const cloth = CLOTH[h % CLOTH.length];
  const tilt = ((h >> 3) % 7) - 3;
  const id = `c${h}`;

  return (
    <div className="shot" role="img" aria-label={name}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <defs>
          <filter id={`${id}-cloth`} x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={h % 50} result="weave" />
            <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="3" seed={(h >> 2) % 50} result="wear" />
            <feColorMatrix in="weave" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.1 0" result="w1" />
            <feColorMatrix in="wear" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.4 -0.45" result="w2" />
            <feComposite in="w1" in2="SourceGraphic" operator="in" result="w1in" />
            <feComposite in="w2" in2="SourceGraphic" operator="in" result="w2in" />
            <feMerge>
              <feMergeNode in="SourceGraphic" />
              <feMergeNode in="w2in" />
              <feMergeNode in="w1in" />
            </feMerge>
          </filter>
          <radialGradient id={`${id}-lift`} cx="40%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#000" stopOpacity="0.55" />
          </radialGradient>
        </defs>
        <g transform={`rotate(${tilt} 50 50)`}>
          <path d={SHAPES[kind]} fill="#000" opacity="0.6" transform="translate(1.5 2.5)" />
          <path d={SHAPES[kind]} fill={cloth} filter={`url(#${id}-cloth)`} />
          <path d={SHAPES[kind]} fill={`url(#${id}-lift)`} />
          {DETAILS[kind] && <path d={DETAILS[kind]} fill="none" stroke="#000" strokeOpacity="0.45" strokeWidth="0.8" />}
        </g>
      </svg>
    </div>
  );
}
