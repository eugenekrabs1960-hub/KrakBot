import React from 'react';
import PositionTable from '../components/PositionTable';
export default function Positions({ data }: any){ return <div><h2>Positions</h2><PositionTable items={data?.items || []} /></div> }
