import { FC } from 'react';

interface ButtonProps {
  variant?: 'default' | 'outline' | 'secondary';
  size?: 'default' | 'sm' | 'lg';
  children: React.ReactNode;
  onClick: () => void;
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
  className?: string;
}

const Button: FC<ButtonProps> = ({
  variant = 'default',
  size = 'default',
  children,
  onClick,
  type = 'button',
  disabled = false,
  className = '',
}) => {
  // Base classes
  const baseClasses = 'font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';

  // Variant classes
  const variantClasses = {
    default: 'bg-indigo-600 text-white hover:bg-indigo-700',
    outline: 'border border-gray-300 bg-white hover:bg-gray-50',
    secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300',
  }[variant];

  // Size classes
  const sizeClasses = {
    sm: 'px-3 py-2 text-sm',
    default: 'px-4 py-2',
    lg: 'px-6 py-3 text-lg',
  }[size];

  // Disabled classes
  const disabledClasses = disabled
    ? 'opacity-50 cursor-not-allowed'
    : '';

  return (
    <button
      type={type}
      onClick={disabled ? () => {} : onClick}
      disabled={disabled}
      className={`${baseClasses} ${variantClasses} ${sizeClasses} ${disabledClasses} ${className}`}
    >
      {children}
    </button>
  );
};

export default Button;