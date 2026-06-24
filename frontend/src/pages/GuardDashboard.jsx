import { useState, useEffect, useRef } from 'react';

export default function GuardDashboard({ onLogout }) {
  const [alarmActive, setAlarmActive] = useState(false);
  const [intercomState, setIntercomState] = useState('idle'); 
  const [flatNumber, setFlatNumber] = useState('');
  const [feed, setFeed] = useState([
    { id: 1, time: '10:14:05', loc: 'LOBBY_ENTRANCE', type: 'Badge_Swipe', status: 'SUCCESS', color: 'text-emerald-500' },
    { id: 2, time: '10:12:40', loc: 'NORTH_GATE', type: 'Camera_Scan', status: 'SUCCESS (0.98)', color: 'text-emerald-500' }
  ]);
  const feedEndRef = useRef(null);

  const [resolutionStep, setResolutionStep] = useState(null); 
  const [actionTaken, setActionTaken] = useState('');
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    const gates = ["NORTH_GATE", "SOUTH_GATE", "LOBBY_ENTRANCE", "SERVICE_GATE"];
    const events = ["Badge_Swipe", "Camera_Scan", "QR_Scan"];
    
    const interval = setInterval(() => {
      if(!alarmActive && !resolutionStep) {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        const newEvent = {
          id: Date.now(),
          time: time,
          loc: gates[Math.floor(Math.random() * gates.length)],
          type: events[Math.floor(Math.random() * events.length)],
          status: 'SUCCESS',
          color: 'text-emerald-500'
        };
        setFeed(prev => [...prev, newEvent].slice(-15));
      }
    }, 3500);
    return () => clearInterval(interval);
  }, [alarmActive, resolutionStep]);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [feed]);

  const initiateResolution = (action) => {
    setActionTaken(action);
    setResolutionStep('feedback');
  };

  const submitFeedback = (e) => {
    e.preventDefault();
    setResolutionStep('submitted');
    setTimeout(() => {
      setAlarmActive(false);
      setResolutionStep(null);
      setFeedback('');
      if (actionTaken === 'BLACKLIST') {
        alert("A formal Blacklist Request has been forwarded to the Admin Control Tower.");
      }
    }, 2500);
  };

  const handleCall = (e) => {
    e.preventDefault();
    if (!flatNumber) return;
    setIntercomState('calling');
    setTimeout(() => {
      setIntercomState('connected');
    }, 3000);
  };

  const endCall = () => {
    setIntercomState('idle');
    setFlatNumber('');
  };

  return (
    <div className="bg-gray-950 min-h-screen font-sans text-gray-200 h-screen overflow-hidden flex flex-col w-full">
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex justify-between items-center shrink-0">
        <div className="flex items-center space-x-3">
          <span className="text-xl font-bold tracking-widest text-white">HEIMDALL LOC</span>
          <span className="px-2 py-0.5 bg-emerald-900/40 text-emerald-400 border border-emerald-800 rounded text-xs font-mono font-bold animate-pulse">STREAM ONLINE</span>
        </div>
        <div className="flex items-center space-x-6">
          <div className="text-right border-r border-gray-800 pr-6 hidden sm:block">
            <p className="text-xs text-gray-500 uppercase tracking-wider font-bold">Active Queue</p>
            <p className={`text-sm font-bold font-mono ${alarmActive ? 'text-red-400' : 'text-blue-400'}`}>
              {alarmActive ? '1 Pending Alarm' : '0 Pending Alarms'}
            </p>
          </div>
          <button onClick={onLogout} className="text-sm bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-4 py-2 rounded-lg transition">Log Out</button>
        </div>
      </nav>

      <main className="p-6 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        <div className="lg:col-span-2 space-y-6 flex flex-col h-full overflow-y-auto pr-2">
          <div className={`bg-gray-900 border border-gray-800 rounded-xl p-6 transition-all duration-300 shadow-2xl shrink-0 ${alarmActive && !resolutionStep ? 'animate-pulseRed' : ''}`}>
            {!alarmActive ? (
              <div className="py-16 text-center">
                <svg className="w-16 h-16 text-gray-700 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <h3 className="text-xl font-bold text-gray-400">Perimeter Stream Stable</h3>
                <p className="text-sm text-gray-500 mt-1">Autonomous AI investigation queue is currently empty.</p>
                <button onClick={() => setAlarmActive(true)} className="mt-8 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-bold transition shadow-lg border border-blue-500">Simulate AI Trigger</button>
              </div>
            ) : resolutionStep === 'feedback' ? (
              <div className="animate-fadeIn block py-4">
                <div className="flex items-center space-x-3 border-b border-gray-800 pb-4 mb-4">
                  <div className="p-2 bg-blue-900/30 rounded-lg border border-blue-800 text-blue-400">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">Provide AI Training Context</h3>
                    <p className="text-xs text-gray-400 mt-0.5">Your input tunes the Heimdall LLM for future incidents.</p>
                  </div>
                </div>
                
                <form onSubmit={submitFeedback} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-widest">
                      Action Logged: <span className={actionTaken === 'DISMISSED' ? 'text-blue-400 font-bold' : 'text-red-400 font-bold'}>{actionTaken}</span>
                    </label>
                    <textarea 
                      required
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      placeholder="e.g., Resident was carrying heavy groceries, authorized a friend to hold the door. False positive on tailgating."
                      className="w-full px-4 py-3 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition h-28 resize-none shadow-inner"
                    ></textarea>
                  </div>
                  
                  <div className="flex justify-end space-x-3 pt-2">
                    <button type="button" onClick={() => setResolutionStep(null)} className="px-5 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition font-medium border border-gray-700">Cancel</button>
                    <button type="submit" className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg text-sm transition shadow-[0_0_15px_rgba(37,99,235,0.4)] flex items-center space-x-2 border border-blue-500">
                      <span>Submit to Neural Net</span>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                    </button>
                  </div>
                </form>
              </div>
            ) : resolutionStep === 'submitted' ? (
              <div className="py-16 text-center animate-fadeIn">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-900/30 border border-emerald-800 mb-4 shadow-[0_0_20px_rgba(16,185,129,0.2)]">
                  <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                </div>
                <h3 className="text-xl font-bold text-emerald-400">Context Ingested Successfully</h3>
                <p className="text-sm text-gray-400 mt-2">LLM weights will be adjusted in the next nightly batch training.</p>
                <p className="text-xs text-gray-500 mt-1 font-mono">Clearing active alarm queue...</p>
              </div>
            ) : (
              <div className="animate-fadeIn block">
                <div className="flex justify-between items-start border-b border-gray-800 pb-4 mb-4">
                  <div>
                    <span className="px-2 py-1 bg-red-900/50 text-red-400 border border-red-800 text-xs font-mono rounded font-bold uppercase tracking-wide mr-2">CRITICAL</span>
                    <h2 className="text-xl font-bold text-white inline-block mt-2 sm:mt-0">IDENTITY_THEFT_SUSPECT</h2>
                    <p className="text-sm text-gray-400 mt-1 font-mono">Location: server_room_door</p>
                  </div>
                  <span className="text-xs font-mono text-gray-500 bg-gray-950 px-2 py-1 rounded border border-gray-800">Just Now</span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                  <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                    <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Profile Identity</p>
                    <p className="text-sm font-bold text-white mt-1">Bob Vance (res_250)</p>
                    <p className="text-xs text-yellow-400 mt-0.5">Trust: 70 | Past Infractions: 2</p>
                  </div>
                  <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                    <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Location History</p>
                    <p className="text-sm font-bold text-white mt-1">North Gate</p>
                    <p className="text-xs text-gray-400 mt-0.5">0 incidents today</p>
                  </div>
                  <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                    <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">2Hr Global Sync</p>
                    <p className="text-sm font-bold text-white mt-1">Clear</p>
                    <p className="text-xs text-gray-400 mt-0.5">No concurrent anomalies</p>
                  </div>
                </div>

                <div className="mb-5">
                  <h4 className="text-xs text-blue-400 uppercase tracking-widest font-bold mb-2">AI Diagnostic Rationale</h4>
                  <div className="bg-gray-950 p-4 rounded-lg border-l-4 border-blue-500 text-sm text-gray-300 leading-relaxed">
                    Analyzing telemetry vectors... Tailgating anomaly detected. Subject Bob Vance swiped access card, but perimeter cameras detected an unauthorized individual following closely behind. Given Bob's history of past infractions, there is a high probability of deliberate rule circumvention.
                  </div>
                </div>

                <div className="flex flex-wrap justify-between items-center pt-4 border-t border-gray-800 gap-3">
                  <button onClick={() => initiateResolution('BLACKLIST')} className="px-4 py-2 bg-purple-900/40 hover:bg-purple-900/60 text-purple-300 border border-purple-800 rounded-lg text-sm transition flex items-center space-x-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                    <span>Request Admin Blacklist</span>
                  </button>
                  <div className="flex space-x-3">
                    <button onClick={() => initiateResolution('DISMISSED')} className="px-5 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition border border-gray-700">Dismiss</button>
                    <button onClick={() => initiateResolution('DISPATCHED')} className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white font-bold rounded-lg text-sm transition shadow-lg">Confirm Threat & Intercept</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg shrink-0">
            <div className="flex items-center space-x-2 mb-4">
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Resident Intercom</h2>
            </div>
            
            <form onSubmit={handleCall} className="flex gap-3">
              <div className="flex-1 relative">
                <input 
                  type="text" 
                  value={flatNumber}
                  onChange={(e) => setFlatNumber(e.target.value)}
                  disabled={intercomState !== 'idle'}
                  required 
                  placeholder="Enter Flat (e.g., A-402)" 
                  className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition disabled:opacity-50" 
                />
              </div>
              <button 
                type="submit" 
                disabled={intercomState !== 'idle'}
                className="bg-gray-800 hover:bg-gray-700 text-white px-6 py-2.5 rounded-lg border border-gray-700 font-bold transition flex items-center space-x-2 disabled:opacity-50"
              >
                <span>Call</span>
              </button>
            </form>

            {intercomState !== 'idle' && (
              <div className={`mt-3 p-3 border rounded-lg flex items-center justify-between ${intercomState === 'calling' ? 'bg-blue-900/20 border-blue-800/50' : 'bg-emerald-900/20 border-emerald-800/50'}`}>
                <div className="flex items-center space-x-3">
                  <span className="flex h-3 w-3 relative">
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${intercomState === 'calling' ? 'bg-blue-400' : 'bg-emerald-400'}`}></span>
                    <span className={`relative inline-flex rounded-full h-3 w-3 ${intercomState === 'calling' ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
                  </span>
                  <span className={`text-sm font-mono ${intercomState === 'calling' ? 'text-blue-400' : 'text-emerald-400'}`}>
                    {intercomState === 'calling' ? `Dialing Flat ${flatNumber.toUpperCase()}...` : `Connected to ${flatNumber.toUpperCase()} (00:01)`}
                  </span>
                </div>
                <button type="button" onClick={endCall} className="text-xs bg-red-900/50 text-red-400 hover:bg-red-900 px-3 py-1 rounded border border-red-800 transition">End Call</button>
              </div>
            )}
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full overflow-hidden shadow-lg shadow-blue-900/10">
          <div className="p-4 border-b border-gray-800 bg-gray-950/30 flex justify-between items-center">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Live Event Stream</h3>
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping"></span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-[11px] text-gray-500 scroll-smooth">
            {feed.map((item) => (
              <div key={item.id} className="border-b border-gray-800/50 pb-2 animate-fadeIn">
                <span className="text-gray-400">[{item.time}]</span> {item.loc} <br/> 
                {item.type} <span className={`${item.color} ml-2`}>{item.status}</span>
              </div>
            ))}
            <div ref={feedEndRef} />
          </div>
        </div>
      </main>
    </div>
  );
}