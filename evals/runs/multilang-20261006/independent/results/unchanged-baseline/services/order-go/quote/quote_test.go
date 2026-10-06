package quote

import "testing"

func TestEmpty(t *testing.T) { got, err := Calculate(nil); if err != nil || got != (Quote{}) { t.Fatalf("%+v %v", got, err) } }
func TestOrdinary(t *testing.T) {
    lines := []Line{{1200, 2}, {300, 1}}
    got, err := Calculate(lines)
    if err != nil || got != (Quote{2700, 500, 3200}) { t.Fatalf("%+v %v", got, err) }
    if lines[0] != (Line{1200, 2}) || lines[1] != (Line{300, 1}) { t.Fatal("input changed") }
}
func TestZeroPrice(t *testing.T) { got, err := Calculate([]Line{{0, 1}}); if err != nil || got != (Quote{}) { t.Fatalf("%+v %v", got, err) } }
func TestInvalidQuantity(t *testing.T) { if _, err := Calculate([]Line{{100, 0}}); err == nil { t.Fatal("accepted zero quantity") } }
func TestOverflow(t *testing.T) { if _, err := Calculate([]Line{{^uint64(0), 2}}); err == nil { t.Fatal("accepted overflow") } }
