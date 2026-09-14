import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Heart,
  MapPin,
  Building2,
  Sparkles,
  ChevronLeft,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/useAuth';
import type { AdoptionListing } from '../types';

export const AdoptionDetail: React.FC = () => {
  const { listingId } = useParams<{ listingId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [listing, setListing] = useState<AdoptionListing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDetail = async () => {
      if (!listingId) return;
      try {
        setLoading(true);
        setError(null);
        const res = await api.get(`/adoptions/${listingId}`);
        setListing(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load adoption listing');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [listingId]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="max-w-2xl mx-auto p-8 bg-white rounded-2xl text-center border border-gray-100 shadow-sm space-y-4">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
        <h2 className="text-xl font-bold text-gray-900">Listing Not Found</h2>
        <p className="text-sm text-gray-500">{error || 'This animal listing is unavailable or has already been adopted.'}</p>
        <Link to="/adopt" className="inline-block px-5 py-2 bg-brand-teal text-white rounded-xl text-sm font-semibold">
          Back to Adoption Catalog
        </Link>
      </div>
    );
  }

  const handleApply = () => {
    if (!isAuthenticated) {
      navigate(`/login?redirect=/adopt/${listing.id}/apply`);
    } else {
      navigate(`/adopt/${listing.id}/apply`);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Back button */}
      <Link to="/adopt" className="inline-flex items-center text-sm font-semibold text-gray-500 hover:text-brand-teal transition">
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back to Catalog
      </Link>

      <div className="bg-white rounded-3xl overflow-hidden shadow-sm border border-gray-100 grid grid-cols-1 md:grid-cols-12">
        {/* Left Column: Media & Quick Badges */}
        <div className="md:col-span-6 bg-slate-50 flex flex-col justify-between p-6 sm:p-8 border-b md:border-b-0 md:border-r border-gray-100">
          <div className="aspect-square rounded-2xl overflow-hidden bg-gray-200 relative shadow-inner flex items-center justify-center">
            {listing.public_image_url ? (
              <img src={listing.public_image_url} alt={listing.title} className="w-full h-full object-cover" />
            ) : (
              <div className="text-gray-400 flex flex-col items-center">
                <Heart className="w-16 h-16 stroke-1 mb-2" />
                <span className="text-sm font-medium">Verified Profile</span>
              </div>
            )}
            <span className="absolute top-4 left-4 bg-brand-darkNavy/85 backdrop-blur-md text-white px-3 py-1 rounded-full text-xs font-bold tracking-wide">
              {listing.species}
            </span>
          </div>

          <div className="mt-6 space-y-3">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Health & Status</span>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white p-3 rounded-xl border border-gray-200 text-xs">
                <span className="text-gray-400 block">Sterilization</span>
                <span className="font-bold text-emerald-700 mt-0.5 block">{listing.sterilization_status || 'Pending'}</span>
              </div>
              <div className="bg-white p-3 rounded-xl border border-gray-200 text-xs">
                <span className="text-gray-400 block">Vaccination</span>
                <span className="font-bold text-blue-700 mt-0.5 block">{listing.vaccination_status || 'Up to date'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Narrative Details & Apply CTA */}
        <div className="md:col-span-6 p-6 sm:p-8 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div>
              <div className="flex items-center space-x-2 text-xs font-semibold text-brand-teal uppercase tracking-wider mb-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Ready for Adoption</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900">{listing.title}</h1>
            </div>

            {/* General Specs */}
            <div className="flex flex-wrap gap-2 text-xs">
              {listing.sex && (
                <span className="px-3 py-1 rounded-lg bg-gray-100 font-medium text-gray-700">
                  Sex: <strong className="text-gray-900">{listing.sex}</strong>
                </span>
              )}
              {listing.approx_age && (
                <span className="px-3 py-1 rounded-lg bg-gray-100 font-medium text-gray-700">
                  Age: <strong className="text-gray-900">{listing.approx_age}</strong>
                </span>
              )}
              {listing.colour && (
                <span className="px-3 py-1 rounded-lg bg-gray-100 font-medium text-gray-700">
                  Colour: <strong className="text-gray-900">{listing.colour}</strong>
                </span>
              )}
            </div>

            {/* Description */}
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-gray-800">About this rescue</h3>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                {listing.public_description || 'This wonderful animal is looking for a caring, permanent home.'}
              </p>
            </div>

            {/* Medical Summary */}
            {listing.medical_summary && (
              <div className="bg-emerald-50/70 border border-emerald-100 p-4 rounded-xl space-y-1">
                <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider block flex items-center">
                  <CheckCircle className="w-3.5 h-3.5 mr-1" />
                  Veterinary Recovery Complete
                </span>
                <p className="text-xs text-emerald-900 leading-relaxed">{listing.medical_summary}</p>
              </div>
            )}

            {/* Organization & Location Information */}
            <div className="border-t border-gray-100 pt-4 space-y-2 text-xs text-gray-500">
              <div className="flex items-center space-x-2">
                <Building2 className="w-4 h-4 text-gray-400" />
                <span>
                  Rescued and managed by: <strong className="text-gray-800">{listing.organization_name}</strong>
                </span>
              </div>
              {listing.locality && (
                <div className="flex items-center space-x-2">
                  <MapPin className="w-4 h-4 text-gray-400" />
                  <span>
                    Current Area: <strong className="text-gray-800">{listing.locality}</strong>
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Action CTA */}
          <div className="pt-6 border-t border-gray-100 space-y-3">
            <button
              onClick={handleApply}
              className="w-full py-3.5 bg-brand-teal hover:bg-teal-600 text-white font-bold rounded-xl shadow-md hover:shadow-lg transition text-sm flex items-center justify-center space-x-2"
            >
              <Heart className="w-4 h-4 fill-current" />
              <span>Apply to Adopt {listing.title.split(' ')[0]}</span>
            </button>
            <p className="text-[11px] text-gray-400 text-center">
              The managing NGO will review your application, contact you, and arrange a safe meet-and-greet visit.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
