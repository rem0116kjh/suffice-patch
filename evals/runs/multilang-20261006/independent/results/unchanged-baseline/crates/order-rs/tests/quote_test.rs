use order_rs::{Line, Quote, quote};

#[test]
fn empty() { assert_eq!(quote(&[]), Ok(Quote {subtotal_cents: 0, shipping_cents: 0, total_cents: 0})); }
#[test]
fn ordinary() { assert_eq!(quote(&[Line {price_cents: 1200, quantity: 2}, Line {price_cents: 300, quantity: 1}]), Ok(Quote {subtotal_cents: 2700, shipping_cents: 500, total_cents: 3200})); }
#[test]
fn invalid_quantity() { assert!(quote(&[Line {price_cents: 100, quantity: 0}]).is_err()); }
#[test]
fn overflow() { assert!(quote(&[Line {price_cents: u64::MAX, quantity: 2}]).is_err()); }
