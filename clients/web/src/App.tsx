function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          WearForce-Clean Dashboard
        </h1>
        <p className="text-gray-600 mb-6">
          Welcome to the WearForce-Clean conversational CRM + ERP system.
        </p>
        <div className="space-y-4">
          <div className="p-4 bg-blue-50 rounded">
            <h2 className="font-semibold text-blue-900">🚀 Status</h2>
            <p className="text-blue-700">Web application is running on port 3001</p>
          </div>
          <div className="p-4 bg-yellow-50 rounded">
            <h2 className="font-semibold text-yellow-900">⚠️ Backend Services</h2>
            <p className="text-yellow-700">Backend services need to be started</p>
          </div>
          <div className="p-4 bg-green-50 rounded">
            <h2 className="font-semibold text-green-900">📍 Clean Project Ports</h2>
            <ul className="text-green-700 text-sm">
              <li>• Web: 3001</li>
              <li>• Gateway: 8180</li>
              <li>• GraphQL: 9000</li>
              <li>• Database: 5532</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App