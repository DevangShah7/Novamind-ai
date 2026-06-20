import { render, screen } from '@testing-library/react';
import AdminLayout from '../components/layout/AdminLayout';
import StatsCard from '../components/admin/StatsCard';

test('renders admin layout', () => {
  const { container } = render(
    <AdminLayout>
      <h1>Admin Content</h1>
    </AdminLayout>
  );
  expect(container.querySelector('h1')).toHaveTextContent('Admin Content');
});

test('renders stats card', () => {
  render(<StatsCard title="Test Stat" value="100" />);
  expect(screen.getByText('Test Stat')).toBeInTheDocument();
  expect(screen.getByText('100')).toBeInTheDocument();
});