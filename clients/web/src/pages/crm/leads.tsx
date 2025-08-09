import { ComingSoonPage } from '@/components/common/coming-soon'

export function LeadsPage() {
  return (
    <ComingSoonPage
      title="Leads Management"
      description="Track and nurture potential customers through your sales funnel"
      features={[
        'Lead scoring and qualification',
        'Automated follow-up workflows',
        'Source tracking and analytics',
        'Lead assignment and routing',
        'Conversion tracking',
      ]}
    />
  )
}