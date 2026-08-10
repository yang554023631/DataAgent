import { useState } from 'react';
import { Clarification, QualityIssueV2 } from '../services/api';
import { QualityIssueList } from './QualityIssueList';

interface ClarificationModalProps {
  clarification: Clarification;
  hitlType?: 'cot_clarification' | 'quality_hitl' | null;
  qualityIssues?: QualityIssueV2[];
  onSubmit: (selectedValue: string) => void;
  onClose: () => void;
}

export default function ClarificationModal({ clarification, hitlType, qualityIssues, onSubmit, onClose }: ClarificationModalProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = () => {
    let value = '';
    if (selected) {
      value = selected;
    } else if (customInput.trim() && clarification.allow_custom_input) {
      value = customInput.trim();
    }
    if (!value) return;

    setSubmitting(true);
    onSubmit(value);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          {clarification.question}
        </h3>

        {/* Quality issues section (for quality_hitl type) */}
        {hitlType === 'quality_hitl' && qualityIssues && qualityIssues.length > 0 && (
          <div className="mb-4">
            <div className="text-sm font-medium text-gray-700 mb-2">质量问题：</div>
            <QualityIssueList issues={qualityIssues} />
          </div>
        )}

        <div className="space-y-2 mb-6">
          {clarification.options.map((option) => (
            <button
              key={option.value}
              onClick={() => setSelected(option.value)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                selected === option.value
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        {clarification.allow_custom_input && hitlType !== 'quality_hitl' && (
          <div className="mb-6">
            <input
              type="text"
              value={customInput}
              onChange={(e) => { setCustomInput(e.target.value); setSelected(null); }}
              placeholder="或输入自定义内容..."
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={(!selected && !customInput.trim()) || submitting}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? '处理中...' : hitlType === 'quality_hitl' ? '确认操作' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
}
