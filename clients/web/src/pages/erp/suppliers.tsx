import { ComingSoonPage } from '@/components/common/coming-soon'

export function SuppliersPage() {
  return (
    <ComingSoonPage
      title="Supplier Management"
      description="Manage vendor relationships and procurement processes"
      features={[
        'Supplier contact management',
        'Purchase order creation and tracking',
        'Vendor performance analytics',
        'Contract and pricing management',
        'Automated reordering workflows',
      ]}
      estimatedDate="Q2 2024"
    />
  )
}