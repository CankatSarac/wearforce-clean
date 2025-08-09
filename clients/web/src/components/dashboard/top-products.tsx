import { TrendingUp, TrendingDown, Package } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

interface Product {
  id: string
  name: string
  category: string
  sales: number
  revenue: number
  growth: number
  stock: number
  image?: string
}

interface TopProductsProps {
  products?: Product[]
  limit?: number
}

export function TopProducts({ products = [], limit = 5 }: TopProductsProps) {
  const displayProducts = products.slice(0, limit)
  const maxSales = Math.max(...displayProducts.map(p => p.sales), 1)

  if (displayProducts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <Package className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No products data available</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {displayProducts.map((product, index) => (
        <div
          key={product.id}
          className="flex items-center space-x-4 p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
        >
          {/* Rank */}
          <div className="flex-shrink-0">
            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
              {index + 1}
            </div>
          </div>

          {/* Product Image/Icon */}
          <div className="flex-shrink-0">
            {product.image ? (
              <img
                src={product.image}
                alt={product.name}
                className="w-10 h-10 rounded-lg object-cover"
              />
            ) : (
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                <Package className="h-5 w-5 text-muted-foreground" />
              </div>
            )}
          </div>

          {/* Product Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm font-medium text-foreground truncate">
                {product.name}
              </p>
              <div className="flex items-center space-x-1">
                {product.growth > 0 ? (
                  <TrendingUp className="h-3 w-3 text-green-500" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-500" />
                )}
                <span
                  className={`text-xs font-medium ${
                    product.growth > 0 ? 'text-green-500' : 'text-red-500'
                  }`}
                >
                  {product.growth > 0 ? '+' : ''}{product.growth.toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between mb-2">
              <Badge variant="secondary" className="text-xs">
                {product.category}
              </Badge>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Revenue</p>
                <p className="text-sm font-medium">
                  ${(product.revenue / 1000).toFixed(1)}k
                </p>
              </div>
            </div>

            {/* Sales Progress */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">
                  {product.sales} sales
                </span>
                <span className="text-muted-foreground">
                  Stock: {product.stock}
                </span>
              </div>
              <Progress 
                value={(product.sales / maxSales) * 100} 
                className="h-2"
              />
            </div>

            {/* Stock Warning */}
            {product.stock < 10 && (
              <div className="flex items-center space-x-1 mt-2">
                <Badge variant="destructive" className="text-xs">
                  Low Stock
                </Badge>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}