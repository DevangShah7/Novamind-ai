import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getApiKeys, getSystemStats } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import StatsCard from '../../components/admin/StatsCard';
import ApiKeyList from '../../components/admin/ApiKeyList';

export default function AdminDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState({});
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    if (!user) {
      router.replace('/login');
      return;
    }

    setLoading(true);
    try {
      const [statsData, apiKeysData] = await Promise.all([
        getSystemStats(),
        getApiKeys()
      ]);
      setStats(statsData);
      setApiKeys(apiKeysData);
    } catch (err) {
      setError('Failed to load admin dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return null; // Redirect handled in useEffect
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-red-500 text-center">{error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="pb-6">
          <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Welcome back, {user.full_name || user.email}
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
          <StatsCard title="Total Users" value={stats.total_users || 0} />
          <StatsCard title="Admin Users" value={stats.admin_users || 0} />
          <StatsCard title="Active Users" value={stats.active_users || 0} />
          <StatsCard title="API Keys" value={stats.api_keys || 0} />
        </div>

        {/* API Keys Section */}
        <div className="bg-white shadow rounded-lg divide-y divide-gray-200">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg font-medium text-gray-900">
              API Keys
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Manage API keys for programmatic access
            </p>
          </div>
          <div className="py-3">
            <ApiKeyList apiKeys={apiKeys} onRefresh={loadData} />
          </div>
        </div>
      </div>
    </div>
  );
}