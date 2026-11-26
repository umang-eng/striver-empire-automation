export interface ValidationResult {
  valid: boolean;
  category?: string;
  discount?: number;
  error?: string;
}

const DISCOUNT_PATTERNS = [
  /(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*%\s*(?:off|discount)?/i,
  /(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*(?:percent|pct)\b(?:\s*off)?/i,
  /(?:^|[\s,\-|])(-?\d+(?:\.\d+)?)\s*$/,
];

export function validateTaskMessage(rawInput: string): ValidationResult {
  const trimmed = rawInput.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return { valid: false, error: "Enter a category and discount, e.g. women 25%." };
  }

  for (const pattern of DISCOUNT_PATTERNS) {
    const match = trimmed.match(pattern);
    if (!match || match.index === undefined) continue;

    const rawNum = match[1];
    const discount = Number(rawNum);
    if (!Number.isFinite(discount)) {
      return { valid: false, error: `Invalid discount value "${rawNum}".` };
    }
    if (discount < 0 || discount >= 100) {
      return {
        valid: false,
        error: "Discount must be at least 0% and less than 100%.",
      };
    }

    const before = trimmed.slice(0, match.index);
    const after = trimmed.slice(match.index + match[0].length);
    const remaining = `${before} ${after}`
      .replace(/\b(discount|off)\b/gi, "")
      .replace(/^[\s,\-|;]+|[\s,\-|;]+$/g, "")
      .replace(/\s+/g, " ")
      .trim();

    if (!remaining) {
      return {
        valid: false,
        error: "Category name is required before the discount (e.g. women 25%).",
      };
    }

    return {
      valid: true,
      category: remaining,
      discount,
    };
  }

  return {
    valid: false,
    error: "Include a numeric discount percentage (e.g. women 25% or men formal pants 12.5%).",
  };
}
