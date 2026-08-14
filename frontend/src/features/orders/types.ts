export interface CredentialMetadata {
  credentialPreview?: string | null;
  credentialAvailable: boolean;
}

export interface UserOrder extends CredentialMetadata {
  id: string;
  title: string;
  brand: string;
  duration: string;
  status: "active" | "expired" | "cancelled" | "refunded";
  createdAt: string;
  expiresAt?: string | null;
  assetUrl?: string | null;
  icon: string;
  gradient: string;
  totalAmount: number;
}

export interface CredentialReveal {
  orderId: string;
  credential: string;
}

export interface UserOrdersPage {
  orders: UserOrder[];
  nextCursor: string | null;
}

export interface CheckoutResult {
  status: string;
  order: CredentialMetadata & {
    id: string;
    productTitle: string;
    productBrand: string;
    variantDuration: string;
    createdAt: string;
    totalAmount: number;
  };
}
