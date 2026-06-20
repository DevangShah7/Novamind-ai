import { render, screen } from '@testing-library/react';
import Button from '../components/ui/Button';

test('renders button', () => {
  render(<Button onClick={() => {}}>Click me</Button>);
  expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
});

test('button calls onClick when clicked', () => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click me</Button>);
  const button = screen.getByRole('button', { name: /click me/i });
  fireEvent.click(button);
  expect(handleClick).toHaveBeenCalledTimes(1);
});