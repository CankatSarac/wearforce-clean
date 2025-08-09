import { ComingSoonPage } from '@/components/common/coming-soon'

export function SettingsPage() {
  return (
    <ComingSoonPage
      title="Settings"
      description="Configure your WearForce application and preferences"
      features={[
        'User preferences and profiles',
        'Team and role management',
        'Integration configurations',
        'Notification settings',
        'Security and authentication',
        'Data export and backup options',
      ]}
      estimatedDate="Q1 2024"
    />
  )
}