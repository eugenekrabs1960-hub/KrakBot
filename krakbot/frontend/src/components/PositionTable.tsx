import React from 'react';
export default function PositionTable({ items = [] }: any) {
  return <table><thead><tr><th>Symbol</th><th>Qty</th></tr></thead><tbody>{items.map((x:any)=><tr key={x.symbol}><td>{x.symbol}</td><td>{x.qty}</td></tr>)}</tbody></table>
}
