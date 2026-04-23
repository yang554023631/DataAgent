import { useState } from 'react';
import { Clarification } from '../services/api';

interface ClarificationModalProps {
  clarification: Clarification;
  onSubmit: (selectedValue: string) => void;
  onClose: () => void;
}

export default function ClarificationModal({ clarification, onSubmit, onClose }: ClarificationModalProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState('');

  const handleConfirm = () => {
    if (selected) {
      onSubmit(selected);
    } else if (customInput.trim() && clarification.allow_custom_input) {
      onSubmit(customInput.trim());
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          {clarification.question}
        </h3>

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

        {clarification.allow_custom_input && (
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
            disabled={!selected && !customInput.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            确认
          </button>
        </div>
      </div>
    </div>
  );
}
