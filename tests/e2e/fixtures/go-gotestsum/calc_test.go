package calc

import "testing"

func TestAdultAt18(t *testing.T) {
	if !IsAdult(18) {
		t.Fatal("18 should be an adult")
	}
}

func TestAdultAt30(t *testing.T) {
	if !IsAdult(30) {
		t.Fatal("30 should be an adult")
	}
}
