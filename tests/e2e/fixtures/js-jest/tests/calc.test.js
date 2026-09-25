const { isAdult } = require("../src/calc");

test("adult at 18", () => {
  expect(isAdult(18)).toBe(true);
});

test("adult at 30", () => {
  expect(isAdult(30)).toBe(true);
});
