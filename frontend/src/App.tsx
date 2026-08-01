import { Dashboard } from "./pages/Dashboard";
import { AuthGate } from "./components/AuthGate";

export default function App() {
  return (
    <AuthGate>
      <Dashboard />
    </AuthGate>
  );
}
