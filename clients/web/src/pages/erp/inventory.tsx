import { ComingSoonPage } from '@/components/common/coming-soon'

export function InventoryPage() {
  return (
    <ComingSoonPage
      title="Inventory Management"
      description="Track stock levels, manage products, and optimize inventory"
      features={[
        'Real-time stock level tracking',
        'Low stock alerts and reordering',
        'Product catalog management',
        'Warehouse location tracking',
        'Inventory valuation reports',
        'Barcode scanning integration',
      ]}
      estimatedDate="Q1 2024"
    />
  )
}