export type Branch = { branch_id: number; branch_name: string; city: string };
export type MenuItem = {
  id: number;
  pizza_name: string;
  price: number;
  diet_type: string;
  stock_quantity: number;
};
export type OrderResult = {
  order_id: number;
  subtotal: number;
  vat_amount: number;
  total_price: number;
};

export type Role = "customer" | "staff" | "partner";
export type Session =
  | { role: "customer"; customer_id: number; name: string; email: string }
  | { role: "staff"; staff_id: number; name: string; branch_id: number; branch_name: string }
  | { role: "partner"; partner_id: number; name: string; branch_id: number; branch_name: string };

export type OrderLine = { pizza_name: string; quantity: number };
export type KitchenOrder = {
  order_id: number;
  order_time: string;
  status: string;
  delivery_mode: string;
  total_price: number;
  customer_name: string;
  items: OrderLine[];
};
export type DeliveryOrder = {
  order_id: number;
  order_time: string;
  status: string;
  total_price: number;
  customer_name: string;
};
