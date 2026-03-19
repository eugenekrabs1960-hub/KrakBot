import React from 'react';
import DecisionTable from '../components/DecisionTable';
export default function Decisions({ data }: any){ return <div><h2>Decisions</h2><DecisionTable items={data?.decisions || []} /><pre>{JSON.stringify(data?.policy || [], null, 2)}</pre></div> }
