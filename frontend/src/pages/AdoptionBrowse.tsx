import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Heart, Search, ShieldCheck, MapPin, Sparkles } from 'lucide-react';
import api from '../services/api';
import type { AdoptionListing } from '../types';

export const AdoptionBrowse: React.FC = () => {
  const [listings, setListings] = useState<AdoptionListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSpecies, setSelectedSpecies] = useState('ALL');

  useEffect(() => {
    const fetchListings = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await api.get('/adoptions');
        setListings(res.data || []);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load adoption catalog');
      } finally {
        setLoading(false);
      }
    };
    fetchListings();
  }, []);

  const filteredListings = listings.filter((item) => {
    const matchesSearch =
      item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.public_description && item.public_description.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (item.locality && item.locality.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesSpecies = selectedSpecies === 'ALL' || item.species.toUpperCase() === selectedSpecies.toUpperCase();

    return matchesSearch && matchesSpecies;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Hero section */}
      <div className="relative overflow-hidden bg-gradient-to-r from-brand-darkNavy via-teal-950 to-slate-900 rounded-3xl p-8 sm:p-12 text-white shadow-xl">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center space-x-2 bg-teal-500/20 backdrop-blur-md px-3 py-1 rounded-full text-xs font-semibold text-brand-brightTeal border border-teal-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Verified Rescues Ready For Forever Homes</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
            Give a Rescue Pet a Second Chance
          </h1>
          <p className="text-gray-300 text-sm sm:text-base leading-relaxed">
            All animals featured here have completed full medical triage, veterinary treatment, and post-care recovery. Browse verified profiles and submit an adoption application directly to the responsible NGO.
          </p>
        </div>
      </div>

      {/* Filter and search bar */}
      <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, locality, or trait..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-teal focus:bg-white transition"
          />
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider hidden sm:block">Species:</span>
          {['ALL', 'DOG', 'CAT'].map((species) => (
            <button
              key={species}
              onClick={() => setSelectedSpecies(species)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex-shrink-0 ${
                selectedSpecies === species
                  ? 'bg-brand-teal text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {species}
            </button>
          ))}
        </div>
      </div>

      {/* Listings Grid */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-2xl text-center">
          <p className="font-semibold">{error}</p>
        </div>
      ) : filteredListings.length === 0 ? (
        <div className="bg-white rounded-3xl p-16 text-center border border-gray-100 shadow-sm">
          <Heart className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-gray-800">No animals matching your criteria</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
            Check back soon as recovered animals from veterinary facilities and foster homes are regularly listed for adoption!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredListings.map((item) => (
            <Link
              key={item.id}
              to={`/adopt/${item.id}`}
              className="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-lg transition-all group flex flex-col justify-between"
            >
              <div>
                <div className="h-52 bg-slate-100 relative overflow-hidden flex items-center justify-center">
                  {item.public_image_url ? (
                    <img
                      src={item.public_image_url}
                      alt={item.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="text-gray-300 flex flex-col items-center">
                      <Heart className="w-12 h-12 stroke-1" />
                      <span className="text-xs mt-1">Photo pending</span>
                    </div>
                  )}
                  <span className="absolute top-3 left-3 bg-brand-darkNavy/80 backdrop-blur-md text-white text-xs font-semibold px-2.5 py-1 rounded-full">
                    {item.species}
                  </span>
                  {item.locality && (
                    <span className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-md text-gray-800 text-xs font-medium px-2.5 py-1 rounded-full flex items-center shadow-sm">
                      <MapPin className="w-3 h-3 mr-1 text-brand-teal" />
                      {item.locality}
                    </span>
                  )}
                </div>

                <div className="p-5 space-y-3">
                  <h3 className="text-lg font-bold text-gray-900 group-hover:text-brand-teal transition">
                    {item.title}
                  </h3>

                  <p className="text-sm text-gray-600 line-clamp-2 leading-relaxed">
                    {item.public_description || 'Friendly companion looking for a loving home.'}
                  </p>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {item.sterilization_status && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <ShieldCheck className="w-3 h-3 mr-1 text-emerald-600" />
                        {item.sterilization_status}
                      </span>
                    )}
                    {item.vaccination_status && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        Vaccinated
                      </span>
                    )}
                    {item.sex && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                        {item.sex}
                      </span>
                    )}
                    {item.approx_age && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                        {item.approx_age}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="px-5 py-3.5 bg-gray-50/70 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                <span>By {item.organization_name}</span>
                <span className="font-semibold text-brand-teal group-hover:translate-x-1 transition-transform flex items-center">
                  View Profile →
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
