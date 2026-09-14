import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Heart, ChevronLeft, Send, AlertCircle, ShieldCheck } from 'lucide-react';
import api from '../services/api';
import type { AdoptionListing } from '../types';

export const AdoptionApplicationPage: React.FC = () => {
  const { listingId } = useParams<{ listingId: string }>();
  const navigate = useNavigate();

  const [listing, setListing] = useState<AdoptionListing | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form Fields
  const [housingType, setHousingType] = useState('Apartment');
  const [hasFencedGarden, setHasFencedGarden] = useState(false);
  const [hasOtherPets, setHasOtherPets] = useState(false);
  const [familyMembersCount, setFamilyMembersCount] = useState(2);
  const [experienceWithPets, setExperienceWithPets] = useState('');
  const [reasonForAdoption, setReasonForAdoption] = useState('');

  useEffect(() => {
    const fetchListing = async () => {
      if (!listingId) return;
      try {
        setLoading(true);
        const res = await api.get(`/adoptions/${listingId}`);
        setListing(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load animal listing');
      } finally {
        setLoading(false);
      }
    };
    fetchListing();
  }, [listingId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!listingId) return;
    try {
      setSubmitting(true);
      setError(null);
      await api.post(`/adoptions/listings/${listingId}/apply`, {
        housing_type: housingType,
        has_fenced_garden: hasFencedGarden,
        has_other_pets: hasOtherPets,
        family_members_count: Number(familyMembersCount),
        experience_with_pets: experienceWithPets,
        reason_for_adoption: reasonForAdoption,
      });
      navigate('/adoption-applications', { state: { submittedSuccess: true } });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit adoption application');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Link to={`/adopt/${listingId}`} className="inline-flex items-center text-sm font-semibold text-gray-500 hover:text-brand-teal transition">
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back to Animal Profile
      </Link>

      {/* Listing Summary Card */}
      {listing && (
        <div className="bg-white p-5 rounded-2xl border border-teal-100 shadow-sm flex items-center space-x-4">
          <div className="w-16 h-16 rounded-xl bg-gray-100 overflow-hidden flex-shrink-0">
            {listing.public_image_url ? (
              <img src={listing.public_image_url} alt={listing.title} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400">
                <Heart className="w-6 h-6" />
              </div>
            )}
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">{listing.title}</h2>
            <p className="text-xs text-gray-500">
              {listing.species} • Managed by {listing.organization_name}
            </p>
          </div>
        </div>
      )}

      {/* Form Container */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-gray-100 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Adoption Application</h1>
          <p className="text-sm text-gray-500 mt-1">
            Please share a few details about your home and lifestyle. This helps the NGO ensure a happy, safe match for both you and the pet.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5 text-sm">
          {/* Housing details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-gray-700 font-semibold mb-1">Housing Type *</label>
              <select
                value={housingType}
                onChange={(e) => setHousingType(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand-teal focus:bg-white outline-none"
              >
                <option value="Apartment">Apartment</option>
                <option value="Independent House">Independent House</option>
                <option value="Villa">Villa / Bungalow</option>
                <option value="Farmhouse">Farmhouse</option>
              </select>
            </div>

            <div>
              <label className="block text-gray-700 font-semibold mb-1">Family Members in Home *</label>
              <input
                type="number"
                min={1}
                max={20}
                required
                value={familyMembersCount}
                onChange={(e) => setFamilyMembersCount(parseInt(e.target.value, 10))}
                className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand-teal focus:bg-white outline-none"
              />
            </div>
          </div>

          {/* Amenities & other pets */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <label className="flex items-center space-x-3 p-3.5 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 cursor-pointer transition">
              <input
                type="checkbox"
                checked={hasFencedGarden}
                onChange={(e) => setHasFencedGarden(e.target.checked)}
                className="w-4 h-4 text-brand-teal rounded border-gray-300 focus:ring-brand-teal"
              />
              <span className="text-gray-700 font-medium">Has secure fenced garden / outdoor area</span>
            </label>

            <label className="flex items-center space-x-3 p-3.5 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 cursor-pointer transition">
              <input
                type="checkbox"
                checked={hasOtherPets}
                onChange={(e) => setHasOtherPets(e.target.checked)}
                className="w-4 h-4 text-brand-teal rounded border-gray-300 focus:ring-brand-teal"
              />
              <span className="text-gray-700 font-medium">Currently have other pets at home</span>
            </label>
          </div>

          {/* Past Experience */}
          <div>
            <label className="block text-gray-700 font-semibold mb-1">Previous Pet Experience</label>
            <textarea
              rows={2}
              placeholder="e.g. Raised rescued dogs for 5 years, familiar with basic training and vet schedules..."
              value={experienceWithPets}
              onChange={(e) => setExperienceWithPets(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand-teal focus:bg-white outline-none"
            />
          </div>

          {/* Reason for adoption */}
          <div>
            <label className="block text-gray-700 font-semibold mb-1">Why would you like to adopt this pet? *</label>
            <textarea
              required
              rows={4}
              placeholder="Tell the NGO about your routine, why this pet caught your eye, and how they will fit into your family..."
              value={reasonForAdoption}
              onChange={(e) => setReasonForAdoption(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand-teal focus:bg-white outline-none"
            />
          </div>

          <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-2 text-xs text-gray-500">
              <ShieldCheck className="w-4 h-4 text-brand-teal" />
              <span>Direct application sent to verified rescue organization</span>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto px-8 py-3 bg-brand-teal hover:bg-teal-600 text-white font-bold rounded-xl shadow-md transition disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              <Send className="w-4 h-4" />
              <span>{submitting ? 'Submitting Application...' : 'Submit Application'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
