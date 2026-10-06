import example.order.Line;
import example.order.QuoteService;
import java.util.ArrayList;
import java.util.List;

public final class IndependentQuoteCheck {
    private static int passed, total;
    private static final StringBuilder details = new StringBuilder();
    private static void check(String name, List<Line> values, QuoteService.Quote expected, Class<? extends Throwable> expectedError) {
        var lines = new ArrayList<>(values);
        var before = List.copyOf(lines);
        boolean okay;
        try { okay = QuoteService.quote(lines).equals(expected) && expectedError == null; }
        catch (Throwable error) { okay = expectedError != null && expectedError.isInstance(error); }
        okay &= lines.equals(before);
        if (total > 0) details.append(',');
        details.append("{\"name\":\"").append(name).append("\",\"passed\":").append(okay).append('}');
        total++; if (okay) passed++;
    }
    public static void main(String[] args) {
        check("below_threshold", List.of(new Line(9999,1)), new QuoteService.Quote(9999,500,10499), null);
        check("at_threshold", List.of(new Line(10000,1)), new QuoteService.Quote(10000,0,10000), null);
        check("above_threshold", List.of(new Line(10001,1)), new QuoteService.Quote(10001,0,10001), null);
        check("threshold_from_multiple_lines", List.of(new Line(7000,1),new Line(3000,1)), new QuoteService.Quote(10000,0,10000), null);
        check("threshold_from_quantity", List.of(new Line(2500,4)), new QuoteService.Quote(10000,0,10000), null);
        check("below_from_quantity", List.of(new Line(3333,3)), new QuoteService.Quote(9999,500,10499), null);
        check("empty", List.of(), new QuoteService.Quote(0,0,0), null);
        check("zero_price", List.of(new Line(0,3)), new QuoteService.Quote(0,0,0), null);
        check("maximum_representable_subtotal", List.of(new Line(Long.MAX_VALUE,1)), new QuoteService.Quote(Long.MAX_VALUE,0,Long.MAX_VALUE), null);
        check("invalid_quantity", List.of(new Line(1,0)), null, IllegalArgumentException.class);
        check("invalid_after_free_shipping_line", List.of(new Line(10000,1),new Line(1,0)), null, IllegalArgumentException.class);
        check("negative_price", List.of(new Line(-1,1)), null, IllegalArgumentException.class);
        check("multiplication_overflow", List.of(new Line(Long.MAX_VALUE,2)), null, ArithmeticException.class);
        check("summation_overflow", List.of(new Line(Long.MAX_VALUE,1),new Line(1,1)), null, ArithmeticException.class);
        System.out.println("{\"passed\":"+passed+",\"total\":"+total+",\"failed\":"+(total-passed)+",\"checks\":["+details+"]}");
        if (passed != total) System.exit(1);
    }
}
