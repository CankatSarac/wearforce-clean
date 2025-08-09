import { ComingSoonPage } from '@/components/common/coming-soon'

export function AnalyticsPage() {
  return (
    <ComingSoonPage
      title="Advanced Analytics"
      description="Comprehensive business intelligence and reporting platform"
      features={[
        'Custom dashboard builder',
        'Advanced data visualization',
        'Predictive analytics and forecasting',
        'Export and scheduling options',
        'KPI tracking and alerts',
        'Cross-module data correlation',
      ]}
      estimatedDate="Q3 2024"
    />
  )
}