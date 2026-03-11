import { jsx as _jsx } from "react/jsx-runtime";
export default function Badge({ tone, children }) {
    return _jsx("span", { className: `badge ${tone}`, children: children });
}
