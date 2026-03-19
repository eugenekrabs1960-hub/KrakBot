import React from 'react';
import SettingsForms from '../components/SettingsForms';
export default function Settings({ data, onSave }: any){ return <div><h2>Settings</h2><SettingsForms initial={data} onSave={onSave} /></div> }
