// Small helpers that reproduce how Python rounds and prints numbers, so the browser shows
// exactly the same figures and sentences as the Python chatbot.

/** Python's round(x): halves go to the even number. */
export function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Python's round(x, 2) for a share between 0 and 1. */
export function round2(x) {
  const eighths = x * 8;
  if (Number.isInteger(eighths) && eighths % 2 !== 0) return roundHalfEven(x * 100) / 100; // exact tie
  return Number(x.toFixed(2));
}

/** f"{value:,}" for whole numbers and plain decimals. */
export function money(value) {
  const [whole, fraction] = String(value).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction === undefined ? grouped : `${grouped}.${fraction}`;
}

/** Python prints a float with a trailing .0, which the "Understood as" line shows. */
export function floatMoney(value) {
  return Number.isInteger(value) ? `${money(value)}.0` : money(value);
}

/** repr() of a short string: 'london' (or "it's" when the text contains a quote). */
export function pyRepr(text) {
  const s = String(text);
  if (s.includes("'") && !s.includes('"')) return `"${s}"`;
  return `'${s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}

export function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}
