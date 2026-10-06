mod money;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Line { pub price_cents: u64, pub quantity: u64 }
#[derive(Debug, PartialEq)]
pub struct Quote { pub subtotal_cents: u64, pub shipping_cents: u64, pub total_cents: u64 }

pub fn quote(lines: &[Line]) -> Result<Quote, &'static str> {
    let subtotal_cents = money::subtotal(lines)?;
    let shipping_cents = if subtotal_cents == 0 { 0 } else { 500 };
    let total_cents = subtotal_cents.checked_add(shipping_cents).ok_or("amount overflow")?;
    Ok(Quote { subtotal_cents, shipping_cents, total_cents })
}
