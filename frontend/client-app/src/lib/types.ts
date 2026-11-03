export type StockState = "IN_STOCK" | "LOW_STOCK" | "SOLD_OUT";

export interface Price {
  listCents: number;
  priceCents: number;
  onSale: boolean;
  promoEligible: boolean;
  excludedFromPromo: boolean;
  percentOff: number;
}

export interface Swatch { name: string; hex: string; family: string; image: string | null; soldOut: boolean }

export interface ProductCard {
  id: string; name: string; label: string; department: string; category: string; fit: string | null;
  price: Price; image: string | null; hoverImage: string | null; colors: Swatch[]; sizes: string[];
  stockState: StockState; rating: number; reviewCount: number; isNew: boolean; collections: string[];
}

export interface SkuView { sku: string; color: string; size: string; stock: number; soldOut: boolean; lowStock: boolean }
export interface ProductImage { position: number; url: string; alt: string; color: string | null }

export interface ProductDetail extends Omit<ProductCard, "image" | "hoverImage"> {
  description: string; details: string; materials: string; images: ProductImage[]; skus: SkuView[]; related: ProductCard[];
}

export interface Facet { value: string; count: number }
export interface ProductPage {
  items: ProductCard[]; total: number; page: number; pageSize: number;
  facets: { categories: Facet[]; sizes: Facet[]; colors: Facet[]; fits: Facet[]; priceMinCents: number; priceMaxCents: number };
}

export interface Collection { slug: string; name: string; department: string | null; description: string; heroImage: string; sortOrder: number }

export interface PromotionView {
  active: boolean; id: string | null; name: string | null; headline: string | null; subhead: string | null;
  bannerText: string | null; startsAt: string | null; endsAt: string | null; percentOff: number;
  excludedCollections: string[]; codes: { code: string; description: string; minSubtotalCents: number }[];
}

export interface BagLine {
  sku: string; productId: string; name: string; color: string; size: string; image: string | null; quantity: number;
  stock: number; unitListCents: number; unitPriceCents: number; lineSubtotalCents: number; discountCents: number;
  lineTotalCents: number; promoEligible: boolean; excludedFromPromo: boolean;
}

export interface Bag {
  id: string; items: BagLine[]; itemCount: number; listSubtotalCents: number; subtotalCents: number;
  discountCents: number; merchandiseCents: number; promoCode: string | null; promoDescription: string | null;
  promoError: string | null; freeShippingThresholdCents: number; freeShippingRemainingCents: number;
}

export interface Fee { code: string; label: string; amountCents: number }
export interface Totals {
  subtotalCents: number; discountCents: number; shippingCents: number; fees: Fee[]; feesCents: number;
  taxRate: number; taxCents: number; totalCents: number;
}

export interface Store {
  id: string; name: string; address: string; city: string; state: string; zip: string; phone: string; hours: string;
  latitude: number | null; longitude: number | null; pickupEnabled: boolean; pickupReadyHours: number;
}

export interface Quote { bag: Bag; totals: Totals; fulfillment: string; shippingMethod: string | null; store: Store | null }

export interface Address { name: string; line1: string; line2?: string | null; city: string; state: string; zip: string }

export interface OrderLine {
  lineNo: number; sku: string; productId: string; name: string; color: string; size: string; image: string | null;
  quantity: number; unitListCents: number; unitPriceCents: number; discountCents: number; lineTotalCents: number;
}

export interface Order {
  id: string; orderNumber: string; invoiceNumber: string; email: string; status: string; fulfillment: "SHIP" | "PICKUP";
  shippingMethod: string | null;
  pickup: { storeId: string; storeName: string; address: string; city: string; state: string; zip: string; readyInHours: number } | null;
  shipTo: Address | null; phone: string | null; promoCode: string | null; lines: OrderLine[]; subtotalCents: number;
  discountCents: number; shippingCents: number; fees: Fee[]; feesCents: number; taxRate: number; taxCents: number;
  totalCents: number; cardBrand: string; cardLast4: string; pointsEarned: number; createdAt: string;
}

export interface Customer { id: string; email: string; firstName: string; lastName: string; rewardsPoints: number; createdAt: string }
export interface OrderSummary { orderNumber: string; status: string; fulfillment: string; itemCount: number; totalCents: number; createdAt: string; image: string | null }
