package demo;

import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class CalcTest {
    @Test
    void adultAt18() {
        assertTrue(Calc.isAdult(18));
    }

    @Test
    void adultAt30() {
        assertTrue(Calc.isAdult(30));
    }
}
