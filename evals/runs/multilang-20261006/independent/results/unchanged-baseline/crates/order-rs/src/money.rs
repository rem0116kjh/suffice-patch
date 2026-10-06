use crate::Line;

pub(crate) fn subtotal(lines: &[Line]) -> Result<u64, &'static str> {
    let mut total = 0_u64;
    for line in lines {
        if line.quantity == 0 { return Err("invalid quantity"); }
        let amount = line.price_cents.checked_mul(line.quantity).ok_or("amount overflow")?;
        total = total.checked_add(amount).ok_or("amount overflow")?;
    }
    Ok(total)
}
