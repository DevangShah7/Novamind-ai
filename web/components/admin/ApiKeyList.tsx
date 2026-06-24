import { useState } from 'react';
import { ApiKey } from '../../types';
import Link from 'next/link';
import Button from '../ui/Button';

interface ApiKeyListProps {
  apiKeys: ApiKey[];
  onRefresh: () => Promise<void>;
}

export default function ApiKeyList({ apiKeys, onRefresh }: ApiKeyListProps) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showValidateModal, setShowValidateModal] = useState(false);
  const [selectedKeyId, setSelectedKeyId] = useState<number | null>(null);
  const [validationResult, setValidationResult] = useState<any>(null);

  const handleCreateClick = () => {
    setShowCreateModal(true);
  };

  const handleValidateClick = (keyId: number) => {
    setSelectedKeyId(keyId);
    setShowValidateModal(true);
  };

  const handleRefreshClick = async () => {
    await onRefresh();
  };

  return (
    <>
      <div className="px-4 py-5 sm:px-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <h3 className="text-lg font-medium text-gray-900">
              API Keys
            </h3>
          </div>
          <div className="ml-4 flex items-center space-x-2">
            <Button variant="outline" onClick={handleRefreshClick}>
              Refresh
            </Button>
            <Button onClick={handleCreateClick}>
              Create API Key
            </Button>
          </div>
        </div>
      </div>

      <div className="py-3">
        {apiKeys.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">
              No API keys yet. Create your first API key to access the NovaMind AI API programmatically.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {apiKeys.map((key) => (
              <div key={key.id} className="px-4 py-4 sm:px-6 flex justify-between items-center">
                <div className="flex items-center space-x-3">
                  <div className="flex-shrink-0 h-8 w-8 flex items-center justify-center bg-indigo-100 text-indigo-600 rounded-full">
                    {/* Key icon or first letter */}
                    {key.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{key.name}</p>
                    <p className="text-sm text-gray-500 truncate max-w-xs">
                      {/* Show masked key */}
                      {`sk_${'*'.repeat(8)}${key.key.slice(-8)}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-sm">
                    <span className={key.is_active ? 'text-green-500' : 'text-gray-400'}>
                      {key.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleValidateClick(key.id)}
                    >
                      Validate
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // In a real app, this would open a delete confirmation modal
                        console.log('Delete key:', key.id);
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create API Key Modal */}
      <div className={`fixed inset-0 z-50 flex items-center justify-center ${
        showCreateModal ? 'block' : 'hidden'
      }`}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowCreateModal(false)} />
        <div className="bg-white rounded-lg shadow-xl w-96 max-w-xl mx-4 p-6">
          <div className="flex justify-between items-start mb-4">
            <button
              className="text-gray-400 hover:text-gray-500"
              onClick={() => setShowCreateModal(false)}
            >
              ×
            </button>
          </div>
          <form className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name
              </label>
              <input
                type="text"
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter API key name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description (optional)
              </label>
              <textarea
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter description"
              />
            </div>
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                onClick={() => {
                  // In a real app, this would submit the form
                  alert('API key created successfully! (Feature coming soon)');
                  setShowCreateModal(false);
                }}
              >
                Create Key
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Validate API Key Modal */}
      <div className={`fixed inset-0 z-50 flex items-center justify-center ${
        showValidateModal ? 'block' : 'hidden'
      }`}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => {
          setShowValidateModal(false);
          setSelectedKeyId(null);
          setValidationResult(null);
        }} />
        <div className="bg-white rounded-lg shadow-xl w-96 max-w-xl mx-4 p-6">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Validate API Key
            </h3>
            <button
              className="text-gray-400 hover:text-gray-500"
              onClick={() => {
                setShowValidateModal(false);
                setSelectedKeyId(null);
                setValidationResult(null);
              }}
            >
              ×
            </button>
          </div>
          {selectedKeyId && (
            <>
              <div className="mb-4">
                <p className="text-sm font-medium text-gray-700">
                  Validating API key...
                </p>
              </div>
              {validationResult ? (
                <div className="space-y-4">
                  <div className="border-t pt-4">
                    <p className="text-sm font-medium text-gray-700">
                      Validation Results
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex">
                      <span className="w-32 text-sm font-medium text-gray-600">
                        Status:
                      </span>
                      <span className={`${validationResult.valid ? 'text-green-500' : 'text-red-500'} text-sm font-medium`}>
                        {validationResult.valid ? 'Valid' : 'Invalid'}
                      </span>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-sm font-medium text-gray-600">
                        Key ID:
                      </span>
                      <span className="text-sm">{validationResult.key_id}</span>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-sm font-medium text-gray-600">
                        Name:
                      </span>
                      <span className="text-sm">{validationResult.name}</span>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-sm font-medium text-gray-600">
                        Usage Count:
                      </span>
                      <span className="text-sm">{validationResult.usage_count}</span>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-sm font-medium text-gray-600">
                        Last Used:
                      </span>
                      <span className="text-sm">
                        {validationResult.last_used_at || 'Never'}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                  <p className="text-sm text-gray-500">Validating API key...</p>
                </div>
              )}
              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  className="px-4 py-2 bg-gray-200 text-gray-700 font-medium rounded-md hover:bg-gray-300"
                  onClick={() => {
                    setShowValidateModal(false);
                    setSelectedKeyId(null);
                    setValidationResult(null);
                  }}
                >
                  Close
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}