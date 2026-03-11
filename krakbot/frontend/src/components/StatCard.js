import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function StatCard({ label, value, hint }) {
    return (_jsxs("div", { className: "card", children: [_jsx("div", { className: "muted", children: label }), _jsx("div", { className: "kpi-value", children: value }), hint && _jsx("div", { className: "muted", children: hint })] }));
}
