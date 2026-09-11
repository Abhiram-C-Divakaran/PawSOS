import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Camera, MapPin, AlertTriangle, CheckCircle } from 'lucide-react';

export const ReportRescue = () => {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form State
  const [species, setSpecies] = useState('Dog');
  const [photo, setPhoto] = useState<string | null>(null);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [address, setAddress] = useState('');
  
  // Triage state
  const [triage, setTriage] = useState({
    bleeding: false,
    can_walk: true,
    conscious: true,
    vehicle_accident: false,
    breathing_difficulty: false,
  });
  const [description, setDescription] = useState('');

  const [submittedCase, setSubmittedCase] = useState<any>(null);

  const handleNext = () => setStep((s) => Math.min(s + 1, 6));
  const handleBack = () => setStep((s) => Math.max(s - 1, 1));

  const handleGetLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude
          });
          setAddress(`Lat: ${position.coords.latitude.toFixed(4)}, Lng: ${position.coords.longitude.toFixed(4)}`);
        },
        () => alert('Location access denied. Please enter manually.')
      );
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      const payload = {
        species,
        description,
        latitude: location?.lat || 19.0760,
        longitude: location?.lng || 72.8777,
        address_text: address || 'Location not specified',
        bleeding: triage.bleeding,
        can_walk: triage.can_walk,
        conscious: triage.conscious,
        vehicle_accident: triage.vehicle_accident,
        breathing_difficulty: triage.breathing_difficulty,
        image_url: photo || 'https://res.cloudinary.com/demo/image/upload/sample.jpg'
      };

      const response = await api.post('/rescues', payload);
      setSubmittedCase(response.data);
      setStep(6);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit report. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      {/* Progress Bar */}
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="text-sm font-medium text-brand-darkNavy">
          {step < 6 ? `Step ${step} of 5` : 'Submission Complete'}
        </div>
        <div className="flex space-x-1">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className={`h-2 w-8 rounded-full ${step >= i ? 'bg-brand-teal' : 'bg-gray-200'}`} />
          ))}
        </div>
      </div>

      <div className="p-6 md:p-8">
        {error && (
          <div className="mb-4 bg-red-50 text-red-600 p-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Step 1: Animal */}
        {step === 1 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">What animal needs help?</h2>
            <div className="grid grid-cols-2 gap-4">
              {['Dog', 'Cat', 'Cattle', 'Bird', 'Other'].map((animal) => (
                <button
                  key={animal}
                  onClick={() => setSpecies(animal)}
                  className={`p-4 rounded-xl border-2 text-lg font-medium transition-all ${
                    species === animal 
                      ? 'border-brand-teal bg-brand-softMint text-brand-teal' 
                      : 'border-gray-200 hover:border-brand-teal hover:bg-gray-50'
                  }`}
                >
                  {animal}
                </button>
              ))}
            </div>
            <button onClick={handleNext} className="w-full bg-brand-darkNavy text-white py-3 rounded-lg font-semibold mt-8">
              Continue
            </button>
          </div>
        )}

        {/* Step 2: Photo */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Take a Photo</h2>
            <p className="text-gray-600">A clear photo helps responders identify the animal.</p>
            
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center justify-center bg-gray-50">
              <Camera className="w-12 h-12 text-gray-400 mb-4" />
              <button 
                onClick={() => setPhoto('https://res.cloudinary.com/demo/image/upload/sample.jpg')}
                className="bg-white border border-gray-300 px-6 py-2 rounded-lg font-medium shadow-sm"
              >
                Mock Upload Photo
              </button>
              {photo && <p className="text-brand-teal mt-4 text-sm font-medium">Photo attached!</p>}
            </div>

            <div className="flex space-x-4 pt-4">
              <button onClick={handleBack} className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold">Back</button>
              <button onClick={handleNext} className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold">Continue</button>
            </div>
          </div>
        )}

        {/* Step 3: Location */}
        {step === 3 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Animal Location</h2>
            
            <button 
              onClick={handleGetLocation}
              className="w-full bg-brand-softMint border border-brand-teal text-brand-teal py-4 rounded-xl font-semibold flex items-center justify-center text-lg hover:bg-teal-50"
            >
              <MapPin className="w-6 h-6 mr-2" />
              Use My Current Location
            </button>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Or enter address manually</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. Near Central Park entrance"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal"
              />
            </div>

            <div className="flex space-x-4 pt-4">
              <button onClick={handleBack} className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold">Back</button>
              <button onClick={handleNext} className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold" disabled={!address && !location}>Continue</button>
            </div>
          </div>
        )}

        {/* Step 4: Condition */}
        {step === 4 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Visible Condition</h2>
            
            <div className="bg-orange-50 border border-orange-200 p-4 rounded-lg flex items-start">
              <AlertTriangle className="w-5 h-5 text-orange-600 mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-orange-800">
                <strong>Safety Notice:</strong> Do not approach an animal if doing so could put you or the animal at risk. PawReach helps prioritize rescue cases but does not provide veterinary diagnosis.
              </p>
            </div>

            <div className="space-y-4">
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer">
                <input type="checkbox" checked={triage.bleeding} onChange={(e) => setTriage({...triage, bleeding: e.target.checked})} className="w-5 h-5 text-brand-teal rounded" />
                <span className="font-medium text-gray-800">Is the animal bleeding?</span>
              </label>
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer">
                <input type="checkbox" checked={!triage.can_walk} onChange={(e) => setTriage({...triage, can_walk: !e.target.checked})} className="w-5 h-5 text-brand-teal rounded" />
                <span className="font-medium text-gray-800">Unable to stand or walk?</span>
              </label>
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer">
                <input type="checkbox" checked={!triage.conscious} onChange={(e) => setTriage({...triage, conscious: !e.target.checked})} className="w-5 h-5 text-brand-teal rounded" />
                <span className="font-medium text-gray-800">Unconscious?</span>
              </label>
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer">
                <input type="checkbox" checked={triage.vehicle_accident} onChange={(e) => setTriage({...triage, vehicle_accident: e.target.checked})} className="w-5 h-5 text-brand-teal rounded" />
                <span className="font-medium text-gray-800">Hit by a vehicle?</span>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tell us anything else you noticed (Optional)</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal"
                rows={3}
              />
            </div>

            <div className="flex space-x-4 pt-4">
              <button onClick={handleBack} className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold">Back</button>
              <button onClick={handleNext} className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold">Review</button>
            </div>
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Review Details</h2>
            
            <div className="bg-gray-50 rounded-lg p-6 space-y-4 border border-gray-200">
              <div>
                <span className="text-sm text-gray-500">Animal</span>
                <p className="font-medium">{species}</p>
              </div>
              <div>
                <span className="text-sm text-gray-500">Location</span>
                <p className="font-medium">{address}</p>
              </div>
              <div>
                <span className="text-sm text-gray-500">Condition Flags</span>
                <ul className="list-disc pl-5 mt-1 font-medium">
                  {triage.bleeding && <li className="text-red-600">Bleeding</li>}
                  {!triage.can_walk && <li className="text-red-600">Unable to walk</li>}
                  {!triage.conscious && <li className="text-red-600">Unconscious</li>}
                  {triage.vehicle_accident && <li className="text-red-600">Vehicle accident</li>}
                  {triage.breathing_difficulty && <li className="text-red-600">Breathing difficulty</li>}
                  {Object.values(triage).every(v => v === false || v === true && !['bleeding','vehicle_accident','breathing_difficulty'].includes(v as any)) && <li>No severe flags</li>}
                </ul>
              </div>
              {description && (
                <div>
                  <span className="text-sm text-gray-500">Notes</span>
                  <p className="font-medium">{description}</p>
                </div>
              )}
            </div>

            <div className="flex space-x-4 pt-4">
              <button onClick={handleBack} disabled={loading} className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold">Edit</button>
              <button 
                onClick={handleSubmit} 
                disabled={loading}
                className="w-2/3 bg-brand-coral hover:bg-red-500 text-white py-3 rounded-lg font-bold text-lg shadow-md transition-colors"
              >
                {loading ? 'Submitting...' : 'Send Rescue Alert'}
              </button>
            </div>
          </div>
        )}

        {/* Step 6: Success */}
        {step === 6 && submittedCase && (
          <div className="space-y-6 text-center animate-in fade-in py-8">
            <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="w-10 h-10" />
            </div>
            <h2 className="text-3xl font-bold text-brand-darkNavy">Rescue Alert Sent</h2>
            
            <div className="bg-gray-50 rounded-xl p-6 text-left inline-block max-w-sm w-full border border-gray-200">
              <div className="mb-4">
                <span className="text-sm text-gray-500 block">Case Number</span>
                <span className="text-lg font-bold font-mono">{submittedCase.case_number}</span>
              </div>
              <div className="mb-4">
                <span className="text-sm text-gray-500 block">Emergency Priority Assessment</span>
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold mt-1
                  ${submittedCase.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-800' : 
                    submittedCase.triage_priority === 'URGENT' ? 'bg-orange-100 text-orange-800' : 'bg-blue-100 text-blue-800'}
                `}>
                  {submittedCase.triage_priority}
                </span>
              </div>
              <div>
                <span className="text-sm text-gray-500 block">Status</span>
                <span className="font-medium">{submittedCase.status.replace('_', ' ')}</span>
              </div>
            </div>

            <p className="text-gray-600 text-sm max-w-sm mx-auto mt-4">
              A veterinarian should assess the animal's medical condition. We are currently searching for nearby responders.
            </p>

            <button 
              onClick={() => navigate(`/cases/${submittedCase.id}`)}
              className="w-full max-w-sm bg-brand-darkNavy text-white py-3 rounded-lg font-semibold mt-6 mx-auto block"
            >
              Track This Rescue
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
