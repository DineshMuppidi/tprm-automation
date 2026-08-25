import type { JSX } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import AdminAssign from "./pages/AdminAssign";
import AdminFindingDetail from "./pages/AdminFindingDetail";
import AdminFindings from "./pages/AdminFindings";
import AssessmentList from "./pages/AssessmentList";
import FindingDetail from "./pages/FindingDetail";
import FindingsList from "./pages/FindingsList";
import Login from "./pages/Login";
import MonitoringDashboard from "./pages/MonitoringDashboard";
import Questionnaire from "./pages/Questionnaire";
import Result from "./pages/Result";
import Verify from "./pages/Verify";
import { getSession } from "./lib/api";

function RequireSession({ children }: { children: JSX.Element }) {
  return getSession() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to={getSession() ? "/assessments" : "/login"} replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/assessments" element={<RequireSession><AssessmentList /></RequireSession>} />
        <Route path="/assessments/:id" element={<RequireSession><Questionnaire /></RequireSession>} />
        <Route path="/assessments/:id/result" element={<RequireSession><Result /></RequireSession>} />
        <Route path="/findings" element={<RequireSession><FindingsList /></RequireSession>} />
        <Route path="/findings/:id" element={<RequireSession><FindingDetail /></RequireSession>} />
        <Route path="/admin" element={<AdminAssign />} />
        <Route path="/admin/monitoring" element={<MonitoringDashboard />} />
        <Route path="/admin/findings" element={<AdminFindings />} />
        <Route path="/admin/findings/:id" element={<AdminFindingDetail />} />
      </Routes>
    </Router>
  );
}
