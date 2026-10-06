package example.order;
import java.util.List;
final class Money {
    static long subtotal(List<Line> lines) {
        long subtotal = 0;
        for (Line line : lines) {
            if (line.priceCents() < 0 || line.quantity() <= 0) throw new IllegalArgumentException("invalid line");
            subtotal = Math.addExact(subtotal, Math.multiplyExact(line.priceCents(), line.quantity()));
        }
        return subtotal;
    }
}
