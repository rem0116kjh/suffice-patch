package example.order;
import java.util.List;
public final class QuoteTests {
    public static void main(String[] args) {
        assert QuoteService.quote(List.of()).equals(new QuoteService.Quote(0, 0, 0));
        var lines = List.of(new Line(1200, 2), new Line(300, 1));
        assert QuoteService.quote(lines).equals(new QuoteService.Quote(2700, 500, 3200));
        assert lines.get(0).equals(new Line(1200, 2));
        assert QuoteService.quote(List.of(new Line(0, 1))).totalCents() == 0;
        boolean invalid = false;
        try { QuoteService.quote(List.of(new Line(100, 0))); } catch (IllegalArgumentException expected) { invalid = true; }
        assert invalid;
        boolean overflow = false;
        try { QuoteService.quote(List.of(new Line(Long.MAX_VALUE, 2))); } catch (ArithmeticException expected) { overflow = true; }
        assert overflow;
        System.out.println("JAVA_BASELINE_OK groups=5");
    }
}
