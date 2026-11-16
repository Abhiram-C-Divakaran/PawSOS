import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import type { RescueCase } from '../types';
import { AlertCircle, Clock, MapPin, Activity } from 'lucide-react';

export const MyCases = () => {
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchCases = async () => {
      try {
        const response = await api.get('/rescues/my');
        setCases(response.data);
      } catch (err: any) {
        setError(formatApiError(err, 'Failed to load your rescue cases.'));
      } finally {
        setLoading(false);
      }
    };
    fetchCases();
  }, []);

  if (loading) return <div role="status" className="text-center py-12 text-gray-600 font-medium">Loading cases...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-brand-darkNavy">My Rescue Reports</h1>
        <Link to="/report" className="self-start sm:self-auto bg-brand-teal text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-brightTeal transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-darkNavy">
          Report New Animal
        </Link>
      </div>

      {error && (
        <div role="alert" className="mb-6 bg-red-50 text-red-600 p-4 rounded-lg flex items-start">
          <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {cases.length === 0 && !error ? (
        <div className="bg-white p-12 rounded-xl shadow-sm border border-gray-100 text-center">
          <Activity className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-700 mb-2">No rescue reports yet</h3>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">If you find an animal in distress, PawReach can help connect it with nearby support.</p>
          <Link to="/report" className="inline-block bg-brand-teal text-white px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-brand-brightTeal transition">
            Report an Animal Now
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cases.map((rescue) => (
            <Link key={rescue.id} to={`/cases/${rescue.id}`} className="block">
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:border-brand-teal hover:shadow-md transition-all">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center space-x-2">
                    <span className="bg-gray-100 text-gray-800 text-xs font-mono px-2 py-1 rounded">
                      {rescue.case_number}
                    </span>
                    <span className="font-semibold text-lg text-brand-darkNavy">{rescue.species}</span>
                  </div>
                  <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                    rescue.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                    rescue.triage_priority === 'URGENT' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {rescue.triage_priority}
                  </span>
                </div>
                
                <p className="text-gray-600 text-sm mb-4 line-clamp-2">{rescue.description}</p>
                
                <div className="space-y-2 text-sm text-gray-500">
                  <div className="flex items-center">
                    <MapPin className="w-4 h-4 mr-2" /> {rescue.address_text}
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center">
                      <Clock className="w-4 h-4 mr-2" /> 
                      {new Date(rescue.created_at).toLocaleDateString()}
                    </div>
                    <span className="font-medium text-brand-teal">{rescue.status.replace(/_/g, ' ')}</span>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
