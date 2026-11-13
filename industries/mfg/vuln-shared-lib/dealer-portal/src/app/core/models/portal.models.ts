export interface PortalSession {
  email: string;
  dealerId: string;
  expiresAt: string;
}

export interface Vehicle {
  vin: string;
  model: string;
  year: number;
  status: string;
  priceCents: number;
  imageUrl: string;
}

export interface WarrantyClaim {
  id: string;
  vin: string;
  status: string;
  description: string;
  submittedAt: string;
}

export interface NewWarrantyClaim {
  vin: string;
  description: string;
}

export interface DealerNotice {
  id: string;
  title: string;
  severity: string;
  publishedAt: string;
  body: string;
}
