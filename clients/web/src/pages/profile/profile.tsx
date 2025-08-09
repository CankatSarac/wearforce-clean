import { ComingSoonPage } from '@/components/common/coming-soon'

export function ProfilePage() {
  return (
    <ComingSoonPage
      title="User Profile"
      description="Manage your personal information and account settings"
      features={[
        'Personal information management',
        'Password and security settings',
        'Notification preferences',
        'Activity history',
        'Account integration options',
      ]}
      estimatedDate="Q1 2024"
    />
  )
}