/**
 * Shared frontend validation helpers.
 *
 * Keep these in lock-step with the backend rules in
 * `backend/app/schemas/user.py` (PASSWORD_MIN_LENGTH,
 * _PASSWORD_COMPOSITION, _validate_password). The backend is the
 * source of truth — if you change the rules there, change them here
 * too so the client and server agree on what's a valid password
 * before the form submits.
 */

/** Minimum allowed password length, mirrored from backend. */
export const PASSWORD_MIN_LENGTH = 8;

/** Returns a list of human-readable reasons the password is too weak. */
export function passwordIssues(password: string, email?: string): string[] {
  const issues: string[] = [];
  if (password.length < PASSWORD_MIN_LENGTH) {
    issues.push(`At least ${PASSWORD_MIN_LENGTH} characters`);
  }
  if (!/[A-Za-z]/.test(password)) {
    issues.push('At least one letter');
  }
  if (!/\d/.test(password)) {
    issues.push('At least one number');
  }
  if (
    email &&
    typeof email === 'string' &&
    password.toLowerCase() === email.toLowerCase()
  ) {
    issues.push("Don't use your email as the password");
  }
  return issues;
}

/** True iff the password passes every rule. */
export function passwordMeetsRules(password: string, email?: string): boolean {
  return passwordIssues(password, email).length === 0;
}

/**
 * Score the strength of a password from 0 (too short) to 5 (excellent).
 * The thresholds were tuned so a freshly-valid password ("abcdefg1")
 * lands in the "Fair" band, and adding length / symbols / mixed-case
 * walks the bar up from there. Visible in the signup strength meter
 * and the admin "set password" form.
 */
export type PasswordStrength = {
  score: number;
  label: string;
  color: string;
};

export function getPasswordStrength(password: string): PasswordStrength {
  let score = 0;
  if (password.length >= PASSWORD_MIN_LENGTH) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  const labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Excellent'];
  const colors = [
    'bg-muted',
    'bg-destructive',
    'bg-orange-500',
    'bg-amber-500',
    'bg-emerald-500',
    'bg-emerald-600',
  ];
  return { score, label: labels[score], color: colors[score] };
}

/**
 * Coerce a fetch `Response` into a human-readable error string.
 *
 * FastAPI returns `detail` as either a plain string (custom 4xx
 * errors) or a list of validation objects (422 with multiple field
 * errors). For 422s, each item's `msg` is what the user needs to
 * see — not the field name, not the type, just the human message.
 */
export async function extractErrorMessage(
  res: Response,
  fallback: string
): Promise<string> {
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    return fallback;
  }
  if (Array.isArray(body?.detail)) {
    return body.detail
      .map((d: any) => d?.msg)
      .filter(Boolean)
      .join('; ') || fallback;
  }
  if (typeof body?.detail === 'string') return body.detail;
  if (typeof body?.message === 'string') return body.message;
  return fallback;
}
