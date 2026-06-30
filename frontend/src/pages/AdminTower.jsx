import { useState, useEffect } from 'react';

const API = "http://127.0.0.1:8000";

export default function AdminTower({ onLogout }) {
  const [lockdown, setLockdown] = useState(false);
  const [provTab, setProvTab] = useState('resident'); 
  const [numResidents, setNumResidents] = useState(1);
  const [flatNum, setFlatNum] = useState('');
  const [badges, setBadges] = useState(['']);
  const [numSec, setNumSec] = useState(1);
  const [generatedCreds, setGeneratedCreds] = useState(null);
  const [broadcastTitle, setBroadcastTitle] = useState(''); 
  const [broadcastMsg, setBroadcastMsg] = useState('');
  const [broadcastSent, setBroadcastSent] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [directoryRoleFilter, setDirectoryRoleFilter] = useState('All'); 
  const [users, setUsers] = useState([]);

  const [pendingRequests, setPendingRequests] = useState([
    { id: 'res_250', name: 'Bob Vance', details: 'AI flagged 3rd tailgating violation. Guard intercepted and verified intentional breach. Requesting immediate credential revocation.', origin: 'Unit Alpha' },
    { id: 'res_104', name: 'Michael Scott', details: 'Access card pattern anomaly detected. Entity logged entering North Gate and South Gate within 30 seconds.', origin: 'System Kernel' },
    { id: 'res_882', name: 'Dwight Schrute', details: 'Manual override log warning requested. Override activated on perimeter vault perimeter sensor asset.', origin: 'Watch Tower 2' }
  ]);

  const [alerts, setAlerts] = useState([
    { id: 1, severity: 'HIGH', message: 'Gate 3 Relay Timeout anomaly recorded. Attempting auto-recovery handshake.', timestamp: '10 mins ago', color: 'border-red-500 text-red-400 bg-red-950/20' },
    { id: 2, severity: 'MEDIUM', message: 'Tailgating validation warning triggered at Lobby Turnstile.', timestamp: '24 mins ago', color: 'border-yellow-500 text-yellow-400 bg-yellow-950/20' },
    { id: 3, severity: 'LOW', message: 'System maintenance sync scheduled for tonight at 02:00 AM.', timestamp: '1 hr ago', color: 'border-blue-500 text-blue-400 bg-blue-950/20' },
    { id: 4, severity: 'HIGH', message: 'Gate 3 Relay Timeout anomaly recorded. Attempting auto-recovery handshake.', timestamp: '10 mins ago', color: 'border-red-500 text-red-400 bg-red-950/20' },
    { id: 5, severity: 'MEDIUM', message: 'Tailgating validation warning triggered at Lobby Turnstile.', timestamp: '24 mins ago', color: 'border-yellow-500 text-yellow-400 bg-yellow-950/20' },
    { id: 6, severity: 'LOW', message: 'System maintenance sync scheduled for tonight at 02:00 AM.', timestamp: '1 hr ago', color: 'border-blue-500 text-blue-400 bg-blue-950/20' }
  ]);

  const fetchDirectory = async () => {
    try {
      const response = await fetch(`${API}/community/community-directory`);
      if (!response.ok) throw new Error('Failed to fetch directory');
      const data = await response.json();
      
      const mappedUsers = data.map((item) => {
        const uId = item.id;
        const inferredRole = item.role;
        const isSecurity = inferredRole === 'Security';

        return {
          id: uId,
          name: item.name || (isSecurity ? 'Guard Duty' : 'Resident Host'),
          role: inferredRole,
          score: item.score !== undefined ? item.score : 100,
          status: item.status || 'Active',
          isInitialized: item.is_initialized, // Track account activation status from database
          cardStatus: item.card_status || 'active', // Track card block status
          color: item.score === 0 ? 'text-red-500' : 'text-emerald-400',
          roleColor: isSecurity ? 'bg-gray-800 text-gray-400' : 'bg-gray-800'
        };
      });
      setUsers(mappedUsers);
    } catch (err) {
      console.error('Directory sync error:', err);
    }
  };

  useEffect(() => {
    fetchDirectory();
  }, []);

  const filteredUsers = users.filter(u => {
    const matchesSearch = u.name.toLowerCase().includes(searchQuery.toLowerCase()) || u.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = directoryRoleFilter === 'All' || u.role === directoryRoleFilter;
    return matchesSearch && matchesFilter;
  });

  const handleBlacklist = async (residentId) => {
    if (!residentId) return;
    try {
      const response = await fetch(`${API}/community/resident/${residentId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        alert(`Blacklist Approved. Credentials for ${residentId} have been permanently revoked.`);
        fetchDirectory();
        setPendingRequests(pendingRequests.filter(req => req.id !== residentId));
      } else {
        const data = await response.json();
        alert(data.detail || "Revocation request rejected by server.");
      }
    } catch (err) {
      alert("Network failure resolving blacklist sequence.");
    }
  };

  const handleRejectRequestLocal = (reqId) => {
    alert(`Request Rejected. Informing origin node terminal.`);
    setPendingRequests(pendingRequests.filter(req => req.id !== reqId));
  };

  const handleNumResidentsChange = (e) => {
    const num = parseInt(e.target.value) || 1;
    setNumResidents(num);
    const newBadges = [...badges];
    while(newBadges.length < num) newBadges.push('');
    setBadges(newBadges.slice(0, num));
  };

  const handleBadgeChange = (index, value) => {
    const newBadges = [...badges];
    newBadges[index] = value;
    setBadges(newBadges);
  };

  const handleProvision = async (e) => {
    e.preventDefault();
    setGeneratedCreds(null);

    try {
      let response;

      if (provTab === "resident") {
        response = await fetch(`${API}/resident/generate-identities`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            number_of_residents: numResidents,
            flat_number: flatNum,
            resident_badge_ids: badges,
          }),
        });
      } else {
        response = await fetch(`${API}/security/generate-security-guards`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            number_of_new_guards: numSec,
          }),
        });
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Provision failed");
      }

      const creds = data.map((item) => ({
        role: item.Resident || item.Security,
        id: item.ID,
        tempPwd: item.Password,
        flat: item.Flat || "N/A",
        badge: item.Badge || "N/A",
      }));

      setGeneratedCreds(creds);
      fetchDirectory();

    } catch (err) {
      alert(err.message);
    }
  };

  const handleBroadcast = async (e) => {
    e.preventDefault();
    setBroadcastSent(false);

    try {
      const response = await fetch(`${API}/announcement/send-announcement`, {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: broadcastTitle,
          message: broadcastMsg
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to sync noticeboard broadcast.');
      }

      setBroadcastSent(true);
      setBroadcastTitle('');
      setBroadcastMsg('');
      setTimeout(() => setBroadcastSent(false), 3000);

    } catch (err) {
      alert(err.message);
    }
  };

  const handleRemoveUserDirect = async (userId) => {
    if (!window.confirm(`Revoke clearance credentials for: ${userId}?`)) return;

    try {
      const response = await fetch(`${API}/community/resident/${userId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        fetchDirectory();
      } else {
        const data = await response.json();
        alert(data.detail || 'Failed to drop target membership identifier.');
      }
    } catch (err) {
      alert('Error connection timeout syncing delete instruction.');
    }
  };

  const handleUnblockCard = async (userId) => {
    try {
      const response = await fetch(`${API}/resident/unblock-card/${userId}`, {
        method: 'POST',
        headers: { "Content-Type": "application/json" }
      });

      if (response.ok) {
        alert(`Access Card for ${userId} successfully restored to Active.`);
        fetchDirectory();
      } else {
        const data = await response.json();
        alert(data.detail || 'Failed to unblock target access card.');
      }
    } catch (err) {
      alert('Network communication error restoring card status.');
    }
  };

  return (
    <div className={`min-h-screen font-sans text-gray-200 transition-colors duration-500 overflow-x-hidden w-full pb-10 ${lockdown ? 'bg-red-950/90' : 'bg-gray-950'}`}>
      <nav className="bg-gray-900 border-b border-purple-900/50 px-6 py-4 flex justify-between items-center sticky top-0 z-40">
        <div className="flex items-center space-x-3">
          <span className="text-xl font-bold tracking-widest text-white">HEIMDALL</span>
          <span className="px-2 py-0.5 bg-purple-900/40 text-purple-400 border border-purple-800 rounded text-xs font-mono font-bold hidden sm:inline-block">ADMIN PORTAL</span>
        </div>
        <button onClick={onLogout} className="text-sm bg-gray-800 hover:bg-gray-700 border border-gray-700 text-red-400 px-4 py-2 rounded-lg transition">Sign Out</button>
      </nav>

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Top Analytics Metrics Cards Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-900 p-5 rounded-xl border border-gray-800">
            <span className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">AI Detection Accuracy</span>
            <div className="text-2xl font-bold text-emerald-400 mt-1">99.4%</div>
          </div>
          <div className="bg-gray-900 p-5 rounded-xl border border-gray-800">
            <span className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">False Alerts</span>
            <div className="text-2xl font-bold text-blue-400 mt-1">1.2%</div>
          </div>
          <div className="bg-gray-900 p-5 rounded-xl border border-gray-800">
            <span className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">Access Events Today</span>
            <div className="text-2xl font-bold text-gray-200 mt-1 font-mono">1,402</div>
          </div>
          <div className="bg-gray-900 p-5 rounded-xl border border-gray-800">
            <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Gates Status</span>
            <div className="text-2xl font-bold text-purple-300 mt-1">14 / 14 Online</div>
          </div>
        </div>

        {/* Middle Sections Grid Row Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-6 flex flex-col">
            <div className="bg-gray-900 rounded-xl border border-gray-800 flex-1 flex flex-col">
              <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-gray-950/30">
                <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Pending Requests</h2>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${pendingRequests.length > 0 ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-400'}`}>
                  {pendingRequests.length} Pending
                </span>
              </div>
              
              <div className="p-4 space-y-4 overflow-y-auto max-h-[340px]" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
                {pendingRequests.length > 0 ? (
                  pendingRequests.map((req) => (
                    <div key={req.id} className="bg-gray-950 border border-gray-800 rounded-lg p-4 animate-fadeIn space-y-2">
                      <div className="flex justify-between items-start">
                        <span className="text-[10px] text-gray-500">From: {req.origin}</span>
                      </div>
                      <h3 className="text-sm font-bold text-white mb-1">Subject: {req.name} ({req.id})</h3>
                      <p className="text-xs text-gray-400 mb-3">{req.details}</p>
                      
                      <div className="flex space-x-2 border-t border-gray-800 pt-3">
                        <button onClick={() => handleBlacklist(req.id)} className="flex-1 bg-red-900/50 hover:bg-red-900 text-red-300 border border-red-800 py-1.5 rounded text-xs font-bold transition">Revoke Access</button>
                        <button onClick={() => handleRejectRequestLocal(req.id)} className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 py-1.5 rounded text-xs transition">Reject</button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 animate-fadeIn">
                    <svg className="w-10 h-10 text-gray-700 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                    <p className="text-sm text-gray-500">All requests resolved.</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Alerts box panel component */}
          <div className="lg:col-span-2 bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full">
            <div className="p-4 border-b border-gray-800 flex justify-between items-center">
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">System Alerts Log</h2>
              <span className="text-xs bg-green-800 text-gray-400 px-2 py-1 rounded border border-gray-700">Live</span>
            </div>
            
            <div className="p-4 space-y-3 overflow-y-auto h-[340px]" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
              {alerts.map((alertItem) => (
                <div key={alertItem.id} className={`p-3 border-l-4 rounded-r-lg ${alertItem.color}`}>
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold uppercase">{alertItem.severity} SEVERITY</span>
                    <span className="text-[10px] text-gray-500">{alertItem.timestamp}</span>
                  </div>
                  <p className="text-sm mt-1">{alertItem.message}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Utility Grid Options */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 shadow-lg flex flex-col min-h-[250px]">
            <div className="flex items-center space-x-2 mb-4">
              <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"></path></svg>
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Priority Broadcast</h2>
            </div>
            <p className="text-[10px] text-gray-500 mb-4 uppercase tracking-widest">Push notification to all residents</p>
            
            <form onSubmit={handleBroadcast} className="space-y-4 flex-1 flex flex-col">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Broadcast Title</label>
                <input 
                  type="text" 
                  required 
                  value={broadcastTitle}
                  onChange={(e) => setBroadcastTitle(e.target.value)} 
                  placeholder="Ex: Emergency Broadcast" 
                  className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 transition" 
                />
              </div>

              <div className="flex-1 flex flex-col">
                <label className="block text-xs font-medium text-gray-400 mb-1">Broadcast Message</label>
                <textarea 
                  required 
                  value={broadcastMsg}
                  onChange={(e) => setBroadcastMsg(e.target.value)}
                  placeholder="Enter emergency or system abnormality notification here..."
                  className="w-full flex-1 min-h-[120px] px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 transition mb-4 resize-none" 
                />
              </div>
              
              {broadcastSent && <div className="text-green-400 text-xs text-center p-2 bg-green-900/30 border border-green-800 rounded mb-3">Broadcast successfully transmitted!</div>}
              <button type="submit" className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-2.5 rounded-lg transition shadow-lg mt-auto">Transmit to All</button>
            </form>
          </div>

          <div className="lg:col-span-2 bg-gray-900 rounded-xl p-6 border border-gray-800 shadow-lg">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Entity Provisioning Engine</h2>
            
            <div className="flex border-b border-gray-800 mb-5">
              <button onClick={() => { setProvTab('resident'); setGeneratedCreds(null); }} className={`px-4 py-2 text-sm font-medium transition-colors ${provTab === 'resident' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Add Residents</button>
              <button onClick={() => { setProvTab('security'); setGeneratedCreds(null); }} className={`px-4 py-2 text-sm font-medium transition-colors ${provTab === 'security' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-gray-500 hover:text-gray-300'}`}>Add Security Guards</button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <form onSubmit={handleProvision} className="space-y-4">
                {provTab === 'resident' ? (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1">Number of Residents</label>
                        <input type="number" min="1" max="10" value={numResidents} onChange={handleNumResidentsChange} required className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1">Flat Number</label>
                        <input type="text" placeholder="e.g. A-402" value={flatNum} onChange={(e) => setFlatNum(e.target.value)} required className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                    </div>
                    
                    <div className="space-y-3 max-h-40 overflow-y-auto pr-2" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
                      {badges.map((badge, idx) => (
                        <div key={idx}>
                          <label className="block text-[10px] font-medium text-gray-500 mb-1">Resident {idx + 1} Badge ID</label>
                          <input type="text" placeholder="e.g. BDG-9981" value={badge} onChange={(e) => handleBadgeChange(idx, e.target.value)} required className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1">Number of New Guards</label>
                    <input type="number" min="1" max="20" value={numSec} onChange={(e) => setNumSec(parseInt(e.target.value))} required className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
                  </div>
                )}
                
                <button type="submit" className={`w-full text-white font-bold py-2.5 rounded-lg transition shadow-lg mt-4 ${provTab === 'resident' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-emerald-600 hover:bg-emerald-700'}`}>
                  Generate Identities
                </button>
              </form>

              <div className="bg-gray-950 border border-gray-800 rounded-lg p-4 flex flex-col h-full min-h-[200px]">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 border-b border-gray-800 pb-2">Account Credentials</h3>
                
                {!generatedCreds ? (
                  <div className="flex-1 flex items-center justify-center text-sm text-gray-600 italic">Generate an account to view credentials...</div>
                ) : (
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2" style={{ maxHeight: '200px', scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
                    {generatedCreds.map((cred, idx) => (
                      <div key={idx} className="bg-gray-900 border border-gray-800 p-3 rounded text-xs font-mono">
                        <div className="flex justify-between mb-1">
                          <span className={`${cred.role === 'Resident' ? 'text-blue-400' : 'text-emerald-400'} font-bold`}>{cred.role}</span>
                          <span className="text-gray-400">ID: <span className="text-white">{cred.id}</span></span>
                        </div>
                        <div className="text-gray-400 flex justify-between">
                          <span>Temp PWD: <span className="text-yellow-400">{cred.tempPwd}</span></span>
                          {cred.flat !== 'N/A' && <span>Flat: {cred.flat}</span>}
                        </div>
                        {cred.badge !== 'N/A' && <div className="text-gray-500 mt-1">Badge: {cred.badge}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Community Directory */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col mt-6">
          <div className="p-4 border-b border-gray-800 flex justify-between items-center flex-wrap gap-3">
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Community Directory</h2>
            
            <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
              <div className="flex space-x-1 p-0.5 bg-gray-950 rounded border border-gray-800">
                {['All', 'Resident', 'Security'].map(filterRole => (
                  <button
                    key={filterRole}
                    onClick={() => setDirectoryRoleFilter(filterRole)}
                    className={`px-3 py-1 text-xs rounded font-medium transition-all ${directoryRoleFilter === filterRole ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
                  >
                    {filterRole === 'All' ? 'All' : filterRole === 'Resident' ? 'Residents' : 'Guards'}
                  </button>
                ))}
              </div>

              <div className="relative flex-1 sm:flex-initial">
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search ID or Name..." 
                  className="pl-8 pr-3 py-1.5 bg-gray-950 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-purple-500 w-full sm:w-64 transition"
                />
                <svg className="w-4 h-4 text-gray-500 absolute left-2.5 top-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto overflow-y-auto max-h-[400px]" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
            <table className="w-full text-left text-sm text-gray-300 min-w-[600px]">
              <thead className="text-xs text-gray-500 uppercase border-b border-gray-800 bg-gray-950/50 sticky top-0 z-10">
                {/* 🛠️ Added "Status" to table head mapping structure */}
                <tr>
                  <th className="py-3 px-4 font-medium bg-gray-900">User Profile</th>
                  <th className="py-3 px-4 font-medium bg-gray-900">Role</th>
                  <th className="py-3 px-4 font-medium bg-gray-900">Status</th>
                  <th className="py-3 px-4 font-medium bg-gray-900">Score</th>
                  <th className="py-3 px-4 font-medium text-right bg-gray-900">Action</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs divide-y divide-gray-800">
                {filteredUsers.length > 0 ? filteredUsers.map((u) => (
                  <tr key={`${u.role}-${u.id}`} className="hover:bg-gray-800/50 transition">
                    <td className="px-6 py-4">
                      <p className="text-white font-bold font-sans">{u.name}</p>
                      <p className="text-gray-500">{u.id}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded text-[10px] uppercase tracking-wider ${u.roleColor}`}>{u.role}</span>
                    </td>
                    {/* 🛠️ Dynamic account activation status indicator added below */}
                    <td className="px-6 py-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium uppercase ${u.isInitialized ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/50' : 'bg-amber-950 text-yellow-500 border border-amber-900/50'}`}>
                        {u.isInitialized ? 'Activated' : 'Pending Activation'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`font-bold ${u.color}`}>{u.score === 0 ? '0 (BLACKLIST)' : u.score}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end space-x-3">
                        <button 
                          onClick={() => handleRemoveUserDirect(u.id)}
                          className="text-purple-400 hover:text-purple-300 text-xs font-sans"
                        >
                          Revoke
                        </button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="5" className="text-center py-8 text-gray-500 font-sans">No users found matching "{searchQuery}"</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}