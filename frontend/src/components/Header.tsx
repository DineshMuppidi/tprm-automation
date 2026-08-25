import { useNavigate } from "react-router-dom";
import { clearSession, getSession } from "../lib/api";

export default function Header() {
  const navigate = useNavigate();
  const session = getSession();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href="/assessments" className="font-semibold text-slate-900">TPRM Vendor Portal</a>
          {session && <a href="/findings" className="text-sm text-blue-600 hover:underline">Findings</a>}
        </div>
        {session && (
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>{session.vendor_name}</span>
            <button
              onClick={() => { clearSession(); navigate("/login"); }}
              className="text-blue-600 hover:underline"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
