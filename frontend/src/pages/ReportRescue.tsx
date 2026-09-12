import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import { Camera, AlertTriangle, CheckCircle, UploadCloud, Loader2 } from 'lucide-react';
import { MapPicker } from '../components/MapPicker';
import { Toast, type ToastMessage } from '../components/Toast';

export const ReportRescue = () => {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Form State
  const [species, setSpecies] = useState('Dog');
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
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

  const handleNext = () => {
    if (step === 3 && !location) {
      setToast({
        id: 'loc-required',
        type: 'warning',
        message: 'Please pinpoint the animal location on the map or click "Detect My Exact Location".',
      });
      return;
    }
    setStep((s) => Math.min(s + 1, 6));
  };

  const handleBack = () => setStep((s) => Math.max(s - 1, 1));

  const handleImageFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate type
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setToast({
        id: 'img-type-err',
        type: 'error',
        message: 'Unsupported image format. Please select a JPG, PNG, or WEBP photo.',
      });
      return;
    }

    // Validate size (10 MB)
    if (file.size > 10 * 1024 * 1024) {
      setToast({
        id: 'img-size-err',
        type: 'error',
        message: 'File size exceeds 10 MB. Please upload a smaller image.',
      });
      return;
    }

    // Set local preview
    setPhotoPreview(URL.createObjectURL(file));
    setUploadingImage(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/uploads/image', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setPhotoUrl(response.data.image_url);
      setToast({
        id: 'img-upload-ok',
        type: 'success',
        message: 'Photo uploaded and ready.',
      });
    } catch (err: any) {
      setToast({
        id: 'img-upload-fail',
        type: 'error',
        message: formatApiError(err, 'Failed to upload photo. Please try again.'),
      });
      setPhotoPreview(null);
      setPhotoUrl(null);
    } finally {
      setUploadingImage(false);
    }
  };

  const handleSubmit = async () => {
    if (!location) {
      setToast({
        id: 'no-loc',
        type: 'error',
        message: 'Coordinates are required to dispatch rescue teams.',
      });
      return;
    }

    setLoading(true);
    try {
      const payload = {
        species,
        description,
        latitude: location.lat,
        longitude: location.lng,
        address_text: address || `Lat: ${location.lat}, Lng: ${location.lng}`,
        bleeding: triage.bleeding,
        can_walk: triage.can_walk,
        conscious: triage.conscious,
        vehicle_accident: triage.vehicle_accident,
        breathing_difficulty: triage.breathing_difficulty,
        image_url: photoUrl,
      };

      const response = await api.post('/rescues', payload);
      setSubmittedCase(response.data);
      setStep(6);
    } catch (err: any) {
      setToast({
        id: 'submit-fail',
        type: 'error',
        message: formatApiError(err, 'Failed to submit report. Please try again.'),
      });
    } finally {
      setLoading(false);
    }
  };

  const hasSevereFlags =
    triage.bleeding ||
    !triage.can_walk ||
    !triage.conscious ||
    triage.vehicle_accident ||
    triage.breathing_difficulty;

  return (
    <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* Progress Header */}
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="text-sm font-medium text-brand-darkNavy">
          {step < 6 ? `Step ${step} of 5` : 'Submission Complete'}
        </div>
        <div className="flex space-x-1">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className={`h-2 w-8 rounded-full ${step >= i ? 'bg-brand-teal' : 'bg-gray-200'}`}
            />
          ))}
        </div>
      </div>

      <div className="p-6 md:p-8">
        {/* Step 1: Animal */}
        {step === 1 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">What animal needs help?</h2>
            <div className="grid grid-cols-2 gap-4">
              {['Dog', 'Cat', 'Cattle', 'Bird', 'Other'].map((animal) => (
                <button
                  key={animal}
                  type="button"
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
            <button
              type="button"
              onClick={handleNext}
              className="w-full bg-brand-darkNavy text-white py-3 rounded-lg font-semibold mt-8 hover:bg-brand-deepNavy transition-colors"
            >
              Continue
            </button>
          </div>
        )}

        {/* Step 2: Photo */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Capture or Upload a Photo</h2>
            <p className="text-gray-600">A clear photo helps responders locate and assess the animal's physical state.</p>

            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center justify-center bg-gray-50 relative">
              {photoPreview ? (
                <div className="w-full flex flex-col items-center">
                  <img
                    src={photoPreview}
                    alt="Animal preview"
                    className="max-h-64 object-contain rounded-lg border border-gray-200 mb-4 shadow-sm"
                  />
                  {uploadingImage ? (
                    <div className="flex items-center text-brand-teal text-sm font-semibold">
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Uploading photo to secure storage...
                    </div>
                  ) : (
                    <div className="flex items-center text-emerald-600 text-sm font-semibold">
                      <CheckCircle className="w-4 h-4 mr-1.5" /> Photo successfully uploaded!
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <Camera className="w-12 h-12 text-gray-400 mb-3" />
                  <p className="text-sm font-medium text-gray-700 mb-1">Click to browse or take photo</p>
                  <p className="text-xs text-gray-500 mb-4">JPG, PNG, or WEBP (Max 10 MB)</p>
                </>
              )}

              <label className="cursor-pointer mt-2 bg-white border border-gray-300 hover:border-brand-teal px-5 py-2.5 rounded-lg font-medium shadow-sm text-sm text-gray-700 hover:text-brand-teal transition-all flex items-center">
                <UploadCloud className="w-4 h-4 mr-2 text-brand-teal" />
                {photoPreview ? 'Choose Different Photo' : 'Select Photo File'}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageFileChange}
                  className="hidden"
                />
              </label>
            </div>

            <div className="flex space-x-4 pt-4">
              <button
                type="button"
                onClick={handleBack}
                className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleNext}
                disabled={uploadingImage}
                className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold hover:bg-brand-deepNavy transition-colors disabled:opacity-50"
              >
                {photoUrl ? 'Continue' : 'Skip / Continue without Photo'}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Location */}
        {step === 3 && (
          <div className="space-y-6 animate-in fade-in">
            <div>
              <h2 className="text-2xl font-bold text-brand-darkNavy">Animal Location</h2>
              <p className="text-sm text-gray-600 mt-1">
                Real coordinates ensure responders can navigate directly to the distressed animal.
              </p>
            </div>

            <MapPicker
              initialLat={location?.lat}
              initialLng={location?.lng}
              onLocationSelect={(coords) => {
                setLocation({ lat: coords.lat, lng: coords.lng });
                if (coords.addressText && !address) {
                  setAddress(coords.addressText);
                }
              }}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Landmark or Street Details
              </label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. Near Linking Road junction, opposite Metro pillar #42"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal text-sm"
              />
            </div>

            <div className="flex space-x-4 pt-4">
              <button
                type="button"
                onClick={handleBack}
                className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleNext}
                disabled={!location}
                className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold hover:bg-brand-deepNavy transition-colors disabled:opacity-50"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Condition */}
        {step === 4 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Visible Emergency Condition</h2>

            <div className="bg-orange-50 border border-orange-200 p-4 rounded-lg flex items-start">
              <AlertTriangle className="w-5 h-5 text-orange-600 mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-orange-800">
                <strong>Safety Notice:</strong> Do not put yourself or the animal at risk. This triage helps responders prioritize dispatch, not diagnose.
              </p>
            </div>

            <div className="space-y-3">
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={triage.bleeding}
                  onChange={(e) => setTriage({ ...triage, bleeding: e.target.checked })}
                  className="w-5 h-5 text-brand-teal rounded"
                />
                <span className="font-medium text-gray-800">Is the animal visibly bleeding?</span>
              </label>

              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={!triage.can_walk}
                  onChange={(e) => setTriage({ ...triage, can_walk: !e.target.checked })}
                  className="w-5 h-5 text-brand-teal rounded"
                />
                <span className="font-medium text-gray-800">Unable to stand or walk?</span>
              </label>

              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={!triage.conscious}
                  onChange={(e) => setTriage({ ...triage, conscious: !e.target.checked })}
                  className="w-5 h-5 text-brand-teal rounded"
                />
                <span className="font-medium text-gray-800">Unconscious or unresponsive?</span>
              </label>

              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={triage.vehicle_accident}
                  onChange={(e) => setTriage({ ...triage, vehicle_accident: e.target.checked })}
                  className="w-5 h-5 text-brand-teal rounded"
                />
                <span className="font-medium text-gray-800">Hit by a vehicle or traffic collision?</span>
              </label>

              {/* Requirement #32: Breathing difficulty control */}
              <label className="flex items-center space-x-3 bg-gray-50 p-4 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={triage.breathing_difficulty}
                  onChange={(e) => setTriage({ ...triage, breathing_difficulty: e.target.checked })}
                  className="w-5 h-5 text-brand-teal rounded"
                />
                <span className="font-medium text-gray-800">Does the animal have severe difficulty breathing?</span>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Additional observations (Optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal text-sm"
                rows={3}
                placeholder="Specific animal markings, behavior, exact spot where hidden, etc."
              />
            </div>

            <div className="flex space-x-4 pt-4">
              <button
                type="button"
                onClick={handleBack}
                className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleNext}
                className="w-2/3 bg-brand-darkNavy text-white py-3 rounded-lg font-semibold hover:bg-brand-deepNavy transition-colors"
              >
                Review
              </button>
            </div>
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div className="space-y-6 animate-in fade-in">
            <h2 className="text-2xl font-bold text-brand-darkNavy">Review Details Before Dispatch</h2>

            <div className="bg-gray-50 rounded-xl p-6 space-y-4 border border-gray-200 text-sm">
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Animal</span>
                <p className="font-semibold text-gray-800 text-base">{species}</p>
              </div>

              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Location</span>
                <p className="font-medium text-gray-800">{address || `Lat: ${location?.lat}, Lng: ${location?.lng}`}</p>
              </div>

              {photoUrl && (
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Attached Photo</span>
                  <div className="mt-1 w-28 h-28 rounded-lg overflow-hidden border border-gray-200">
                    <img src={photoUrl} alt="Attached rescue photo" className="w-full h-full object-cover" />
                  </div>
                </div>
              )}

              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Triage Flags</span>
                <ul className="list-disc pl-5 mt-1 font-medium space-y-1">
                  {triage.bleeding && <li className="text-red-600">Visible bleeding</li>}
                  {!triage.can_walk && <li className="text-red-600">Unable to walk</li>}
                  {!triage.conscious && <li className="text-red-600">Unconscious / unresponsive</li>}
                  {triage.vehicle_accident && <li className="text-red-600">Vehicle collision reported</li>}
                  {triage.breathing_difficulty && <li className="text-red-600">Breathing difficulty</li>}
                  {!hasSevereFlags && (
                    <li className="text-gray-600 font-normal">No severe emergency flags reported</li>
                  )}
                </ul>
              </div>

              {description && (
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Citizen Notes</span>
                  <p className="text-gray-700 italic mt-1">"{description}"</p>
                </div>
              )}
            </div>

            <div className="flex space-x-4 pt-4">
              <button
                type="button"
                onClick={handleBack}
                disabled={loading}
                className="w-1/3 bg-gray-100 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
              >
                Edit
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                className="w-2/3 bg-brand-coral hover:bg-red-500 text-white py-3.5 rounded-lg font-bold text-lg shadow-md transition-all flex items-center justify-center disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Dispatching Alert...
                  </>
                ) : (
                  'Send Rescue Alert'
                )}
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
                <span className="text-xs text-gray-500 block uppercase font-semibold">Case Number</span>
                <span className="text-lg font-bold font-mono text-brand-darkNavy">{submittedCase.case_number}</span>
              </div>
              <div className="mb-4">
                <span className="text-xs text-gray-500 block uppercase font-semibold">Emergency Priority</span>
                <span
                  className={`inline-block px-3 py-1 rounded-full text-xs font-bold mt-1 tracking-wide ${
                    submittedCase.triage_priority === 'CRITICAL'
                      ? 'bg-red-100 text-red-800'
                      : submittedCase.triage_priority === 'URGENT'
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-blue-100 text-blue-800'
                  }`}
                >
                  {submittedCase.triage_priority}
                </span>
              </div>
              <div>
                <span className="text-xs text-gray-500 block uppercase font-semibold">Status</span>
                <span className="font-semibold text-brand-teal">{submittedCase.status.replace(/_/g, ' ')}</span>
              </div>
            </div>

            <p className="text-gray-600 text-sm max-w-sm mx-auto">
              We have alerted nearby responders. You can follow live updates and rescuer dispatch on the tracking dashboard.
            </p>

            <button
              type="button"
              onClick={() => navigate(`/cases/${submittedCase.id}`)}
              className="w-full max-w-sm bg-brand-darkNavy text-white py-3 rounded-lg font-semibold mt-4 mx-auto block hover:bg-brand-deepNavy transition-colors"
            >
              Track This Rescue Live
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
