import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function AppShell({ nav, active, onChange, children }) {
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("aside", { className: "sidebar", children: [_jsx("div", { className: "brand", children: "KrakBot Operator UI" }), _jsx("div", { className: "nav-row", children: nav.map((item) => (_jsx("button", { className: `nav-btn ${active === item.id ? 'active' : ''}`, onClick: () => onChange(item.id), children: item.label }, item.id))) })] }), _jsx("div", { className: "content", children: children })] }));
}
