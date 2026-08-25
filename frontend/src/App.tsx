import type { JSX } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import AdminAssign from "./pages/AdminAssign";
import AssessmentList from "./pages/AssessmentList";
import Login from "./pages/Login";
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
        <Route path="/admin" element={<AdminAssign />} />
      </Routes>
    </Router>
  );
}
