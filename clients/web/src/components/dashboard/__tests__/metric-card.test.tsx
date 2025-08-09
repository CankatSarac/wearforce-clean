import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/utils'
import { MetricCard } from '../metric-card'
import { DollarSign } from 'lucide-react'

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(
      <MetricCard
        title="Total Revenue"
        value="$125,000"
        icon={DollarSign}
      />
    )
    
    expect(screen.getByText('Total Revenue')).toBeInTheDocument()
    expect(screen.getByText('$125,000')).toBeInTheDocument()
  })

  it('displays positive change trend', () => {
    render(
      <MetricCard
        title="Sales"
        value="100"
        icon={DollarSign}
        change={{ value: 12.5, isPositive: true }}
      />
    )
    
    expect(screen.getByText('+12.5%')).toBeInTheDocument()
    expect(screen.getByText('from last period')).toBeInTheDocument()
  })

  it('displays negative change trend', () => {
    render(
      <MetricCard
        title="Orders"
        value="50"
        icon={DollarSign}
        change={{ value: 5.2, isPositive: false }}
      />
    )
    
    expect(screen.getByText('-5.2%')).toBeInTheDocument()
  })

  it('applies warning variant styles', () => {
    render(
      <MetricCard
        title="Low Stock"
        value="12"
        icon={DollarSign}
        variant="warning"
      />
    )
    
    // Check if warning styles are applied
    const card = screen.getByText('Low Stock').closest('.rounded-lg')
    expect(card).toHaveClass('border-yellow-200')
  })

  it('renders without change data', () => {
    render(
      <MetricCard
        title="New Metric"
        value="42"
        icon={DollarSign}
      />
    )
    
    expect(screen.getByText('New Metric')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.queryByText('from last period')).not.toBeInTheDocument()
  })
})