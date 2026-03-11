import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function PageHeader({ title, subtitle }) {
    return (_jsxs("header", { className: "page-header", children: [_jsx("h2", { children: title }), _jsx("p", { className: "page-sub", children: subtitle })] }));
}
