require_relative "../lib/calc"

RSpec.describe Calc do
  it "is adult at 18" do
    expect(Calc.adult?(18)).to be true
  end

  it "is adult at 30" do
    expect(Calc.adult?(30)).to be true
  end
end
