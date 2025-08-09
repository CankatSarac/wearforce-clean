import { ComingSoonPage } from '@/components/common/coming-soon'

export function OpportunitiesPage() {
  return (
    <ComingSoonPage
      title="Sales Opportunities"
      description="Manage your sales pipeline and track deal progression"
      features={[
        'Visual sales pipeline management',
        'Opportunity scoring and forecasting',
        'Deal stage automation',
        'Revenue tracking and analytics',
        'Team collaboration tools',
      ]}
      estimatedDate="Q2 2024"
    />
  )
}