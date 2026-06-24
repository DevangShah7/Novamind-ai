import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getUsers } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import { User } from '../../types';

export default function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    if (!user) {
      router.replace('/login');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const usersData = await getUsers();
      setUsers(usersData);
    } catch (err) {
      setError('Failed to fetch users: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-4"></div>
        <p className="text-sm text-gray-500">Loading users...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-md p-6 text-center max-w-xl">
          <h2 className="text-xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-600">{error}</p>
          <button
            onClick={loadUsers}
            className="mt-4 px-4 py-2 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Users Management</h1>
          <div className="flex items-center space-x-3">
            {/* In a real app, this would navigate to a create user form */}
            <button
              onClick={() => {
                // Placeholder for create user functionality
                alert('Create user functionality would go here');
              }}
              className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700"
            >
              New User
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">User List ({users.length})</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {users.length === 0 ? (
              <div className="py-8 text-center text-gray-500">
                <p>No users found.</p>
              </div>
            ) : (
              users.map((user) => (
                <div key={user.id} className="px-6 py-4 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    {/* Avatar or initials */}
                    <div className="h-10 w-10 flex items-center justify-center bg-gray-200 rounded-full">
                      {user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">
                        {user.full_name || user.username || 'Unnamed User'}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {user.email || 'No email'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4 text-sm">
                    <span className={user.is_active ? 'text-green-500' : 'text-gray-400'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className={user.is_verified ? 'text-blue-500' : 'text-gray-400'}>
                      {user.is_verified ? 'Verified' : 'Unverified'}
                    </span>
                    {/* In a real app, these would be buttons/link to edit/delete */}
                    <div className="flex space-x-2">
                      <button
                        onClick={() => {
                          // Placeholder for edit functionality
                          alert(`Edit user ${user.id}`);
                        }}
                        className="px-2 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          // Placeholder for delete functionality
                          if (confirm(`Delete user ${user.full_name || user.username}?`)) {
                            alert(`Delete user ${user.id} functionality would go here`);
                          }
                        }}
                        className="px-2 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
