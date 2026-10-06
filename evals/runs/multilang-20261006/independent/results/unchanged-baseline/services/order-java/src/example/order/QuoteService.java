package example.order;
import java.util.List;
public final class QuoteService {
    public record Quote(long subtotalCents, long shippingCents, long totalCents) {}
    public static Quote quote(List<Line> lines) {
        long subtotal = Money.subtotal(lines);
        long shipping = subtotal == 0 ? 0 : 500;
        return new Quote(subtotal, shipping, Math.addExact(subtotal, shipping));
    }
}
