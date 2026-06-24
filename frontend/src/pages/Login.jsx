import { useState } from 'react';

export default function Login({ onLogin }) {
  const [view, setView] = useState('signin');
  const [role, setRole] = useState('Resident');
  const [signupRole, setSignupRole] = useState('Resident');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setTimeout(() => {
      onLogin(role);
    }, 500);
  };

  const handleSignup = (e) => {
    e.preventDefault();
    const p1 = e.target.newPwd.value;
    const p2 = e.target.confirmPwd.value;

    if (p1 !== p2) {
      setError('Passwords do not match.');
      setSuccess('');
    } else {
      setError('');
      setSuccess('Registration successful! Routing to login...');
      setTimeout(() => {
        setSuccess('');
        setView('signin');
      }, 1500);
    }
  };

  return (
    <div className="bg-gray-950 flex items-center justify-center min-h-screen font-sans text-gray-200 p-4 w-full">
      <div className="w-full max-w-md bg-gray-900 rounded-2xl shadow-2xl border border-gray-800 p-8 relative overflow-hidden" style={{ boxShadow: '0 0 20px rgba(59, 130, 246, 0.15)' }}>
        <div className="text-center mb-6">
          <div className="flex justify-center mb-3">
            <svg className="w-10 h-10 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-widest">HEIMDALL</h1>
          <p className="text-xs text-gray-500 mt-1 uppercase tracking-wider">Authentication Gateway</p>
        </div>

        {view === 'signin' ? (
          <div className="animate-fadeIn block">
            <div className="mb-6">
              <p className="text-xs text-gray-400 mb-2 text-center">Select Operating Role</p>
              <div className="flex space-x-2">
                {['Resident', 'Security', 'Admin'].map(r => (
                  <button key={r} type="button" onClick={() => setRole(r)}
                    className={`flex-1 py-2 text-sm rounded-lg border transition-all ${role === r ? 'bg-blue-600 text-white border-blue-600' : 'bg-transparent text-gray-400 border-gray-600 hover:border-gray-500'}`}>
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Network ID</label>
                <input type="text" placeholder="ID (e.g. res_142)" required className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition" />
              </div>

              <div className="relative">
                <label className="block text-sm font-medium text-gray-400 mb-1">Password</label>
                <input type={showPwd ? "text" : "password"} placeholder="••••••••" required className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition pr-12" />
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-9 text-gray-500 hover:text-gray-300">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                </button>
              </div>

              <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg mt-4 transition shadow-lg">
                Authenticate
              </button>
            </form>

            <div className="mt-6 text-center text-sm">
              <span className="text-gray-500">Unregistered entity? </span>
              <button onClick={() => setView('signup')} className="text-blue-400 hover:text-blue-300 font-semibold transition">Activate Account</button>
            </div>
          </div>
        ) : (
          <div className="animate-fadeIn block">
            <div className="mb-4 border-b border-gray-800 pb-3">
              <h2 className="text-lg font-bold text-white text-center">Entity Registration</h2>
            </div>

            <div className="mb-4">
              <p className="text-[10px] text-gray-500 mb-2 uppercase tracking-widest text-center">Select Identity Type</p>
              <div className="flex space-x-2">
                {['Resident', 'Security'].map(r => (
                  <button key={r} type="button" onClick={() => setSignupRole(r)}
                    className={`flex-1 py-2 text-xs font-bold rounded-lg border transition-all ${signupRole === r ? 'bg-cyan-700 text-white border-cyan-600 shadow-inner' : 'bg-gray-950 text-gray-400 border-gray-700 hover:border-gray-500'}`}>
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleSignup} className="space-y-4 max-h-[55vh] overflow-y-auto pr-2 pb-2" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Allotted ID</label>
                  <input type="text" placeholder="e.g. res_142" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Temp Passcode</label>
                  <input type="text" placeholder="Passcode" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Full Name</label>
                <input type="text" placeholder="e.g. Jane Doe" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Age</label>
                  <input type="number" min="18" placeholder="Age" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Phone Number</label>
                  <input type="tel" placeholder="Phone" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
                </div>
              </div>

              {signupRole === 'Resident' && (
                <div className="animate-fadeIn">
                  <label className="block text-xs font-medium text-gray-400 mb-1">Flat Number</label>
                  <input type="text" placeholder="e.g. A-402" required className="w-full px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition" />
                </div>
              )}

              <div className="relative pt-2 border-t border-gray-800/50">
                <label className="block text-xs font-medium text-gray-400 mb-1">New Secure Password</label>
                <input name="newPwd" type={showPwd ? "text" : "password"} placeholder="••••••••" required className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition pr-12" />
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-10 text-gray-500 hover:text-gray-300">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                </button>
              </div>

              <div className="relative">
                <label className="block text-xs font-medium text-gray-400 mb-1">Confirm New Password</label>
                <input name="confirmPwd" type={showPwd ? "text" : "password"} placeholder="••••••••" required className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition pr-12" />
              </div>

              {error && <div className="text-red-400 text-xs text-center p-2 bg-red-900/30 border border-red-800 rounded">{error}</div>}
              {success && <div className="text-green-400 text-xs text-center p-2 bg-green-900/30 border border-green-800 rounded">{success}</div>}

              <button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 px-4 rounded-lg mt-2 transition">
                Initialize Credentials
              </button>
            </form>

            <div className="mt-4 text-center text-sm border-t border-gray-800 pt-4">
              <button onClick={() => setView('signin')} className="text-gray-500 hover:text-white transition">← Return to Authentication</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}