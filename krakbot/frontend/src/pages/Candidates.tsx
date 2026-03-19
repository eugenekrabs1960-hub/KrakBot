import React from 'react';
import CandidateTable from '../components/CandidateTable';
export default function Candidates({ data }: any){ return <div><h2>Candidates</h2><CandidateTable items={data?.items || []} /></div> }
