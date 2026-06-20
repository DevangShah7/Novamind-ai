import { FC } from 'react';

interface StatsCardProps {
  title: string;
  value: number | string;
  icon?: React.ReactNode;
}

const StatsCard: FC<StatsCardProps> = ({ title, value, icon }) => {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg border">
      <div className="p-4 sm:p-6">
        <div className="text-sm font-medium text-gray-500">{title}</div>
        <div className="mt-1 flex items-center">
          {icon && (
            <span className="mr-2 text-indigo-500 h-5 w-5">{icon}</span>
          )}
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );
};

export default StatsCard;