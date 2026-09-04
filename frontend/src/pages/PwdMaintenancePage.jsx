import React from 'react';
import PwdModal from '../components/common/PwdModal';

export default function PwdMaintenancePage({ onClose }) {
  return (
    <div className="p-4 max-w-[1920px] mx-auto">
      <PwdModal onClose={onClose || (() => {})} />
    </div>
  );
}
