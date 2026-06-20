                onChange={(e) => setUserFormData(prev => ({ ...prev, full_name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter full name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bio (optional)
              </label>
              <textarea
                rows="3"
                value={userFormData.bio || ''}
                onChange={(e) => setUserFormData(prev => ({ ...prev, bio: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter bio"
              />
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={userFormData.is_active || false}
                  onChange={(e) => setUserFormData(prev => ({ ...prev, is_active: e.target.checked }))}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label className="ml-2 text-sm font-medium text-gray-700">Active</label>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={userFormData.is_verified || false}
                  onChange={(e) => setUserFormData(prev => ({ ...prev, is_verified: e.target.checked }))}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label className="ml-2 text-sm font-medium text-gray-700">Verified</label>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={userFormData.is_admin || false}
                  onChange={(e) => setUserFormData(prev => ({ ...prev, is_admin: e.target.checked }))}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label className="ml-2 text-sm font-medium text-gray-700">Admin</label>
              </div>
            </div