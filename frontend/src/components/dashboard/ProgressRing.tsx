interface Props {
  percent: number;
  completed: number;
  total: number;
  size?: number;
}

export default function ProgressRing({
  percent,
  completed,
  total,
  size = 132,
}: Props) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#DFE2D8"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#263A5C"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <div className="-mt-[86px] flex flex-col items-center">
        <span className="font-serif text-2xl font-semibold text-ink">{percent}%</span>
        <span className="text-xs text-inkSoft">
          {completed} of {total} done
        </span>
      </div>
    </div>
  );
}
