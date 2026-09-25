namespace Demo;

public class CalcTests
{
    [Fact]
    public void AdultAt18() => Assert.True(Calc.IsAdult(18));

    [Fact]
    public void AdultAt30() => Assert.True(Calc.IsAdult(30));
}
