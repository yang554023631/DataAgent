import React from 'react';

interface Highlight {
  type: 'positive' | 'negative' | 'info';
  text: string;
}

interface HighlightListProps {
  highlights: Highlight[];
}

export const HighlightList: React.FC<HighlightListProps> = ({ highlights }) => {
  const getTypeStyles = (type: string) => {
    switch (type) {
      case 'positive': return 'bg-green-50 border-green-200 text-green-800';
      case 'negative': return 'bg-red-50 border-red-200 text-red-800';
      default: return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  return (
    <div className="space-y-2">
      {highlights.map((highlight, index) => (
        <div
          key={index}
          className={`p-3 rounded-lg border ${getTypeStyles(highlight.type)}`}
        >
          {highlight.text}
        </div>
      ))}
    </div>
  );
};
