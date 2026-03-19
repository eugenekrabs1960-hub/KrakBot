import React from 'react';
export default function DecisionTable({ items = [] }: any) {
  return <table><thead><tr><th>Symbol</th><th>Action</th><th>Confidence</th></tr></thead><tbody>{items.map((x:any,i:number)=><tr key={i}><td>{x.symbol}</td><td>{x.action}</td><td>{x.confidence}</td></tr>)}</tbody></table>
}
