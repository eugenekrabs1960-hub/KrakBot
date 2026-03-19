import React from 'react';
export default function CandidateTable({ items = [] }: any) {
  return <table><thead><tr><th>Coin</th><th>Rank</th><th>Opportunity</th><th>Tradability</th></tr></thead><tbody>{items.map((x:any)=><tr key={x.symbol}><td>{x.coin}</td><td>{x.rank_score?.toFixed?.(3)}</td><td>{x.ml_scores?.opportunity_score?.toFixed?.(3)}</td><td>{x.ml_scores?.tradability_score?.toFixed?.(3)}</td></tr>)}</tbody></table>
}
