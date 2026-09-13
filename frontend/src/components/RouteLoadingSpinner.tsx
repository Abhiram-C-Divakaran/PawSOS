import React from 'react';
import { Loader2 } from 'lucide-react';

export const RouteLoadingSpinner: React.FC = () => {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-8" data-testid="route-loading-spinner">
      <div className="flex items-center space-x-3 text-emerald-600">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span className="text-sm font-semibold tracking-wide text-gray-700">Loading PawReach...</span>
      </div>
    </div>
  );
};
