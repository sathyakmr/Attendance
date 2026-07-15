const STATUS_MAP = {
  VALIDATED: { label: 'Validated', variant: 'validated' },
  PENDING_VALIDATION: { label: 'Pending', variant: 'pending' },
  FLAGGED: { label: 'Flagged', variant: 'flagged' },
  REJECTED: { label: 'Rejected', variant: 'rejected' },
  SUPERSEDED: { label: 'Superseded', variant: 'neutral' },
  PENDING: { label: 'Pending', variant: 'pending' },
  AI_PRESCREENED: { label: 'AI Pre-screened', variant: 'pending' },
  APPROVED: { label: 'Approved', variant: 'approved' },
  ESCALATED: { label: 'Escalated', variant: 'escalated' },
  OPEN: { label: 'Open', variant: 'flagged' },
  CLEARED: { label: 'Cleared', variant: 'validated' },
  CONFIRMED: { label: 'Confirmed', variant: 'rejected' },
  DISMISSED: { label: 'Dismissed', variant: 'neutral' },
  RESOLVED: { label: 'Resolved', variant: 'neutral' },
  SENT: { label: 'Sent', variant: 'sent' },
  DELIVERED: { label: 'Delivered', variant: 'delivered' },
  READ: { label: 'Read', variant: 'read' },
  FAILED: { label: 'Failed', variant: 'rejected' },
}

export default function StatusStamp({ status }) {
  const meta = STATUS_MAP[status] || { label: status, variant: 'neutral' }
  return <span className={`stamp stamp--${meta.variant}`}>{meta.label}</span>
}
