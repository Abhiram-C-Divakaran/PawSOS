import React, { useEffect, useState, useCallback } from 'react';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import type { TriageDetailResponse, RescuePriority } from '../types';
import {
  ShieldAlert,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Info,
  CheckCircle2,
  Clock,
  Activity,
} from 'lucide-react';

interface TriageAdvisoryCardProps {
  caseId: string;
  canRetry?: boolean;
  onTriageUpdated?: () => void;
  className?: string;
}

export const TriageAdvisoryCard: React.FC<TriageAdvisoryCardProps> = ({
  caseId,
  canRetry = false,
  onTriageUpdated,
  className = '',
}) => {
  const [triage, setTriage] = useState<TriageDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchTriage = useCallback(async () => {
    try {
      const res = await api.get(`/rescues/${caseId}/triage`);
      setTriage(res.data);
      setError(null);
    } catch (err: any) {
      setError(formatApiError(err, 'Unable to load triage assessment.'));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const res = await api.get(`/rescues/${caseId}/triage`);
        if (active) {
          setTriage(res.data);
          setError(null);
        }
      } catch (err: any) {
        if (active) {
          setError(formatApiError(err, 'Unable to load triage assessment.'));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [caseId]);

  const handleRetry = async () => {
    setRetrying(true);
    setActionNotice(null);
    try {
      const res = await api.post(`/rescues/${caseId}/triage/retry?force=true`);
      setActionNotice(res.data?.message || 'Triage queued for retry.');
      // Refresh triage state after brief delay
      setTimeout(() => {
        void fetchTriage();
        onTriageUpdated?.();
      }, 1500);
    } catch (err: any) {
      setActionNotice(formatApiError(err, 'Failed to trigger triage retry.'));
    } finally {
      setRetrying(false);
    }
  };

  const getPriorityBadgeClass = (priority?: RescuePriority) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'URGENT':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'MODERATE':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      default:
        return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  if (loading) {
    return (
      <div className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm animate-pulse ${className}`}>
        <div className="flex items-center space-x-2 mb-3">
          <div className="w-5 h-5 bg-gray-200 rounded-full" />
          <div className="h-4 bg-gray-200 rounded w-40" />
        </div>
        <div className="h-16 bg-gray-100 rounded-lg mb-3" />
        <div className="h-8 bg-gray-100 rounded w-3/4" />
      </div>
    );
  }

  if (error || !triage) {
    return (
      <div className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm text-sm text-gray-600 ${className}`}>
        <div className="flex items-center space-x-2 text-gray-700 font-semibold mb-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span>Triage Assessment</span>
        </div>
        <p>{error || 'No triage information available for this case.'}</p>
      </div>
    );
  }

  const { rule_assessment, ai_assessment, final_priority, final_score, final_reason } = triage;
  const rulePriority = rule_assessment?.priority || final_priority || 'GENERAL';
  const ruleScore = rule_assessment?.score ?? final_score ?? 0;
  const ruleReasons = rule_assessment?.reasons ?? [];
  const isPending = ai_assessment?.status === 'PENDING' && ai_assessment?.provider !== 'disabled';
  const isCompleted = ai_assessment?.status === 'COMPLETED';
  const isFailed = ai_assessment?.status === 'FAILED';
  const isSkipped = ai_assessment?.status === 'SKIPPED';
  const isNotRequested = ai_assessment?.status === 'NOT_REQUESTED' || (ai_assessment?.status === 'PENDING' && ai_assessment?.provider === 'disabled');
  const confidencePct = ai_assessment?.confidence ? Math.round(ai_assessment.confidence * 100) : null;

  return (
    <div
      data-testid="triage-advisory-card"
      className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4 ${className}`}
    >
      {/* Header with combined final priority */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-brand-teal" />
          <h3 className="text-base font-bold text-brand-darkNavy">Dispatch Triage Advisory</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span
            data-testid="final-priority-badge"
            className={`text-xs font-extrabold px-3 py-1 rounded-full border tracking-wide uppercase ${getPriorityBadgeClass(
              final_priority
            )}`}
          >
            {final_priority} ({final_score}/100)
          </span>
          {canRetry && ai_assessment?.provider !== 'disabled' && (
            <button
              onClick={handleRetry}
              disabled={retrying || isPending}
              title="Re-run visual triage assessment"
              className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 hover:text-brand-darkNavy transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {actionNotice && (
        <div className="text-xs bg-teal-50 border border-teal-200 text-teal-800 p-2.5 rounded-lg flex items-center">
          <Info className="w-4 h-4 mr-1.5 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Grid: Rule-based Assessment vs Visual AI Advisory */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Rule-Based Assessment Panel */}
        <div className="bg-gray-50 rounded-lg p-3.5 border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
              Rule-Based Urgency
            </span>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getPriorityBadgeClass(
                rulePriority
              )}`}
            >
              {rulePriority}
            </span>
          </div>

          <div className="text-xs text-gray-600 space-y-1.5">
            <p>
              <span className="font-semibold text-gray-700">Calculated Score:</span> {ruleScore} / 100
            </p>
            <div>
              <span className="font-semibold text-gray-700 block mb-1">Reported Factors:</span>
              {ruleReasons.length > 0 ? (
                <ul className="list-disc pl-4 space-y-0.5 text-gray-600">
                  {ruleReasons.map((r, idx) => (
                    <li key={idx}>{r}</li>
                  ))}
                </ul>
              ) : (
                <span className="text-gray-500 italic">Standard rescue intake</span>
              )}
            </div>
          </div>
        </div>

        {/* AI Visual Advisory Panel */}
        <div className="bg-brand-lightBlue/30 rounded-lg p-3.5 border border-blue-100">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-brand-teal" />
              <span className="text-xs font-bold text-brand-darkNavy uppercase tracking-wider">
                Visual AI Advisory
              </span>
            </div>
            {isPending && (
              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 animate-pulse">
                <Clock className="w-3 h-3 mr-1 animate-spin" /> Pending
              </span>
            )}
            {isCompleted && (
              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                <CheckCircle2 className="w-3 h-3 mr-1" /> Evaluated
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                <AlertTriangle className="w-3 h-3 mr-1" /> Unavailable
              </span>
            )}
            {isSkipped && (
              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                Skipped
              </span>
            )}
            {isNotRequested && (
              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                {ai_assessment?.provider === 'disabled' ? 'Disabled' : 'Not Requested'}
              </span>
            )}
          </div>

          <div className="text-xs space-y-2">
            {isPending && (
              <p className="text-gray-600 italic">
                Analyzing attached image for visible trauma signs...
              </p>
            )}

            {isCompleted && (
              <>
                <div className="flex items-center justify-between text-gray-700">
                  <span>
                    <strong className="text-gray-800">Visual Urgency:</strong> {ai_assessment.suggested_priority || 'N/A'}
                  </span>
                  {confidencePct !== null && (
                    <span className="font-semibold text-brand-teal">
                      {confidencePct}% confidence
                    </span>
                  )}
                </div>

                {ai_assessment.visible_signs && ai_assessment.visible_signs.length > 0 && (
                  <div>
                    <span className="font-semibold text-gray-800 block mb-1">Detected Indicators:</span>
                    <div className="flex flex-wrap gap-1">
                      {ai_assessment.visible_signs.map((sign, idx) => (
                        <span
                          key={idx}
                          className="bg-white px-2 py-0.5 rounded text-[11px] font-medium border border-blue-200 text-brand-darkNavy"
                        >
                          {sign}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {ai_assessment.explanation && (
                  <p className="text-gray-700 text-[11px] leading-relaxed bg-white/70 p-2 rounded border border-blue-100">
                    "{ai_assessment.explanation}"
                  </p>
                )}

                <div className="text-[10px] text-gray-500 pt-1 flex items-center justify-between">
                  <span>Model: {ai_assessment.model_name || 'pawreach-vision'} {ai_assessment.model_version || ''}</span>
                  <span>Provider: {ai_assessment.provider || 'default'}</span>
                </div>
              </>
            )}

            {isFailed && (
              <p className="text-gray-600">
                Visual triage service was temporarily unavailable. Deterministic rule-based priority is active and invariant.
              </p>
            )}

            {isSkipped && (
              <p className="text-gray-600">
                {ai_assessment?.provider === 'disabled'
                  ? 'Visual urgency review is not enabled. Rule-based dispatch priority remains active.'
                  : (ai_assessment?.explanation || 'Visual triage is currently inactive or no image was supplied.')}
              </p>
            )}

            {isNotRequested && (
              <p className="text-gray-600">
                {ai_assessment?.provider === 'disabled'
                  ? 'Visual urgency review is not enabled. Rule-based dispatch priority remains active.'
                  : (ai_assessment?.explanation || 'Visual triage has not been requested.')}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Final reason synthesis */}
      {final_reason && (
        <div className="text-xs text-gray-700 bg-amber-50/50 p-2.5 rounded-lg border border-amber-200/60">
          <span className="font-bold text-gray-800">Dispatch Justification:</span> {final_reason}
        </div>
      )}

      {/* Safety & Non-Diagnostic Disclaimer */}
      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 flex items-start space-x-2.5">
        <ShieldAlert className="w-4 h-4 text-brand-coral flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-gray-600 leading-normal">
          <strong className="font-semibold text-gray-700">Safety & Legal Notice:</strong>{' '}
          {triage.disclaimer ||
            'AI visual triage provides decision-support for rescue dispatch urgency only. It does not constitute a veterinary medical diagnosis, injury assessment, or treatment prescription.'}
        </p>
      </div>
    </div>
  );
};
