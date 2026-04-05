"use client";

export const REGISTRY_PAGE_LIMITS = [10, 25, 50, 100] as const;

export type RegistryPagerProps = {
  disabled?: boolean;
  pageSize: number;
  onPageSizeChange: (n: number) => void;
  rangeStart: number;
  rangeEnd: number;
  total: number;
  entityLabel: string;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
};

export function RegistryPager({
  disabled,
  pageSize,
  onPageSizeChange,
  rangeStart,
  rangeEnd,
  total,
  entityLabel,
  canPrev,
  canNext,
  onPrev,
  onNext,
}: RegistryPagerProps) {
  const meta =
    total === 0
      ? `0 ${entityLabel}`
      : `${rangeStart.toLocaleString("en-US")}–${rangeEnd.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} ${entityLabel}`;

  return (
    <div className="ws-registry-pager" role="navigation" aria-label={`${entityLabel} pagination`}>
      <label className="ws-registry-pager-size">
        <span className="ws-registry-pager-size-label">Rows</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          disabled={disabled}
          aria-label="Rows per page"
        >
          {REGISTRY_PAGE_LIMITS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <span className="ws-registry-pager-meta">{meta}</span>
      <div className="ws-registry-pager-actions">
        <button type="button" className="ws-btn ws-btn-ghost" disabled={disabled || !canPrev} onClick={onPrev}>
          Previous
        </button>
        <button type="button" className="ws-btn ws-btn-ghost" disabled={disabled || !canNext} onClick={onNext}>
          Next
        </button>
      </div>
    </div>
  );
}
