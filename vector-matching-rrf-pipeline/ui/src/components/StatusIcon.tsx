import { CheckCircle2, XCircle, HelpCircle, AlertCircle, FileQuestion } from 'lucide-react';

interface StatusIconProps {
  decision: string;
  isMatch: boolean;
  size?: number;
}

export function StatusIcon({ decision, isMatch, size = 16 }: StatusIconProps) {
  if (!decision) return <FileQuestion size={size} className="text-zinc-400" />;
  
  if (decision === 'MATCH' || decision === 'Human Confirmed' || (decision.includes('High Confidence') && isMatch)) {
    return <CheckCircle2 size={size} className="text-emerald-500" />;
  }
  
  if (decision === 'Human Rejected') {
    return <XCircle size={size} className="text-rose-500" />;
  }
  
  if (decision.includes('Ambiguous') || decision === 'REQUIRES_HUMAN_REVIEW') {
    return <HelpCircle size={size} className="text-amber-500" />;
  }
  
  if (!isMatch) {
    return <AlertCircle size={size} className="text-rose-500" />;
  }
  
  return <HelpCircle size={size} className="text-amber-500" />;
}
