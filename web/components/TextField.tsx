import { ReactNode, useState, forwardRef } from 'react';
import { Eye, EyeOff, AlertCircle } from 'lucide-react';

interface TextFieldProps {
  id: string;
  label: string;
  type?: 'text' | 'email' | 'password';
  value: string;
  onChange: (v: string) => void;
  error?: string;
  hint?: string;
  autoComplete?: string;
  required?: boolean;
  rightSlot?: ReactNode;
}

const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { id, label, type = 'text', value, onChange, error, hint, autoComplete, required, rightSlot },
  ref,
) {
  const [focused, setFocused] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const isPassword = type === 'password';
  const effectiveType = isPassword && showPwd ? 'text' : type;
  const floated = focused || value.length > 0;

  return (
    <div className="space-y-1.5">
      <div className="relative">
        <input
          ref={ref}
          id={id}
          type={effectiveType}
          value={value}
          required={required}
          autoComplete={autoComplete}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder=" "
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          className={[
            'peer block w-full rounded-lg border bg-card px-3.5 pt-5 pb-2 text-sm text-foreground',
            'placeholder-transparent transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-0',
            error
              ? 'border-destructive focus:border-destructive'
              : 'border-input focus:border-primary',
            (isPassword || rightSlot) ? 'pr-11' : '',
          ].join(' ')}
        />
        <label
          htmlFor={id}
          className={[
            'pointer-events-none absolute left-3.5 transition-all',
            floated
              ? 'top-1.5 text-xs font-medium'
              : 'top-1/2 -translate-y-1/2 text-sm',
            focused ? 'text-primary' : 'text-muted-foreground',
          ].join(' ')}
        >
          {label}
          {required && <span className="text-destructive"> *</span>}
        </label>
        {(isPassword || rightSlot) && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2">
            {isPassword && (
              <button
                type="button"
                onClick={() => setShowPwd((s) => !s)}
                aria-label={showPwd ? 'Hide password' : 'Show password'}
                className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            )}
            {rightSlot}
          </div>
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className="flex items-center gap-1.5 text-xs text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
});

export default TextField;